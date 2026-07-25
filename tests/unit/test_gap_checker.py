from src.clarification.gap_checker import find_gaps
from src.ir_engine.ir_schema import (
    ASIMEventType, Filter, FilterOperator, JoinKind, JoinStage, KqlPipeline, WhereStage,
)


def test_no_caveats_means_no_gaps():
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[WhereStage(filters=[Filter(field="EventResult", operator=FilterOperator.EQ, value="Failure")])],
    )
    assert find_gaps(ir) == []


def test_time_window_caveat_is_classified_and_gets_the_real_data_default():
    ir = KqlPipeline(
        source_table=ASIMEventType.DNS, stages=[],
        abstained=True,
        caveats=["no concrete time window was given, so no threshold filter was added"],
    )
    gaps = find_gaps(ir)
    assert len(gaps) == 1
    assert gaps[0].kind == "missing_time_window"
    assert gaps[0].default == "PT1H"
    assert "1 hour" in gaps[0].question


def test_threshold_caveat_is_classified_with_no_default():
    ir = KqlPipeline(
        source_table=ASIMEventType.NETWORK_SESSION, stages=[],
        abstained=True,
        caveats=["no concrete threshold number was given for the excessive connection count"],
    )
    gaps = find_gaps(ir)
    assert len(gaps) == 1
    assert gaps[0].kind == "missing_threshold"
    assert gaps[0].default is None


def test_generic_caveat_extracts_the_affected_field_when_mentioned():
    ir = KqlPipeline(
        source_table=ASIMEventType.WEB_SESSION, stages=[],
        abstained=True,
        caveats=["no concrete IoC values were given for the source IP check, so no filter on SrcIpAddr was added"],
    )
    gaps = find_gaps(ir)
    assert len(gaps) == 1
    assert gaps[0].kind == "missing_value"
    assert gaps[0].affected_field == "SrcIpAddr"


def test_multiple_caveats_produce_multiple_gaps_in_order():
    ir = KqlPipeline(
        source_table=ASIMEventType.PROCESS, stages=[],
        abstained=True,
        caveats=["first omission", "second omission"],
    )
    gaps = find_gaps(ir)
    assert [g.caveat_text for g in gaps] == ["first omission", "second omission"]


def test_caveats_inside_a_joins_right_pipeline_are_found_recursively():
    right = KqlPipeline(source_table=ASIMEventType.DNS, stages=[], abstained=True, caveats=["right side omission"])
    ir = KqlPipeline(
        source_table=ASIMEventType.NETWORK_SESSION,
        stages=[JoinStage(kind=JoinKind.INNER, right_pipeline=right, join_on=["SrcIpAddr"])],
    )
    gaps = find_gaps(ir)
    assert len(gaps) == 1
    assert gaps[0].caveat_text == "right side omission"
