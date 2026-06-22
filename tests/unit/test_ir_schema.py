import pytest
from pydantic import ValidationError

from src.ir_engine.ir_schema import (
    Aggregation,
    AggregationFunction,
    ASIMEventType,
    Filter,
    FilterOperator,
    SecurityIR,
    Threshold,
    ThresholdOperator,
)


def test_minimal_ir_valid():
    ir = SecurityIR(event_type=ASIMEventType.AUTHENTICATION)
    assert ir.filters == []
    assert ir.aggregation is None


def test_filters_and_aggregation_round_trip():
    ir = SecurityIR(
        event_type=ASIMEventType.AUTHENTICATION,
        filters=[Filter(field="EventResult", operator=FilterOperator.EQ, value="Failure")],
        aggregation=Aggregation(function=AggregationFunction.DISTINCT_COUNT, field="TargetUsername"),
        group_by=["SrcIpAddr"],
        threshold=Threshold(operator=ThresholdOperator.GT, value=20),
        time_window="PT5M",
    )
    assert ir.aggregation.function == AggregationFunction.DISTINCT_COUNT
    assert ir.time_window == "PT5M"


def test_unknown_field_rejected():
    with pytest.raises(ValidationError):
        SecurityIR(event_type=ASIMEventType.AUTHENTICATION, severity_score=5)


def test_invalid_event_type_rejected():
    with pytest.raises(ValidationError):
        SecurityIR(event_type="NotARealEventType")
