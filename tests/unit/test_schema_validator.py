from src.ir_engine.ir_schema import (
    Aggregation, AggregationFunction, AndGroup, ASIMEventType, Filter, FilterGroup, FilterOperator,
    KqlPipeline, WhereStage, SummarizeStage, ProjectStage, JoinStage, JoinKind, ExtendStage, ComputedField
)
from src.ir_engine.ir_validator import validate_ir

ASIM_SCHEMA = {
    "AuthenticationEvent": {"fields": ["EventResult", "TargetUsername", "SrcIpAddr", "TimeGenerated", "Dvc"]},
    "DnsEvent": {"fields": ["DnsQuery", "SrcIpAddr", "DnsResponseName", "TimeGenerated"]},
    "NetworkSessionEvent": {"fields": ["SrcIpAddr", "DstIpAddr", "DstPortNumber", "TimeGenerated"]},
    "ProcessEvent": {"fields": ["TimeGenerated", "Dvc", "ActingProcessName"]},
}

def test_valid_ir_passes():
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[
            WhereStage(filters=[Filter(field="EventResult", operator=FilterOperator.EQ, value="Failure")])
        ]
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert result.passed

def test_field_not_found():
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[
            WhereStage(filters=[Filter(field="SourceIP", operator=FilterOperator.EQ, value="x")])
        ]
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "FIELD_NOT_FOUND"

def test_output_fields_are_validated():
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[
            WhereStage(filters=[Filter(field="EventResult", operator=FilterOperator.EQ, value="Failure")]),
            ProjectStage(fields=["EventResult", "NotARealField"])
        ]
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "FIELD_NOT_FOUND"

def test_output_fields_can_reference_aggregation_alias():
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[
            SummarizeStage(
                aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="FailCount")],
                group_by=["TargetUsername"],
                time_window="PT1H",
            ),
            ProjectStage(fields=["TargetUsername", "FailCount"])
        ]
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert result.passed

def test_join_stage_keys_validated():
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[
            JoinStage(
                kind=JoinKind.INNER,
                right_pipeline=KqlPipeline(source_table=ASIMEventType.DNS, stages=[]),
                join_on=["DnsQuery"]
            )
        ]
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "JOIN_KEY_NOT_FOUND_LEFT"

def test_filter_field_ref_validated_against_available_schema():
    """Added §4AA: field_ref is checked the same way `field` is — it's
    typically a column produced by an earlier stage or a joined
    right_pipeline, which `available_schema` already tracks by the time
    a later WhereStage runs, so a typo'd/hallucinated field_ref is
    caught the same way a typo'd field would be."""
    ir = KqlPipeline(
        source_table=ASIMEventType.PROCESS,
        stages=[
            JoinStage(
                kind=JoinKind.INNER,
                right_pipeline=KqlPipeline(
                    source_table=ASIMEventType.AUTHENTICATION,
                    stages=[
                        SummarizeStage(
                            aggregations=[Aggregation(function=AggregationFunction.MIN, field="TimeGenerated", result_alias="FirstAuthTime")],
                            group_by=["Dvc"], time_window="P1D",
                        ),
                    ],
                ),
                join_on=["Dvc"],
            ),
            WhereStage(filters=[Filter(field="TimeGenerated", operator=FilterOperator.GTE, field_ref="NotARealColumn")]),
        ],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "FIELD_NOT_FOUND"


def test_filter_field_ref_to_a_joined_column_passes():
    ir = KqlPipeline(
        source_table=ASIMEventType.PROCESS,
        stages=[
            JoinStage(
                kind=JoinKind.INNER,
                right_pipeline=KqlPipeline(
                    source_table=ASIMEventType.AUTHENTICATION,
                    stages=[
                        SummarizeStage(
                            aggregations=[Aggregation(function=AggregationFunction.MIN, field="TimeGenerated", result_alias="FirstAuthTime")],
                            group_by=["Dvc"], time_window="P1D",
                        ),
                    ],
                ),
                join_on=["Dvc"],
            ),
            WhereStage(filters=[Filter(field="TimeGenerated", operator=FilterOperator.GTE, field_ref="FirstAuthTime")]),
        ],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert result.passed


def test_extend_creates_new_fields():
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[
            ExtendStage(computed_fields=[ComputedField(alias="MyNewField", expression="EventResult")]),
            ProjectStage(fields=["MyNewField"])
        ]
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert result.passed

def test_summarize_drops_unused_fields():
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[
            SummarizeStage(
                aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="FailCount")],
                group_by=["TargetUsername"],
                time_window="PT1H",
            ),
            WhereStage(filters=[Filter(field="EventResult", operator=FilterOperator.EQ, value="Failure")])
        ]
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "FIELD_NOT_FOUND"


