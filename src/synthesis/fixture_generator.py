"""Auto-generates should-fire/should-not-fire synthetic events directly
from a generated IR's own GenerationMeta — completing the loop §4Z's
critique asked for: every synthesized rule comes with its own execution
test, for free, because the IR (and the events that should/shouldn't
satisfy it) were both derived from the SAME generation step, not written
by hand per case.

Dispatches per template rather than trying to interpret an arbitrary
KqlPipeline generically — a generic "invert the filters" approach
breaks down fast for multi-stage constructs (a threshold needs enough
ROWS to cross the bin, not one row with a different value; an anomaly
detection needs a whole time series, not a single event). Each
generator function here mirrors the same fixture-construction patterns
already manually validated in tests/integration/test_live_e2e_execution_validation.py.

Field-identity decoupling (§4Z follow-up, found via the first synthesis
eval run): for templates where the grouping/ordering field's NAME
carries no semantic weight of its own (threshold_summarize, arg_max_latest,
join_baseline, make_series_anomaly — any reasonable entity identifier
works equally for testing the count/recency/anomaly LOGIC, which is
what's actually under test), the fixture is now built around whatever
field the SYSTEM'S OWN regenerated IR actually references, not the
generator's original choice. Found live: the system reasonably
regrouping by "Process" instead of the generator's "ActingProcessName"
was being scored as a field-not-found crash, not a logic check — a
fixture that over-specifies field identity marks a correct query wrong
whenever the model makes a different-but-equivalent choice, exactly the
kind of brittleness this project has fought since §4T's "two early
synthetic events were too narrow" lesson, recurring at the harness
level. For templates where the field identity IS the semantic content
under test (simple_filter, or_list, has_all_evasion, parse_extract —
filtering the WRONG kind of data is a real miss, not a naming variant),
field identity is intentionally still pinned to the generator's choice.
"""
from typing import List, Optional

from src.ir_engine.ir_schema import FilterOperator, KqlPipeline
from src.synthesis.ir_generator import GenerationMeta

_NOW_DATE = "2026-06-24"


def _first_group_by_field(ir: Optional[KqlPipeline]) -> Optional[str]:
    """The first group_by field from any SummarizeStage or MakeSeriesStage
    in the pipeline — used to build a fixture around whatever entity
    field the system actually chose, not what the generator chose."""
    if ir is None:
        return None
    for stage in ir.stages:
        if stage.type in ("summarize", "make_series") and stage.group_by:
            return stage.group_by[0]
    return None


def _arg_max_order_field(ir: Optional[KqlPipeline]) -> Optional[str]:
    if ir is None:
        return None
    for stage in ir.stages:
        if stage.type == "summarize" and (stage.arg_max or stage.arg_min):
            picked = stage.arg_max or stage.arg_min
            return picked.order_field
    return None


_NUMERIC_AGG_FUNCTIONS = {"sum", "avg", "stdev", "variance", "percentile"}


def _placeholder_fields(ir: Optional[KqlPipeline]) -> dict:
    """Every field a SummarizeStage/MakeSeriesStage in the system's IR
    actually references — every group_by entry (not just the first) and
    every aggregation's `field` (e.g. dcount(DnsQuery) needs a DnsQuery
    value to count) — mapped to a generic placeholder value, EXCEPT
    TimeGenerated (the fixture's own time-series construction owns that
    field; a generic overwrite would break it). Found live (§4Z):
    the system reasonably choosing dcount(DnsQuery) where the generator
    only ever used count() (no field needed) left DnsQuery missing from
    every fixture row — the SAME class of field-identity coupling as
    the group_by case, just one level deeper (an aggregation's operand,
    not just its grouping key)."""
    out = {}
    if ir is None:
        return out
    for stage in ir.stages:
        if stage.type not in ("summarize", "make_series"):
            continue
        for gb in stage.group_by or []:
            if gb != "TimeGenerated":
                out[gb] = "entity-A"
        for agg in stage.aggregations:
            if agg.field and agg.field != "TimeGenerated":
                out[agg.field] = 1 if agg.function.value in _NUMERIC_AGG_FUNCTIONS else "placeholder-value"
    return out


