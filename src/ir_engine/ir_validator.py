import re
from dataclasses import dataclass, field
from typing import Optional

from .ir_schema import AggregationFunction, SecurityIR, ThresholdOperator

_ISO8601_DURATION = re.compile(r"^P(?!$)(\d+D)?(T(?=\d)(\d+H)?(\d+M)?(\d+S)?)?$")

# count()/dcount() can never be < 1 for a group that exists in the
# summarize result — a GT threshold below 1, or a GTE threshold at or
# below 1, is trivially true for every such group and filters nothing.
# Observed live (gpt-4.1-mini, 2026-06-23): "DistinctUserAgents > 1" and
# "ErrorCount >= 1" passed validation while filtering zero rows.
_DEGENERATE_COUNT_FUNCTIONS = {AggregationFunction.COUNT, AggregationFunction.DISTINCT_COUNT}

# Only count() takes zero arguments in KQL — sum/avg/min/max/dcount all
# require a field to operate on. Found live: a baseline-comparison query
# rendered "summarize BaselineCount = avg()" (field left null) — invalid
# KQL, since avg() with no argument doesn't parse.
_FUNCTIONS_REQUIRING_FIELD = {
    AggregationFunction.DISTINCT_COUNT, AggregationFunction.SUM,
    AggregationFunction.AVG, AggregationFunction.MIN, AggregationFunction.MAX,
    AggregationFunction.PERCENTILE, AggregationFunction.MAKE_SET,
    AggregationFunction.MAKE_LIST,
}


def _validate_aggregation_object(aggregation, check_field, label: str) -> Optional["ValidationResult"]:
    """Shared validation for a single Aggregation object — used for the
    main aggregation, each entry in additional_aggregations, and the same
    two on a JoinStage. check_field is the caller's own field-existence
    closure (different schemas for main vs. join stage)."""
    if aggregation is None:
        return None
    if aggregation.field:
        error = check_field(aggregation.field)
        if error:
            return error
    if aggregation.function in _FUNCTIONS_REQUIRING_FIELD and not aggregation.field:
        return ValidationResult(
            passed=False,
            error_type="AGGREGATION_MISSING_FIELD",
            message=(
                f"{label} function '{aggregation.function.value}' requires "
                f"a field — only count() takes zero arguments in KQL. Set "
                f"its field to the column to {aggregation.function.value} over."
            ),
        )
    return _check_percentile_value(aggregation)


def _check_duplicate_aliases(aggregation, additional_aggregations, label: str) -> Optional["ValidationResult"]:
    """summarize X = count(), X = sum(Y) by ... is invalid KQL — duplicate
    column names in the same summarize clause. additional_aggregations
    exists so a detection can compute several columns together (count +
    evidence + timestamps); nothing previously stopped two of them (or one
    of them and the main aggregation) from reusing the same result_alias."""
    if aggregation is None and not additional_aggregations:
        return None
    aliases = ([aggregation.result_alias] if aggregation else []) + [
        a.result_alias for a in additional_aggregations
    ]
    seen = set()
    for alias in aliases:
        if alias in seen:
            return ValidationResult(
                passed=False,
                error_type="DUPLICATE_AGGREGATION_ALIAS",
                message=(
                    f"{label}: result_alias '{alias}' is used more than "
                    f"once across aggregation/additional_aggregations — "
                    f"every column in the same summarize clause needs a "
                    f"distinct alias."
                ),
            )
        seen.add(alias)
    return None


def _check_percentile_value(aggregation) -> Optional["ValidationResult"]:
    """percentile() takes a second argument the other five functions don't
    have — found live: the model substituted min() for "5th percentile of
    frequency" rather than express the percentile itself, which this
    function exists to make expressible. A missing or out-of-[0,100] value
    would render invalid/meaningless KQL the same way a missing field would
    for sum/avg/min/max."""
    if aggregation is None or aggregation.function != AggregationFunction.PERCENTILE:
        return None
    if aggregation.percentile is None or not (0 <= aggregation.percentile <= 100):
        return ValidationResult(
            passed=False,
            error_type="INVALID_PERCENTILE_VALUE",
            message=(
                "aggregation.function is 'percentile' but aggregation.percentile "
                "is missing or out of range — set it to the percentile to "
                "compute, 0-100 (e.g. 95 for the 95th percentile, 5 for the "
                "5th)."
            ),
        )
    return None