# --- Checks restored after the AST migration dropped them ---

def test_degenerate_count_threshold_is_a_hard_error():
    """count()/dcount() can never be < 1 for a group that exists in the
    summarize result — "FailCount > 0" is trivially true and filters
    nothing. Found live, gpt-4.1-mini, before the original SecurityIR
    validator had this check; the AST migration dropped it entirely."""
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[
            SummarizeStage(
                aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="FailCount")],
                group_by=["TargetUsername"], time_window="PT1H",
            ),
            WhereStage(filters=[Filter(field="FailCount", operator=FilterOperator.GT, value=0)]),
        ],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "DEGENERATE_THRESHOLD"


def test_degenerate_count_threshold_gte_one_is_a_hard_error():
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[
            SummarizeStage(
                aggregations=[Aggregation(function=AggregationFunction.DISTINCT_COUNT, field="TargetUsername", result_alias="DC")],
                time_window="PT1H",
            ),
            WhereStage(filters=[Filter(field="DC", operator=FilterOperator.GTE, value=1)]),
        ],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "DEGENERATE_THRESHOLD"


def test_non_degenerate_count_threshold_passes():
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[
            SummarizeStage(
                aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="FailCount")],
                group_by=["TargetUsername"], time_window="PT1H",
            ),
            WhereStage(filters=[Filter(field="FailCount", operator=FilterOperator.GT, value=15)]),
        ],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert result.passed


def test_missing_time_window_on_aggregation_is_a_hard_error():
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[
            SummarizeStage(
                aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="FailCount")],
                group_by=["TargetUsername"],
            ),
        ],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "MISSING_TIME_WINDOW"


def test_invalid_time_window_format_is_a_hard_error():
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[
            SummarizeStage(
                aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="FailCount")],
                time_window="not-a-duration",
            ),
        ],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "INVALID_TIME_WINDOW"


def test_aggregation_missing_field_is_a_hard_error():
    """Only count() takes zero arguments in KQL — sum/avg/min/max/dcount/
    percentile/make_set/make_list all need a field."""
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[
            SummarizeStage(
                aggregations=[Aggregation(function=AggregationFunction.AVG, field=None, result_alias="X")],
                time_window="PT1H",
            ),
        ],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "AGGREGATION_MISSING_FIELD"


def test_percentile_missing_value_is_a_hard_error():
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[
            SummarizeStage(
                aggregations=[Aggregation(function=AggregationFunction.PERCENTILE, field="TargetUsername", percentile=None, result_alias="P")],
                time_window="PT1H",
            ),
        ],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "INVALID_PERCENTILE_VALUE"


def test_percentile_out_of_range_is_a_hard_error():
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[
            SummarizeStage(
                aggregations=[Aggregation(function=AggregationFunction.PERCENTILE, field="TargetUsername", percentile=150, result_alias="P")],
                time_window="PT1H",
            ),
        ],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "INVALID_PERCENTILE_VALUE"


def test_percentile_with_valid_value_passes():
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[
            SummarizeStage(
                aggregations=[Aggregation(function=AggregationFunction.PERCENTILE, field="TargetUsername", percentile=95, result_alias="P")],
                time_window="PT1H",
            ),
        ],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert result.passed


def test_duplicate_aggregation_alias_is_a_hard_error():
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[
            SummarizeStage(
                aggregations=[
                    Aggregation(function=AggregationFunction.COUNT, result_alias="X"),
                    Aggregation(function=AggregationFunction.DISTINCT_COUNT, field="TargetUsername", result_alias="X"),
                ],
                time_window="PT1H",
            ),
        ],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "DUPLICATE_AGGREGATION_ALIAS"


def test_multiple_aggregations_with_distinct_aliases_passes():
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[
            SummarizeStage(
                aggregations=[
                    Aggregation(function=AggregationFunction.COUNT, result_alias="FailCount"),
                    Aggregation(function=AggregationFunction.MAKE_SET, field="SrcIpAddr", result_alias="SourceIps", limit=100),
                ],
                group_by=["TargetUsername"], time_window="PT1H",
            ),
        ],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert result.passed


