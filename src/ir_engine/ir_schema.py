from enum import Enum
from typing import List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ASIMEventType(str, Enum):
    AUTHENTICATION = "AuthenticationEvent"
    NETWORK_SESSION = "NetworkSessionEvent"
    PROCESS = "ProcessEvent"
    FILE = "FileEvent"
    DNS = "DnsEvent"
    WEB_SESSION = "WebSessionEvent"
    REGISTRY = "RegistryEvent"


ASIM_TABLE_NAMES = {
    ASIMEventType.AUTHENTICATION: "imAuthentication",
    ASIMEventType.NETWORK_SESSION: "imNetworkSession",
    ASIMEventType.PROCESS: "imProcessCreate",
    ASIMEventType.FILE: "imFileEvent",
    ASIMEventType.DNS: "imDns",
    ASIMEventType.WEB_SESSION: "imWebSession",
    ASIMEventType.REGISTRY: "imRegistry",
}


class FilterOperator(str, Enum):
    EQ = "=="
    NEQ = "!="
    CONTAINS = "contains"
    NOT_CONTAINS = "!contains"
    STARTSWITH = "startswith"
    NOT_STARTSWITH = "!startswith"
    ENDSWITH = "endswith"
    NOT_ENDSWITH = "!endswith"
    IN = "in"
    NOT_IN = "!in"
    HAS = "has"
    NOT_HAS = "!has"
    HAS_ANY = "has_any"
    # A real, separate KQL operator from has_any — confirmed live in
    # ground truth (e.g. `CommandLine has_all ("accepteula", "-s", "-r",
    # "-q")`, a multi-flag evasion check) after a construct-coverage audit
    # found the prompt was incorrectly telling the model this operator
    # doesn't exist (PROJECT_STATUS.md §4X). Requires EVERY term present,
    # the AND-equivalent of has_any's OR.
    HAS_ALL = "has_all"
    MATCHES_REGEX = "matches regex"
    GT = ">"
    LT = "<"
    GTE = ">="
    LTE = "<="
    # Case-insensitive `in`/`!in` — KQL's plain `in`/`!in` are
    # case-SENSITIVE by default (unlike contains/has/startswith/endswith,
    # which already default case-insensitive above); `in~`/`!in~` are the
    # explicit case-insensitive forms and appear frequently in real ground
    # truth list-membership checks (PROJECT_STATUS.md §4X construct audit).
    IN_CI = "in~"
    NOT_IN_CI = "!in~"
    # Case-insensitive equality/inequality — distinct from plain ==/!=
    # above, which are case-SENSITIVE by default for strings in KQL (the
    # mirror image of IN_CI/NOT_IN_CI's relationship to IN/NOT_IN). Found
    # live in real ground truth (e.g. `FileName =~ "powershell.exe"`,
    # tolerating PowerShell.EXE/POWERSHELL.exe) at 13 occurrences across
    # this project's own verified+held-out corpus — more than several
    # constructs already modeled as core (e.g. make-series, at 9; see
    # CONSTRUCT_COVERAGE.md's frequency audit).
    EQ_CI = "=~"
    NEQ_CI = "!~"
    # Case-SENSITIVE forms of contains/startswith/endswith/has, which are
    # all case-insensitive by default in KQL (see ir_builder_agent.py's
    # worked guidance). Confirmed real in ground truth (e.g. `CommandLine
    # has_cs "-exec bypass -w 1 -enc"`, `CommandLine contains_cs
    # "<base64-encoded payload fragment>"` — where a case-insensitive
    # match would either miss the actual encoded string or over-match
    # unrelated content, since a different-case base64 string decodes to
    # different bytes entirely).
    CONTAINS_CS = "contains_cs"
    NOT_CONTAINS_CS = "!contains_cs"
    STARTSWITH_CS = "startswith_cs"
    NOT_STARTSWITH_CS = "!startswith_cs"
    ENDSWITH_CS = "endswith_cs"
    NOT_ENDSWITH_CS = "!endswith_cs"
    HAS_CS = "has_cs"
    NOT_HAS_CS = "!has_cs"