def _is_degenerate_count_threshold(aggregation, threshold) -> bool:
    if aggregation.function not in _DEGENERATE_COUNT_FUNCTIONS:
        return False
    if threshold.operator == ThresholdOperator.GT:
        return threshold.value < 1
    if threshold.operator == ThresholdOperator.GTE:
        return threshold.value <= 1
    return False


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
        prev = curr
    return prev[-1]


def closest_match(field: str, candidates: list[str]) -> Optional[str]:
    if not candidates:
        return None
    return min(candidates, key=lambda c: _levenshtein(field.lower(), c.lower()))


@dataclass
class ValidationResult:
    passed: bool
    error_type: Optional[str] = None
    message: Optional[str] = None
    warnings: list[str] = field(default_factory=list)


def _validate_filters_and_fields(
    ir_filters, schema_fields, event_type_label: str,
) -> Optional[ValidationResult]:
    """Validate filter fields, group_by, output_fields, and aggregation.field
    for a given set of filters against a specific schema. Reused for both the
    main IR and the JoinStage."""

    def _check_field(field_name: str) -> Optional[ValidationResult]:
        if field_name not in schema_fields:
            return ValidationResult(
                passed=False,
                error_type="FIELD_NOT_FOUND",
                message=(
                    f"field '{field_name}' not found in schema "
                    f"'{event_type_label}'; closest match: "
                    f"{closest_match(field_name, schema_fields)}"
                ),
            )
        return None

    for f in ir_filters:
        if f.type == "group":
            for c in f.conditions:
                error = _check_field(c.field)
                if error:
                    return error
        else:
            error = _check_field(f.field)
            if error:
                return error
    return None


