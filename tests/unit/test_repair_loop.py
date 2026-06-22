from unittest.mock import MagicMock

from langchain_core.exceptions import OutputParserException

from src.ir_engine.ir_schema import (
    Aggregation,
    AggregationFunction,
    ASIMEventType,
    ExtractionOutput,
    Filter,
    FilterOperator,
    SecurityIR,
)
from src.pipeline.repair_loop import run_with_repair

ASIM_SCHEMA = {
    "AuthenticationEvent": {"fields": ["EventResult", "TargetUsername", "SrcIpAddr", "TimeGenerated"]},
}

EXTRACTION = ExtractionOutput(
    likely_event_type="AuthenticationEvent",
    actors=["account"],
    action_description="fails to log in repeatedly",
)

VALID_IR = SecurityIR(
    event_type=ASIMEventType.AUTHENTICATION,
    filters=[Filter(field="EventResult", operator=FilterOperator.EQ, value="Failure")],
    aggregation=Aggregation(function=AggregationFunction.COUNT, result_alias="FailCount"),
    group_by=["TargetUsername"],
    time_window="PT10M",
)


def test_build_failure_is_treated_as_repairable_not_a_crash():
    """A malformed-but-parseable LLM completion (OutputParserException) must
    not propagate as an uncaught exception — it should be retried via the
    structured-error repair path, same as a schema validation failure."""
    ir_builder = MagicMock()
    ir_builder.build.side_effect = OutputParserException("bad completion")

    result = run_with_repair(EXTRACTION, ASIM_SCHEMA, ir_builder, max_attempts=3)

    assert result.success is False
    assert result.reason == "MAX_REPAIR_ATTEMPTS_EXCEEDED"
    # 1 initial build + 1 per loop iteration (max_attempts=3) = 4 total calls
    assert ir_builder.build.call_count == 4


def test_recovers_after_build_failure_then_valid_ir():
    ir_builder = MagicMock()
    ir_builder.build.side_effect = [OutputParserException("bad completion"), VALID_IR]

    result = run_with_repair(EXTRACTION, ASIM_SCHEMA, ir_builder, max_attempts=3)

    assert result.success is True
    assert result.kql is not None
    assert ir_builder.build.call_count == 2


def test_repair_prompt_receives_the_parse_failure_message():
    ir_builder = MagicMock()
    ir_builder.build.side_effect = [OutputParserException("bad completion"), VALID_IR]

    run_with_repair(EXTRACTION, ASIM_SCHEMA, ir_builder, max_attempts=3)

    second_call_kwargs = ir_builder.build.call_args_list[1].kwargs
    assert second_call_kwargs["repair_error"].error_type == "LLM_OUTPUT_PARSE_FAILURE"
