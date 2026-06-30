"""Reverse synthetic generation: sample a valid KqlPipeline directly from
the IR's own schema, across a deliberately chosen set of construct
templates (including the under-covered cells of CONSTRUCT_COVERAGE.md),
instead of waiting for a real ground-truth rule to happen to use one.

Why generate the IR directly rather than write a separate KQL grammar
(PROJECT_STATUS.md §4Z): the deterministic compiler (src/generator/
compiler.py) already turns any valid KqlPipeline into valid KQL by
construction — a second, independent KQL grammar would just be
re-deriving the same guarantee through a different, riskier path
(hand-written KQL strings can be syntactically invalid; a validated
Pydantic IR cannot). Each template samples REAL field names from the
ASIM schema and a curated pool of realistic literal values, so a
generated example is schema-valid AND reads like a plausible detection,
not just structurally legal.

Each generator function returns (KqlPipeline, GenerationMeta) — the
metadata records which construct this exercises and the concrete
parameter choices made, used by both the back-translator (to describe
what was generated) and the fixture generator (to know what a
should-fire/should-not-fire event needs to satisfy or violate).
"""
import random
from dataclasses import dataclass, field
from typing import Callable, List

from src.ir_engine.ir_schema import (
    Aggregation, AggregationFunction, ArgMaxMin, ASIMEventType, Filter,
    FilterGroup, FilterOperator, JoinKind, JoinStage, KqlPipeline,
    MakeSeriesStage, MvExpandStage, ParseStage, ParseToken,
    SeriesAnomalyStage, SummarizeStage, WhereStage,
)

# A small, curated pool per event type — real ASIM field names paired
# with a realistic literal value, so generated filters read like a
# plausible detection rather than a random field/value collision.
_FIELD_VALUE_POOL = {
    ASIMEventType.PROCESS: [
        ("CommandLine", "str", ["whoami /all", "net user hacker P@ssw0rd! /add", "rundll32.exe shell32.dll,Control_RunDLL"]),
        ("ActingProcessName", "str", ["powershell.exe", "cmd.exe", "rundll32.exe", "mshta.exe"]),
        ("TargetProcessName", "str", ["lsass.exe", "svchost.exe", "explorer.exe"]),
        ("ActorUsername", "str", ["svc_backup", "admin", "j.doe"]),
        ("DvcHostname", "str", ["WKSTN-042", "SRV-DC01", "LAPTOP-7Q"]),
    ],
    ASIMEventType.NETWORK_SESSION: [
        ("DstPortNumber", "int", [445, 3389, 4444, 22, 8080]),
        ("SrcIpAddr", "str", ["10.0.0.15", "192.168.1.42", "172.16.5.9"]),
        ("DstIpAddr", "str", ["203.0.113.5", "198.51.100.7", "8.8.8.8"]),
        ("NetworkDirection", "str", ["Outbound", "Inbound"]),
        ("DvcAction", "str", ["Allow", "Deny"]),
    ],
    ASIMEventType.DNS: [
        ("DnsQuery", "str", ["evil-c2.example.ru", "update.contoso.com", "totally-legit.tk"]),
        ("DnsResponseCodeName", "str", ["NXDOMAIN", "NOERROR", "SERVFAIL"]),
        ("SrcIpAddr", "str", ["10.0.0.15", "10.0.0.22"]),
    ],
    ASIMEventType.WEB_SESSION: [
        ("Url", "str", ["http://evil.example.com/payload.ps1", "https://contoso.com/login", "http://x.tk/jndi:ldap://attacker.com/a"]),
        ("HttpUserAgent", "str", ["curl/7.64.1", "Mozilla/5.0", "python-requests/2.25"]),
        ("HttpStatusCode", "int", [200, 403, 404, 500]),
    ],
    ASIMEventType.AUTHENTICATION: [
        ("EventResult", "str", ["Failure", "Success"]),
        ("TargetUsername", "str", ["admin", "svc_account", "j.doe"]),
        ("SrcIpAddr", "str", ["198.51.100.20", "10.0.0.5"]),
    ],
    ASIMEventType.REGISTRY: [
        ("RegistryKey", "str", ["HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run", "HKLM\\...\\Image File Execution Options\\notepad.exe"]),
        ("ActorUsername", "str", ["admin", "SYSTEM"]),
    ],
    ASIMEventType.FILE: [
        ("FileName", "str", ["payload.exe", "invoice.pdf.exe", "config.dat"]),
        ("FilePath", "str", ["C:\\Users\\Public\\payload.exe", "C:\\Windows\\Temp\\stage2.bin"]),
        ("ActorUsername", "str", ["admin", "svc_backup"]),
    ],
}


