from typing import TypedDict, Annotated, List, Optional
from operator import add

class PipelineState(TypedDict):
    # Input
    raw_input: str
    chunks: List[str]
    source_document: Optional[str]

    # Agent extractions
    behaviors: List[dict]
    iocs: List[dict]
    severity: str
    description: str
    tags: List[str]
    entities: dict
    mitre_mappings: List[dict]

    # IR stages
    security_ir: Optional[dict]
    normalized_ir: Optional[dict]

    # Generated rules
    sigma_rule: Optional[str]
    kql_rule: Optional[str]
    spl_rule: Optional[str]

    # Validation
    validation_results: dict
    repair_count: int
    errors: Annotated[List[str], add]

    # Output
    validated_rules: Optional[dict]
    pipeline_status: str      # "running" | "success" | "failed" | "pending_review"
    provenance: dict