# --- New: ExtendStage expression validation (the AST migration's biggest
# unaddressed gap — a raw, unchecked string was the only stage type with
# zero field-hallucination protection) ---

def test_extend_expression_referencing_unknown_field_is_a_hard_error():
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[
            ExtendStage(computed_fields=[ComputedField(alias="Y", expression="SomeFakeField + 1")]),
        ],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "FIELD_NOT_FOUND"


def test_extend_expression_with_real_fields_passes():
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[
            ExtendStage(computed_fields=[ComputedField(alias="Y", expression="strcat(TargetUsername, '_suffix')")]),
            ProjectStage(fields=["Y"]),
        ],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert result.passed


def test_extend_expression_function_names_are_not_treated_as_fields():
    """strcat/tostring/etc. are KQL functions, not field references — an
    identifier immediately followed by "(" must not be checked against the
    schema, or every expression using a real KQL function would falsely
    fail as a hallucinated field."""
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[
            ExtendStage(computed_fields=[ComputedField(alias="Y", expression="tostring(TargetUsername)")]),
        ],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert result.passed


def test_extend_expression_calling_a_hallucinated_function_is_a_hard_error():
    """Found live: the model invented array_diff()/array_avg()/
    array_stddev() inside an extend expression — none are real KQL
    functions. The original "anything followed by '(' is a function,
    skip it" logic let all three sail through completely unchecked."""
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[
            ExtendStage(computed_fields=[ComputedField(alias="Y", expression="array_diff(TargetUsername)")]),
        ],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "UNKNOWN_FUNCTION_IN_EXPRESSION"


def test_extend_expression_with_multiple_real_functions_passes():
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[
            ExtendStage(computed_fields=[ComputedField(alias="Y", expression="strcat(tolower(TargetUsername), '_x')")]),
        ],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert result.passed


def test_extend_expression_string_literals_are_not_treated_as_fields():
    """A quoted string literal's contents must not be parsed for field-like
    tokens — e.g. a literal containing words that happen to look like
    identifiers should not be flagged."""
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[
            ExtendStage(computed_fields=[ComputedField(alias="Y", expression='strcat("NotAFieldName", TargetUsername)')]),
        ],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert result.passed


def test_extend_can_reference_a_field_defined_by_an_earlier_extend():
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[
            ExtendStage(computed_fields=[ComputedField(alias="A", expression="TargetUsername")]),
            ExtendStage(computed_fields=[ComputedField(alias="B", expression="A")]),
            ProjectStage(fields=["B"]),
        ],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert result.passed


def test_field_vs_field_comparison_via_extend_then_where():
    """The baseline-vs-current pattern: Filter.value is always a literal,
    so comparing two fields requires extend (compute the diff) then where
    (filter on the computed diff) — confirms this two-step pattern, the
    documented way to do field-to-field comparisons, actually validates."""
    ir = KqlPipeline(
        source_table=ASIMEventType.NETWORK_SESSION,
        stages=[
            SummarizeStage(
                aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="CurrentCount")],
                group_by=["SrcIpAddr"], time_window="P1D",
            ),
            JoinStage(
                kind=JoinKind.INNER,
                join_on=["SrcIpAddr"],
                right_pipeline=KqlPipeline(
                    source_table=ASIMEventType.NETWORK_SESSION,
                    stages=[
                        SummarizeStage(
                            aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="BaselineCount")],
                            group_by=["SrcIpAddr"], time_window="P14D",
                        ),
                        ExtendStage(computed_fields=[ComputedField(alias="BaselineAvg", expression="BaselineCount / 14")]),
                    ],
                ),
            ),
            ExtendStage(computed_fields=[ComputedField(alias="Margin", expression="CurrentCount - BaselineAvg")]),
            WhereStage(filters=[Filter(field="Margin", operator=FilterOperator.GT, value=50)]),
        ],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert result.passed


# --- Regression test for the crash found during AST-migration hardening ---

