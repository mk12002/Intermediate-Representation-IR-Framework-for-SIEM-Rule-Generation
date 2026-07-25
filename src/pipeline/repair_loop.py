import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from langchain_core.exceptions import OutputParserException
from pydantic import ValidationError

from src.agents.ir_builder_agent import IRBuilderAgent
from src.generator.compiler import generate_kql
from src.ir_engine.ir_schema import ExtractionOutput, KqlPipeline
from src.ir_engine.ir_validator import ValidationResult, validate_ir
from src.validation.syntax_validators import ValidationResult as SyntaxValidationResult, validate_kql_syntax

logger = logging.getLogger(__name__)

_NUMBER = re.compile(r"\d+(?:\.\d+)?")


# The one verifier critique category measured to be unreliable (§4Q):
# every false positive found rejecting a CORRECT join+bin temporal-
# correlation pattern used this exact combination of words ("binning
# before joining can miss a pair across a bin boundary", "groups events
# by a 1-hour time bin before joining, which can mismatch... different
# bins", "uses a 1-hour bin for both events and joins on that bin...
# bin boundary"). Every true positive found (AND/OR confusion, wrong
# event type, wrong field, wrong aggregation) used none of these words
# together. Excluding only this specific combination from blocking lets
# selective blocking capture the real wins (e.g. 7b3ed03a-sop's AND-of-
# OR-sets bug, which no structural validator check can catch) without
# reintroducing the regression blocking everything caused.
_BIN_JOIN_FALSE_POSITIVE_RE = re.compile(
    r"\bbin\b.*\b(boundary|join|joins|joining|bucket)\b|\b(join|joins|joining)\b.*\bbin\b",
    re.IGNORECASE,
)


def _is_known_bin_join_false_positive(issue: str) -> bool:
    return bool(_BIN_JOIN_FALSE_POSITIVE_RE.search(issue))


# Maps the verifier's own 3-check category (verifier_agent.py's
# VerificationResult.category) to a structured error_type name and a
# templated message prefix — the bridge §4S identified as missing: "the
# IR Builder couldn't act on a free-text critique within 3 attempts the
# way it reliably acts on a precise structured validator error." Wrapping
# the verifier's free-text issue in the same named-category style as
# every other structured error (e.g. THRESHOLD_VALUE_MISMATCH) gives the
# repair prompt a clear defect class up front, with the verifier's own
# specific sentence still included as the detail.
_VERIFIER_CATEGORY_ERROR_TYPES = {
    "event_type": "VERIFIER_WRONG_EVENT_TYPE",
    "comparison_direction": "VERIFIER_COMPARISON_DIRECTION_INVERTED",
    "aggregation_grouping": "VERIFIER_AGGREGATION_INTENT_MISMATCH",
    "other": "VERIFIER_SEMANTIC_MISMATCH",
}

_VERIFIER_CATEGORY_PREFIXES = {
    "event_type": "the query runs on the wrong event type/table for what the description describes",
    "comparison_direction": "a comparison or threshold direction does not match the description",
    "aggregation_grouping": "the aggregation or grouping does not match the entity/statistic the description asks for",
    "other": "a semantic mismatch was found between the query and the description",
}


def _format_verifier_validation_error(category: str, issue: str) -> ValidationResult:
    error_type = _VERIFIER_CATEGORY_ERROR_TYPES.get(category, _VERIFIER_CATEGORY_ERROR_TYPES["other"])
    prefix = _VERIFIER_CATEGORY_PREFIXES.get(category, _VERIFIER_CATEGORY_PREFIXES["other"])
    return ValidationResult(
        passed=False,
        error_type=error_type,
        message=f"{prefix}: {issue}" if issue else prefix,
    )


def _extract_unambiguous_number(text: Optional[str]) -> Optional[float]:
    if not text:
        return None
    matches = _NUMBER.findall(text)
    if len(matches) != 1:
        return None
    return float(matches[0])


def _collect_aggregation_aliases(pipeline: KqlPipeline) -> set:
    """All result_alias names introduced by any SummarizeStage in this
    pipeline, including nested join right_pipelines, PLUS every alias
    introduced by an ExtendStage — the fields a threshold-style WhereStage
    filter would actually be checking. Extend aliases matter just as much
    as raw aggregation aliases: a baseline-vs-current or
    percentile-of-aggregates pattern always finishes with an ExtendStage
    computing a derived comparison value (Margin, Deviation, IsRare, ...)
    and the threshold then filters THAT field, not a raw aggregation
    result. Found live: a correct, schema-valid baseline-vs-current IR
    filtering "Margin > 50" was flagged as THRESHOLD_VALUE_MISMATCH because
    "Margin" isn't a SummarizeStage alias — the same false-positive shape
    already fixed once for TopStage.limit and Aggregation.percentile in
    _has_matching_non_filter_number, just for a third construct."""
    aliases = set()
    for stage in pipeline.stages:
        if stage.type == "summarize":
            aliases.update(agg.result_alias for agg in stage.aggregations)
        elif stage.type == "extend":
            aliases.update(comp.alias for comp in stage.computed_fields)
        elif stage.type == "join":
            aliases.update(_collect_aggregation_aliases(stage.right_pipeline))
    return aliases


