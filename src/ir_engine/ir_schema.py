from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Union
from uuid import uuid4
from datetime import datetime

class FilterCondition(BaseModel):
    field: str
    operator: Literal["equals", "not_equals", "contains", "starts_with", "in",
                       "not_in", "in_cidr", "not_in_cidr", "regex", "greater_than",
                       "less_than", "exists"]
    value: Union[str, int, float, List[Union[str, int, float]]]
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    note: Optional[str] = None

class ThresholdConfig(BaseModel):
    operator: Literal["greater_than", "less_than", "equals", "gte", "lte"]
    value: Union[int, float]

class AggregationConfig(BaseModel):
    function: Literal["count", "sum", "distinct_count", "min", "max", "avg"]
    target_field: Optional[str] = None   # for sum/min/max/avg
    group_by: List[str] = Field(default_factory=list)
    threshold: ThresholdConfig

class TimeframeConfig(BaseModel):
    duration: int
    unit: Literal["seconds", "minutes", "hours", "days"]
    type: Literal["sliding_window", "fixed_window", "session_window"] = "sliding_window"

class MITREMapping(BaseModel):
    tactic: str
    tactic_id: str          # TA####
    technique: str
    technique_id: str       # T####
    sub_technique: Optional[str] = None
    sub_technique_id: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str

class IRMetadata(BaseModel):
    rule_name: str
    description: str
    severity: Literal["informational", "low", "medium", "high", "critical"]
    tags: List[str] = Field(default_factory=list)
    author: str = "IR Framework"

class DetectionLogic(BaseModel):
    event_type: str
    filters: List[FilterCondition] = Field(default_factory=list)
    aggregation: Optional[AggregationConfig] = None
    timeframe: Optional[TimeframeConfig] = None

class EntityMapping(BaseModel):
    entities: dict = Field(default_factory=dict)

class TemporalLogic(BaseModel):
    correlations: List[dict] = Field(default_factory=list)

class OutputConfig(BaseModel):
    target_platforms: List[str] = ["sigma", "kql", "spl"]

class SecurityIR(BaseModel):
    ir_version: str = "1.0"
    rule_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    source_document: Optional[str] = None
    confidence_overall: float = Field(default=0.8, ge=0.0, le=1.0)
    repair_count: int = 0

    metadata: IRMetadata
    detection_logic: DetectionLogic
    entity_mapping: EntityMapping = Field(default_factory=EntityMapping)
    temporal_logic: Optional[TemporalLogic] = None
    mitre_mapping: List[MITREMapping] = Field(default_factory=list)
    output_config: OutputConfig = Field(default_factory=OutputConfig)
    provenance: dict = Field(default_factory=dict)
