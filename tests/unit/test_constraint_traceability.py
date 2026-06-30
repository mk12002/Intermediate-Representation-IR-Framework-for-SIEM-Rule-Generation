from src.ir_engine.ir_schema import (
    ASIMEventType, ExtractionOutput, KqlPipeline, FilterOperator, Filter,
    WhereStage, SummarizeStage, Aggregation, AggregationFunction, JoinStage, JoinKind, TopStage,
)
from src.pipeline.repair_loop import _check_constraint_traceability, _extract_unambiguous_number

def _extraction(threshold_language):
    return ExtractionOutput(
        likely_event_type="WebSessionEvent",
        actors=["source"],
        action_description="generates many requests",
        threshold_language=threshold_language,
    )

def _ir(value):
    return KqlPipeline(
        source_table=ASIMEventType.WEB_SESSION,
        stages=[
            WhereStage(filters=[Filter(field="CurrentCount", operator=FilterOperator.GT, value=value)])
        ]
    )

def test_extract_unambiguous_number_single():
    assert _extract_unambiguous_number("more than 50 connections") == 50.0

def test_extract_unambiguous_number_none_when_absent():
    assert _extract_unambiguous_number("many connections") is None
    assert _extract_unambiguous_number(None) is None

def test_extract_unambiguous_number_none_when_multiple():
    assert _extract_unambiguous_number("more than 50 connections over 14 days") is None

def test_constraint_check_flags_a_real_mismatch():
    result = _check_constraint_traceability(_extraction("more than 50 connections"), _ir(1))
    assert not result.passed
    assert result.error_type == "THRESHOLD_VALUE_MISMATCH"
    assert "50" in result.message

def test_constraint_check_passes_when_values_agree():
    result = _check_constraint_traceability(_extraction("more than 50 connections"), _ir(50))
    assert result is None

def test_constraint_check_skipped_when_threshold_language_is_ambiguous():
    result = _check_constraint_traceability(_extraction("more than 50 connections over 14 days"), _ir(1))
    assert result is None

def test_constraint_check_skipped_when_no_threshold_language():
    result = _check_constraint_traceability(_extraction(None), _ir(50))
    assert result is None

def test_constraint_check_skipped_when_ir_has_no_threshold():
    ir = KqlPipeline(source_table=ASIMEventType.WEB_SESSION, stages=[])
    result = _check_constraint_traceability(_extraction("more than 50 connections"), ir)
    assert not result.passed
    assert result.error_type == "THRESHOLD_VALUE_MISMATCH"


# --- Hardening added during the AST migration: must anchor on an
# aggregation alias when one exists, not any filter in the pipeline ---

def test_unrelated_filter_sharing_the_number_does_not_count_as_a_match():
    """A coincidental match on an unrelated filter (e.g. a join's constant
    key, or a filter on a completely different field) must not satisfy
    the check — only a filter on the aggregation's own result_alias
    should count once a real aggregation exists in the pipeline."""
    ir = KqlPipeline(
        source_table=ASIMEventType.WEB_SESSION,
        stages=[
            SummarizeStage(
                aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="RequestCount")],
                time_window="PT1H",
            ),
            WhereStage(filters=[Filter(field="SomeUnrelatedField", operator=FilterOperator.EQ, value=50)]),
            WhereStage(filters=[Filter(field="RequestCount", operator=FilterOperator.GT, value=1)]),
        ],
    )
    result = _check_constraint_traceability(_extraction("more than 50 connections"), ir)
    assert not result.passed
    assert result.error_type == "THRESHOLD_VALUE_MISMATCH"


def test_filter_on_the_aggregation_alias_matching_the_number_passes():
    ir = KqlPipeline(
        source_table=ASIMEventType.WEB_SESSION,
        stages=[
            SummarizeStage(
                aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="RequestCount")],
                time_window="PT1H",
            ),
            WhereStage(filters=[Filter(field="RequestCount", operator=FilterOperator.GT, value=50)]),
        ],
    )
    result = _check_constraint_traceability(_extraction("more than 50 connections"), ir)
    assert result is None


def test_aggregation_alias_inside_a_join_right_pipeline_is_tracked():
    ir = KqlPipeline(
        source_table=ASIMEventType.WEB_SESSION,
        stages=[
            JoinStage(
                kind=JoinKind.INNER,
                join_on=["SrcIpAddr"],
                right_pipeline=KqlPipeline(
                    source_table=ASIMEventType.WEB_SESSION,
                    stages=[
                        SummarizeStage(
                            aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="BaselineCount")],
                            time_window="P14D",
                        ),
                    ],
                ),
            ),
            WhereStage(filters=[Filter(field="BaselineCount", operator=FilterOperator.GT, value=50)]),
        ],
    )
    result = _check_constraint_traceability(_extraction("more than 50 connections"), ir)
    assert result is None


def test_top_n_ranking_limit_satisfies_the_check_not_a_where_filter():
    """Found live: "top 25 noisiest clients" correctly compiles to
    TopStage(limit=25, ...), not a WhereStage filter — the check was
    flagging this as a false THRESHOLD_VALUE_MISMATCH and forcing an
    unnecessary, actively harmful repair cycle on an already-correct IR."""
    ir = KqlPipeline(
        source_table=ASIMEventType.DNS,
        stages=[
            SummarizeStage(
                aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="ErrorCount")],
                time_window="P1D",
            ),
            TopStage(limit=25, by_field="ErrorCount", desc=True),
        ],
    )
    result = _check_constraint_traceability(_extraction("top 25 noisiest"), ir)
    assert result is None


def test_top_n_limit_not_matching_the_number_still_flags_a_mismatch():
    ir = KqlPipeline(
        source_table=ASIMEventType.DNS,
        stages=[
            SummarizeStage(
                aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="ErrorCount")],
                time_window="P1D",
            ),
            TopStage(limit=10, by_field="ErrorCount", desc=True),
        ],
    )
    result = _check_constraint_traceability(_extraction("top 25 noisiest"), ir)
    assert not result.passed
    assert result.error_type == "THRESHOLD_VALUE_MISMATCH"


def test_percentile_parameter_satisfies_the_check_not_a_where_filter():
    """Found live: "at or below the 5th percentile" correctly compiles to
    Aggregation(function="percentile", percentile=5), not a WhereStage
    filter — the check was flagging this as a false
    THRESHOLD_VALUE_MISMATCH on the single hardest case in the dataset."""
    ir = KqlPipeline(
        source_table=ASIMEventType.PROCESS,
        stages=[
            SummarizeStage(
                aggregations=[Aggregation(function=AggregationFunction.PERCENTILE, field="Frequency", percentile=5, result_alias="P5")],
                time_window="P3D",
            ),
        ],
    )
    result = _check_constraint_traceability(_extraction("at or below the 5th percentile"), ir)
    assert result is None