@dataclass
class GenerationMeta:
    template: str
    event_type: ASIMEventType
    constructs: List[str]
    notes: dict = field(default_factory=dict)


def _pool(event_type: ASIMEventType):
    return _FIELD_VALUE_POOL[event_type]


def _rand_field_value(event_type: ASIMEventType):
    field_name, kind, values = random.choice(_pool(event_type))
    return field_name, random.choice(values)


def gen_simple_filter(rng_event: ASIMEventType = None) -> "tuple[KqlPipeline, GenerationMeta]":
    et = rng_event or random.choice(list(_FIELD_VALUE_POOL))
    n = random.randint(1, 2)
    filters = []
    used = set()
    for _ in range(n):
        f, v = _rand_field_value(et)
        if f in used:
            continue
        used.add(f)
        op = FilterOperator.EQ if isinstance(v, int) else random.choice([FilterOperator.EQ, FilterOperator.CONTAINS])
        filters.append(Filter(field=f, operator=op, value=v))
    ir = KqlPipeline(source_table=et, stages=[WhereStage(filters=filters)])
    return ir, GenerationMeta("simple_filter", et, ["where"], {"filters": [(f.field, f.operator.value, f.value) for f in filters]})


def gen_threshold_summarize(rng_event: ASIMEventType = None) -> "tuple[KqlPipeline, GenerationMeta]":
    et = rng_event or random.choice(list(_FIELD_VALUE_POOL))
    group_field, _, _ = random.choice(_pool(et))
    threshold = random.choice([5, 10, 20, 50])
    ir = KqlPipeline(source_table=et, stages=[
        SummarizeStage(
            aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="EventCount")],
            group_by=[group_field], time_window="PT1H",
        ),
        WhereStage(filters=[Filter(field="EventCount", operator=FilterOperator.GT, value=threshold)]),
    ])
    return ir, GenerationMeta("threshold_summarize", et, ["summarize", "where"], {"group_field": group_field, "threshold": threshold})


def gen_or_list(rng_event: ASIMEventType = None) -> "tuple[KqlPipeline, GenerationMeta]":
    et = rng_event or random.choice(list(_FIELD_VALUE_POOL))
    field_name, _, values = random.choice(_pool(et))
    chosen = random.sample(values, k=min(2, len(values)))
    ir = KqlPipeline(source_table=et, stages=[
        WhereStage(filters=[Filter(field=field_name, operator=FilterOperator.HAS_ANY, value=chosen)]),
    ])
    return ir, GenerationMeta("or_list", et, ["where", "has_any"], {"field": field_name, "values": chosen})


def gen_has_all_evasion() -> "tuple[KqlPipeline, GenerationMeta]":
    flags = random.sample(["-accepteula", "-s", "-r", "-q", "-nop", "-w hidden"], k=3)
    proc_field = "ActingProcessName"
    excluded_name = random.choice(["sdelete.exe", "psexec.exe", "mimikatz.exe"])
    ir = KqlPipeline(source_table=ASIMEventType.PROCESS, stages=[
        WhereStage(filters=[
            Filter(field="CommandLine", operator=FilterOperator.HAS_ALL, value=flags),
            Filter(field=proc_field, operator=FilterOperator.NOT_ENDSWITH, value=excluded_name),
        ]),
    ])
    return ir, GenerationMeta("has_all_evasion", ASIMEventType.PROCESS, ["where", "has_all"], {"flags": flags, "excluded_name": excluded_name})


def gen_arg_max_latest() -> "tuple[KqlPipeline, GenerationMeta]":
    et = random.choice(list(_FIELD_VALUE_POOL))
    group_field, _, _ = random.choice(_pool(et))
    ir = KqlPipeline(source_table=et, stages=[
        SummarizeStage(
            arg_max=ArgMaxMin(order_field="TimeGenerated", carry_fields=["*"], result_alias="LatestEventTime"),
            group_by=[group_field], time_window="P1D",
        ),
    ])
    return ir, GenerationMeta("arg_max_latest", et, ["summarize", "arg_max"], {"group_field": group_field})


