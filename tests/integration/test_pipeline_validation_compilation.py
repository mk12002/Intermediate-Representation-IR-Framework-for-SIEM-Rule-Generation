"""Integration tests for the real (non-mocked) Schema Validator -> KQL
Compiler -> KQL Syntax Validator chain, on hand-built IRs representing the
complex, realistic patterns this project's live-test-and-fix rounds found
and fixed: percentile-of-aggregates, baseline-vs-current, multi-column
group_by, every JoinKind, and every hard-error check the validator raises.

Unlike tests/unit/test_schema_validator.py (one check at a time, in
isolation) and tests/unit/test_templates.py (the compiler alone), these
exercise validate_ir() and generate_kql() together on the SAME pipeline
object, the way the real pipeline actually uses them — this project's own
history (see PROJECT_STATUS.md) found multiple bugs that only showed up
when components were wired together, not when each was tested alone.
"""
import pytest

from src.ir_engine.ir_schema import (
    Aggregation, AggregationFunction, AndGroup, ASIMEventType, ComputedField,
    ExtendStage, Filter, FilterGroup, FilterOperator, JoinKind, JoinStage,
    KqlPipeline, ProjectStage, SummarizeStage, TopStage, WhereStage,
)
from src.ir_engine.ir_validator import validate_ir
from src.generator.compiler import generate_kql
from src.validation.syntax_validators import validate_kql_syntax

ASIM_SCHEMA = {
    "NetworkSessionEvent": {
        "fields": ["SrcIpAddr", "DstIpAddr", "SrcPortNumber", "DstPortNumber", "TimeGenerated"]
    },
    "DnsEvent": {"fields": ["SrcIpAddr", "DnsQuery", "TimeGenerated"]},
    "ProcessEvent": {"fields": ["ActingProcessName", "ActingProcessCommandLine", "TimeGenerated"]},
}


def _assert_valid_and_compiles(pipeline: KqlPipeline) -> str:
    result = validate_ir(pipeline, ASIM_SCHEMA)
    assert result.passed, f"expected valid, got {result.error_type}: {result.message}"
    kql = generate_kql(pipeline)
    syntax = validate_kql_syntax(kql)
    assert syntax.passed, f"compiled KQL failed syntax check: {syntax.message}\n{kql}"
    return kql


def test_percentile_of_aggregates_self_join_validates_and_compiles():
    """The constant-key self-join pattern that makes 'Nth percentile across
    groups' expressible — the single largest capability gap the old flat
    SecurityIR model could never close (PROJECT_STATUS.md §4E-§4J)."""
    right = KqlPipeline(
        source_table=ASIMEventType.PROCESS,
        stages=[
            SummarizeStage(
                aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="Frequency")],
                group_by=["ActingProcessName"], time_window="P3D",
            ),
            SummarizeStage(
                aggregations=[Aggregation(
                    function=AggregationFunction.PERCENTILE, field="Frequency",
                    percentile=5, result_alias="P5Frequency",
                )],
                time_window="P3D",
            ),
            ExtendStage(computed_fields=[ComputedField(alias="JoinKey", expression="1")]),
        ],
    )
    pipeline = KqlPipeline(
        source_table=ASIMEventType.PROCESS,
        stages=[
            SummarizeStage(
                aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="Frequency")],
                group_by=["ActingProcessName"], time_window="P3D",
            ),
            ExtendStage(computed_fields=[ComputedField(alias="JoinKey", expression="1")]),
            JoinStage(kind=JoinKind.INNER, right_pipeline=right, join_on=["JoinKey"]),
            ExtendStage(computed_fields=[ComputedField(alias="IsRare", expression="Frequency - P5Frequency")]),
            WhereStage(filters=[Filter(field="IsRare", operator=FilterOperator.LTE, value=0)]),
        ],
    )
    kql = _assert_valid_and_compiles(pipeline)
    assert "percentile(Frequency, 5" in kql
    assert "join kind=inner" in kql


def test_baseline_vs_current_extend_threshold_validates_and_compiles():
    """A WhereStage filtering an ExtendStage-derived comparison field
    (Margin), not a raw aggregation alias — the exact shape that was a
    false THRESHOLD_VALUE_MISMATCH before _collect_aggregation_aliases
    learned to include extend aliases too."""
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
    pipeline = KqlPipeline(
        source_table=ASIMEventType.NETWORK_SESSION,
        stages=[
            SummarizeStage(
                aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="CurrentCount")],
                group_by=["SrcIpAddr"], time_window="P1D",
            ),
            JoinStage(kind=JoinKind.INNER, right_pipeline=right, join_on=["SrcIpAddr"]),
            ExtendStage(computed_fields=[ComputedField(alias="Margin", expression="CurrentCount - BaselineAvg")]),
            WhereStage(filters=[Filter(field="Margin", operator=FilterOperator.GT, value=50)]),
        ],
    )
    kql = _assert_valid_and_compiles(pipeline)
    assert "Margin = CurrentCount - BaselineAvg" in kql
    assert "where Margin > 50" in kql