class Filter(BaseModel):
    type: Literal["filter"] = "filter"
    field: str
    operator: FilterOperator
    # List[Union[str, int, float]], not List[str]: a list-valued filter
    # against a numeric field (e.g. "DstPortNumber in (139, 445)") needs an
    # int list. List[str]-only rejected that with a 5-error union-match
    # cascade and pushed the LLM's retry into a worse, malformed shape —
    # confirmed live during the AST migration's first hardening pass.
    value: Optional[Union[str, int, float, bool, List[Union[str, int, float]]]] = None
    # Compares `field` against ANOTHER COLUMN instead of a literal —
    # mutually exclusive with `value`. Added §4AA: found live that a
    # correlation needing "ProcessTime between FirstAuthTime and
    # LastAuthTime" (both columns from a joined right_pipeline) had no
    # way to be expressed — `value` is always rendered as a literal, so
    # the model fell back to comparing against the quoted STRING NAME of
    # the other column (syntactically valid, silently wrong: it can
    # never correctly match). Typically a column produced by an earlier
    # stage in this same pipeline or a joined right_pipeline rather than
    # a raw ASIM source field — but the validator's `available_schema`
    # already tracks those (extend aliases, joined-in columns) by the
    # time a later WhereStage runs, so it IS checked the same way `field`
    # is (ir_validator.py), not exempted.
    field_ref: Optional[str] = None

    @model_validator(mode="after")
    def _exactly_one_of_value_or_field_ref(self) -> "Filter":
        if (self.value is None) == (self.field_ref is None):
            raise ValueError("Filter must set exactly one of `value` or `field_ref`, not both/neither")
        return self


class AndGroup(BaseModel):
    type: Literal["and_group"] = "and_group"
    # An AND-ed sub-condition, usable only INSIDE a FilterGroup — lets a
    # FilterGroup express "(A and B) or (C and D)", not just a flat OR of
    # single atoms. Found live (PROJECT_STATUS.md §4N): a multi-app/port
    # mismatch detection needs "(app==dns and port!=53) or (app==http and
    # port!=80) or ..." — each branch itself a conjunction — which a flat
    # FilterGroup structurally cannot represent, forcing every live attempt
    # into a different wrong approximation (including an outright
    # tautology). A bare AndGroup at the top level of WhereStage.filters
    # would be redundant (multiple WhereStage.filters entries are already
    # AND-ed) — it only adds expressiveness nested inside an OR.
    conditions: List[Filter] = Field(min_length=2)


class FilterGroup(BaseModel):
    type: Literal["group"] = "group"
    conditions: List[Union[Filter, AndGroup]] = Field(min_length=2)


class AggregationFunction(str, Enum):
    COUNT = "count"
    DISTINCT_COUNT = "distinct_count"
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    PERCENTILE = "percentile"
    MAKE_SET = "make_set"
    MAKE_LIST = "make_list"
    # KQL's real spread/regularity functions. Added after a live case
    # (interval-regularity beaconing detection) had no real aggregation to
    # reach for and the model invented array_avg()/array_stddev() instead —
    # neither exists in KQL. stdev()/variance() are real summarize
    # aggregations and are the correct general-purpose tool for "how
    # consistent/regular is this value across the group" detections.
    STDEV = "stdev"
    VARIANCE = "variance"


KQL_AGG_FUNCTIONS = {
    AggregationFunction.COUNT: "count",
    AggregationFunction.DISTINCT_COUNT: "dcount",
    AggregationFunction.SUM: "sum",
    AggregationFunction.AVG: "avg",
    AggregationFunction.MIN: "min",
    AggregationFunction.MAX: "max",
    AggregationFunction.PERCENTILE: "percentile",
    AggregationFunction.MAKE_SET: "make_set",
    AggregationFunction.MAKE_LIST: "make_list",
    AggregationFunction.STDEV: "stdev",
    AggregationFunction.VARIANCE: "variance",
}