def _fire_rows_simple_filter(meta: GenerationMeta, system_ir: Optional[KqlPipeline]) -> List[dict]:
    row = {}
    for field, op, value in meta.notes["filters"]:
        row[field] = value
    return [row]


def _no_fire_rows_simple_filter(meta: GenerationMeta, system_ir: Optional[KqlPipeline]) -> List[dict]:
    row = {}
    for field, op, value in meta.notes["filters"]:
        row[field] = "definitely-not-a-match-XYZ" if isinstance(value, str) else -999999
    return [row]


def _group_field_for(meta: GenerationMeta, system_ir: Optional[KqlPipeline]) -> str:
    """Prefer the system's own chosen group_by field (field-identity
    decoupling); fall back to the generator's original choice only if
    the system's IR doesn't have a usable one — that fallback case will
    then correctly surface as a real structural mismatch, not a naming
    difference, if the system's IR turns out to lack a SummarizeStage
    at all."""
    return _first_group_by_field(system_ir) or meta.notes["group_field"]


def _fire_rows_threshold_summarize(meta: GenerationMeta, system_ir: Optional[KqlPipeline]) -> List[dict]:
    gf = _group_field_for(meta, system_ir)
    extra = _placeholder_fields(system_ir)
    n = meta.notes["threshold"] + 5
    return [{**extra, gf: "entity-A", "TimeGenerated": f"{_NOW_DATE}T01:00:00Z"} for _ in range(n)]


def _no_fire_rows_threshold_summarize(meta: GenerationMeta, system_ir: Optional[KqlPipeline]) -> List[dict]:
    gf = _group_field_for(meta, system_ir)
    extra = _placeholder_fields(system_ir)
    n = max(1, meta.notes["threshold"] - 3)
    return [{**extra, gf: "entity-A", "TimeGenerated": f"{_NOW_DATE}T01:00:00Z"} for _ in range(n)]


def _fire_rows_or_list(meta: GenerationMeta, system_ir: Optional[KqlPipeline]) -> List[dict]:
    return [{meta.notes["field"]: meta.notes["values"][0]}]


def _no_fire_rows_or_list(meta: GenerationMeta, system_ir: Optional[KqlPipeline]) -> List[dict]:
    return [{meta.notes["field"]: "none-of-the-listed-values-QQQ"}]


_NEGATED_EXCLUSION_OPERATORS = {
    FilterOperator.NEQ, FilterOperator.NEQ_CI, FilterOperator.NOT_CONTAINS,
    FilterOperator.NOT_CONTAINS_CS, FilterOperator.NOT_STARTSWITH, FilterOperator.NOT_STARTSWITH_CS,
    FilterOperator.NOT_ENDSWITH, FilterOperator.NOT_ENDSWITH_CS, FilterOperator.NOT_HAS,
    FilterOperator.NOT_HAS_CS, FilterOperator.NOT_IN, FilterOperator.NOT_IN_CI,
}


