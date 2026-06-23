import pytest
from pydantic import ValidationError

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
    Threshold,
    ThresholdOperator,
)


def test_minimal_ir_valid():
    ir = SecurityIR(event_type=ASIMEventType.AUTHENTICATION)
    assert ir.filters == []
    assert ir.aggregation is None
    assert ir.join is None


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


# --- New operator tests ---

def test_negated_operators_exist():
    """All negated/word-boundary operators must be accessible by name."""
    assert FilterOperator.NOT_CONTAINS.value == "!contains"
    assert FilterOperator.NOT_STARTSWITH.value == "!startswith"
    assert FilterOperator.NOT_ENDSWITH.value == "!endswith"
    assert FilterOperator.NOT_IN.value == "!in"
    assert FilterOperator.HAS.value == "has"
    assert FilterOperator.HAS_ANY.value == "has_any"
    assert FilterOperator.MATCHES_REGEX.value == "matches regex"


def test_filter_with_negated_operator_round_trips():
    f = Filter(field="ProcessCommandLine", operator=FilterOperator.NOT_CONTAINS, value="sdelete")
    data = f.model_dump()
    f2 = Filter(**data)
    assert f2.operator == FilterOperator.NOT_CONTAINS
    assert f2.value == "sdelete"


def test_filter_with_has_any_accepts_list():
    f = Filter(field="DnsQuery", operator=FilterOperator.HAS_ANY, value=["mining.com", "pool.org"])
    assert f.value == ["mining.com", "pool.org"]


# --- JoinStage tests ---

def test_join_kind_values():
    assert JoinKind.INNER.value == "inner"
    assert JoinKind.LEFTANTI.value == "leftanti"
    assert JoinKind.LEFTOUTER.value == "leftouter"


def test_join_stage_round_trip():
    js = JoinStage(
        alias="Baseline",
        event_type=ASIMEventType.DNS,
        filters=[Filter(field="DnsQuery", operator=FilterOperator.NOT_CONTAINS, value="internal.corp")],
        aggregation=Aggregation(function=AggregationFunction.DISTINCT_COUNT, field="DnsQuery", result_alias="BaselineCount"),
        group_by=["SrcIpAddr"],
        time_window="P14D",
        join_on=["SrcIpAddr"],
        join_kind=JoinKind.INNER,
    )
    data = js.model_dump()
    js2 = JoinStage(**data)
    assert js2.alias == "Baseline"
    assert js2.join_kind == JoinKind.INNER
    assert js2.join_on == ["SrcIpAddr"]
    assert len(js2.filters) == 1


def test_security_ir_with_join_round_trips():
    ir = SecurityIR(
        event_type=ASIMEventType.DNS,
        filters=[Filter(field="DnsQuery", operator=FilterOperator.HAS, value="mining")],
        aggregation=Aggregation(function=AggregationFunction.COUNT, result_alias="QueryCount"),
        group_by=["SrcIpAddr"],
        time_window="PT1H",
        join=JoinStage(
            alias="Baseline",
            event_type=ASIMEventType.DNS,
            aggregation=Aggregation(function=AggregationFunction.DISTINCT_COUNT, field="DnsQuery", result_alias="BaselineCount"),
            group_by=["SrcIpAddr"],
            time_window="P14D",
            join_on=["SrcIpAddr"],
            join_kind=JoinKind.INNER,
        ),
    )
    data = ir.model_dump()
    ir2 = SecurityIR(**data)
    assert ir2.join is not None
    assert ir2.join.alias == "Baseline"
    assert ir2.join.event_type == ASIMEventType.DNS


def test_join_stage_requires_at_least_one_join_on_key():
    with pytest.raises(ValidationError):
        JoinStage(
            event_type=ASIMEventType.DNS,
            join_on=[],
            join_kind=JoinKind.INNER,
        )


def test_backward_compat_ir_without_join():
    """Existing IRs without a join field must still serialize/deserialize cleanly."""
    ir = SecurityIR(
        event_type=ASIMEventType.AUTHENTICATION,
        filters=[Filter(field="EventResult", operator=FilterOperator.EQ, value="Failure")],
    )
    data = ir.model_dump()
    assert data.get("join") is None
    ir2 = SecurityIR(**data)
    assert ir2.join is None

