from enum import Enum
from typing import List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


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
    MATCHES_REGEX = "matches regex"
    GT = ">"
    LT = "<"
    GTE = ">="
    LTE = "<="


class Filter(BaseModel):
    """A single condition. Items at the top level of SecurityIR.filters are
    implicitly AND-ed together (one KQL "| where" clause each) — there is no
    way to express OR between two top-level Filters; use a FilterGroup for
    that."""

    type: Literal["filter"] = "filter"
    field: str
    operator: FilterOperator
    value: Union[str, int, float, List[str]]


class FilterGroup(BaseModel):
    """A parenthesized block of conditions OR-ed together, e.g. KQL's
    "(CommandLine has 'user' or CommandLine has 'group')". Use this when the
    detection needs "(A or B) and (C or D)"-style logic — a FilterGroup in
    SecurityIR.filters is still AND-ed with every other item in that list,
    same as a plain Filter; only the conditions *inside* the group are OR-ed.
    Needs at least 2 conditions to be meaningful."""

    type: Literal["group"] = "group"
    conditions: List[Filter] = Field(min_length=2)


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
}


class Aggregation(BaseModel):
    """percentile is required (0-100) when function="percentile" — KQL's
    percentile() takes a field AND a percentile value, unlike every other
    supported function. This computes the Nth percentile of field's
    per-row values *within* each group (e.g. P95 connection duration per
    host) — it does not support computing a percentile *across* groups'
    own aggregate results (e.g. "processes at or below the 5th percentile
    of their own execution frequency"), which needs a second aggregation
    pass over a scalar derived from the first and is out of scope.

    limit is optional and only meaningful for make_set/make_list — KQL's
    own default cap (128) applies when omitted; unlike percentile's value,
    a missing limit is not an error."""

    function: AggregationFunction
    field: Optional[str] = None
    result_alias: str = "AggregatedValue"
    percentile: Optional[float] = None
    limit: Optional[int] = None


class ThresholdOperator(str, Enum):
    GT = ">"
    GTE = ">="
    LT = "<"
    LTE = "<="
    EQ = "=="


class Threshold(BaseModel):
    """value is a plain literal by default: "{aggregation result} {operator}
    {value}". Set compare_to_join_field for a baseline-vs-current detection
    ("current exceeds the 14-day baseline by more than 50") — it must name
    the join stage's own aggregation.result_alias, and value becomes the
    margin added to it: "{aggregation result} {operator} {compare_to_join_field}
    + {value}". Use value=0 for a direct comparison with no margin."""

    operator: ThresholdOperator
    value: Union[int, float]
    compare_to_join_field: Optional[str] = None


class JoinKind(str, Enum):
    """KQL join flavors used in ASIM correlation rules."""
    INNER = "inner"
    LEFTANTI = "leftanti"
    LEFTOUTER = "leftouter"


class JoinStage(BaseModel):
    """A sub-query joined against the main query — covers the correlation
    patterns (baseline-vs-current, enrichment lookup, exclusion via leftanti)
    that a flat single-table IR cannot express.

    Renders as:
        let <alias> = <table> | where ... | summarize ...;
        MainQuery | join kind=<join_kind> (<alias>) on <join_on keys>
    """
    model_config = ConfigDict(extra="forbid")

    alias: str = "SubQuery"
    event_type: ASIMEventType
    filters: List[Union[Filter, FilterGroup]] = Field(default_factory=list)
    aggregation: Optional[Aggregation] = None
    # Extra summarize columns computed alongside `aggregation` in the same
    # clause (e.g. an evidence make_set() next to the count that drives the
    # join) — see SecurityIR.additional_aggregations for the rationale.
    additional_aggregations: List[Aggregation] = Field(default_factory=list)
    group_by: Optional[List[str]] = None
    time_window: Optional[str] = None  # ISO 8601 duration
    join_on: List[str] = Field(min_length=1)
    join_kind: JoinKind = JoinKind.INNER


class SecurityIR(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: ASIMEventType
    # Plain (smart-mode) union, not Field(discriminator="type") — a
    # discriminator requires the "type" tag to be *present* in the input
    # even though it has a Python-level default, so models that omit it on
    # an ordinary Filter (the common case — most filters never need
    # FilterGroup) failed to parse at all. Smart-mode union matches
    # structurally instead (does it have "conditions"? -> FilterGroup;
    # does it have "field"/"operator"/"value"? -> Filter) and tolerates
    # the tag being absent.
    filters: List[Union[Filter, FilterGroup]] = Field(default_factory=list)
    aggregation: Optional[Aggregation] = None
    # Extra summarize columns computed alongside `aggregation` in the same
    # clause — e.g. "ErrorCount = count(), Urls = make_set(Url, 100),
    # EventStartTime = min(TimeGenerated)" all in one summarize. Most real
    # ASIM analytic rules compute several columns together, not one; before
    # this field, the IR could only ever express the single column a
    # threshold applies to. `threshold` always compares against
    # `aggregation`'s own result_alias, never one of these — they're
    # side evidence/context, not alerting conditions.
    additional_aggregations: List[Aggregation] = Field(default_factory=list)
    group_by: Optional[List[str]] = None
    threshold: Optional[Threshold] = None
    time_window: Optional[str] = None  # ISO 8601 duration, e.g. "PT5M"
    output_fields: Optional[List[str]] = None
    join: Optional[JoinStage] = None


class ExtractionOutput(BaseModel):
    """Loose, pre-schema extraction surfaced by the Extraction Agent.

    Deliberately under-constrained relative to SecurityIR — it is the
    IR Builder Agent's job to commit to a schema-conformant structure.
    """

    likely_event_type: str
    actors: List[str] = Field(default_factory=list)
    action_description: str
    threshold_language: Optional[str] = None
    time_language: Optional[str] = None
    candidate_fields: List[str] = Field(default_factory=list)
