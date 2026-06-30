from unittest.mock import MagicMock
from langchain_core.exceptions import OutputParserException
from src.ir_engine.ir_schema import (
    Aggregation, AggregationFunction, ASIMEventType, ExtractionOutput,
    Filter, FilterOperator, KqlPipeline, WhereStage, SummarizeStage
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

VALID_IR = KqlPipeline(
    source_table=ASIMEventType.AUTHENTICATION,
    stages=[
        WhereStage(filters=[Filter(field="EventResult", operator=FilterOperator.EQ, value="Failure")]),
        SummarizeStage(
            aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="FailCount")],
            group_by=["TargetUsername"],
            time_window="PT10M"
        )
    ]
)

INVALID_IR = KqlPipeline(
    source_table=ASIMEventType.AUTHENTICATION,
    stages=[
        WhereStage(filters=[Filter(field="NotARealField", operator=FilterOperator.EQ, value="x")])
    ]
)

def test_build_failure_is_treated_as_repairable_not_a_crash():
    ir_builder = MagicMock()
    ir_builder.build.side_effect = OutputParserException("bad completion")
    result = run_with_repair(EXTRACTION, ASIM_SCHEMA, ir_builder, max_attempts=3)
    assert result.success is False
    assert result.reason == "MAX_REPAIR_ATTEMPTS_EXCEEDED"
    assert ir_builder.build.call_count == 4

def test_recovers_after_build_failure_then_valid_ir():
    ir_builder = MagicMock()
    ir_builder.build.side_effect = [OutputParserException("bad completion"), VALID_IR]
    result = run_with_repair(EXTRACTION, ASIM_SCHEMA, ir_builder, max_attempts=3)
    assert result.success is True
    assert result.kql is not None
    assert ir_builder.build.call_count == 2

def test_temperature_escalation_only_fires_on_a_genuine_consecutive_repeat():
    ir_builder = MagicMock()
    ir_builder.build.return_value = INVALID_IR
    run_with_repair(EXTRACTION, ASIM_SCHEMA, ir_builder, max_attempts=3)
    overrides = [call.kwargs.get("temperature_override") for call in ir_builder.build.call_args_list]
    assert overrides == [None, None, 0.3, 0.6]

def test_unmatched_likely_event_type_falls_back_to_full_union_not_empty_list():
    schema = {
        "AuthenticationEvent": {"fields": ["EventResult", "TargetUsername"]},
        "DnsEvent": {"fields": ["DnsQuery", "SrcIpAddr"]},
    }
    extraction = ExtractionOutput(
        likely_event_type="Suspicious DNS Lookups",
        actors=["IP address"],
        action_description="performs DNS lookups",
    )
    ir_builder = MagicMock()
    ir_builder.build.return_value = VALID_IR
    run_with_repair(extraction, schema, ir_builder, max_attempts=3)
    first_call_args = ir_builder.build.call_args_list[0].args
    assert set(first_call_args[1]) == {"EventResult", "TargetUsername", "DnsQuery", "SrcIpAddr"}


def test_verifier_none_by_default_preserves_existing_behavior():
    """No verifier passed at all -> a schema-valid IR succeeds on attempt
    1, exactly as before this feature existed."""
    ir_builder = MagicMock()
    ir_builder.build.return_value = VALID_IR
    result = run_with_repair(EXTRACTION, ASIM_SCHEMA, ir_builder, max_attempts=3)
    assert result.success is True
    assert result.attempts_used == 1
    assert ir_builder.build.call_count == 1


def test_verifier_advisory_mode_is_the_default_and_never_blocks():
    """Measured live (PROJECT_STATUS.md §4Q): blocking on the verifier's
    verdict cost 20+ points of completion/FVR and 33 points of RRR on the
    full dataset, almost entirely on a pattern the verifier
    systematically misjudges. Advisory (the default) must surface the
    same critique as a warning without ever failing the case over it."""
    ir_builder = MagicMock()
    ir_builder.build.return_value = VALID_IR
    verifier = MagicMock()
    verifier.verify.return_value = MagicMock(matches_intent=False, issue="wrong comparison direction")
    result = run_with_repair(EXTRACTION, ASIM_SCHEMA, ir_builder, max_attempts=3, verifier=verifier)
    assert result.success is True
    assert result.attempts_used == 1
    assert ir_builder.build.call_count == 1
    assert any("wrong comparison direction" in w for w in result.warnings)