def test_two_field_group_by_pair_is_compiled_together():
    pipeline = KqlPipeline(
        source_table=ASIMEventType.NETWORK_SESSION,
        stages=[
            SummarizeStage(
                aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="ConnCount")],
                group_by=["SrcIpAddr", "DstPortNumber"], time_window="P1D",
            ),
        ],
    )
    kql = _assert_valid_and_compiles(pipeline)
    assert "by SrcIpAddr, DstPortNumber" in kql


@pytest.mark.parametrize("function,kql_name", [
    (AggregationFunction.STDEV, "stdev"),
    (AggregationFunction.VARIANCE, "variance"),
])
def test_stdev_and_variance_aggregations_validate_and_compile(function, kql_name):
    """stdev()/variance() of a per-group count requires TWO chained
    SummarizeStages, same as percentile-of-aggregates — real KQL cannot
    reference one aggregation's alias from another aggregation in the
    SAME summarize clause; the validator's stage-by-stage available_schema
    only exposes an alias to LATER stages, never sibling aggregations."""
    pipeline = KqlPipeline(
        source_table=ASIMEventType.NETWORK_SESSION,
        stages=[
            SummarizeStage(
                aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="ConnCount")],
                group_by=["SrcIpAddr"], time_window="P1D",
            ),
            SummarizeStage(
                aggregations=[Aggregation(function=function, field="ConnCount", result_alias="Spread")],
                time_window="P1D",
            ),
        ],
    )
    kql = _assert_valid_and_compiles(pipeline)
    assert f"Spread = {kql_name}(ConnCount)" in kql


def test_aggregate_function_called_inside_extend_is_a_hard_error():
    """stdev()/count()/etc. only exist inside summarize — there is no
    scalar form. Calling one inside an extend expression must be rejected
    with a specific, actionable error, not silently compiled into invalid
    KQL or confused with a hallucinated-field/-function error."""
    pipeline = KqlPipeline(
        source_table=ASIMEventType.NETWORK_SESSION,
        stages=[
            SummarizeStage(
                aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="ConnCount")],
                group_by=["SrcIpAddr"], time_window="P1D",
            ),
            ExtendStage(computed_fields=[ComputedField(alias="Bad", expression="stdev(ConnCount)")]),
        ],
    )
    result = validate_ir(pipeline, ASIM_SCHEMA)
    assert result.passed is False
    assert result.error_type == "AGGREGATE_FUNCTION_IN_EXTEND"


@pytest.mark.parametrize("kind,keyword", [
    (JoinKind.INNER, "join kind=inner"),
    (JoinKind.INNERUNIQUE, "join kind=innerunique"),
    (JoinKind.LEFTOUTER, "join kind=leftouter"),
    (JoinKind.RIGHTOUTER, "join kind=rightouter"),
    (JoinKind.FULLOUTER, "join kind=fullouter"),
    (JoinKind.LEFTANTI, "join kind=leftanti"),
    (JoinKind.RIGHTANTI, "join kind=rightanti"),
    (JoinKind.LEFTSEMI, "join kind=leftsemi"),
    (JoinKind.RIGHTSEMI, "join kind=rightsemi"),
])
def test_every_join_kind_validates_and_compiles_to_its_kql_keyword(kind, keyword):
    right = KqlPipeline(
        source_table=ASIMEventType.NETWORK_SESSION,
        stages=[WhereStage(filters=[Filter(field="DstPortNumber", operator=FilterOperator.EQ, value=445)])],
    )
    pipeline = KqlPipeline(
        source_table=ASIMEventType.NETWORK_SESSION,
        stages=[JoinStage(kind=kind, right_pipeline=right, join_on=["SrcIpAddr"])],
    )
    kql = _assert_valid_and_compiles(pipeline)
    assert keyword in kql


def test_top_n_ranking_compiles_and_does_not_need_a_threshold_where():
    pipeline = KqlPipeline(
        source_table=ASIMEventType.NETWORK_SESSION,
        stages=[
            SummarizeStage(
                aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="ConnCount")],
                group_by=["SrcIpAddr"], time_window="P1D",
            ),
            TopStage(limit=25, by_field="ConnCount", desc=True),
        ],
    )
    kql = _assert_valid_and_compiles(pipeline)
    assert "top 25 by ConnCount desc" in kql


