"""The clarification resolver: merges user answers to gap-checker
questions back into the IR by reusing the EXISTING repair-loop
plumbing (the IR Builder's own structured-IR-construction ability),
not by hand-mutating the AST.

Why reuse repair, not write AST-mutation code: a hand-written mutator
would need separate, bespoke handling for every gap shape (add a new
WhereStage filter vs. set SummarizeStage.time_window vs. un-abstain a
totally-abstained pipeline and build a real pipeline from scratch).
Routing the answers through one more repair-style rebuild reuses logic
this project has already tested extensively (the same `_build_ir` path
every ordinary validation-error repair takes) and handles new gap
shapes for free, the same engineering judgment this project applied
when it chose worked-example prompting over hand-written field-by-
field IR construction in the first place.

One round only, by explicit design: ask once, take what's answered,
and report whatever gaps remain afterward rather than looping —
the caller decides whether that's good enough or should fall back to
the original (honestly abstained) result.
"""
from typing import Dict, List

from src.agents.ir_builder_agent import IRBuilderAgent
from src.clarification.gap_checker import Gap, find_ambiguities, find_gaps
from src.generator.compiler import generate_kql
from src.ir_engine.ir_schema import Ambiguity, ExtractionOutput, KqlPipeline
from src.ir_engine.ir_validator import ValidationResult, validate_ir
from src.pipeline.repair_loop import PipelineResult, _build_ir
from src.validation.syntax_validators import validate_kql_syntax


def _format_clarification_message(gaps: List[Gap], answers: Dict[str, str]) -> str:
    lines = [
        "The user has answered the following previously-unresolved questions. "
        "Incorporate each answer as a CONCRETE value in the IR (a real filter, "
        "threshold, or time_window) -- do not caveat or omit anything the user "
        "just answered, and do not re-ask about it. If this was the IR's only "
        "reason for abstained=true, set abstained=false and build the real "
        "pipeline; otherwise keep any remaining, still-unanswered caveats as-is."
    ]
    for gap in gaps:
        answer = answers.get(gap.caveat_text)
        if answer is None:
            continue
        lines.append(f'- Previously omitted because: "{gap.caveat_text}" -> user answered: "{answer}"')
    return "\n".join(lines)


_MAX_REBUILD_ATTEMPTS = 2  # the initial instructed rebuild + 1 repair attempt if it's not schema-valid


def _rebuild_with_instruction(
    extraction: ExtractionOutput,
    ir: KqlPipeline,
    error_type: str,
    message: str,
    ir_builder: IRBuilderAgent,
    asim_schema: dict,
) -> PipelineResult:
    """Shared rebuild path for both resolve_clarification (open
    questions, missing info) and resolve_ambiguity (closed questions,
    a chosen-among-multiple fork) -- both are "feed the IR Builder a
    repair-style instruction and re-validate/re-compile," differing
    only in what the instruction says.

    Bounded retry, not a bare single shot: found live (PROJECT_STATUS.md
    §4AG) that a single attempt can hit an ordinary FIELD_NOT_FOUND
    (e.g. un-abstaining into a newly-chosen event type and guessing a
    plausible-but-wrong field name for it) that the NORMAL repair loop
    would simply self-correct on a second attempt -- there's no reason
    a clarification rebuild should be more fragile than an ordinary
    build just because it's one call instead of run_with_repair's full
    loop. Capped at _MAX_REBUILD_ATTEMPTS (small, not the full 3) since
    this is meant to stay a quick "one clarification round," not a
    second complete pipeline run."""
    if extraction.likely_event_type in asim_schema:
        asim_field_list = asim_schema[extraction.likely_event_type]["fields"]
    else:
        asim_field_list = sorted({f for event in asim_schema.values() for f in event["fields"]})

    instruction = ValidationResult(passed=False, error_type=error_type, message=message)
    new_ir, build_error = _build_ir(
        ir_builder, extraction, asim_field_list,
        repair_error=instruction, previous_ir=ir,
    )
    if build_error is not None:
        return PipelineResult(success=False, reason=build_error.error_type, warnings=[build_error.message or ""])

    ir_validation = validate_ir(new_ir, asim_schema)
    attempt = 1
    while not ir_validation.passed and attempt < _MAX_REBUILD_ATTEMPTS:
        new_ir, build_error = _build_ir(
            ir_builder, extraction, asim_field_list,
            repair_error=ir_validation, previous_ir=new_ir,
        )
        if build_error is not None:
            return PipelineResult(success=False, reason=build_error.error_type, warnings=[build_error.message or ""])
        ir_validation = validate_ir(new_ir, asim_schema)
        attempt += 1
    if not ir_validation.passed:
        return PipelineResult(
            success=False, ir=new_ir, reason=ir_validation.error_type,
            warnings=[ir_validation.message or ""],
        )

    kql = generate_kql(new_ir)
    if not new_ir.abstained:
        syntax_validation = validate_kql_syntax(kql)
        if not syntax_validation.passed:
            return PipelineResult(success=False, ir=new_ir, kql=kql, reason="TEMPLATE_BUG")

    remaining_gaps = find_gaps(new_ir)
    remaining_ambiguities = find_ambiguities(new_ir)
    return PipelineResult(
        success=True, ir=new_ir, kql=kql, attempts_used=attempt,
        caveats=list(new_ir.caveats),
        warnings=[g.question for g in remaining_gaps] + [a.description for a in remaining_ambiguities],
    )


