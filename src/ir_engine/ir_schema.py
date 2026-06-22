from enum import Enum
from typing import List, Optional, Union

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
    STARTSWITH = "startswith"
    IN = "in"
    GT = ">"
    LT = "<"
    GTE = ">="
    LTE = "<="


class Filter(BaseModel):
    field: str
    operator: FilterOperator
    value: Union[str, int, float, List[str]]


class AggregationFunction(str, Enum):
    COUNT = "count"
    DISTINCT_COUNT = "distinct_count"
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"


KQL_AGG_FUNCTIONS = {
    AggregationFunction.COUNT: "count",
    AggregationFunction.DISTINCT_COUNT: "dcount",
    AggregationFunction.SUM: "sum",
    AggregationFunction.AVG: "avg",
    AggregationFunction.MIN: "min",
    AggregationFunction.MAX: "max",
}


class Aggregation(BaseModel):
    function: AggregationFunction
    field: Optional[str] = None
    result_alias: str = "AggregatedValue"


class ThresholdOperator(str, Enum):
    GT = ">"
    GTE = ">="
    LT = "<"
    LTE = "<="
    EQ = "=="


class Threshold(BaseModel):
    operator: ThresholdOperator
    value: Union[int, float]


class SecurityIR(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: ASIMEventType
    filters: List[Filter] = Field(default_factory=list)
    aggregation: Optional[Aggregation] = None
    group_by: Optional[List[str]] = None
    threshold: Optional[Threshold] = None
    time_window: Optional[str] = None  # ISO 8601 duration, e.g. "PT5M"
    output_fields: Optional[List[str]] = None


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
