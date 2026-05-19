from .state import PipelineState
from typing import Literal

def route_after_validation(state: PipelineState) -> Literal["pass", "repair", "max_retries"]:
    """
    Route based on validation results and repair count.
    """
    validation = state.get("validation_results", {})
    all_passed = validation.get("passed", False) if validation else False
    repair_count = state.get("repair_count", 0)
    MAX_RETRIES = 3

    if all_passed:
        return "pass"
    if repair_count >= MAX_RETRIES:
        return "max_retries"
    return "repair"