def test_tautological_negation_group_is_a_hard_error():
    pipeline = KqlPipeline(
        source_table=ASIMEventType.PROCESS,
        stages=[WhereStage(filters=[FilterGroup(conditions=[
            Filter(field="ActingProcessName", operator=FilterOperator.NOT_ENDSWITH, value="a.exe"),
            Filter(field="ActingProcessName", operator=FilterOperator.NOT_ENDSWITH, value="b.exe"),
        ])])],
    )
    result = validate_ir(pipeline, ASIM_SCHEMA)
    assert result.passed is False
    assert result.error_type == "TAUTOLOGICAL_FILTER_GROUP"


def test_complementary_operator_pair_is_a_hard_error():
    pipeline = KqlPipeline(
        source_table=ASIMEventType.PROCESS,
        stages=[WhereStage(filters=[FilterGroup(conditions=[
            Filter(field="ActingProcessName", operator=FilterOperator.IN, value=["a.exe"]),
            Filter(field="ActingProcessName", operator=FilterOperator.NOT_IN, value=["a.exe"]),
        ])])],
    )
    result = validate_ir(pipeline, ASIM_SCHEMA)
    assert result.passed is False
    assert result.error_type == "TAUTOLOGICAL_FILTER_GROUP"


def test_hallucinated_function_in_extend_is_a_hard_error():
    pipeline = KqlPipeline(
        source_table=ASIMEventType.DNS,
        stages=[ExtendStage(computed_fields=[ComputedField(alias="X", expression="array_stddev(DnsQuery)")])],
    )
    result = validate_ir(pipeline, ASIM_SCHEMA)
    assert result.passed is False
    assert result.error_type == "UNKNOWN_FUNCTION_IN_EXPRESSION"


def test_unrecognized_source_table_is_a_hard_error_with_a_suggestion():
    pipeline = KqlPipeline(source_table="some made up event", stages=[])
    result = validate_ir(pipeline, ASIM_SCHEMA)
    assert result.passed is False
    assert result.error_type == "INVALID_SOURCE_TABLE"
    assert "DnsEvent" in result.message or "ProcessEvent" in result.message or "NetworkSessionEvent" in result.message


def test_or_of_and_pairs_app_port_mismatch_validates_and_compiles_correctly():
    """The a61e9fc1-style structural gap (PROJECT_STATUS.md §4N): GT needs
    '(app==dns and port!=53) or (app==http and port!=80)' — a disjunction
    of conjunctions. A flat FilterGroup of plain Filters cannot express
    this; AndGroup closes the gap. Confirms the compiled KQL keeps each
    branch's AND together inside the outer OR, not flattened apart."""
    pipeline = KqlPipeline(
        source_table=ASIMEventType.NETWORK_SESSION,
        stages=[WhereStage(filters=[FilterGroup(conditions=[
            AndGroup(conditions=[
                Filter(field="DstIpAddr", operator=FilterOperator.EQ, value="dns"),
                Filter(field="DstPortNumber", operator=FilterOperator.NEQ, value=53),
            ]),
            AndGroup(conditions=[
                Filter(field="DstIpAddr", operator=FilterOperator.EQ, value="http"),
                Filter(field="DstPortNumber", operator=FilterOperator.NEQ, value=80),
            ]),
        ])])],
    )
    kql = _assert_valid_and_compiles(pipeline)
    assert kql.endswith(
        '| where ((DstIpAddr == "dns" and DstPortNumber != 53) or '
        '(DstIpAddr == "http" and DstPortNumber != 80))'
    )


def test_and_group_with_unknown_field_is_a_hard_error_through_full_pipeline():
    pipeline = KqlPipeline(
        source_table=ASIMEventType.NETWORK_SESSION,
        stages=[WhereStage(filters=[FilterGroup(conditions=[
            AndGroup(conditions=[
                Filter(field="DstIpAddr", operator=FilterOperator.EQ, value="dns"),
                Filter(field="NotARealField", operator=FilterOperator.NEQ, value=53),
            ]),
            Filter(field="DstIpAddr", operator=FilterOperator.EQ, value="http"),
        ])])],
    )
    result = validate_ir(pipeline, ASIM_SCHEMA)
    assert result.passed is False
    assert result.error_type == "FIELD_NOT_FOUND"


def test_project_stage_narrows_schema_and_compiles():
    pipeline = KqlPipeline(
        source_table=ASIMEventType.DNS,
        stages=[
            ProjectStage(fields=["SrcIpAddr", "DnsQuery"]),
        ],
    )
    kql = _assert_valid_and_compiles(pipeline)
    assert "project SrcIpAddr, DnsQuery" in kql