def test_nested_join_pipeline_parses_as_a_real_object_not_a_dict():
    """Found live: JoinStage.right_pipeline was typed as Any, so a
    malformed nested pipeline "parsed successfully" as a raw dict, and
    validate_ir's recursive call crashed with AttributeError ('dict' object
    has no attribute 'source_table') instead of failing validation cleanly.
    right_pipeline must be a real, Pydantic-validated KqlPipeline."""
    ir = KqlPipeline(
        source_table=ASIMEventType.NETWORK_SESSION,
        stages=[
            JoinStage(
                kind=JoinKind.INNER,
                join_on=["SrcIpAddr"],
                right_pipeline=KqlPipeline(source_table=ASIMEventType.NETWORK_SESSION, stages=[]),
            ),
        ],
    )
    assert isinstance(ir.stages[0].right_pipeline, KqlPipeline)
    result = validate_ir(ir, ASIM_SCHEMA)  # must not raise
    assert result.passed


def test_filter_value_accepts_a_numeric_list():
    """Found live: Filter.value's list variant was List[str]-only, so an
    "in" filter against a numeric field (e.g. DstPortNumber in (139, 445))
    failed Pydantic validation and cascaded into a confusing multi-error
    union-match failure."""
    ir = KqlPipeline(
        source_table=ASIMEventType.NETWORK_SESSION,
        stages=[
            WhereStage(filters=[Filter(field="DstPortNumber", operator=FilterOperator.IN, value=[139, 445])]),
        ],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert result.passed


# --- New: tautological FilterGroup of negations (recurring renamed-binary
# evasion bug, AST migration round 2) ---

def test_or_of_negated_conditions_on_same_field_different_values_is_a_hard_error():
    """Found live, repeatedly: a renamed-binary-evasion exclusion ("not
    literally sdelete.exe, and also not sdelete64.exe") wrapped in an OR
    instead of AND — "!endswith 'a' or !endswith 'b'" is always true since
    nothing can simultaneously end with both 'a' and 'b'."""
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[
            WhereStage(filters=[FilterGroup(conditions=[
                Filter(field="TargetUsername", operator=FilterOperator.NEQ, value="admin"),
                Filter(field="TargetUsername", operator=FilterOperator.NEQ, value="root"),
            ])]),
        ],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "TAUTOLOGICAL_FILTER_GROUP"


def test_or_of_positive_conditions_on_same_field_is_not_flagged():
    """A genuine OR — "name is cmd.exe or powershell.exe" — must not be
    confused with the negation-tautology pattern; only negated operators
    on the same field with different literals are structurally always-true."""
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[
            WhereStage(filters=[FilterGroup(conditions=[
                Filter(field="TargetUsername", operator=FilterOperator.EQ, value="admin"),
                Filter(field="TargetUsername", operator=FilterOperator.EQ, value="root"),
            ])]),
        ],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert result.passed


def test_or_of_negated_conditions_on_different_fields_is_not_flagged():
    """Negated conditions on different fields aren't structurally
    tautological the same way — must not be falsely flagged."""
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[
            WhereStage(filters=[FilterGroup(conditions=[
                Filter(field="TargetUsername", operator=FilterOperator.NEQ, value="admin"),
                Filter(field="SrcIpAddr", operator=FilterOperator.NEQ, value="10.0.0.1"),
            ])]),
        ],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert result.passed


def test_complementary_operator_pair_on_same_field_and_value_is_a_hard_error():
    """Found live: the model wrapped a positive membership check and its
    own negation, same field and value, in one OR'd group — "X in (...) or
    X !in (...)" is the most basic tautology (X or not-X)."""
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[
            WhereStage(filters=[FilterGroup(conditions=[
                Filter(field="TargetUsername", operator=FilterOperator.IN, value=["admin", "root"]),
                Filter(field="TargetUsername", operator=FilterOperator.NOT_IN, value=["admin", "root"]),
            ])]),
        ],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "TAUTOLOGICAL_FILTER_GROUP"


def test_complementary_operator_pair_with_different_values_is_not_flagged():
    """Same field, opposite operators, but DIFFERENT values is not a
    tautology — "X == 'a' or X != 'b'" is not always true."""
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[
            WhereStage(filters=[FilterGroup(conditions=[
                Filter(field="TargetUsername", operator=FilterOperator.EQ, value="admin"),
                Filter(field="TargetUsername", operator=FilterOperator.NEQ, value="root"),
            ])]),
        ],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert result.passed


# --- New: tautology detection covers the EQ_CI/CONTAINS_CS/etc. operator
# family the same way it covers plain ==/contains/etc. ---

def test_or_of_negated_case_insensitive_equality_on_different_values_is_a_hard_error():
    """The same negation-tautology pattern as
    test_or_of_negated_conditions_on_same_field_different_values_is_a_hard_error
    above, but using !~ (NEQ_CI) instead of != — added alongside the
    operator itself so the tautology check doesn't silently stop applying
    just because the IR used the case-insensitive spelling."""
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[
            WhereStage(filters=[FilterGroup(conditions=[
                Filter(field="TargetUsername", operator=FilterOperator.NEQ_CI, value="admin"),
                Filter(field="TargetUsername", operator=FilterOperator.NEQ_CI, value="root"),
            ])]),
        ],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "TAUTOLOGICAL_FILTER_GROUP"


def test_complementary_case_sensitive_contains_pair_is_a_hard_error():
    """"X contains_cs 'a' or X !contains_cs 'a'" is X-or-not-X, the same
    basic tautology as the plain contains/!contains pair, via the
    CONTAINS_CS/NOT_CONTAINS_CS complementary-operator mapping."""
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[
            WhereStage(filters=[FilterGroup(conditions=[
                Filter(field="TargetUsername", operator=FilterOperator.CONTAINS_CS, value="UwB0AGE="),
                Filter(field="TargetUsername", operator=FilterOperator.NOT_CONTAINS_CS, value="UwB0AGE="),
            ])]),
        ],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "TAUTOLOGICAL_FILTER_GROUP"


# --- New: unrecognized source_table gets a clear, actionable error ---

def test_unrecognized_source_table_is_a_hard_error_not_a_confusing_field_error():
    """Found live: the model invented a free-text source_table ("error
    event") for a description with no real technical signal. Every
    subsequent field check then failed with an unhelpful "closest match:
    None" (available_schema was empty) instead of clearly diagnosing the
    actual problem — the source table itself, not the field names."""
    ir = KqlPipeline(
        source_table="error event",
        stages=[
            WhereStage(filters=[Filter(field="ActorUserId", operator=FilterOperator.EQ, value="x")]),
        ],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "INVALID_SOURCE_TABLE"
    assert "error event" in result.message


def test_recognized_source_table_passes_through_normally():
    ir = KqlPipeline(source_table=ASIMEventType.AUTHENTICATION, stages=[])
    result = validate_ir(ir, ASIM_SCHEMA)
    assert result.passed


def test_unrecognized_source_table_inside_join_right_pipeline_is_also_caught():
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[
            JoinStage(
                kind=JoinKind.INNER,
                join_on=["SrcIpAddr"],
                right_pipeline=KqlPipeline(source_table="made up table", stages=[]),
            ),
        ],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "INVALID_SOURCE_TABLE"


def test_and_group_inside_filter_group_with_valid_fields_passes():
    ir = KqlPipeline(
        source_table=ASIMEventType.NETWORK_SESSION,
        stages=[
            WhereStage(filters=[FilterGroup(conditions=[
                AndGroup(conditions=[
                    Filter(field="DstIpAddr", operator=FilterOperator.EQ, value="dns"),
                    Filter(field="DstPortNumber", operator=FilterOperator.NEQ, value=53),
                ]),
                AndGroup(conditions=[
                    Filter(field="DstIpAddr", operator=FilterOperator.EQ, value="http"),
                    Filter(field="DstPortNumber", operator=FilterOperator.NEQ, value=80),
                ]),
            ])]),
        ],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert result.passed


def test_and_group_with_unknown_field_is_a_hard_error():
    ir = KqlPipeline(
        source_table=ASIMEventType.NETWORK_SESSION,
        stages=[
            WhereStage(filters=[FilterGroup(conditions=[
                AndGroup(conditions=[
                    Filter(field="DstIpAddr", operator=FilterOperator.EQ, value="dns"),
                    Filter(field="NotARealField", operator=FilterOperator.NEQ, value=53),
                ]),
                Filter(field="DstIpAddr", operator=FilterOperator.EQ, value="http"),
            ])]),
        ],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "FIELD_NOT_FOUND"
    assert "NotARealField" in result.message


def test_and_group_mixed_with_plain_filters_does_not_false_positive_tautology():
    """An AndGroup entry mixed into a FilterGroup with plain Filters must
    not confuse the tautology checks, which only reason about flat,
    same-field, same-shape Filter entries."""
    ir = KqlPipeline(
        source_table=ASIMEventType.NETWORK_SESSION,
        stages=[
            WhereStage(filters=[FilterGroup(conditions=[
                AndGroup(conditions=[
                    Filter(field="DstIpAddr", operator=FilterOperator.EQ, value="1.2.3.4"),
                    Filter(field="DstPortNumber", operator=FilterOperator.NEQ, value=53),
                ]),
                Filter(field="DstPortNumber", operator=FilterOperator.NEQ, value=80),
            ])]),
        ],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert result.passed


def test_function_call_written_as_a_filter_value_is_a_hard_error():
    ir = KqlPipeline(
        source_table=ASIMEventType.DNS,
        stages=[WhereStage(filters=[Filter(field="TimeGenerated", operator=FilterOperator.GTE, value="ago(1h)")])],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "FUNCTION_CALL_AS_LITERAL_VALUE"


def test_ordinary_string_filter_value_is_not_flagged_as_a_function_call():
    ir = KqlPipeline(
        source_table=ASIMEventType.DNS,
        stages=[WhereStage(filters=[Filter(field="DnsQuery", operator=FilterOperator.CONTAINS, value="evil.com")])],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert result.passed


# --- New: a literal value that's itself a real in-scope column name almost
# certainly means field_ref was intended (the §4AA field_ref bug,
# generalized — same mistake, the model reverting to the old broken
# pattern instead of forgetting the capability exists at all) ---

def test_literal_value_matching_a_real_column_name_on_comparison_operator_is_a_hard_error():
    """"DstIpAddr >= 'SrcIpAddr'" compiles to a quoted STRING LITERAL
    comparison — can never match a real IP — when the model almost
    certainly meant field_ref="SrcIpAddr" (an unquoted column reference)."""
    ir = KqlPipeline(
        source_table=ASIMEventType.NETWORK_SESSION,
        stages=[WhereStage(filters=[
            Filter(field="DstIpAddr", operator=FilterOperator.GTE, value="SrcIpAddr"),
        ])],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "LITERAL_MATCHES_SCHEMA_FIELD"


def test_field_ref_itself_is_not_flagged_by_the_literal_matches_field_check():
    """The correct, already-built way to express this (field_ref, not
    value) must never trip the check that exists to catch its absence."""
    ir = KqlPipeline(
        source_table=ASIMEventType.NETWORK_SESSION,
        stages=[WhereStage(filters=[
            Filter(field="DstIpAddr", operator=FilterOperator.GTE, field_ref="SrcIpAddr"),
        ])],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert result.passed


def test_literal_value_matching_a_column_name_on_a_non_comparison_operator_is_not_flagged():
    """Restricted to EQ/NEQ/GT/LT/GTE/LTE (+ CI variants) deliberately —
    a `contains`/`has`/`startswith` value that happens to spell like a
    column name is far more likely to be an unusual but real literal
    than a mistaken field reference, and flagging it would be a
    needless false positive on a different, much more common pattern."""
    ir = KqlPipeline(
        source_table=ASIMEventType.NETWORK_SESSION,
        stages=[WhereStage(filters=[
            Filter(field="DstIpAddr", operator=FilterOperator.CONTAINS, value="SrcIpAddr"),
        ])],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert result.passed


# --- Literal-value provenance check (advisory warning, not a hard error) ---

def test_literal_not_present_in_input_and_not_a_common_value_produces_a_warning():
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[WhereStage(filters=[Filter(field="TargetUsername", operator=FilterOperator.EQ, value="WannaCry")])],
    )
    result = validate_ir(ir, ASIM_SCHEMA, nl_description="Alert when a specific account logs in.")
    assert result.passed
    assert any("WannaCry" in w for w in result.warnings)


def test_literal_present_verbatim_in_input_produces_no_warning():
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[WhereStage(filters=[Filter(field="TargetUsername", operator=FilterOperator.EQ, value="jsmith")])],
    )
    result = validate_ir(ir, ASIM_SCHEMA, nl_description="Alert when jsmith logs in from an unusual location.")
    assert result.passed
    assert result.warnings == []


def test_common_status_value_is_never_flagged_even_when_absent_from_input():
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[WhereStage(filters=[Filter(field="EventResult", operator=FilterOperator.EQ, value="Failure")])],
    )
    result = validate_ir(ir, ASIM_SCHEMA, nl_description="Alert on repeated login failures.")
    assert result.passed
    assert result.warnings == []


def test_numeric_literal_values_are_never_flagged_as_ungrounded():
    """Domain-knowledge numeric constants (port numbers, thresholds) are
    routinely correct without appearing in casual NL text — only strings
    are checked."""
    ir = KqlPipeline(
        source_table=ASIMEventType.NETWORK_SESSION,
        stages=[WhereStage(filters=[Filter(field="DstPortNumber", operator=FilterOperator.EQ, value=445)])],
    )
    result = validate_ir(ir, ASIM_SCHEMA, nl_description="Flag unusual SMB traffic.")
    assert result.passed
    assert result.warnings == []


def test_no_nl_description_means_no_provenance_check_at_all():
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[WhereStage(filters=[Filter(field="TargetUsername", operator=FilterOperator.EQ, value="WannaCry")])],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert result.passed
    assert result.warnings == []


# --- New: alias-implies-filter check (advisory warning, not a hard error) ---
# Generalizes the §4AC NXDomainCount bug: an aggregation alias naming a
# specific subset is a promise that subset was actually filtered to
# first. Necessarily heuristic (camelCase token matching, no real
# semantic understanding), so advisory only — same calibration as the
# literal-provenance check above.

def test_aggregation_alias_implying_an_unfiltered_subset_produces_a_warning():
    """"NXDomainCount" implies the count was restricted to NXDOMAIN
    responses, but no upstream filter mentions NXDOMAIN anywhere — the
    alias is making a claim its own structure doesn't deliver."""
    ir = KqlPipeline(
        source_table=ASIMEventType.DNS,
        stages=[
            SummarizeStage(
                aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="NXDomainCount")],
                group_by=["SrcIpAddr"], time_window="P1D",
            ),
        ],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert result.passed
    assert any("NXDomain" in w for w in result.warnings)


def test_aggregation_alias_with_matching_upstream_filter_produces_no_warning():
    """Same alias, but this time a WhereStage actually filters to
    NXDOMAIN responses before the summarize — the alias's claim is
    backed by real structure, so no warning."""
    ir = KqlPipeline(
        source_table=ASIMEventType.DNS,
        stages=[
            WhereStage(filters=[Filter(field="DnsResponseName", operator=FilterOperator.EQ, value="NXDOMAIN")]),
            SummarizeStage(
                aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="NXDomainCount")],
                group_by=["SrcIpAddr"], time_window="P1D",
            ),
        ],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert result.passed
    assert result.warnings == []


def test_generic_aggregation_alias_is_never_flagged():
    """"ConnectionCount"/"EventCount"-shaped aliases describe the
    aggregation TYPE and a generic entity, not a specific filtered
    subset — must never warn regardless of upstream filters."""
    ir = KqlPipeline(
        source_table=ASIMEventType.NETWORK_SESSION,
        stages=[
            SummarizeStage(
                aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="ConnectionCount")],
                group_by=["SrcIpAddr"], time_window="PT1H",
            ),
        ],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert result.passed
    assert result.warnings == []


def test_field_not_found_message_includes_a_value_type_hint_for_the_suggestion():
    ir = KqlPipeline(
        source_table=ASIMEventType.NETWORK_SESSION,
        stages=[WhereStage(filters=[Filter(field="DstPortNumbr", operator=FilterOperator.EQ, value=445)])],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "FIELD_NOT_FOUND"
    assert "DstPortNumber" in result.message
    assert "expects" in result.message


def test_dns_rcode_enum_value_is_never_flagged_as_ungrounded():
    ir = KqlPipeline(
        source_table=ASIMEventType.DNS,
        stages=[WhereStage(filters=[Filter(field="DnsResponseName", operator=FilterOperator.NEQ, value="NOERROR")])],
    )
    result = validate_ir(ir, ASIM_SCHEMA, nl_description="Flag DNS responses that indicate an error.")
    assert result.passed
    assert result.warnings == []


def test_value_that_is_input_wording_plus_a_common_extension_is_not_flagged():
    ir = KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[WhereStage(filters=[Filter(field="TargetUsername", operator=FilterOperator.EQ, value="rundll32.exe")])],
    )
    result = validate_ir(ir, ASIM_SCHEMA, nl_description="Hunt for rundll32 being used to proxy execution.")
    assert result.passed
    assert result.warnings == []


# --- DEGENERATE_SPREAD_OVER_SINGLE_ROW (stdev/variance over an
# already-1-row-per-group prior summarize) ---

def test_stdev_over_same_signature_prior_summarize_is_a_hard_error():
    ir = KqlPipeline(
        source_table=ASIMEventType.NETWORK_SESSION,
        stages=[
            SummarizeStage(
                aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="ConnCount")],
                group_by=["SrcIpAddr"], time_window="P14D",
            ),
            SummarizeStage(
                aggregations=[Aggregation(function=AggregationFunction.STDEV, field="ConnCount", result_alias="X")],
                group_by=["SrcIpAddr"], time_window="P14D",
            ),
        ],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "DEGENERATE_SPREAD_OVER_SINGLE_ROW"


def test_stdev_over_a_finer_prior_summarize_passes():
    """The correct pattern: the first stage uses a FINER bucket (daily)
    than the second (14-day reduction), so the second stage genuinely
    has multiple rows per group to compute spread over."""
    ir = KqlPipeline(
        source_table=ASIMEventType.NETWORK_SESSION,
        stages=[
            SummarizeStage(
                aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="ConnCount")],
                group_by=["SrcIpAddr"], time_window="P1D",
            ),
            SummarizeStage(
                aggregations=[Aggregation(function=AggregationFunction.STDEV, field="ConnCount", result_alias="X")],
                group_by=["SrcIpAddr"], time_window="P14D",
            ),
        ],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert result.passed


def test_stdev_with_same_signature_but_intervening_join_does_not_false_positive():
    """A join between two same-signature summarizes can re-expand row
    cardinality (the percentile-of-aggregates pattern relies on exactly
    this) — must not be flagged just because the signatures match."""
    right = KqlPipeline(
        source_table=ASIMEventType.NETWORK_SESSION,
        stages=[
            SummarizeStage(
                aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="ConnCount")],
                group_by=["SrcIpAddr"], time_window="P14D",
            ),
        ],
    )
    ir = KqlPipeline(
        source_table=ASIMEventType.NETWORK_SESSION,
        stages=[
            SummarizeStage(
                aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="ConnCount")],
                group_by=["SrcIpAddr"], time_window="P14D",
            ),
            JoinStage(kind=JoinKind.INNER, right_pipeline=right, join_on=["SrcIpAddr"]),
            SummarizeStage(
                aggregations=[Aggregation(function=AggregationFunction.STDEV, field="ConnCount", result_alias="X")],
                group_by=["SrcIpAddr"], time_window="P14D",
            ),
        ],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert result.passed


