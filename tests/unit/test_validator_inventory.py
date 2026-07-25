"""Insurance against the exact regression class that already happened once
(PROJECT_STATUS.md §4K): an external rewrite of the validator silently
dropped five previously-shipping checks, and nothing in the test suite
caught it because each check's own test only proves "this check works
when present," never "this check is still present at all."

This file is the single source of truth for "every error_type the
validator can raise, and a minimal input that makes it fire." Two things
are asserted, not one:
  1. `_KNOWN_BAD_IRS`'s keys exactly match every `error_type="..."`
     literal actually written in src/ir_engine/ir_validator.py — so
     adding a new check without adding a matching entry here (or
     deleting a check without removing its entry) fails the suite
     immediately, not silently.
  2. Each known-bad IR actually produces ITS named error_type, not some
     other one (a check could still exist but fire on the wrong
     condition).
"""
import re
from pathlib import Path

import pytest

from src.ir_engine.ir_schema import (
    Aggregation, AggregationFunction, ASIMEventType, ComputedField,
    ExtendStage, Filter, FilterGroup, FilterOperator, JoinKind, JoinStage,
    KqlPipeline, MvExpandStage, ParseStage, ParseToken, ProjectStage,
    SummarizeStage, UnionStage, WhereStage,
)
from src.ir_engine.ir_validator import validate_ir

ASIM_SCHEMA = {
    "AuthenticationEvent": {"fields": ["EventResult", "TargetUsername", "SrcIpAddr", "TimeGenerated"]},
    "DnsEvent": {"fields": ["DnsQuery", "SrcIpAddr", "DnsResponseName", "TimeGenerated"]},
    "NetworkSessionEvent": {"fields": ["SrcIpAddr", "DstIpAddr", "DstPortNumber", "TimeGenerated"]},
}

_VALIDATOR_SOURCE = (
    Path(__file__).parent.parent.parent / "src" / "ir_engine" / "ir_validator.py"
).read_text(encoding="utf-8")
_SHIPPED_ERROR_TYPES = set(re.findall(r'error_type="([A-Z_]+)"', _VALIDATOR_SOURCE))


def _bad_invalid_source_table():
    return KqlPipeline(source_table="made up event type", stages=[])


def _bad_field_not_found():
    return KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[WhereStage(filters=[Filter(field="NotARealField", operator=FilterOperator.EQ, value="x")])],
    )


def _bad_function_call_as_literal_value():
    return KqlPipeline(
        source_table=ASIMEventType.DNS,
        stages=[WhereStage(filters=[Filter(field="TimeGenerated", operator=FilterOperator.GTE, value="ago(1h)")])],
    )


def _bad_degenerate_threshold():
    return KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[
            SummarizeStage(
                aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="FailCount")],
                group_by=["TargetUsername"], time_window="PT1H",
            ),
            WhereStage(filters=[Filter(field="FailCount", operator=FilterOperator.GT, value=0)]),
        ],
    )


def _bad_tautological_filter_group():
    return KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[WhereStage(filters=[FilterGroup(conditions=[
            Filter(field="TargetUsername", operator=FilterOperator.NEQ, value="a"),
            Filter(field="TargetUsername", operator=FilterOperator.NEQ, value="b"),
        ])])],
    )


def _bad_duplicate_aggregation_alias():
    return KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[SummarizeStage(
            aggregations=[
                Aggregation(function=AggregationFunction.COUNT, result_alias="X"),
                Aggregation(function=AggregationFunction.DISTINCT_COUNT, field="TargetUsername", result_alias="X"),
            ],
            time_window="PT1H",
        )],
    )


def _bad_redundant_raw_time_field_in_group_by():
    return KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[SummarizeStage(
            aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="X")],
            group_by=["TargetUsername", "TimeGenerated"],
            time_window="P1D",
        )],
    )


def _bad_degenerate_spread_over_single_row():
    return KqlPipeline(
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


def _bad_aggregation_missing_field():
    return KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[SummarizeStage(
            aggregations=[Aggregation(function=AggregationFunction.AVG, field=None, result_alias="X")],
            time_window="PT1H",
        )],
    )


def _bad_invalid_percentile_value():
    return KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[SummarizeStage(
            aggregations=[Aggregation(
                function=AggregationFunction.PERCENTILE, field="TargetUsername",
                percentile=150, result_alias="X",
            )],
            time_window="PT1H",
        )],
    )


def _bad_missing_time_window():
    return KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[SummarizeStage(
            aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="X")],
        )],
    )


def _bad_invalid_time_window():
    return KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[SummarizeStage(
            aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="X")],
            time_window="not-a-duration",
        )],
    )


def _bad_aggregate_function_in_extend():
    return KqlPipeline(
        source_table=ASIMEventType.NETWORK_SESSION,
        stages=[
            SummarizeStage(
                aggregations=[Aggregation(function=AggregationFunction.COUNT, result_alias="ConnCount")],
                group_by=["SrcIpAddr"], time_window="PT1H",
            ),
            ExtendStage(computed_fields=[ComputedField(alias="X", expression="stdev(ConnCount)")]),
        ],
    )


def _bad_unknown_function_in_expression():
    return KqlPipeline(
        source_table=ASIMEventType.DNS,
        stages=[ExtendStage(computed_fields=[ComputedField(alias="X", expression="array_stddev(DnsQuery)")])],
    )