def _process_name_field_for_has_all_evasion(system_ir: Optional[KqlPipeline], fallback: str = "ActingProcessName") -> str:
    """The field the system's own WhereStage uses for the renamed-binary
    EXCLUSION check specifically — found while auditing this template's
    previously-unexplained low (2/5, 40%) evasion-fire rate
    (CONSTRUCT_COVERAGE.md §4Z): the generator pins this to
    "ActingProcessName", but the live system varies between "Process"/
    "ActingProcessName"/"TargetProcessName"/"ParentProcessName" for "the
    process's own name" (confirmed directly against live sdelete-case
    and has_all_evasion output runs this same round) — the identical
    field-identity-coupling risk already decoupled for every OTHER
    template in this file, just never applied here.

    Must be restricted to a NEGATED operator specifically, not just "the
    first non-has_all filter with a string value" — found live, this
    same round: the system often ALSO adds a POSITIVE confirmation
    filter first (e.g. "ProcessName =~ 'powershell.exe'", confirming the
    process really is the expected interpreter) before the actual
    exclusion filter ("ParentProcessName !~ 'psexec.exe'"). An earlier,
    unrestricted version of this helper grabbed the positive
    confirmation filter's field instead, populating the WRONG field as
    "renamed_tool.exe" and leaving the real exclusion field unpopulated
    — silently passing the FIRE case for the wrong reason (an absent
    field trivially satisfies NOT_ENDSWITH-family checks) rather than
    actually exercising the exclusion logic this template exists to
    test."""
    if system_ir is None:
        return fallback
    for stage in system_ir.stages:
        if stage.type != "where":
            continue
        for f in stage.filters:
            if f.type == "filter" and f.operator in _NEGATED_EXCLUSION_OPERATORS and isinstance(f.value, str):
                return f.field
    return fallback


def _has_all_flags_for(system_ir: Optional[KqlPipeline], fallback: List[str]) -> List[str]:
    """The has_all filter's OWN value list from the system's IR, not the
    generator's randomly-drawn flags — found live, this round, auditing
    this template's persistent ~40% fire rate (the SAME finding that
    motivated _process_name_field_for_has_all_evasion above, one layer
    deeper): back-translation doesn't faithfully preserve the
    generator's exact literal flag set, and per EXISTING, INTENTIONAL
    guidance (PROJECT_STATUS.md §4N — "recall a named tool's real
    documented syntax"), the IR Builder correctly substitutes a named
    tool's REAL flags over whatever the NL's paraphrase implied,
    sometimes adding flags never in the generator's draw, sometimes
    dropping one, sometimes respelling one ("-w hidden" -> "-windowstyle
    hidden"). That is correct, intentional model behavior, not a bug —
    but it means a fixture built from meta.notes["flags"] is checking
    the WRONG flag set whenever this happens, the literal-value version
    of the field-identity-coupling lesson this whole file is built
    around. Falls back to the generator's flags only if the system's IR
    has no has_all filter at all (a genuine, different-construct
    outcome — e.g. four separate plain "has" filters instead, which the
    interpreter handles identically to has_all and needs no special
    casing here)."""
    if system_ir is None:
        return fallback
    for stage in system_ir.stages:
        if stage.type != "where":
            continue
        for f in stage.filters:
            if f.type == "filter" and f.operator == FilterOperator.HAS_ALL and isinstance(f.value, list):
                return [str(v) for v in f.value]
    return fallback


def _other_positive_filter_values_for_has_all_evasion(system_ir: Optional[KqlPipeline], exclusion_field: str) -> dict:
    """Any THIRD filter the system added beyond has_all and the renamed-
    binary exclusion — e.g. an extra "ActingProcessName =~
    'powershell.exe'" confirming the process's own identity, on a field
    OTHER than the one the exclusion check uses (found live, this
    round: a back-translated NL blending PowerShell-flag and sdelete-
    evasion framing produced exactly this 3-filter shape). All filters
    in one WhereStage are AND-ed, so leaving this field unpopulated
    makes the whole stage False regardless of has_all/exclusion,
    failing the FIRE case for a reason that has nothing to do with the
    evasion logic under test. Populated from the system's OWN literal
    value, the same decoupling principle as every other helper here."""
    out = {}
    if system_ir is None:
        return out
    for stage in system_ir.stages:
        if stage.type != "where":
            continue
        for f in stage.filters:
            if (
                f.type == "filter" and f.field != exclusion_field
                and f.operator not in ({FilterOperator.HAS_ALL} | _NEGATED_EXCLUSION_OPERATORS)
                and isinstance(f.value, str)
            ):
                out[f.field] = f.value
    return out


