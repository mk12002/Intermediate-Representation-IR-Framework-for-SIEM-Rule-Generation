"""Integration tests for run_with_repair() driving the REAL validator and
compiler (only the IR Builder Agent is stubbed) across the broken-then-
fixed sequences this project's live rounds actually hit. tests/unit/
test_repair_loop.py and test_constraint_traceability.py exercise these
checks individually with simple synthetic IRs; these tests instead chain
realistic multi-stage pipelines through validate_ir -> generate_kql ->
validate_kql_syntax exactly as run_with_repair does in production, to
catch the class of bug this project found repeatedly: a check that works
fine in isolation but misfires once real, complex IRs flow through the
whole loop together.
"""
from unittest.mock import MagicMock

from src.ir_engine.ir_schema import (
    Aggregation, AggregationFunction, ASIMEventType, ComputedField,
    ExtendStage, ExtractionOutput, Filter, FilterOperator, JoinKind,
    JoinStage, KqlPipeline, SummarizeStage, WhereStage,
)
from src.pipeline.repair_loop import run_with_repair

ASIM_SCHEMA = {
    "NetworkSessionEvent": {
        "fields": ["SrcIpAddr", "DstIpAddr", "SrcPortNumber", "DstPortNumber", "TimeGenerated"]
    },
    "ProcessEvent": {"fields": ["ActingProcessName", "ActingProcessCommandLine", "TimeGenerated"]},
}


def _baseline_vs_current_ir(threshold: float = 50) -> KqlPipeline:
    right = KqlPipeline(
        source_table=ASIMEventType.NETWORK_SESSION,
        stages=[
            SummarizeStage(
                aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="BaselineCount")],
                group_by=["SrcIpAddr"], time_window="P14D",
            ),
            ExtendStage(computed_fields=[ComputedField(alias="BaselineAvg", expression="BaselineCount / 14")]),
        ],
    )
    return KqlPipeline(
        source_table=ASIMEventType.NETWORK_SESSION,
        stages=[
            SummarizeStage(
                aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="CurrentCount")],
                group_by=["SrcIpAddr"], time_window="P1D",
            ),
            JoinStage(kind=JoinKind.INNER, right_pipeline=right, join_on=["SrcIpAddr"]),
            ExtendStage(computed_fields=[ComputedField(alias="Margin", expression="CurrentCount - BaselineAvg")]),
            WhereStage(filters=[Filter(field="Margin", operator=FilterOperator.GT, value=threshold)]),
        ],
    )


def test_baseline_vs_current_extend_threshold_is_not_falsely_rejected_on_first_attempt():
    """Regression test for the live false-positive found while tracing
    8717e498: a correct baseline-vs-current IR filtering an extend-derived
    'Margin' field was rejected as THRESHOLD_VALUE_MISMATCH because Margin
    isn't a raw SummarizeStage alias. The full loop (not just
    _check_constraint_traceability in isolation) must accept it first try."""
    extraction = ExtractionOutput(
        likely_event_type="NetworkSessionEvent",
        actors=["source"],
        action_description="connection count exceeds its 14-day baseline average by more than 50",
        threshold_language="more than 50",
    )
    ir_builder = MagicMock()
    ir_builder.build.return_value = _baseline_vs_current_ir(threshold=50)

    result = run_with_repair(extraction, ASIM_SCHEMA, ir_builder, max_attempts=3)

    assert result.success is True
    assert result.attempts_used == 1
    assert ir_builder.build.call_count == 1
    assert "Margin > 50" in result.kql


def test_drifted_threshold_on_an_extend_field_is_still_caught():
    """The widened check must not become so permissive it stops catching
    genuine drift — only the SET of acceptable field names grew, not the
    exact-value-match requirement."""
    extraction = ExtractionOutput(
        likely_event_type="NetworkSessionEvent",
        actors=["source"],
        action_description="connection count exceeds its 14-day baseline average by more than 50",
        threshold_language="more than 50",
    )
    drifted_then_fixed = [_baseline_vs_current_ir(threshold=1), _baseline_vs_current_ir(threshold=50)]
    ir_builder = MagicMock()
    ir_builder.build.side_effect = drifted_then_fixed

    result = run_with_repair(extraction, ASIM_SCHEMA, ir_builder, max_attempts=3)

    assert result.success is True
    assert ir_builder.build.call_count == 2
    assert "Margin > 50" in result.kql


def test_aggregate_function_in_extend_triggers_a_real_repair_then_succeeds():
    """A first attempt that misuses stdev() inside extend (invalid KQL)
    must be caught by the real validator and trigger exactly one repair
    call; the second, corrected attempt (stdev moved into summarize) must
    then succeed and compile."""
    broken = KqlPipeline(
        source_table=ASIMEventType.NETWORK_SESSION,
        stages=[
            SummarizeStage(
                aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="ConnCount")],
                group_by=["SrcIpAddr"], time_window="P1D",
            ),
            ExtendStage(computed_fields=[ComputedField(alias="Spread", expression="stdev(ConnCount)")]),
        ],
    )
    fixed = KqlPipeline(
        source_table=ASIMEventType.NETWORK_SESSION,
        stages=[
            SummarizeStage(
                aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="ConnCount")],
                group_by=["SrcIpAddr"], time_window="P1D",
            ),
            SummarizeStage(
                aggregations=[Aggregation(function=AggregationFunction.STDEV, field="ConnCount", result_alias="Spread")],
                time_window="P1D",
            ),
        ],
    )
    extraction = ExtractionOutput(
        likely_event_type="NetworkSessionEvent", actors=["source"],
        action_description="connection count spread per source",
    )
    ir_builder = MagicMock()
    ir_builder.build.side_effect = [broken, fixed]

    result = run_with_repair(extraction, ASIM_SCHEMA, ir_builder, max_attempts=3)

    assert result.success is True
    assert ir_builder.build.call_count == 2
    repair_call_kwargs = ir_builder.build.call_args_list[1].kwargs
    assert repair_call_kwargs["repair_error"].error_type == "AGGREGATE_FUNCTION_IN_EXTEND"


def test_every_attempt_including_the_last_is_validated_not_just_rebuilt():
    """Regression test for the repair-loop off-by-one (PROJECT_STATUS.md
    §4I): with max_attempts=2, a sequence of 2 broken IRs followed by a
    valid one on the 3rd build must succeed, not be discarded — the loop
    must validate every build it makes, including the final one."""
    valid = _baseline_vs_current_ir(threshold=50)
    invalid = KqlPipeline(
        source_table=ASIMEventType.NETWORK_SESSION,
        stages=[WhereStage(filters=[Filter(field="NotARealField", operator=FilterOperator.EQ, value="x")])],
    )
    extraction = ExtractionOutput(
        likely_event_type="NetworkSessionEvent", actors=["source"],
        action_description="baseline comparison",
    )
    ir_builder = MagicMock()
    ir_builder.build.side_effect = [invalid, invalid, valid]

    result = run_with_repair(extraction, ASIM_SCHEMA, ir_builder, max_attempts=2)

    assert result.success is True
    assert ir_builder.build.call_count == 3