class Aggregation(BaseModel):
    function: AggregationFunction
    field: Optional[str] = None
    result_alias: str = "AggregatedValue"
    percentile: Optional[float] = None
    limit: Optional[int] = None


class ArgMaxMin(BaseModel):
    """`arg_max(order_field, *)` / `arg_min(order_field, *)` — KQL's "get
    the FULL ROW at the max/min value of order_field, per group" idiom
    (e.g. "the most recent event per host, with every other column from
    that same row"). Modeled as its own field on SummarizeStage, not a
    plain Aggregation, because it is structurally different from every
    other aggregation here: it doesn't reduce to ONE output column under
    ONE result_alias — each carried field becomes its OWN output column,
    keeping ITS OWN name, exactly as real KQL names them. Found in the
    construct-coverage audit (CONSTRUCT_COVERAGE.md): 36 real-query
    occurrences, previously only "Partial" (the function name was
    whitelisted for ExtendStage, where this idiom can never actually be
    expressed — arg_max/arg_min only exist inside summarize)."""
    order_field: str
    # The other columns to carry through from the max/min row, each
    # keeping its own name in the output (not under result_alias). Use
    # ["*"] to carry every other field still in scope — KQL's own `*`
    # shorthand for "all remaining columns."
    carry_fields: List[str] = Field(min_length=1)
    # Real KQL DOES support renaming the order_field's own output column
    # (e.g. "LatestIndicatorTime = arg_max(TimeGenerated, *)") — found
    # live in 30+ real ground-truth uses of this exact pattern
    # (threat-intel indicator deduplication before a join), none of
    # which leave the order_field under its raw name. None means "use
    # order_field's own name," the simpler, equally-real case this
    # was originally scoped to.
    result_alias: Optional[str] = None


class ComputedField(BaseModel):
    alias: str
    expression: str


class JoinKind(str, Enum):
    INNER = "inner"
    INNERUNIQUE = "innerunique"
    LEFTOUTER = "leftouter"
    RIGHTOUTER = "rightouter"
    FULLOUTER = "fullouter"
    LEFTANTI = "leftanti"
    RIGHTANTI = "rightanti"
    LEFTSEMI = "leftsemi"
    RIGHTSEMI = "rightsemi"


class WhereStage(BaseModel):
    type: Literal["where"] = "where"
    filters: List[Union[Filter, FilterGroup]] = Field(default_factory=list)


class SummarizeStage(BaseModel):
    type: Literal["summarize"] = "summarize"
    aggregations: List[Aggregation] = Field(default_factory=list)
    group_by: Optional[List[str]] = None
    time_window: Optional[str] = None
    # arg_max/arg_min combine freely with aggregations/group_by in the
    # same real summarize clause (e.g. "count(), arg_max(TimeGenerated, *)
    # by Dvc" is valid KQL) — siblings, not alternatives.
    arg_max: Optional[ArgMaxMin] = None
    arg_min: Optional[ArgMaxMin] = None


class ExtendStage(BaseModel):
    type: Literal["extend"] = "extend"
    computed_fields: List[ComputedField] = Field(default_factory=list)


class JoinStage(BaseModel):
    type: Literal["join"] = "join"
    kind: JoinKind = JoinKind.INNER
    # Forward ref, not Any: right_pipeline must be a real, Pydantic-validated
    # KqlPipeline, not a raw dict. With Any, a malformed nested pipeline from
    # the model parsed "successfully" (Any accepts anything) and crashed
    # validate_ir's recursive call with an AttributeError instead of being
    # caught as a clean LLM_OUTPUT_PARSE_FAILURE — confirmed live.
    right_pipeline: "KqlPipeline"
    join_on: List[str] = Field(min_length=1)


class UnionStage(BaseModel):
    type: Literal["union"] = "union"
    tables: List[str]


class ProjectStage(BaseModel):
    type: Literal["project"] = "project"
    fields: List[str]