def test_verifier_blocking_mode_rejecting_a_schema_valid_ir_triggers_one_targeted_repair():
    ir_builder = MagicMock()
    ir_builder.build.return_value = VALID_IR
    verifier = MagicMock()
    verifier.verify.side_effect = [
        MagicMock(matches_intent=False, issue="wrong comparison direction", category="comparison_direction"),
        MagicMock(matches_intent=True, issue=""),
    ]
    result = run_with_repair(
        EXTRACTION, ASIM_SCHEMA, ir_builder, max_attempts=3, verifier=verifier, verifier_blocking=True
    )
    assert result.success is True
    assert ir_builder.build.call_count == 2
    repair_call_kwargs = ir_builder.build.call_args_list[1].kwargs
    assert repair_call_kwargs["repair_error"].error_type == "VERIFIER_COMPARISON_DIRECTION_INVERTED"
    assert "wrong comparison direction" in repair_call_kwargs["repair_error"].message


def test_verifier_accepting_immediately_does_not_change_attempt_count():
    ir_builder = MagicMock()
    ir_builder.build.return_value = VALID_IR
    verifier = MagicMock()
    verifier.verify.return_value = MagicMock(matches_intent=True, issue="")
    result = run_with_repair(EXTRACTION, ASIM_SCHEMA, ir_builder, max_attempts=3, verifier=verifier)
    assert result.success is True
    assert result.attempts_used == 1
    assert ir_builder.build.call_count == 1
    assert verifier.verify.call_count == 1


def test_verifier_blocking_mode_persistent_rejection_exhausts_repair_budget():
    ir_builder = MagicMock()
    ir_builder.build.return_value = VALID_IR
    verifier = MagicMock()
    verifier.verify.return_value = MagicMock(matches_intent=False, issue="always wrong")
    result = run_with_repair(
        EXTRACTION, ASIM_SCHEMA, ir_builder, max_attempts=2, verifier=verifier, verifier_blocking=True
    )
    assert result.success is False
    assert result.reason == "MAX_REPAIR_ATTEMPTS_EXCEEDED"
    assert ir_builder.build.call_count == 3


def test_selective_blocking_still_blocks_a_genuine_true_positive_critique():
    """A critique with no bin/join-boundary language (e.g. an AND/OR
    confusion, the 7b3ed03a-sop class of bug) must still block in
    blocking mode — only the one measured-unreliable category is
    excluded."""
    ir_builder = MagicMock()
    ir_builder.build.return_value = VALID_IR
    verifier = MagicMock()
    verifier.verify.side_effect = [
        MagicMock(matches_intent=False, issue="The query uses OR where the description needs AND between the two conditions.", category="other"),
        MagicMock(matches_intent=True, issue=""),
    ]
    result = run_with_repair(
        EXTRACTION, ASIM_SCHEMA, ir_builder, max_attempts=3, verifier=verifier, verifier_blocking=True
    )
    assert result.success is True
    assert ir_builder.build.call_count == 2
    repair_kwargs = ir_builder.build.call_args_list[1].kwargs
    assert repair_kwargs["repair_error"].error_type == "VERIFIER_SEMANTIC_MISMATCH"


def test_selective_blocking_does_not_block_the_known_bin_join_false_positive():
    """The one measured-unreliable critique category (PROJECT_STATUS.md
    §4Q) must never block, even in blocking mode — it must succeed
    immediately with a warning instead."""
    ir_builder = MagicMock()
    ir_builder.build.return_value = VALID_IR
    verifier = MagicMock()
    verifier.verify.return_value = MagicMock(
        matches_intent=False,
        issue="The query bins both sides to the same window before joining, which can miss a pair across a bin boundary.",
    )
    result = run_with_repair(
        EXTRACTION, ASIM_SCHEMA, ir_builder, max_attempts=3, verifier=verifier, verifier_blocking=True
    )
    assert result.success is True
    assert result.attempts_used == 1
    assert ir_builder.build.call_count == 1
    assert any("not blocking" in w for w in result.warnings)