def validate_ir(ir: SecurityIR, asim_schema: dict) -> ValidationResult:
    """Schema Validator — pure Python, no LLM call.

    Runs checks in order, short-circuiting on the first failure so a
    repair prompt always addresses exactly one issue.
    """
    schema_fields = asim_schema[ir.event_type.value]["fields"]

    def _check_field(field_name: str) -> Optional[ValidationResult]:
        if field_name not in schema_fields:
            return ValidationResult(
                passed=False,
                error_type="FIELD_NOT_FOUND",
                message=(
                    f"field '{field_name}' not found in schema "
                    f"'{ir.event_type.value}'; closest match: "
                    f"{closest_match(field_name, schema_fields)}"
                ),
            )
        return None

    # --- Filter field validation (main IR) ---
    filter_error = _validate_filters_and_fields(
        ir.filters, schema_fields, ir.event_type.value,
    )
    if filter_error:
        return filter_error

    if ir.group_by:
        for gb in ir.group_by:
            error = _check_field(gb)
            if error:
                return error

    if ir.output_fields:
        # Found live: never checked, so a hallucinated field name in the
        # final "| project" clause (e.g. "ParentProcessCommandLine",
        # "DnsQueryTimeDelta" — plausible-sounding, not real ASIM fields)
        # passed IR validation and was only caught downstream by
        # eval/metrics.py's text-level FVR check, undercounting FVR for
        # queries whose filters/group_by were otherwise correct.
        #
        # local_aliases: an aggregation's own result_alias (and, when a
        # join is present, the join's aggregation result_alias) are
        # legitimate self-defined column names, not schema fields — found
        # live, a query projecting its own aggregation alias (e.g.
        # "| summarize FailCount = count() by X | project X, FailCount",
        # completely standard KQL) was rejected as FIELD_NOT_FOUND because
        # this check didn't know about either category.
        local_aliases = set()
        if ir.aggregation:
            local_aliases.add(ir.aggregation.result_alias)
        local_aliases.update(a.result_alias for a in ir.additional_aggregations)
        if ir.join and ir.join.aggregation:
            local_aliases.add(ir.join.aggregation.result_alias)
        local_aliases.update(a.result_alias for a in (ir.join.additional_aggregations if ir.join else []))
        for of in ir.output_fields:
            if of in local_aliases:
                continue
            error = _check_field(of)
            if error:
                return error

    # --- Aggregation field validation (was missing — dcount(FakeField) passed) ---
    agg_error = _validate_aggregation_object(ir.aggregation, _check_field, "aggregation")
    if agg_error:
        return agg_error
    for extra_agg in ir.additional_aggregations:
        agg_error = _validate_aggregation_object(extra_agg, _check_field, "additional_aggregations entry")
        if agg_error:
            return agg_error

    if ir.additional_aggregations and not ir.aggregation:
        return ValidationResult(
            passed=False,
            error_type="ADDITIONAL_AGGREGATIONS_WITHOUT_AGGREGATION",
            message=(
                "additional_aggregations is set but aggregation is null — "
                "additional_aggregations adds extra summarize columns "
                "alongside the main one, so there must be a main aggregation "
                "for them to sit next to."
            ),
        )

    alias_error = _check_duplicate_aliases(ir.aggregation, ir.additional_aggregations, "main IR")
    if alias_error:
        return alias_error

    if ir.aggregation and not ir.time_window:
        return ValidationResult(
            passed=False,
            error_type="MISSING_TIME_WINDOW",
            message=(
                "aggregation present but time_window is null — this "
                "would scan the entire table with no time bound"
            ),
        )

    # --- time_window without aggregation ---
    if ir.time_window and not ir.aggregation:
        return ValidationResult(
            passed=False,
            error_type="TIME_WINDOW_WITHOUT_AGGREGATION",
            message=(
                "time_window is set but aggregation is null — "
                "bin(TimeGenerated, ...) requires a summarize clause "
                "to attach to. Either add an aggregation or remove "
                "the time_window."
            ),
        )

    if ir.time_window and not _ISO8601_DURATION.match(ir.time_window):
        return ValidationResult(
            passed=False,
            error_type="INVALID_TIME_WINDOW",
            message=(
                f"time_window '{ir.time_window}' is not a valid ISO 8601 "
                f"duration (e.g. 'PT5M', 'PT1H', 'P1D')"
            ),
        )

    if ir.threshold and not ir.aggregation:
        # Was a soft warning; promoted to a hard error because the compiler
        # has no left-hand side to render the threshold comparison against
        # without an aggregation result — kql_query.kql.j2's
        # `{{ aggregation.result_alias }}` resolves to empty string on a
        # null aggregation, producing dead KQL like "| where  > 1" that
        # still passes syntax validation (no left operand isn't a grammar
        # error, just a no-op). Observed live during a gpt-4.1-mini MVP run.
        return ValidationResult(
            passed=False,
            error_type="THRESHOLD_WITHOUT_AGGREGATION",
            message=(
                "threshold is set but aggregation is null — there is no "
                "aggregation result for the threshold to compare against. "
                "Either add an aggregation this threshold applies to, or "
                "remove the threshold."
            ),
        )

    if ir.threshold and ir.aggregation and _is_degenerate_count_threshold(ir.aggregation, ir.threshold):
        return ValidationResult(
            passed=False,
            error_type="DEGENERATE_THRESHOLD",
            message=(
                f"threshold '{ir.threshold.operator.value} {ir.threshold.value}' "
                f"on a {ir.aggregation.function.value} aggregation is trivially "
                f"true for every group that exists in the summarize result "
                f"(count/distinct_count is always >= 1 for an existing group) "
                f"— it filters nothing. Use a threshold value that reflects "
                f"the actual quantity described in the detection, or remove "
                f"the threshold entirely if the description gives no real "
                f"number."
            ),
        )

    if ir.threshold and ir.threshold.compare_to_join_field:
        # Found live: a baseline-vs-current detection ("current exceeds the
        # 14-day baseline by more than 50") rendered a join stage that
        # computed the baseline correctly, then a threshold that compared
        # the current count against a bare literal — the join's
        # BaselineAvg column was projected for display but never actually
        # gated the alert, because the IR had no way to express "compare
        # to the joined column" at all. compare_to_join_field closes that
        # gap, but only when it actually names the join's own aggregation.
        if not (ir.join and ir.join.aggregation):
            return ValidationResult(
                passed=False,
                error_type="INVALID_THRESHOLD_JOIN_REFERENCE",
                message=(
                    "threshold.compare_to_join_field is set but there is no "
                    "join stage with an aggregation to compare against — "
                    "either add a join stage with an aggregation, or remove "
                    "compare_to_join_field and use a plain literal threshold."
                ),
            )
        if ir.threshold.compare_to_join_field != ir.join.aggregation.result_alias:
            return ValidationResult(
                passed=False,
                error_type="INVALID_THRESHOLD_JOIN_REFERENCE",
                message=(
                    f"threshold.compare_to_join_field "
                    f"'{ir.threshold.compare_to_join_field}' does not match "
                    f"the join stage's aggregation result_alias "
                    f"'{ir.join.aggregation.result_alias}' — it must "
                    f"reference exactly that column."
                ),
            )

    # --- Join stage validation ---
    if ir.join:
        if ir.join.event_type.value not in asim_schema:
            return ValidationResult(
                passed=False,
                error_type="INVALID_JOIN_EVENT_TYPE",
                message=(
                    f"join stage event_type '{ir.join.event_type.value}' "
                    f"is not a recognized ASIM event type"
                ),
            )

        join_fields = asim_schema[ir.join.event_type.value]["fields"]

        # Validate join stage filter fields
        join_filter_error = _validate_filters_and_fields(
            ir.join.filters, join_fields, ir.join.event_type.value,
        )
        if join_filter_error:
            return join_filter_error

        # Validate join stage group_by fields
        if ir.join.group_by:
            for gb in ir.join.group_by:
                if gb not in join_fields:
                    return ValidationResult(
                        passed=False,
                        error_type="FIELD_NOT_FOUND",
                        message=(
                            f"join stage group_by field '{gb}' not found in "
                            f"schema '{ir.join.event_type.value}'; closest "
                            f"match: {closest_match(gb, join_fields)}"
                        ),
                    )

        # Validate join stage aggregation field(s)
        def _check_join_field(field_name: str) -> Optional[ValidationResult]:
            if field_name not in join_fields:
                return ValidationResult(
                    passed=False,
                    error_type="FIELD_NOT_FOUND",
                    message=(
                        f"join stage aggregation field '{field_name}' "
                        f"not found in schema '{ir.join.event_type.value}'; "
                        f"closest match: {closest_match(field_name, join_fields)}"
                    ),
                )
            return None

        join_agg_error = _validate_aggregation_object(ir.join.aggregation, _check_join_field, "join stage aggregation")
        if join_agg_error:
            return join_agg_error
        for extra_agg in ir.join.additional_aggregations:
            join_agg_error = _validate_aggregation_object(extra_agg, _check_join_field, "join stage additional_aggregations entry")
            if join_agg_error:
                return join_agg_error

        if ir.join.additional_aggregations and not ir.join.aggregation:
            return ValidationResult(
                passed=False,
                error_type="ADDITIONAL_AGGREGATIONS_WITHOUT_AGGREGATION",
                message=(
                    "join stage additional_aggregations is set but "
                    "aggregation is null — additional_aggregations adds "
                    "extra summarize columns alongside the main one."
                ),
            )

        join_alias_error = _check_duplicate_aliases(ir.join.aggregation, ir.join.additional_aggregations, "join stage")
        if join_alias_error:
            return join_alias_error

        # A join-stage aggregation with no time bound scans the subquery's
        # entire table history — the exact problem the main IR's
        # MISSING_TIME_WINDOW check exists to prevent. That check was never
        # mirrored for the join stage: confirmed live, a JoinStage with an
        # aggregation and time_window=None passed validation.
        if ir.join.aggregation and not ir.join.time_window:
            return ValidationResult(
                passed=False,
                error_type="MISSING_TIME_WINDOW",
                message=(
                    "join stage aggregation present but time_window is "
                    "null — this would scan the entire join subquery's "
                    "table with no time bound"
                ),
            )

        # Validate join_on keys exist in both schemas
        for key in ir.join.join_on:
            if key not in schema_fields:
                return ValidationResult(
                    passed=False,
                    error_type="FIELD_NOT_FOUND",
                    message=(
                        f"join_on key '{key}' not found in main schema "
                        f"'{ir.event_type.value}'; closest match: "
                        f"{closest_match(key, schema_fields)}"
                    ),
                )
            if key not in join_fields:
                return ValidationResult(
                    passed=False,
                    error_type="FIELD_NOT_FOUND",
                    message=(
                        f"join_on key '{key}' not found in join schema "
                        f"'{ir.join.event_type.value}'; closest match: "
                        f"{closest_match(key, join_fields)}"
                    ),
                )

        # Validate join stage time_window format
        if ir.join.time_window and not _ISO8601_DURATION.match(ir.join.time_window):
            return ValidationResult(
                passed=False,
                error_type="INVALID_TIME_WINDOW",
                message=(
                    f"join stage time_window '{ir.join.time_window}' is not "
                    f"a valid ISO 8601 duration (e.g. 'PT5M', 'PT1H', 'P1D')"
                ),
            )

    return ValidationResult(passed=True)
