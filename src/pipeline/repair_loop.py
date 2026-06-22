import logging
from dataclasses import dataclass
from typing import Optional

from src.agents.ir_builder_agent import IRBuilderAgent
from src.generator.compiler import generate_kql
from src.ir_engine.ir_schema import ExtractionOutput, SecurityIR
from src.ir_engine.ir_validator import validate_ir
from src.validation.syntax_validators import validate_kql_syntax

logger = logging.getLogger(__name__)


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
    """
    asim_field_list = asim_schema[extraction.likely_event_type]["fields"] if extraction.likely_event_type in asim_schema else []
    ir = ir_builder.build(extraction, asim_field_list)
    repair_error = None

    for attempt in range(max_attempts):
        ir_validation = validate_ir(ir, asim_schema)
        if not ir_validation.passed:
            repair_error = ir_validation
            ir = ir_builder.build(extraction, asim_field_list, repair_error=repair_error, previous_ir=ir)
            continue

        kql = generate_kql(ir)
        syntax_validation = validate_kql_syntax(kql)
        if not syntax_validation.passed:
            log_template_bug(ir, kql, syntax_validation)
            return PipelineResult(success=False, reason="TEMPLATE_BUG", ir=ir, kql=kql)

        return PipelineResult(success=True, ir=ir, kql=kql, attempts_used=attempt + 1)

    return PipelineResult(success=False, reason="MAX_REPAIR_ATTEMPTS_EXCEEDED", ir=ir)
