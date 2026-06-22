from src.ir_engine.ir_schema import (
    Aggregation,
    AggregationFunction,
    ASIMEventType,
    Filter,
    FilterOperator,
    SecurityIR,
)
from src.ir_engine.ir_validator import validate_ir

ASIM_SCHEMA = {
    "AuthenticationEvent": {"fields": ["EventResult", "TargetUsername", "SrcIpAddr", "TimeGenerated"]},
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


def test_threshold_without_aggregation_warns_but_passes():
    from src.ir_engine.ir_schema import Threshold, ThresholdOperator

    ir = SecurityIR(
        event_type=ASIMEventType.AUTHENTICATION,
        threshold=Threshold(operator=ThresholdOperator.GT, value=15),
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert result.passed
    assert result.warnings
