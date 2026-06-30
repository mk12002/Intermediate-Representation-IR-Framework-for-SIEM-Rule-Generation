from src.agents.extraction_agent import ExtractionAgent
from src.agents.ir_builder_agent import IRBuilderAgent

from .repair_loop import PipelineResult, run_with_repair


def run_system_b(
    nl_description: str,
    asim_schema: dict,
    extraction_agent: ExtractionAgent,
    ir_builder: IRBuilderAgent,
    max_attempts: int = 3,
    verifier=None,
    verifier_blocking: bool = False,
) -> PipelineResult:
    """End-to-end System B: Extraction Agent -> IR Builder Agent (with repair) -> KQL.

    verifier, if given a VerifierAgent, adds a semantic intent-match check
    after schema validation passes — the one dimension schema/syntax
    validation structurally cannot check. Optional and off by default so
    every existing caller (ablations, ablation-style tests) keeps running
    exactly as before unless it opts in.

    verifier_blocking defaults to False (advisory): measured live
    (PROJECT_STATUS.md §4Q), blocking on the verifier's verdict cost 20+
    points of completion/FVR and 33 points of RRR, almost entirely on the
    join+bin temporal-correlation pattern it systematically misjudges.
    Advisory mode surfaces the same critique as a warning without ever
    failing a case over it. Only set True once that specific failure mode
    has been independently addressed.
    """
    extraction = extraction_agent.extract(nl_description)
    return run_with_repair(
        extraction, asim_schema, ir_builder, max_attempts=max_attempts,
        nl_description=nl_description, verifier=verifier, verifier_blocking=verifier_blocking,
    )