def _has_matching_non_filter_number(pipeline: KqlPipeline, expected: float) -> bool:
    """A threshold-language number doesn't always belong in a WhereStage
    filter — "top 25 noisiest clients" is a ranking limit (TopStage.limit);
    "at or below the 5th percentile" is a percentile parameter
    (Aggregation.percentile). Found live, twice: the constraint-
    traceability check only looked at WhereStage filters, so fully correct
    IRs using either construct were flagged as false
    THRESHOLD_VALUE_MISMATCH and forced into unnecessary, actively harmful
    repair cycles."""
    for stage in pipeline.stages:
        if stage.type == "top" and float(stage.limit) == expected:
            return True
        if stage.type == "summarize":
            for agg in stage.aggregations:
                if agg.percentile is not None and float(agg.percentile) == expected:
                    return True
        if stage.type == "join" and _has_matching_non_filter_number(stage.right_pipeline, expected):
            return True
    return False


def _check_constraint_traceability(extraction: ExtractionOutput, ir: KqlPipeline) -> Optional[ValidationResult]:
    """Schema validation confirms field/value *shapes* are valid; it
    cannot catch a threshold value that silently drifted from what the
    description specifies (e.g. NL says "more than 50", the IR's where
    stage ends up with 1, both schema-valid). Checks WhereStage filters
    specifically on a known aggregation/extend alias when any aggregation
    or extend stage exists in the pipeline — a filter unrelated to any of
    those that happens to share the same literal number (e.g. a join's
    constant key) must not count as a match. Also accepts a matching
    TopStage.limit, since "top N" is a ranking limit, not a magnitude
    threshold, and correctly compiles to a different stage entirely. Falls
    back to checking any filter only when the pipeline has no aggregation
    or extend stage at all, since there's nothing more specific to anchor
    to. Deliberately conservative: only fires when threshold_language
    contains exactly one number, to avoid false positives on multi-number
    descriptions (a margin and a lookback window in the same phrase)."""
    expected = _extract_unambiguous_number(extraction.threshold_language)
    if expected is None:
        return None

    if _has_matching_non_filter_number(ir, expected):
        return None

    aggregation_aliases = _collect_aggregation_aliases(ir)
    found_match = False
    for stage in ir.stages:
        if stage.type != "where":
            continue
        for f in stage.filters:
            if f.type != "filter":
                continue
            if aggregation_aliases and f.field not in aggregation_aliases:
                continue
            if isinstance(f.value, (int, float)) and not isinstance(f.value, bool) and float(f.value) == expected:
                found_match = True

    if not found_match:
        return ValidationResult(
            passed=False,
            error_type="THRESHOLD_VALUE_MISMATCH",
            message=(
                f"the description's threshold language "
                f"('{extraction.threshold_language}') specifies {expected}, "
                f"but no where-stage filter on an aggregation result checks "
                f"for this exact number — use the number the description "
                f"actually gives, not a substitute."
            ),
        )
    return None


@dataclass
class PipelineResult:
    success: bool
    ir: Optional[KqlPipeline] = None
    kql: Optional[str] = None
    attempts_used: Optional[int] = None
    reason: Optional[str] = None
    warnings: list = field(default_factory=list)
    # The IR Builder's own self-disclosed abstentions (ir.caveats),
    # surfaced separately from warnings (which are verifier-sourced
    # critiques of the result) — see ir_schema.py's KqlPipeline.caveats.
    caveats: list = field(default_factory=list)


def log_template_bug(ir: KqlPipeline, kql: str, syntax_validation) -> None:
    logger.error(
        "TEMPLATE_BUG: deterministic KQL generation produced invalid syntax. "
        "ir=%s kql=%r error=%s", ir.model_dump_json(), kql, syntax_validation.message,
    )


def _build_ir(ir_builder, extraction, asim_field_list, repair_error=None, previous_ir=None, temperature_override=None):
    try:
        ir = ir_builder.build(
            extraction, asim_field_list,
            repair_error=repair_error, previous_ir=previous_ir,
            temperature_override=temperature_override,
        )
        return ir, None
    except (OutputParserException, ValidationError) as e:
        return None, ValidationResult(
            passed=False,
            error_type="LLM_OUTPUT_PARSE_FAILURE",
            message=f"model output failed to parse into a valid KqlPipeline object: {e}",
        )