class TopStage(BaseModel):
    type: Literal["top"] = "top"
    limit: int
    by_field: str
    desc: bool = True


class MvExpandStage(BaseModel):
    type: Literal["mv_expand"] = "mv_expand"
    # Most real detections expand exactly one dynamic-array field
    # (mv-expand Field). Multiple fields (mv-expand A, B, C — expanding
    # several arrays in lockstep, the same pattern make-series ->
    # series_decompose_anomalies -> mv-expand needs to flatten the
    # timestamp/value/anomaly-flag series back into one row per bucket)
    # is also real KQL and not meaningfully harder to model, so this
    # takes a list rather than a single field from the start.
    fields: List[str] = Field(min_length=1)
    as_type: Optional[str] = None  # `to typeof(...)` — only valid for a single field


class MakeSeriesStage(BaseModel):
    """`make-series` — produces one row per group_by combination, with
    each requested aggregation as a DYNAMIC ARRAY of per-bucket values
    spanning the time range (not one scalar per row, unlike
    SummarizeStage). This is the construct a baseline-vs-current
    comparison cannot substitute for: it preserves the full per-bucket
    sequence for series_decompose_anomalies (SeriesAnomalyStage below)
    or other series_*() functions to operate on, where SummarizeStage
    only ever produces one collapsed value per group."""

    type: Literal["make_series"] = "make_series"
    aggregations: List[Aggregation] = Field(min_length=1)
    group_by: Optional[List[str]] = None
    from_time: str  # a literal KQL time expression, e.g. "ago(14d)"
    to_time: str = "now()"  # same — a literal KQL time expression
    step: str  # bin width as ISO 8601, e.g. "PT1H" — same convention as
    # SummarizeStage.time_window elsewhere in this schema, NOT a raw KQL
    # duration literal like "1h" (from_time/to_time above are the
    # exception, not the pattern — they're full time expressions with no
    # ISO 8601 equivalent, not bin widths)


class SeriesAnomalyStage(BaseModel):
    """`series_decompose_anomalies()` — the real KQL anomaly-detection
    function, applied to a series produced by a prior MakeSeriesStage.
    Found live (PROJECT_STATUS.md §4T/§4U, case 01191239): with no
    construct for this at all, the model could only ever approximate a
    DGA/outlier detection as a flat count, self-disclosing the gap via
    `caveats` rather than silently faking it — the honest behavior at
    the time, but a real, closeable capability gap, not a permanent
    one. Always introduces 3 new series-typed fields for a later
    MvExpandStage to flatten back into rows; score_threshold maps to
    series_decompose_anomalies' own threshold parameter (KQL default 1.5
    if not given)."""

    type: Literal["series_anomaly"] = "series_anomaly"
    series_field: str  # the array-valued aggregation alias from MakeSeriesStage
    score_threshold: float = 1.5
    flag_alias: str = "AnomalyFlag"
    score_alias: str = "AnomalyScore"
    baseline_alias: str = "Baseline"


class ParseToken(BaseModel):
    """One token in a `parse ... with ...` clause, in left-to-right
    order. "literal" matches an exact substring (the text between
    extracted fields); "column" extracts the text at that position into
    a new field, named `value`; "wildcard" (KQL's bare `*`) skips any
    text at that position without extracting it — used for an unparsed
    prefix/suffix, e.g. "parse Message with * '(' DNSName ')' *"."""
    type: Literal["literal", "column", "wildcard"]
    value: Optional[str] = None  # the literal text, or the new column's name — unused for "wildcard"


class ParseStage(BaseModel):
    """KQL's `parse` pipe operator (simple/positional mode — covers the
    dominant real-world usage; `kind=regex`/`kind=relaxed` parse modes
    are out of scope, per CONSTRUCT_COVERAGE.md's tail policy). Extracts
    one or more new fields from a single source field by alternating
    literal delimiter text and named extraction points, e.g. "parse
    Message with * '(' DNSName ')' *" extracts DNSName from inside
    parentheses, ignoring everything else in Message."""
    type: Literal["parse"] = "parse"
    source_field: str
    tokens: List[ParseToken] = Field(min_length=1)