def _fire_rows_has_all_evasion(meta: GenerationMeta, system_ir: Optional[KqlPipeline]) -> List[dict]:
    flags = _has_all_flags_for(system_ir, meta.notes["flags"])
    cmdline = "renamed_tool.exe " + " ".join(flags)
    proc_field = _process_name_field_for_has_all_evasion(system_ir)
    extra = _other_positive_filter_values_for_has_all_evasion(system_ir, proc_field)
    return [{**extra, "CommandLine": cmdline, proc_field: "renamed_tool.exe"}]


def _no_fire_rows_has_all_evasion(meta: GenerationMeta, system_ir: Optional[KqlPipeline]) -> List[dict]:
    # Missing one required flag -> has_all fails.
    flags = _has_all_flags_for(system_ir, meta.notes["flags"])
    cmdline = "renamed_tool.exe " + " ".join(flags[:-1])
    proc_field = _process_name_field_for_has_all_evasion(system_ir)
    extra = _other_positive_filter_values_for_has_all_evasion(system_ir, proc_field)
    return [{**extra, "CommandLine": cmdline, proc_field: "renamed_tool.exe"}]


def _fire_rows_arg_max_latest(meta: GenerationMeta, system_ir: Optional[KqlPipeline]) -> List[dict]:
    gf = _group_field_for(meta, system_ir)
    of = _arg_max_order_field(system_ir) or "TimeGenerated"
    return [
        {gf: "entity-A", of: f"{_NOW_DATE}T01:00:00Z"},
        {gf: "entity-A", of: f"{_NOW_DATE}T05:00:00Z"},
    ]


def _fire_rows_parse_extract(meta: GenerationMeta, system_ir: Optional[KqlPipeline]) -> List[dict]:
    return [{"Url": "http://x.example.com/jndi:ldap://attacker.example.com/payload"}]


def _no_fire_rows_parse_extract(meta: GenerationMeta, system_ir: Optional[KqlPipeline]) -> List[dict]:
    return [{"Url": "http://contoso.com/login"}]


def _series_field_names(ir: Optional[KqlPipeline]) -> "tuple[Optional[str], Optional[str]]":
    """(make_series group_by field, the aggregation alias series_anomaly
    actually analyzes) — both read from the system's own IR, the same
    field-identity decoupling as the group_by helpers above, since a
    make_series chain has the MOST aliases that can legitimately differ
    run to run (the count alias, the group field, all 3 of the
    series_anomaly output aliases)."""
    group_field = None
    for stage in ir.stages if ir else []:
        if stage.type == "make_series":
            group_field = stage.group_by[0] if stage.group_by else None
    for stage in ir.stages if ir else []:
        if stage.type == "series_anomaly":
            return group_field, stage.series_field
    return group_field, None


def _fire_rows_make_series_anomaly(meta: GenerationMeta, system_ir: Optional[KqlPipeline]) -> List[dict]:
    group_field, _ = _series_field_names(system_ir)
    group_field = group_field or "SrcIpAddr"
    # count()'s result needs nothing extra — the interpreter derives it
    # from how many rows fall in each bucket. But the system may
    # reasonably choose dcount(SomeField) instead (a defensible reading
    # of "query activity," found live, §4Z) — _placeholder_fields covers
    # that case the same way it covers threshold_summarize's. For the
    # FIRE scenario specifically, a dcount-style field must also VARY
    # per row during the spike, or an identical placeholder value across
    # every spike row leaves the distinct count flat even while the raw
    # row count spikes — undermining the exact anomaly being tested.
    extra = _placeholder_fields(system_ir)
    quiet_days = [f"2026-06-{17+i:02d}" for i in range(6)]
    spike_day = "2026-06-23"
    rows = [{**extra, group_field: "entity-A", "TimeGenerated": f"{d}T12:00:00Z"} for d in quiet_days for _ in range(2)]
    for i in range(40):
        spike_extra = {k: (f"{v}-{i}" if isinstance(v, str) else v) for k, v in extra.items()}
        rows.append({**spike_extra, group_field: "entity-A", "TimeGenerated": f"{spike_day}T12:00:00Z"})
    return rows


