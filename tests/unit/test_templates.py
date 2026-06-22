from src.generator.compiler import generate_kql
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


def test_simple_ir_filters_only():
    ir = SecurityIR(
        event_type=ASIMEventType.AUTHENTICATION,
        filters=[Filter(field="EventResult", operator=FilterOperator.EQ, value="Failure")],
    )
    kql = generate_kql(ir)
    assert kql.startswith("imAuthentication")
    assert 'where EventResult == "Failure"' in kql
    assert "summarize" not in kql


def test_moderate_ir_aggregation_threshold_time_window():
    ir = SecurityIR(
        event_type=ASIMEventType.AUTHENTICATION,
        filters=[Filter(field="EventResult", operator=FilterOperator.EQ, value="Failure")],
        aggregation=Aggregation(function=AggregationFunction.COUNT, result_alias="FailCount"),
        group_by=["TargetUsername"],
        threshold=Threshold(operator=ThresholdOperator.GT, value=15),
        time_window="PT10M",
    )
    kql = generate_kql(ir)
    assert "summarize FailCount = count()" in kql
    assert "by TargetUsername, bin(TimeGenerated, 10m)" in kql
    assert "where FailCount > 15" in kql


def test_output_fields_projected():
    ir = SecurityIR(
        event_type=ASIMEventType.NETWORK_SESSION,
        output_fields=["SrcIpAddr", "DstIpAddr"],
    )
    kql = generate_kql(ir)
    assert "project SrcIpAddr, DstIpAddr" in kql
    assert kql.startswith("imNetworkSession")


def test_distinct_count_renders_dcount():
    ir = SecurityIR(
        event_type=ASIMEventType.AUTHENTICATION,
        aggregation=Aggregation(
            function=AggregationFunction.DISTINCT_COUNT, field="TargetUsername", result_alias="DistinctUsers"
        ),
        group_by=["SrcIpAddr"],
        time_window="PT5M",
    )
    kql = generate_kql(ir)
    assert "dcount(TargetUsername)" in kql
