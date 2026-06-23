from src.ir_engine.ir_schema import (
    Aggregation,
    AggregationFunction,
    ASIMEventType,
    Filter,
    FilterGroup,
    FilterOperator,
    JoinKind,
    JoinStage,
    SecurityIR,
)
from src.ir_engine.ir_validator import validate_ir

ASIM_SCHEMA = {
    "AuthenticationEvent": {"fields": ["EventResult", "TargetUsername", "SrcIpAddr", "TimeGenerated"]},
    "DnsEvent": {"fields": ["DnsQuery", "SrcIpAddr", "DnsResponseName", "TimeGenerated"]},
    "NetworkSessionEvent": {"fields": ["SrcIpAddr", "DstIpAddr", "DstPortNumber", "TimeGenerated"]},
}


def test_valid_ir_passes():
    ir = SecurityIR(
        event_type=ASIMEventType.AUTHENTICATION,
        filters=[Filter(field="EventResult", operator=FilterOperator.EQ, value="Failure")],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert result.passed


def test_field_not_found():
    ir = SecurityIR(
        event_type=ASIMEventType.AUTHENTICATION,
        filters=[Filter(field="SourceIP", operator=FilterOperator.EQ, value="x")],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "FIELD_NOT_FOUND"
    assert "SrcIpAddr" in result.message  # closest_match suggestion


def test_output_fields_are_validated_too():
    """Found live: output_fields was never checked against the schema, so a
    hallucinated "| project" field (e.g. "ParentProcessCommandLine" on an
    event type that doesn't have it) passed IR validation and was only
    caught downstream by eval/metrics.py's text-level FVR check —
    undercounting FVR for queries whose filters/group_by were correct."""
    ir = SecurityIR(
        event_type=ASIMEventType.AUTHENTICATION,
        filters=[Filter(field="EventResult", operator=FilterOperator.EQ, value="Failure")],
        output_fields=["EventResult", "NotARealField"],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "FIELD_NOT_FOUND"
    assert "NotARealField" in result.message


def test_output_fields_may_reference_the_aggregations_own_alias():
    """Found live (real model call): a query projecting its own aggregation
    alias -- "| summarize FailCount = count() by X | project X, FailCount",
    completely standard KQL -- was rejected as FIELD_NOT_FOUND because the
    output_fields check above didn't know aggregation.result_alias is a
    legitimate self-defined column, not a schema field."""
    ir = SecurityIR(
        event_type=ASIMEventType.AUTHENTICATION,
        aggregation=Aggregation(function=AggregationFunction.COUNT, result_alias="FailCount"),
        group_by=["TargetUsername"],
        time_window="PT1H",
        output_fields=["TargetUsername", "FailCount"],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert result.passed


def test_output_fields_may_reference_the_join_aggregations_alias():
    schema = {
        "DnsEvent": {"fields": ["DnsQuery", "SrcIpAddr", "TimeGenerated"]},
    }
    ir = SecurityIR(
        event_type=ASIMEventType.DNS,
        aggregation=Aggregation(function=AggregationFunction.COUNT, result_alias="CurrentCount"),
        group_by=["SrcIpAddr"],
        time_window="PT1H",
        output_fields=["SrcIpAddr", "CurrentCount", "BaselineAvg"],
        join=JoinStage(
            alias="Baseline",
            event_type=ASIMEventType.DNS,
            aggregation=Aggregation(function=AggregationFunction.AVG, field="SrcIpAddr", result_alias="BaselineAvg"),
            group_by=["SrcIpAddr"],
            time_window="P14D",
            join_on=["SrcIpAddr"],
            join_kind=JoinKind.INNER,
        ),
    )
    result = validate_ir(ir, schema)
    assert result.passed


def test_filter_group_with_valid_fields_passes():
    ir = SecurityIR(
        event_type=ASIMEventType.AUTHENTICATION,
        filters=[
            FilterGroup(
                conditions=[
                    Filter(field="TargetUsername", operator=FilterOperator.CONTAINS, value="admin"),
                    Filter(field="TargetUsername", operator=FilterOperator.CONTAINS, value="root"),
                ]
            )
        ],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert result.passed


def test_filter_group_with_bad_field_is_caught():
    """A field inside a FilterGroup's conditions must be checked the same
    way as a top-level Filter's field — this was the easy way to silently
    skip validation when adding the group construct."""
    ir = SecurityIR(
        event_type=ASIMEventType.AUTHENTICATION,
        filters=[
            FilterGroup(
                conditions=[
                    Filter(field="TargetUsername", operator=FilterOperator.CONTAINS, value="admin"),
                    Filter(field="NotARealField", operator=FilterOperator.CONTAINS, value="root"),
                ]
            )
        ],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "FIELD_NOT_FOUND"
    assert "NotARealField" in result.message


def test_group_by_field_not_found():
    ir = SecurityIR(event_type=ASIMEventType.AUTHENTICATION, group_by=["BadField"])
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "FIELD_NOT_FOUND"


def test_missing_time_window_with_aggregation():
    ir = SecurityIR(
        event_type=ASIMEventType.AUTHENTICATION,
        aggregation=Aggregation(function=AggregationFunction.COUNT),
        group_by=["TargetUsername"],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "MISSING_TIME_WINDOW"


def test_aggregation_with_time_window_passes():
    ir = SecurityIR(
        event_type=ASIMEventType.AUTHENTICATION,
        aggregation=Aggregation(function=AggregationFunction.COUNT),
        group_by=["TargetUsername"],
        time_window="PT10M",
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert result.passed


def test_invalid_time_window_format_rejected():
    ir = SecurityIR(
        event_type=ASIMEventType.AUTHENTICATION,
        aggregation=Aggregation(function=AggregationFunction.COUNT),
        group_by=["TargetUsername"],
        time_window="within ten minutes",
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "INVALID_TIME_WINDOW"


def test_degenerate_count_threshold_is_a_hard_error():
    """Observed live: 'DistinctUserAgents > 1' / 'ErrorCount >= 1' passed
    validation while filtering zero rows, since count()/dcount() can never
    be < 1 for a group that exists in the result at all."""
    from src.ir_engine.ir_schema import Threshold, ThresholdOperator

    ir = SecurityIR(
        event_type=ASIMEventType.AUTHENTICATION,
        aggregation=Aggregation(function=AggregationFunction.COUNT, result_alias="ErrorCount"),
        threshold=Threshold(operator=ThresholdOperator.GTE, value=1),
        time_window="PT1H",
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "DEGENERATE_THRESHOLD"


def test_non_degenerate_count_threshold_passes():
    from src.ir_engine.ir_schema import Threshold, ThresholdOperator

    ir = SecurityIR(
        event_type=ASIMEventType.AUTHENTICATION,
        aggregation=Aggregation(function=AggregationFunction.COUNT, result_alias="ErrorCount"),
        threshold=Threshold(operator=ThresholdOperator.GT, value=15),
        time_window="PT1H",
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert result.passed


def test_threshold_without_aggregation_is_a_hard_error():
    """Promoted from a soft warning: the compiler has no left-hand side to
    render the threshold against without an aggregation result, so this
    must block (and trigger repair) rather than pass through to dead KQL
    like "| where  > 1"."""
    from src.ir_engine.ir_schema import Threshold, ThresholdOperator

    ir = SecurityIR(
        event_type=ASIMEventType.AUTHENTICATION,
        threshold=Threshold(operator=ThresholdOperator.GT, value=15),
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "THRESHOLD_WITHOUT_AGGREGATION"


# --- New: aggregation.field validation ---

def test_aggregation_field_validated_against_schema():
    """dcount(FakeField) must be caught — was missing before."""
    ir = SecurityIR(
        event_type=ASIMEventType.AUTHENTICATION,
        aggregation=Aggregation(
            function=AggregationFunction.DISTINCT_COUNT,
            field="FakeField",
            result_alias="DC",
        ),
        time_window="PT1H",
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "FIELD_NOT_FOUND"
    assert "FakeField" in result.message


def test_aggregation_with_valid_field_passes():
    ir = SecurityIR(
        event_type=ASIMEventType.AUTHENTICATION,
        aggregation=Aggregation(
            function=AggregationFunction.DISTINCT_COUNT,
            field="TargetUsername",
            result_alias="DC",
        ),
        group_by=["SrcIpAddr"],
        time_window="PT1H",
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert result.passed


def test_aggregation_count_no_field_passes():
    """count() has no field — should not require one."""
    ir = SecurityIR(
        event_type=ASIMEventType.AUTHENTICATION,
        aggregation=Aggregation(function=AggregationFunction.COUNT, result_alias="C"),
        time_window="PT1H",
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert result.passed


def test_avg_with_no_field_is_a_hard_error():
    """Found live: a baseline-comparison query rendered
    "summarize BaselineCount = avg()" with the field left null — only
    count() takes zero arguments in KQL; sum/avg/min/max/dcount all need one."""
    ir = SecurityIR(
        event_type=ASIMEventType.AUTHENTICATION,
        aggregation=Aggregation(function=AggregationFunction.AVG, field=None, result_alias="C"),
        time_window="PT1H",
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "AGGREGATION_MISSING_FIELD"


def test_join_stage_avg_with_no_field_is_a_hard_error():
    ir = SecurityIR(
        event_type=ASIMEventType.DNS,
        join=JoinStage(
            event_type=ASIMEventType.DNS,
            aggregation=Aggregation(function=AggregationFunction.AVG, field=None),
            time_window="P14D",
            join_on=["SrcIpAddr"],
        ),
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "AGGREGATION_MISSING_FIELD"


def test_percentile_with_no_field_is_a_hard_error():
    """percentile() needs a field same as avg/sum/min/max/dcount."""
    ir = SecurityIR(
        event_type=ASIMEventType.AUTHENTICATION,
        aggregation=Aggregation(function=AggregationFunction.PERCENTILE, field=None, percentile=95, result_alias="P95"),
        time_window="PT1H",
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "AGGREGATION_MISSING_FIELD"


def test_percentile_with_missing_percentile_value_is_a_hard_error():
    """Found live: the model substituted min() for "5th percentile of
    frequency" rather than express the percentile itself — this check
    exists so the field this function actually needs isn't silently null."""
    ir = SecurityIR(
        event_type=ASIMEventType.AUTHENTICATION,
        aggregation=Aggregation(function=AggregationFunction.PERCENTILE, field="EventResult", percentile=None, result_alias="P95"),
        time_window="PT1H",
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "INVALID_PERCENTILE_VALUE"


def test_percentile_value_out_of_range_is_a_hard_error():
    ir = SecurityIR(
        event_type=ASIMEventType.AUTHENTICATION,
        aggregation=Aggregation(function=AggregationFunction.PERCENTILE, field="EventResult", percentile=150, result_alias="P95"),
        time_window="PT1H",
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "INVALID_PERCENTILE_VALUE"


def test_percentile_with_valid_field_and_value_passes():
    ir = SecurityIR(
        event_type=ASIMEventType.AUTHENTICATION,
        aggregation=Aggregation(function=AggregationFunction.PERCENTILE, field="EventResult", percentile=95, result_alias="P95"),
        time_window="PT1H",
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert result.passed


def test_join_stage_percentile_with_missing_value_is_a_hard_error():
    ir = SecurityIR(
        event_type=ASIMEventType.DNS,
        join=JoinStage(
            event_type=ASIMEventType.DNS,
            aggregation=Aggregation(function=AggregationFunction.PERCENTILE, field="DnsResponseName", percentile=None),
            time_window="P14D",
            join_on=["SrcIpAddr"],
        ),
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "INVALID_PERCENTILE_VALUE"


# --- additional_aggregations: most real ASIM rules compute several
# summarize columns together (count + evidence + timestamps), not one ---

def test_additional_aggregations_with_valid_fields_passes():
    ir = SecurityIR(
        event_type=ASIMEventType.AUTHENTICATION,
        aggregation=Aggregation(function=AggregationFunction.COUNT, result_alias="FailCount"),
        additional_aggregations=[
            Aggregation(function=AggregationFunction.MAKE_SET, field="SrcIpAddr", result_alias="SourceIps", limit=100),
            Aggregation(function=AggregationFunction.MIN, field="TimeGenerated", result_alias="EventStartTime"),
        ],
        time_window="PT1H",
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert result.passed


def test_additional_aggregation_bad_field_is_field_not_found():
    ir = SecurityIR(
        event_type=ASIMEventType.AUTHENTICATION,
        aggregation=Aggregation(function=AggregationFunction.COUNT, result_alias="FailCount"),
        additional_aggregations=[
            Aggregation(function=AggregationFunction.MAKE_SET, field="NotARealField", result_alias="Evidence"),
        ],
        time_window="PT1H",
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "FIELD_NOT_FOUND"


def test_make_list_with_no_field_is_a_hard_error():
    ir = SecurityIR(
        event_type=ASIMEventType.AUTHENTICATION,
        aggregation=Aggregation(function=AggregationFunction.COUNT, result_alias="FailCount"),
        additional_aggregations=[
            Aggregation(function=AggregationFunction.MAKE_LIST, field=None, result_alias="Evidence"),
        ],
        time_window="PT1H",
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "AGGREGATION_MISSING_FIELD"


def test_additional_aggregations_without_main_aggregation_is_a_hard_error():
    ir = SecurityIR(
        event_type=ASIMEventType.AUTHENTICATION,
        additional_aggregations=[
            Aggregation(function=AggregationFunction.COUNT, result_alias="FailCount"),
        ],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "ADDITIONAL_AGGREGATIONS_WITHOUT_AGGREGATION"


def test_duplicate_result_alias_across_aggregations_is_a_hard_error():
    ir = SecurityIR(
        event_type=ASIMEventType.AUTHENTICATION,
        aggregation=Aggregation(function=AggregationFunction.COUNT, result_alias="X"),
        additional_aggregations=[
            Aggregation(function=AggregationFunction.MIN, field="TimeGenerated", result_alias="X"),
        ],
        time_window="PT1H",
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "DUPLICATE_AGGREGATION_ALIAS"


def test_join_stage_additional_aggregations_validated():
    ir = SecurityIR(
        event_type=ASIMEventType.DNS,
        join=JoinStage(
            event_type=ASIMEventType.DNS,
            aggregation=Aggregation(function=AggregationFunction.COUNT, result_alias="Count"),
            additional_aggregations=[
                Aggregation(function=AggregationFunction.MAKE_SET, field="NotARealField", result_alias="Evidence"),
            ],
            time_window="P14D",
            join_on=["SrcIpAddr"],
        ),
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "FIELD_NOT_FOUND"


# --- New: time_window without aggregation ---

def test_time_window_without_aggregation_is_error():
    """time_window set but aggregation is None — bin(TimeGenerated, ...)
    requires a summarize clause to attach to."""
    ir = SecurityIR(
        event_type=ASIMEventType.AUTHENTICATION,
        time_window="PT5M",
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "TIME_WINDOW_WITHOUT_AGGREGATION"


# --- New: JoinStage validation ---

def test_valid_join_stage_passes():
    ir = SecurityIR(
        event_type=ASIMEventType.DNS,
        filters=[Filter(field="DnsQuery", operator=FilterOperator.HAS, value="mining")],
        aggregation=Aggregation(function=AggregationFunction.COUNT, result_alias="C"),
        group_by=["SrcIpAddr"],
        time_window="PT1H",
        join=JoinStage(
            alias="Baseline",
            event_type=ASIMEventType.DNS,
            aggregation=Aggregation(
                function=AggregationFunction.DISTINCT_COUNT,
                field="DnsQuery",
                result_alias="BC",
            ),
            group_by=["SrcIpAddr"],
            time_window="P14D",
            join_on=["SrcIpAddr"],
            join_kind=JoinKind.INNER,
        ),
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert result.passed


def test_join_stage_bad_filter_field():
    ir = SecurityIR(
        event_type=ASIMEventType.DNS,
        join=JoinStage(
            event_type=ASIMEventType.DNS,
            filters=[Filter(field="FakeField", operator=FilterOperator.EQ, value="x")],
            join_on=["SrcIpAddr"],
        ),
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "FIELD_NOT_FOUND"
    assert "FakeField" in result.message


def test_join_stage_bad_group_by_field():
    ir = SecurityIR(
        event_type=ASIMEventType.DNS,
        join=JoinStage(
            event_type=ASIMEventType.DNS,
            group_by=["NotAField"],
            join_on=["SrcIpAddr"],
        ),
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "FIELD_NOT_FOUND"
    assert "NotAField" in result.message


def test_join_stage_bad_aggregation_field():
    ir = SecurityIR(
        event_type=ASIMEventType.DNS,
        join=JoinStage(
            event_type=ASIMEventType.DNS,
            aggregation=Aggregation(
                function=AggregationFunction.DISTINCT_COUNT,
                field="HallucinatedField",
            ),
            join_on=["SrcIpAddr"],
            time_window="PT1H",
        ),
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "FIELD_NOT_FOUND"
    assert "HallucinatedField" in result.message


def test_join_stage_aggregation_without_time_window_is_a_hard_error():
    """Mirrors the main IR's MISSING_TIME_WINDOW check, which the join
    stage never got when it was added — found live: a JoinStage with an
    aggregation and time_window=None passed validation, meaning the join
    subquery's summarize would scan the entire table with no time bound."""
    ir = SecurityIR(
        event_type=ASIMEventType.DNS,
        join=JoinStage(
            event_type=ASIMEventType.DNS,
            aggregation=Aggregation(function=AggregationFunction.DISTINCT_COUNT, field="DnsQuery"),
            group_by=["SrcIpAddr"],
            time_window=None,
            join_on=["SrcIpAddr"],
        ),
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "MISSING_TIME_WINDOW"


def test_join_on_key_not_in_main_schema():
    ir = SecurityIR(
        event_type=ASIMEventType.AUTHENTICATION,
        join=JoinStage(
            event_type=ASIMEventType.DNS,
            join_on=["DnsQuery"],  # exists in DNS but not in Auth
        ),
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "FIELD_NOT_FOUND"
    assert "DnsQuery" in result.message
    assert "main schema" in result.message


def test_join_on_key_not_in_join_schema():
    ir = SecurityIR(
        event_type=ASIMEventType.DNS,
        join=JoinStage(
            event_type=ASIMEventType.AUTHENTICATION,
            join_on=["DnsQuery"],  # exists in DNS but not in Auth
        ),
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "FIELD_NOT_FOUND"
    assert "DnsQuery" in result.message
    assert "join schema" in result.message


def test_join_on_key_valid_in_both_schemas():
    """SrcIpAddr exists in both Auth and DNS schemas — should pass."""
    ir = SecurityIR(
        event_type=ASIMEventType.AUTHENTICATION,
        join=JoinStage(
            event_type=ASIMEventType.DNS,
            join_on=["SrcIpAddr"],
        ),
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert result.passed


def test_join_stage_invalid_time_window_format():
    ir = SecurityIR(
        event_type=ASIMEventType.DNS,
        join=JoinStage(
            event_type=ASIMEventType.DNS,
            time_window="two weeks",
            join_on=["SrcIpAddr"],
        ),
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "INVALID_TIME_WINDOW"


# --- Threshold vs. joined column (baseline-vs-current) ---

def test_threshold_compare_to_join_field_requires_a_join_aggregation():
    """Found live: a join correctly computed a baseline average, but the
    threshold compared the current count to a bare literal — the baseline
    was projected for display but never actually gated the alert, because
    the IR had no way to express "compare to the joined column" at all."""
    from src.ir_engine.ir_schema import Threshold, ThresholdOperator

    ir = SecurityIR(
        event_type=ASIMEventType.DNS,
        aggregation=Aggregation(function=AggregationFunction.COUNT, result_alias="CurrentCount"),
        threshold=Threshold(operator=ThresholdOperator.GT, value=50, compare_to_join_field="BaselineAvg"),
        time_window="PT1H",
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "INVALID_THRESHOLD_JOIN_REFERENCE"


def test_threshold_compare_to_join_field_must_match_join_alias():
    from src.ir_engine.ir_schema import Threshold, ThresholdOperator

    ir = SecurityIR(
        event_type=ASIMEventType.DNS,
        aggregation=Aggregation(function=AggregationFunction.COUNT, result_alias="CurrentCount"),
        threshold=Threshold(operator=ThresholdOperator.GT, value=50, compare_to_join_field="WrongName"),
        time_window="PT1H",
        join=JoinStage(
            event_type=ASIMEventType.DNS,
            aggregation=Aggregation(function=AggregationFunction.AVG, field="SrcIpAddr", result_alias="BaselineAvg"),
            time_window="P14D",
            join_on=["SrcIpAddr"],
        ),
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "INVALID_THRESHOLD_JOIN_REFERENCE"


def test_threshold_compare_to_join_field_passes_when_matched():
    from src.ir_engine.ir_schema import Threshold, ThresholdOperator

    ir = SecurityIR(
        event_type=ASIMEventType.DNS,
        aggregation=Aggregation(function=AggregationFunction.COUNT, result_alias="CurrentCount"),
        threshold=Threshold(operator=ThresholdOperator.GT, value=50, compare_to_join_field="BaselineAvg"),
        time_window="PT1H",
        join=JoinStage(
            event_type=ASIMEventType.DNS,
            aggregation=Aggregation(function=AggregationFunction.AVG, field="SrcIpAddr", result_alias="BaselineAvg"),
            time_window="P14D",
            join_on=["SrcIpAddr"],
        ),
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert result.passed