def _no_fire_rows_make_series_anomaly(meta: GenerationMeta, system_ir: Optional[KqlPipeline]) -> List[dict]:
    group_field, _ = _series_field_names(system_ir)
    group_field = group_field or "SrcIpAddr"
    extra = _placeholder_fields(system_ir)
    all_days = [f"2026-06-{17+i:02d}" for i in range(7)]
    return [{**extra, group_field: "entity-A", "TimeGenerated": f"{d}T12:00:00Z"} for d in all_days for _ in range(2)]


def _fire_rows_join_baseline(meta: GenerationMeta, system_ir: Optional[KqlPipeline]) -> List[dict]:
    gf = _group_field_for(meta, system_ir)
    return [{gf: "entity-A", "TimeGenerated": f"{_NOW_DATE}T01:00:00Z"}]


def _no_fire_rows_join_baseline(meta: GenerationMeta, system_ir: Optional[KqlPipeline]) -> List[dict]:
    return []  # no rows at all -> the join's left side is already empty


# --- Construct-combination fixtures -----------------------------------
#
# These apply the field-decoupling lesson from the start (not as a
# follow-up fix) — every intermediate field name (a parse-extracted
# column, a join key, an aggregated/expanded field) is read from the
# SYSTEM'S OWN IR wherever its name carries no semantic weight of its
# own, the same line CONSTRUCT_COVERAGE.md's §4Z entry draws for the
# single-construct templates above.

def _fire_rows_parse_then_summarize(meta: GenerationMeta, system_ir: Optional[KqlPipeline]) -> List[dict]:
    # Only the SOURCE field ("Url") was originally assumed to matter —
    # found live (§4Z, 14/14 field_mismatch on the first scaled run):
    # the system frequently solves "count repeated JNDI lookups" via
    # `where Url contains "jndi"` grouped on an EXISTING ASIM field
    # (DstHostname/SrcIpAddr/SessionId), never invoking parse at all —
    # a genuinely valid alternative reading this template's NL doesn't
    # rule out. Whatever the system's own SummarizeStage groups by must
    # also be populated, the same decoupling already applied to
    # threshold_summarize, generalized to a combination template where
    # the construct itself may not even appear in the system's answer.
    # A second round (§4AA, 9/14 still mismatching after the first fix)
    # found two more gaps: TimeGenerated was never included at all
    # (every summarize bins on it), and other aggregation operands
    # (e.g. a make_set(SessionId), or a non-standard min(starttime))
    # need the same _placeholder_fields treatment threshold_summarize
    # already gets.
    gf = _first_group_by_field(system_ir)
    extra = _placeholder_fields(system_ir)
    n = meta.notes["threshold"] + 5
    row = {**extra, "Url": "http://x.example.com/jndi:ldap://evil-host.example.com/payload", "TimeGenerated": f"{_NOW_DATE}T01:00:00Z"}
    if gf:
        row[gf] = "entity-A"
    return [dict(row) for _ in range(n)]


def _no_fire_rows_parse_then_summarize(meta: GenerationMeta, system_ir: Optional[KqlPipeline]) -> List[dict]:
    gf = _first_group_by_field(system_ir)
    extra = _placeholder_fields(system_ir)
    n = max(1, meta.notes["threshold"] - 2)
    row = {**extra, "Url": "http://x.example.com/jndi:ldap://evil-host.example.com/payload", "TimeGenerated": f"{_NOW_DATE}T01:00:00Z"}
    if gf:
        row[gf] = "entity-A"
    return [dict(row) for _ in range(n)]