def _ir_fingerprint(ir: Optional[KqlPipeline]) -> Optional[str]:
    if ir is None:
        return None
    return ir.model_dump_json(exclude_none=True)


def run_with_repair(
    extraction: ExtractionOutput,
    asim_schema: dict,
    ir_builder: IRBuilderAgent,
    max_attempts: int = 3,
    nl_description: Optional[str] = None,
    verifier=None,
    verifier_blocking: bool = False,
) -> PipelineResult:
    if extraction.likely_event_type in asim_schema:
        asim_field_list = asim_schema[extraction.likely_event_type]["fields"]
    else:
        asim_field_list = sorted({f for event in asim_schema.values() for f in event["fields"]})

    ir, build_error = _build_ir(ir_builder, extraction, asim_field_list)
    prev_fingerprint = None
    temperature_override = None

    for attempt in range(max_attempts + 1):
        if build_error is not None:
            ir_validation = build_error
        else:
            ir_validation = validate_ir(ir, asim_schema, nl_description=nl_description)
            if ir_validation.passed:
                traceability_error = _check_constraint_traceability(extraction, ir)
                if traceability_error is not None:
                    ir_validation = traceability_error

        if ir_validation.passed:
            kql = generate_kql(ir)
            # §4AE: an abstained pipeline's "kql" is deliberately a
            # comment, not a runnable query (generate_kql refuses to
            # emit one on purpose) — running it through validate_kql_syntax
            # would always fail ("no table reference found") and get
            # misclassified as a TEMPLATE_BUG, since that check exists to
            # catch the compiler accidentally emitting bad KQL for a
            # REAL query, not to validate intentionally-non-executable
            # abstention output.
            syntax_validation = validate_kql_syntax(kql) if not ir.abstained else SyntaxValidationResult(passed=True)
            if not syntax_validation.passed:
                log_template_bug(ir, kql, syntax_validation)
                return PipelineResult(success=False, reason="TEMPLATE_BUG", ir=ir, kql=kql)

            if verifier is not None:
                verification = verifier.verify(nl_description or "", kql)
                issue = verification.issue or ""
                should_block = (
                    verifier_blocking
                    and not verification.matches_intent
                    and not _is_known_bin_join_false_positive(issue)
                )
                if should_block:
                    ir_validation = _format_verifier_validation_error(verification.category, issue)
                else:
                    warnings = list(ir_validation.warnings)
                    if not verification.matches_intent:
                        # Advisory mode (the default — see PROJECT_STATUS.md
                        # §4Q): measured live, blocking on EVERY verdict cost
                        # 20+ points of completion/FVR and 33 points of RRR,
                        # almost entirely on the join+bin temporal-
                        # correlation pattern the verifier systematically
                        # misjudges despite explicit leniency instructions.
                        # §4S: selective blocking excludes exactly that
                        # pattern (_is_known_bin_join_false_positive) and
                        # blocks everything else — a critique that reaches
                        # this branch is either advisory mode entirely, or
                        # blocking mode's one known-unreliable category.
                        # Surfacing it as a warning either way keeps the
                        # signal visible without forcing a repair cycle that
                        # can't be won.
                        warnings.append(f"verifier flagged a possible issue (not blocking): {issue}")
                    return PipelineResult(
                        success=True, ir=ir, kql=kql, attempts_used=attempt + 1,
                        warnings=warnings, caveats=ir.caveats,
                    )
            else:
                return PipelineResult(
                    success=True, ir=ir, kql=kql, attempts_used=attempt + 1,
                    warnings=ir_validation.warnings, caveats=ir.caveats,
                )

        if attempt == max_attempts:
            break

        current_fp = _ir_fingerprint(ir) if build_error is None else f"PARSE_FAIL:{build_error.message}"
        if prev_fingerprint is not None and current_fp == prev_fingerprint:
            if temperature_override is None:
                temperature_override = 0.3
                logger.info("identical output on attempt %d — escalating temperature to %.1f", attempt + 1, temperature_override)
            else:
                temperature_override = min(temperature_override + 0.3, 0.7)
                logger.info("still identical on attempt %d — escalating temperature to %.1f", attempt + 1, temperature_override)
        prev_fingerprint = current_fp

        ir, build_error = _build_ir(
            ir_builder, extraction, asim_field_list,
            repair_error=ir_validation, previous_ir=ir,
            temperature_override=temperature_override,
        )

    return PipelineResult(success=False, reason="MAX_REPAIR_ATTEMPTS_EXCEEDED", ir=ir)
