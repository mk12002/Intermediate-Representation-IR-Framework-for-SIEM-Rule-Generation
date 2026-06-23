import logging
import re
from dataclasses import dataclass
from typing import Optional

from langchain_core.exceptions import OutputParserException
from pydantic import ValidationError

from src.agents.ir_builder_agent import IRBuilderAgent
from src.generator.compiler import generate_kql
from src.ir_engine.ir_schema import ExtractionOutput, SecurityIR
from src.ir_engine.ir_validator import ValidationResult, validate_ir
from src.validation.syntax_validators import validate_kql_syntax

logger = logging.getLogger(__name__)

_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def _extract_unambiguous_number(text: Optional[str]) -> Optional[float]:
    """Return the number in text IF there is exactly one. Multiple numbers
    in the same phrase (e.g. "more than 50 connections over 14 days" has
    both 50 and 14) are too ambiguous to safely guess which one a
    threshold should match, so return None rather than risk a false
    mismatch on the wrong number."""
    if not text:
        return None
    matches = _NUMBER.findall(text)
    if len(matches) != 1:
        return None
    return float(matches[0])


def _check_constraint_traceability(extraction: ExtractionOutput, ir: SecurityIR) -> Optional[ValidationResult]:
    """Schema validation confirms field/value *shapes* are valid; it
    cannot catch a threshold value that silently drifted from what the NL
    actually specified — e.g. the description says "more than 50" and the
    IR ends up with threshold.value=1, both perfectly schema-valid.
    Deliberately conservative: only fires when the extracted
    threshold_language contains exactly one number and the IR disagrees
    with it, to avoid false positives on multi-number descriptions
    (a margin number and a lookback-window number in the same phrase)."""
    if not ir.threshold:
        return None
    expected = _extract_unambiguous_number(extraction.threshold_language)
    if expected is None:
        return None
    if ir.threshold.value != expected:
        return ValidationResult(
            passed=False,
            error_type="THRESHOLD_VALUE_MISMATCH",
            message=(
                f"the description's threshold language "
                f"('{extraction.threshold_language}') specifies {expected}, "
                f"but threshold.value is {ir.threshold.value} — use the "
                f"number the description actually gives, not a "
                f"substitute."
            ),
        )
    return None


@dataclass
class PipelineResult:
    success: bool
    ir: Optional[SecurityIR] = None
    kql: Optional[str] = None
    attempts_used: Optional[int] = None
    reason: Optional[str] = None


def log_template_bug(ir: SecurityIR, kql: str, syntax_validation) -> None:
    logger.error(
        "TEMPLATE_BUG: deterministic KQL generation produced invalid syntax. "
        "ir=%s kql=%r error=%s", ir.model_dump_json(), kql, syntax_validation.message,
    )


def _build_ir(ir_builder, extraction, asim_field_list, repair_error=None, previous_ir=None, temperature_override=None):
    """Wraps the IR Builder Agent call so a malformed-but-structurally-close
    LLM completion (valid JSON that fails Pydantic's own type validation,
    e.g. a null where a typed value is required) is treated as a repairable
    validation failure rather than an uncaught exception — consistent with
    "every validator failure should produce a structured, actionable error."
    Returns (ir_or_None, ValidationResult_or_None).
    """
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
            message=f"model output failed to parse into a valid SecurityIR object: {e}",
        )


def _ir_fingerprint(ir: Optional[SecurityIR]) -> Optional[str]:
    """Return a deterministic fingerprint so we can detect identical repeated
    outputs across repair attempts."""
    if ir is None:
        return None
    return ir.model_dump_json(exclude_none=True)


def run_with_repair(
    extraction: ExtractionOutput,
    asim_schema: dict,
    ir_builder: IRBuilderAgent,
    max_attempts: int = 3,
) -> PipelineResult:
    """Drives the IR Builder Agent against the Schema/Syntax validators.

    Re-prompts only on IR validation failure, never on KQL syntax failure —
    KQL generation is deterministic template substitution, so a syntax
    failure there means the template is wrong, not the IR. See
    docs/NL-KQL/architecture.md#the-repair-loop.

    Temperature escalation: at temperature=0 the model is deterministic, so
    a repeated identical failure means re-prompting with the same temperature
    will reproduce the exact same output.  When we detect two consecutive
    identical outputs (same IR fingerprint or same parse failure), we bump
    temperature on the next attempt to introduce stochasticity.
    """
    # extraction.likely_event_type is deliberately free text (ExtractionOutput
    # is under-constrained — see its docstring), so it rarely matches one of
    # the 7 schema keys exactly (observed: 0/10 on a live MVP sample). Falling
    # back to [] there would hand the IR Builder zero fields while still
    # telling it "only use fields from this reference" — i.e. silently
    # reproduce the No-Schema-Grounding ablation's manipulation on the main
    # path. Fall back to the union of all event types' fields instead; the
    # IR Builder still commits to its own `event_type`, and validate_ir checks
    # fields against that committed type's actual sub-schema regardless of
    # what was shown at generation time.
    if extraction.likely_event_type in asim_schema:
        asim_field_list = asim_schema[extraction.likely_event_type]["fields"]
    else:
        asim_field_list = sorted({f for event in asim_schema.values() for f in event["fields"]})

    ir, build_error = _build_ir(ir_builder, extraction, asim_field_list)
    # None, not the initial build's own fingerprint — there is no prior
    # *repair attempt* yet to compare against. Found live: seeding this from
    # the pre-loop build meant the first loop iteration always compared the
    # initial output's fingerprint to itself (trivially equal), escalating
    # temperature on every single repair sequence's first attempt regardless
    # of whether a genuine repeat occurred — confirmed with a mock that never
    # repeats: it still escalated to 0.3 immediately. The repair prompt's
    # structured-error feedback should get a fair shot at a deterministic
    # fix first; only escalate once two *consecutive* attempts agree.
    prev_fingerprint = None
    temperature_override = None  # Start at model's default (0.0)

    # range(max_attempts + 1), not max_attempts: this validates every build,
    # including the one made on the final repair attempt. Found live: with
    # range(max_attempts), the rebuild made at the end of the *last*
    # iteration was never itself checked before the loop exited — a fully
    # valid IR was silently discarded as MAX_REPAIR_ATTEMPTS_EXCEEDED because
    # nothing ever looked at it. Rebuilds still only happen when attempt <
    # max_attempts, so total model calls are unchanged (1 initial +
    # max_attempts repairs) — this adds a validation check, not a model call.
    for attempt in range(max_attempts + 1):
        if build_error is not None:
            ir_validation = build_error
        else:
            ir_validation = validate_ir(ir, asim_schema)
            if ir_validation.passed:
                traceability_error = _check_constraint_traceability(extraction, ir)
                if traceability_error is not None:
                    ir_validation = traceability_error

        if ir_validation.passed:
            kql = generate_kql(ir)
            syntax_validation = validate_kql_syntax(kql)
            if not syntax_validation.passed:
                log_template_bug(ir, kql, syntax_validation)
                return PipelineResult(success=False, reason="TEMPLATE_BUG", ir=ir, kql=kql)
            return PipelineResult(success=True, ir=ir, kql=kql, attempts_used=attempt + 1)

        if attempt == max_attempts:
            break  # out of rebuild budget

        # Temperature escalation: if the new output is identical to the
        # previous *repair attempt's* output, bumping temperature injects
        # stochasticity so the next attempt has a chance of differing.
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
