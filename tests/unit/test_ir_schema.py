import pytest
from pydantic import ValidationError

from src.ir_engine.ir_schema import (
    Aggregation, AggregationFunction, ASIMEventType, Filter, FilterGroup, FilterOperator, 
    JoinKind, JoinStage, KqlPipeline, WhereStage, SummarizeStage, ExtendStage, ProjectStage, TopStage
)

def test_minimal_ir_valid():
    ir = KqlPipeline(source_table=ASIMEventType.AUTHENTICATION)
    assert ir.stages == []

def test_pipeline_with_stages_round_trip():
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[
            WhereStage(filters=[Filter(field="EventResult", operator=FilterOperator.EQ, value="Failure")]),
            SummarizeStage(
                aggregations=[Aggregation(function=AggregationFunction.DISTINCT_COUNT, field="TargetUsername")],
                group_by=["SrcIpAddr"],
                time_window="PT5M"
            )
        ]
    )
    assert len(ir.stages) == 2
    assert isinstance(ir.stages[0], WhereStage)
    assert ir.stages[1].time_window == "PT5M"

def test_unknown_field_rejected():
    with pytest.raises(ValidationError):
        KqlPipeline(source_table=ASIMEventType.AUTHENTICATION, severity_score=5)

def test_negated_operators_exist():
    assert FilterOperator.NOT_CONTAINS.value == "!contains"
    assert FilterOperator.NOT_STARTSWITH.value == "!startswith"

def test_filter_field_ref_round_trip():
    """field_ref compares against ANOTHER COLUMN instead of a literal —
    added §4AA after finding the schema had no way to express "is this
    field's value between two other fields' values" (a real correlation
    pattern found via combination testing)."""
    f = Filter(field="ProcessTime", operator=FilterOperator.GTE, field_ref="FirstAuthTime")
    assert f.value is None
    assert f.field_ref == "FirstAuthTime"

def test_filter_rejects_both_value_and_field_ref():
    with pytest.raises(ValidationError):
        Filter(field="ProcessTime", operator=FilterOperator.GTE, value="x", field_ref="FirstAuthTime")

def test_filter_rejects_neither_value_nor_field_ref():
    with pytest.raises(ValidationError):
        Filter(field="ProcessTime", operator=FilterOperator.GTE)

def test_join_stage_round_trip():
    js = JoinStage(
        kind=JoinKind.INNER,
        right_pipeline=KqlPipeline(source_table=ASIMEventType.DNS),
        join_on=["SrcIpAddr"]
    )
    assert js.kind == JoinKind.INNER
    assert js.join_on == ["SrcIpAddr"]

def test_join_stage_requires_at_least_one_join_on_key():
    with pytest.raises(ValidationError):
        JoinStage(
            kind=JoinKind.INNER,
            right_pipeline=KqlPipeline(source_table=ASIMEventType.DNS),
            join_on=[]
        )