def _left_where_field_value(ir: Optional[KqlPipeline]) -> "tuple[Optional[str], Optional[object]]":
    """The first stage's first plain filter (field, value) — used to
    build a left-side row that satisfies whatever the system's OWN
    leading WhereStage actually checks, not what the generator's
    template happened to use. A list-valued filter (in~/has_any/...)
    returns its first element — a fixture row needs one concrete scalar
    that satisfies the check, not the candidate list itself."""
    if ir is None or not ir.stages:
        return None, None
    first = ir.stages[0]
    if first.type == "where" and first.filters:
        f = first.filters[0]
        if f.type == "filter":
            value = f.value[0] if isinstance(f.value, list) and f.value else f.value
            return f.field, value
    return None, None


def _join_keys_for(ir: Optional[KqlPipeline], fallback: str) -> List[str]:
    """ALL of the join's keys, not just the first — found live (§4Z):
    the system reasonably correlating on (Dvc, ActorUsername) instead
    of the generator's single Dvc key left every extra key entirely
    unpopulated in the fixture, a guaranteed KeyError on a join the
    system got right."""
    if ir:
        for stage in ir.stages:
            if stage.type == "join" and stage.join_on:
                return list(stage.join_on)
    return [fallback]


def _fire_rows_arg_max_in_join(meta: GenerationMeta, system_ir: Optional[KqlPipeline]) -> List[dict]:
    field, value = _left_where_field_value(system_ir)
    field = field or meta.notes["left_filter_field"]
    value = value if value is not None else meta.notes["left_filter_value"]
    join_keys = _join_keys_for(system_ir, meta.notes["join_key"])
    key_fields = {k: "entity-A" for k in join_keys}
    # The same row set feeds both sides of the join (see ir_interpreter.py's
    # join handling) — one row satisfying the left filter, with every join
    # key and a TimeGenerated value, is enough for the right side's
    # arg_max to also find a match.
    return [{field: value, **key_fields, "TimeGenerated": f"{_NOW_DATE}T01:00:00Z"}]


def _no_fire_rows_arg_max_in_join(meta: GenerationMeta, system_ir: Optional[KqlPipeline]) -> List[dict]:
    field, value = _left_where_field_value(system_ir)
    field = field or meta.notes["left_filter_field"]
    join_keys = _join_keys_for(system_ir, meta.notes["join_key"])
    key_fields = {k: "entity-A" for k in join_keys}
    mismatched = "definitely-not-a-match-XYZ" if isinstance(value, str) else -999999
    return [{field: mismatched, **key_fields, "TimeGenerated": f"{_NOW_DATE}T01:00:00Z"}]


def _agg_field_and_group(ir: Optional[KqlPipeline]) -> "tuple[Optional[str], Optional[str]]":
    """(make_set's source field, group_by field) from the first
    SummarizeStage — both read from the system's own IR, decoupled from
    the generator's choice of "Url"/"SrcIpAddr". Specifically a
    make_set/make_list aggregation, not just any aggregation with a
    field — found live (§4AA): the system commonly ALSO computes
    min/max(TimeGenerated) in the same summarize, and since those
    appear earlier in the aggregations list than make_set(Url), an
    earlier "first truthy field wins" version of this helper grabbed
    "TimeGenerated" instead of "Url", leaving the fixture's actual
    aggregated column entirely unpopulated — a guaranteed empty result,
    scored as a system failure that was really a harness bug."""
    if ir is None:
        return None, None
    for stage in ir.stages:
        if stage.type == "summarize":
            gf = stage.group_by[0] if stage.group_by else None
            for agg in stage.aggregations:
                if agg.field and agg.function.value in ("make_set", "make_list"):
                    return agg.field, gf
    return None, None


def _filter_value_after_mv_expand(ir: Optional[KqlPipeline]) -> Optional[str]:
    """The literal value the final WhereStage checks — the system may
    reasonably pick a different suspicious extension than the generator
    did; the fixture should test whatever the system actually filters
    for, not the generator's specific draw."""
    if ir is None:
        return None
    for stage in ir.stages:
        if stage.type == "where" and stage.filters:
            f = stage.filters[0]
            if f.type == "filter" and isinstance(f.value, str):
                return f.value
    return None