Stage = Union[
    WhereStage,
    SummarizeStage,
    ExtendStage,
    JoinStage,
    UnionStage,
    ProjectStage,
    TopStage,
    MvExpandStage,
    MakeSeriesStage,
    SeriesAnomalyStage,
    ParseStage,
]


class Ambiguity(BaseModel):
    """§4AG — a genuine FORK in how to read the description: multiple
    structurally different IRs would each be a defensible reading of
    the SAME input (e.g. "hidden in the recycle bin" supports both a
    process executing FROM that folder, ProcessEvent, and a file
    planted IN it, FileEvent — both real, neither more "correct" than
    the other absent more context). This is NOT the same gap class
    `caveats` covers: caveats discloses information that's ABSENT;
    Ambiguity discloses a choice made among options that are all
    PRESENT as equally valid readings. The IR Builder still commits to
    one reading and builds it into `stages` (picked_option records
    which) — Ambiguity is disclosure of that choice, not an excuse to
    avoid making one, the same "self-disclose, don't silently guess"
    principle caveats already established, applied to chosen-among-
    multiple instead of omitted-entirely."""
    description: str
    options: List[str] = Field(min_length=2)
    picked_option: str


class KqlPipeline(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_table: Union[ASIMEventType, str]
    stages: List[Stage] = Field(default_factory=list)
    # Self-disclosed abstentions — one short string per filter the model
    # deliberately omitted because the description referenced data it
    # could not concretely ground (an external list/watchlist with no
    # values given, an unrecoverable attribution label). Populated by the
    # IR Builder itself, not inferred after the fact — see
    # ir_builder_agent.py's "omit, don't invent" worked examples, each of
    # which now asks for one caveats entry alongside the omission. Kept
    # separate from PipelineResult.warnings (verifier-sourced, about a
    # generated query) since this is the model's own account of a
    # decision it made, not an external critique of the result.
    caveats: List[str] = Field(default_factory=list)
    # §4AE — found live: a PARTIAL abstention (omit one ungroundable
    # filter, keep the rest, disclose via caveats) is safe, but a TOTAL
    # abstention (no concrete detection logic groundable at all) was
    # being expressed as an empty `stages` list — which doesn't fail
    # safe. A KqlPipeline with no WhereStage filtering anything fires on
    # EVERY row of source_table when actually deployed; "abstained" is
    # not "inert," it's "alerts on everything," which is worse than not
    # shipping a rule at all (it buries the analyst in false positives
    # and trains them to ignore the alert). abstained=True is the
    # model's explicit declaration that it could not ground ANY
    # concrete detection logic — generate_kql() refuses to emit runnable
    # KQL for it (renders caveats only, no source_table query), and
    # pipeline_fires() always returns False for it, regardless of what
    # (if anything) ended up in stages. The validator hard-rejects an
    # empty stages list that ISN'T explicitly marked abstained — an
    # empty pipeline must always say why, not just silently exist.
    abstained: bool = False
    # §4AG — see Ambiguity above. Empty when the description supports
    # only one reasonable reading (the common case) — only populate
    # when a SECOND reading is genuinely equally defensible, not for
    # routine field-naming choices that already have an established
    # convention (Src*/Dst* prefix selection, ASIM table naming).
    ambiguities: List[Ambiguity] = Field(default_factory=list)


# Resolves the JoinStage.right_pipeline forward reference now that
# KqlPipeline itself is defined — required for the recursive type to
# build correctly; without this, right_pipeline would stay unresolved.
JoinStage.model_rebuild()
KqlPipeline.model_rebuild()


class ExtractionOutput(BaseModel):
    likely_event_type: str
    actors: List[str] = Field(default_factory=list)
    action_description: str
    threshold_language: Optional[str] = None
    time_language: Optional[str] = None
    candidate_fields: List[str] = Field(default_factory=list)