def _bad_join_key_not_found_left():
    return KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[JoinStage(
            kind=JoinKind.INNER,
            right_pipeline=KqlPipeline(
                source_table=ASIMEventType.DNS,
                stages=[WhereStage(filters=[Filter(field="DnsQuery", operator=FilterOperator.EQ, value="example.com")])],
            ),
            join_on=["DnsQuery"],
        )],
    )


def _bad_join_key_not_found_right():
    # TargetUsername exists on the left (AuthenticationEvent) but not the
    # right (DnsEvent) — the left-side check must pass for this to reach
    # and exercise the right-side check specifically.
    return KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[JoinStage(
            kind=JoinKind.INNER,
            right_pipeline=KqlPipeline(
                source_table=ASIMEventType.DNS,
                stages=[WhereStage(filters=[Filter(field="DnsQuery", operator=FilterOperator.EQ, value="example.com")])],
            ),
            join_on=["TargetUsername"],
        )],
    )


def _bad_empty_union():
    return KqlPipeline(source_table=ASIMEventType.AUTHENTICATION, stages=[UnionStage(tables=[])])


def _bad_mv_expand_as_type_with_multiple_fields():
    return KqlPipeline(
        source_table=ASIMEventType.AUTHENTICATION,
        stages=[MvExpandStage(fields=["TargetUsername", "SrcIpAddr"], as_type="string")],
    )


def _bad_parse_extracts_nothing():
    return KqlPipeline(
        source_table=ASIMEventType.DNS,
        stages=[ParseStage(source_field="DnsQuery", tokens=[
            ParseToken(type="wildcard"), ParseToken(type="literal", value="."), ParseToken(type="wildcard"),
        ])],
    )


def _bad_duplicate_parse_column():
    return KqlPipeline(
        source_table=ASIMEventType.DNS,
        stages=[ParseStage(source_field="DnsQuery", tokens=[
            ParseToken(type="column", value="Part"), ParseToken(type="literal", value="."),
            ParseToken(type="column", value="Part"),
        ])],
    )


def _bad_literal_matches_schema_field():
    return KqlPipeline(
        source_table=ASIMEventType.NETWORK_SESSION,
        stages=[WhereStage(filters=[
            Filter(field="DstIpAddr", operator=FilterOperator.GTE, value="SrcIpAddr"),
        ])],
    )


def _bad_empty_pipeline_not_marked_abstained():
    return KqlPipeline(source_table=ASIMEventType.NETWORK_SESSION, stages=[])


_KNOWN_BAD_IRS = {
    "INVALID_SOURCE_TABLE": _bad_invalid_source_table,
    "FIELD_NOT_FOUND": _bad_field_not_found,
    "REDUNDANT_RAW_TIME_FIELD_IN_GROUP_BY": _bad_redundant_raw_time_field_in_group_by,
    "DEGENERATE_SPREAD_OVER_SINGLE_ROW": _bad_degenerate_spread_over_single_row,
    "FUNCTION_CALL_AS_LITERAL_VALUE": _bad_function_call_as_literal_value,
    "DEGENERATE_THRESHOLD": _bad_degenerate_threshold,
    "TAUTOLOGICAL_FILTER_GROUP": _bad_tautological_filter_group,
    "DUPLICATE_AGGREGATION_ALIAS": _bad_duplicate_aggregation_alias,
    "AGGREGATION_MISSING_FIELD": _bad_aggregation_missing_field,
    "INVALID_PERCENTILE_VALUE": _bad_invalid_percentile_value,
    "MISSING_TIME_WINDOW": _bad_missing_time_window,
    "INVALID_TIME_WINDOW": _bad_invalid_time_window,
    "AGGREGATE_FUNCTION_IN_EXTEND": _bad_aggregate_function_in_extend,
    "UNKNOWN_FUNCTION_IN_EXPRESSION": _bad_unknown_function_in_expression,
    "JOIN_KEY_NOT_FOUND_LEFT": _bad_join_key_not_found_left,
    "JOIN_KEY_NOT_FOUND_RIGHT": _bad_join_key_not_found_right,
    "EMPTY_UNION": _bad_empty_union,
    "MV_EXPAND_AS_TYPE_WITH_MULTIPLE_FIELDS": _bad_mv_expand_as_type_with_multiple_fields,
    "PARSE_EXTRACTS_NOTHING": _bad_parse_extracts_nothing,
    "DUPLICATE_PARSE_COLUMN": _bad_duplicate_parse_column,
    "LITERAL_MATCHES_SCHEMA_FIELD": _bad_literal_matches_schema_field,
    "EMPTY_PIPELINE_NOT_MARKED_ABSTAINED": _bad_empty_pipeline_not_marked_abstained,
}


def test_inventory_covers_every_error_type_the_validator_can_actually_raise():
    """If this fails, either a check was added without a matching entry
    above, or a check was removed/renamed without updating this list —
    exactly the silent-regression shape that happened in §4K."""
    missing_from_inventory = _SHIPPED_ERROR_TYPES - set(_KNOWN_BAD_IRS)
    stale_in_inventory = set(_KNOWN_BAD_IRS) - _SHIPPED_ERROR_TYPES
    assert not missing_from_inventory, f"validator raises these but no inventory test covers them: {missing_from_inventory}"
    assert not stale_in_inventory, f"inventory tests these but the validator no longer raises them: {stale_in_inventory}"


@pytest.mark.parametrize("error_type", sorted(_KNOWN_BAD_IRS))
def test_each_known_error_type_actually_fires_on_its_minimal_bad_input(error_type):
    ir = _KNOWN_BAD_IRS[error_type]()
    result = validate_ir(ir, ASIM_SCHEMA)
    assert result.passed is False
    assert result.error_type == error_type