def _fire_rows_make_set_mv_expand_filter(meta: GenerationMeta, system_ir: Optional[KqlPipeline]) -> List[dict]:
    agg_field, group_field = _agg_field_and_group(system_ir)
    agg_field = agg_field or "Url"
    group_field = group_field or "SrcIpAddr"
    ext = _filter_value_after_mv_expand(system_ir) or meta.notes["suspicious_ext"]
    return [
        {group_field: "entity-A", agg_field: f"http://contoso.com/login", "TimeGenerated": f"{_NOW_DATE}T01:00:00Z"},
        {group_field: "entity-A", agg_field: f"http://evil.example.com/payload{ext}", "TimeGenerated": f"{_NOW_DATE}T01:00:00Z"},
    ]


def _no_fire_rows_make_set_mv_expand_filter(meta: GenerationMeta, system_ir: Optional[KqlPipeline]) -> List[dict]:
    agg_field, group_field = _agg_field_and_group(system_ir)
    agg_field = agg_field or "Url"
    group_field = group_field or "SrcIpAddr"
    return [
        {group_field: "entity-A", agg_field: "http://contoso.com/login", "TimeGenerated": f"{_NOW_DATE}T01:00:00Z"},
        {group_field: "entity-A", agg_field: "http://contoso.com/report.pdf", "TimeGenerated": f"{_NOW_DATE}T01:00:00Z"},
    ]


_FIRE = {
    "simple_filter": _fire_rows_simple_filter,
    "threshold_summarize": _fire_rows_threshold_summarize,
    "or_list": _fire_rows_or_list,
    "has_all_evasion": _fire_rows_has_all_evasion,
    "arg_max_latest": _fire_rows_arg_max_latest,
    "parse_extract": _fire_rows_parse_extract,
    "make_series_anomaly": _fire_rows_make_series_anomaly,
    "join_baseline": _fire_rows_join_baseline,
    "parse_then_summarize": _fire_rows_parse_then_summarize,
    "arg_max_in_join": _fire_rows_arg_max_in_join,
    "make_set_mv_expand_filter": _fire_rows_make_set_mv_expand_filter,
}

_NO_FIRE = {
    "simple_filter": _no_fire_rows_simple_filter,
    "threshold_summarize": _no_fire_rows_threshold_summarize,
    "or_list": _no_fire_rows_or_list,
    "has_all_evasion": _no_fire_rows_has_all_evasion,
    "arg_max_latest": lambda meta, system_ir: [],  # arg_max always "fires" (always returns a row) — no meaningful no-fire case
    "parse_extract": _no_fire_rows_parse_extract,
    "make_series_anomaly": _no_fire_rows_make_series_anomaly,
    "join_baseline": _no_fire_rows_join_baseline,
    "parse_then_summarize": _no_fire_rows_parse_then_summarize,
    "arg_max_in_join": _no_fire_rows_arg_max_in_join,
    "make_set_mv_expand_filter": _no_fire_rows_make_set_mv_expand_filter,
}


def should_fire_rows(meta: GenerationMeta, system_ir: Optional[KqlPipeline] = None) -> List[dict]:
    """system_ir, when given, is the IR actually being evaluated (e.g.
    the live system's regenerated pipeline) — for templates where the
    grouping/ordering field is semantically arbitrary, the fixture is
    built around system_ir's OWN field choice instead of the
    generator's, decoupling the check from field identity. Defaults to
    None for the self-consistency check (ir_generator's own output
    against its own metadata), where there is no separate "system" IR."""
    return _FIRE[meta.template](meta, system_ir)


def should_not_fire_rows(meta: GenerationMeta, system_ir: Optional[KqlPipeline] = None) -> List[dict]:
    return _NO_FIRE[meta.template](meta, system_ir)
