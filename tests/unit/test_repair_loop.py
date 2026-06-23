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
    Threshold,
    ThresholdOperator,
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


def test_unmatched_likely_event_type_falls_back_to_full_union_not_empty_list():
    """ExtractionOutput.likely_event_type is free text (see its docstring) and
    routinely fails to match a schema key exactly (observed: 0/10 on a live
    sample). Falling back to [] would silently hand the IR Builder zero
    fields while the prompt still says "only use fields from this
    reference" — i.e. reproduce the No-Schema-Grounding ablation by
    accident. The fallback must be the union of every event type's fields,
    not an empty list."""
    schema = {
        "AuthenticationEvent": {"fields": ["EventResult", "TargetUsername"]},
        "DnsEvent": {"fields": ["DnsQuery", "SrcIpAddr"]},
    }
    extraction = ExtractionOutput(
        likely_event_type="Suspicious DNS Lookups for Currency Mining Pools",
        actors=["IP address"],
        action_description="performs DNS lookups to mining pools",
    )
    ir_builder = MagicMock()
    ir_builder.build.return_value = VALID_IR

    run_with_repair(extraction, schema, ir_builder, max_attempts=3)

    # ir_builder.build(extraction, asim_field_list, repair_error=..., previous_ir=...)
    first_call_args = ir_builder.build.call_args_list[0].args
    assert set(first_call_args[1]) == {
        "EventResult", "TargetUsername", "DnsQuery", "SrcIpAddr",
    }


INVALID_IR = SecurityIR(
    event_type=ASIMEventType.AUTHENTICATION,
    filters=[Filter(field="NotARealField", operator=FilterOperator.EQ, value="x")],
)


def test_temperature_escalation_only_fires_on_a_genuine_consecutive_repeat():
    """Found live: the escalation baseline (prev_fingerprint) used to be
    seeded from the pre-loop initial build, so the first loop iteration
    always compared that build's output to itself — trivially equal —
    escalating temperature on every repair sequence's first attempt
    regardless of whether a genuine repeat occurred. The first repair
    attempt must run at the model's default temperature (None override);
    escalation should only begin once two *consecutive* attempts actually
    agree."""
    ir_builder = MagicMock()
    ir_builder.build.return_value = INVALID_IR  # always identical output

    run_with_repair(EXTRACTION, ASIM_SCHEMA, ir_builder, max_attempts=3)

    overrides = [call.kwargs.get("temperature_override") for call in ir_builder.build.call_args_list]
    # call 0: initial build. call 1: first repair attempt -- must still be
    # at default temperature, since there's no *prior repair attempt* yet
    # to compare against. call 2: now a genuine repeat (attempt 1's output
    # == attempt 0's) is detected -- escalate. call 3: still repeating --
    # escalate further.
    assert overrides == [None, None, 0.3, 0.6]


def test_the_final_repair_attempts_own_output_is_actually_validated():
    """Found live: with max_attempts=3, the model produced 4 total builds
    (1 initial + 3 repairs) but only the first 3 were ever checked for
    validity -- the rebuild made on the *last* iteration was returned as
    MAX_REPAIR_ATTEMPTS_EXCEEDED without ever being validated, even when
    (as here) it was actually fully valid. Confirmed live on
    365a889c-...-original: a correct IR was discarded this way."""
    ir_builder = MagicMock()
    ir_builder.build.side_effect = [INVALID_IR, INVALID_IR, INVALID_IR, VALID_IR]

    result = run_with_repair(EXTRACTION, ASIM_SCHEMA, ir_builder, max_attempts=3)

    assert result.success is True
    assert result.kql is not None
    assert ir_builder.build.call_count == 4


def test_temperature_never_escalates_when_outputs_never_actually_repeat():
    ir_builder = MagicMock()
    ir_builder.build.side_effect = [
        SecurityIR(event_type=ASIMEventType.AUTHENTICATION, filters=[Filter(field=f"BadField{i}", operator=FilterOperator.EQ, value="x")])
        for i in range(1, 5)
    ]

    run_with_repair(EXTRACTION, ASIM_SCHEMA, ir_builder, max_attempts=3)

    overrides = [call.kwargs.get("temperature_override") for call in ir_builder.build.call_args_list]
    assert overrides == [None, None, None, None]


def test_run_with_repair_treats_threshold_mismatch_as_repairable():
    """End-to-end: a schema-valid IR whose threshold.value silently
    disagrees with the description's own threshold language must trigger
    a repair attempt, not a false success — schema validation alone would
    have accepted it."""
    extraction = ExtractionOutput(
        likely_event_type="AuthenticationEvent",
        actors=["account"],
        action_description="fails to log in repeatedly",
        threshold_language="more than 50 times",
    )
    bad_threshold_ir = SecurityIR(
        event_type=ASIMEventType.AUTHENTICATION,
        aggregation=Aggregation(function=AggregationFunction.COUNT, result_alias="FailCount"),
        group_by=["TargetUsername"],
        time_window="PT10M",
        threshold=Threshold(operator=ThresholdOperator.GT, value=1),
    )
    corrected_ir = bad_threshold_ir.model_copy(update={"threshold": bad_threshold_ir.threshold.model_copy(update={"value": 50})})

    ir_builder = MagicMock()
    ir_builder.build.side_effect = [bad_threshold_ir, corrected_ir]

    result = run_with_repair(extraction, ASIM_SCHEMA, ir_builder, max_attempts=3)

    assert result.success is True
    assert ir_builder.build.call_count == 2
    second_call_kwargs = ir_builder.build.call_args_list[1].kwargs
    assert second_call_kwargs["repair_error"].error_type == "THRESHOLD_VALUE_MISMATCH"