def gen_parse_extract() -> "tuple[KqlPipeline, GenerationMeta]":
    et = ASIMEventType.WEB_SESSION
    ir = KqlPipeline(source_table=et, stages=[
        ParseStage(source_field="Url", tokens=[
            ParseToken(type="wildcard"),
            ParseToken(type="literal", value="jndi:ldap://"),
            ParseToken(type="column", value="JndiHost"),
            ParseToken(type="literal", value="/"),
            ParseToken(type="wildcard"),
        ]),
        WhereStage(filters=[Filter(field="JndiHost", operator=FilterOperator.NEQ, value="")]),
    ])
    return ir, GenerationMeta("parse_extract", et, ["parse", "where"], {})


def gen_make_series_anomaly() -> "tuple[KqlPipeline, GenerationMeta]":
    et = ASIMEventType.DNS
    group_field = "SrcIpAddr"
    ir = KqlPipeline(source_table=et, stages=[
        MakeSeriesStage(
            aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="QueryCount")],
            group_by=[group_field], from_time="ago(14d)", to_time="now()", step="P1D",
        ),
        SeriesAnomalyStage(series_field="QueryCount", score_threshold=1.5),
        MvExpandStage(fields=["TimeGenerated", "QueryCount", "AnomalyFlag", "AnomalyScore", "Baseline"]),
        WhereStage(filters=[Filter(field="AnomalyFlag", operator=FilterOperator.NEQ, value=0)]),
    ])
    return ir, GenerationMeta("make_series_anomaly", et, ["make_series", "series_anomaly", "mv_expand", "where"], {"group_field": group_field})


def gen_join_baseline() -> "tuple[KqlPipeline, GenerationMeta]":
    et = ASIMEventType.NETWORK_SESSION
    group_field = "SrcIpAddr"
    right = KqlPipeline(source_table=et, stages=[
        SummarizeStage(aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="BaselineCount")],
                        group_by=[group_field], time_window="P14D"),
    ])
    ir = KqlPipeline(source_table=et, stages=[
        SummarizeStage(aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="CurrentCount")],
                        group_by=[group_field], time_window="P1D"),
        JoinStage(kind=JoinKind.INNER, right_pipeline=right, join_on=[group_field]),
    ])
    return ir, GenerationMeta("join_baseline", et, ["summarize", "join"], {"group_field": group_field})


# --- Construct-combination templates ---------------------------------
#
# Every template above exercises exactly ONE construct. Found live
# (PROJECT_STATUS.md §4Z): checking whether let-bound subqueries could
# even be fixtured surfaced that real ground truth's hardest composition
# shapes are chains/DAGs of constructs, not single ones — and every bug
# found via single-construct testing this round (the arg_max result_alias
# prefix bug, the parse positional-precision residual) was found in
# isolation, while real detection rules chain parse -> summarize on the
# parsed field, arg_max inside a join, make_set -> mv-expand -> filter.
# These templates sample 2-3-construct CHAINS specifically, because
# isolated per-construct testing structurally cannot surface a seam bug
# (each link can be independently "Supported, 5/5" while the chain
# itself breaks) — the chain is the actual unit of risk for an unseen
# real rule, not the construct.

def gen_parse_then_summarize() -> "tuple[KqlPipeline, GenerationMeta]":
    """parse extracts a field -> summarize groups/thresholds on THAT
    extracted field, not a raw ASIM field — tests whether the IR Builder
    correctly threads a parse-derived column into a later stage."""
    threshold = random.choice([3, 5, 10])
    ir = KqlPipeline(source_table=ASIMEventType.WEB_SESSION, stages=[
        ParseStage(source_field="Url", tokens=[
            ParseToken(type="wildcard"),
            ParseToken(type="literal", value="jndi:ldap://"),
            ParseToken(type="column", value="JndiHost"),
            ParseToken(type="literal", value="/"),
            ParseToken(type="wildcard"),
        ]),
        SummarizeStage(
            aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="HitCount")],
            group_by=["JndiHost"], time_window="PT1H",
        ),
        WhereStage(filters=[Filter(field="HitCount", operator=FilterOperator.GT, value=threshold)]),
    ])
    return ir, GenerationMeta(
        "parse_then_summarize", ASIMEventType.WEB_SESSION, ["parse", "summarize", "where"],
        {"threshold": threshold, "extracted_field": "JndiHost"},
    )


