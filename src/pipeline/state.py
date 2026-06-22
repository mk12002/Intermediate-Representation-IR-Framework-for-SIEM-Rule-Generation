from typing import Optional, TypedDict


class PipelineState(TypedDict):
    nl_description: str

    extraction: Optional[dict]
    asim_field_list: Optional[list[str]]

    ir: Optional[dict]
    ir_validation_error: Optional[str]

    kql: Optional[str]
    syntax_validation_error: Optional[str]

    attempts_used: int
    pipeline_status: str  # "running" | "success" | "failed"
    failure_reason: Optional[str]
