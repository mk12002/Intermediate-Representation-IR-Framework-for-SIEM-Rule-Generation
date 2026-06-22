from src.agents.extraction_agent import ExtractionAgent
from src.agents.ir_builder_agent import IRBuilderAgent

from .repair_loop import PipelineResult, run_with_repair


def run_system_b(
    nl_description: str,
    asim_schema: dict,
    extraction_agent: ExtractionAgent,
    ir_builder: IRBuilderAgent,
    max_attempts: int = 3,
) -> PipelineResult:
    """End-to-end System B: Extraction Agent -> IR Builder Agent (with repair) -> KQL."""
    extraction = extraction_agent.extract(nl_description)
    return run_with_repair(extraction, asim_schema, ir_builder, max_attempts=max_attempts)