def resolve_clarification(
    extraction: ExtractionOutput,
    ir: KqlPipeline,
    gaps: List[Gap],
    answers: Dict[str, str],
    ir_builder: IRBuilderAgent,
    asim_schema: dict,
) -> PipelineResult:
    """Re-invokes the IR Builder with the user's answers merged in as a
    repair-style instruction, then validates and compiles exactly like
    the normal repair loop. Returns a fresh PipelineResult -- the
    caller decides whether to use it over the original result.

    `answers` keys must match a `Gap.caveat_text` exactly (the value
    returned by `find_gaps`) -- unanswered gaps are simply omitted from
    the instruction, so the model knows which of its own caveats are
    still genuinely unresolved."""
    message = _format_clarification_message(gaps, answers)
    return _rebuild_with_instruction(
        extraction, ir, "CLARIFICATION_ANSWERS_PROVIDED", message, ir_builder, asim_schema,
    )


def _format_ambiguity_message(ambiguities: List[Ambiguity], choices: Dict[str, str]) -> str:
    lines = [
        "The user has resolved the following ambiguities you flagged. Rebuild the "
        "pipeline committing FULLY to the chosen option for each -- remove any trace "
        "of the other option(s), and remove the corresponding entry from "
        "`ambiguities` entirely (it is resolved, not still open). Do not re-introduce "
        "the same fork for an ambiguity that isn't in this list."
    ]
    for amb in ambiguities:
        choice = choices.get(amb.description)
        if choice is None:
            continue
        lines.append(f'- Ambiguity: "{amb.description}" -> user chose: "{choice}"')
    return "\n".join(lines)


def resolve_ambiguity(
    extraction: ExtractionOutput,
    ir: KqlPipeline,
    ambiguities: List[Ambiguity],
    choices: Dict[str, str],
    ir_builder: IRBuilderAgent,
    asim_schema: dict,
) -> PipelineResult:
    """The closed-option counterpart to resolve_clarification: instead
    of an open answer to a missing-information question, the user
    picks one of the `options` already offered for a genuine
    structural fork (PROJECT_STATUS.md §4AG). `choices` keys must
    match an `Ambiguity.description` exactly (from `find_ambiguities`);
    values should be one of that ambiguity's own `options` strings."""
    message = _format_ambiguity_message(ambiguities, choices)
    return _rebuild_with_instruction(
        extraction, ir, "AMBIGUITY_RESOLVED", message, ir_builder, asim_schema,
    )