def test_numeric_range_pair_joined_by_or_is_a_hard_error():
    """X > 0 or X <= 60 is a tautology — every number satisfies at least
    one side. Found live: a sequential-events ordering+window check
    (">0 and <=60") flattened into one OR'd FilterGroup instead of two
    AND-ed WhereStage filters."""
    ir = KqlPipeline(
        source_table=ASIMEventType.NETWORK_SESSION,
        stages=[WhereStage(filters=[FilterGroup(conditions=[
            Filter(field="DstPortNumber", operator=FilterOperator.GT, value=0),
            Filter(field="DstPortNumber", operator=FilterOperator.LTE, value=60),
        ])])],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert not result.passed
    assert result.error_type == "TAUTOLOGICAL_FILTER_GROUP"


def test_numeric_range_pair_with_a_real_gap_is_not_flagged():
    """X > 60 or X <= 0 is NOT a tautology (it excludes 0 < X <= 60) —
    only the inverted, gapless ordering should ever be flagged."""
    ir = KqlPipeline(
        source_table=ASIMEventType.NETWORK_SESSION,
        stages=[WhereStage(filters=[FilterGroup(conditions=[
            Filter(field="DstPortNumber", operator=FilterOperator.GT, value=60),
            Filter(field="DstPortNumber", operator=FilterOperator.LTE, value=0),
            Filter(field="SrcIpAddr", operator=FilterOperator.EQ, value="10.0.0.1"),
        ])])],
    )
    result = validate_ir(ir, ASIM_SCHEMA)
    assert result.passed