def gen_arg_max_in_join() -> "tuple[KqlPipeline, GenerationMeta]":
    """arg_max INSIDE a join's right_pipeline — the latest security
    alert per host, joined against current suspicious process activity.
    Tests whether arg_max's output columns survive correctly through a
    join, not just standalone."""
    join_key = "DvcHostname"
    right = KqlPipeline(source_table=ASIMEventType.AUTHENTICATION, stages=[
        SummarizeStage(
            arg_max=ArgMaxMin(order_field="TimeGenerated", carry_fields=["*"], result_alias="LatestAuthTime"),
            group_by=[join_key], time_window="P1D",
        ),
    ])
    ir = KqlPipeline(source_table=ASIMEventType.PROCESS, stages=[
        WhereStage(filters=[Filter(field="ActingProcessName", operator=FilterOperator.EQ, value="powershell.exe")]),
        JoinStage(kind=JoinKind.INNER, right_pipeline=right, join_on=[join_key]),
    ])
    return ir, GenerationMeta(
        "arg_max_in_join", ASIMEventType.PROCESS, ["where", "join", "arg_max"],
        {"join_key": join_key, "left_filter_field": "ActingProcessName", "left_filter_value": "powershell.exe"},
    )


def gen_make_set_mv_expand_filter() -> "tuple[KqlPipeline, GenerationMeta]":
    """summarize make_set(Url) -> mv-expand back into one row per URL ->
    filter the EXPANDED item — the "second, simpler" mv-expand use case
    (per-item reporting, not anomaly detection) chained with a downstream
    filter on what it expanded, not what it aggregated."""
    suspicious_ext = random.choice([".ps1", ".scr", ".vbs"])
    ir = KqlPipeline(source_table=ASIMEventType.WEB_SESSION, stages=[
        SummarizeStage(
            aggregations=[Aggregation(function=AggregationFunction.MAKE_SET, field="Url", result_alias="TouchedUrls")],
            group_by=["SrcIpAddr"], time_window="P1D",
        ),
        MvExpandStage(fields=["TouchedUrls"]),
        WhereStage(filters=[Filter(field="TouchedUrls", operator=FilterOperator.ENDSWITH, value=suspicious_ext)]),
    ])
    return ir, GenerationMeta(
        "make_set_mv_expand_filter", ASIMEventType.WEB_SESSION, ["summarize", "mv_expand", "where"],
        {"suspicious_ext": suspicious_ext},
    )


_TEMPLATES: List[Callable] = [
    gen_simple_filter, gen_threshold_summarize, gen_or_list, gen_has_all_evasion,
    gen_arg_max_latest, gen_parse_extract, gen_make_series_anomaly, gen_join_baseline,
]

_COMBINATION_TEMPLATES: List[Callable] = [
    gen_parse_then_summarize, gen_arg_max_in_join, gen_make_set_mv_expand_filter,
]


def generate_batch(n: int, seed: int = None) -> "list[tuple[KqlPipeline, GenerationMeta]]":
    if seed is not None:
        random.seed(seed)
    return [random.choice(_TEMPLATES)() for _ in range(n)]


def generate_combination_batch(n: int, seed: int = None) -> "list[tuple[KqlPipeline, GenerationMeta]]":
    if seed is not None:
        random.seed(seed)
    return [random.choice(_COMBINATION_TEMPLATES)() for _ in range(n)]


def generate_mixed_batch(n: int, seed: int = None, combination_fraction: float = 0.5) -> "list[tuple[KqlPipeline, GenerationMeta]]":
    """Samples from both pools — combination_fraction is the per-draw
    probability of drawing a combination (chain) template instead of a
    single-construct one. Defaults to half, since the combination shape
    is the higher-value half per §4Z's own finding, not a token addition
    to an otherwise single-construct run."""
    if seed is not None:
        random.seed(seed)
    out = []
    for _ in range(n):
        pool = _COMBINATION_TEMPLATES if random.random() < combination_fraction else _TEMPLATES
        out.append(random.choice(pool)())
    return out
