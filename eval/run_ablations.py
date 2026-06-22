"""The 3 ablations — docs/NL-KQL/MASTER_PLAN.md §18. Same data prerequisites
as run_comparison.py (Phase 1 dataset construction must be complete first).
"""
import json
from pathlib import Path

from src.agents.extraction_agent import ExtractionAgent
from src.agents.ir_builder_agent import IRBuilderAgent
from src.agents.monolithic_agent import MonolithicAgent
from src.generator.compiler import generate_kql
from src.ir_engine.ir_validator import validate_ir
from src.pipeline.repair_loop import run_with_repair
from src.pipeline.system_b import run_system_b

DATA_DIR = Path(__file__).parent.parent / "data"
RESULTS_DIR = Path(__file__).parent / "results" / "ablations"


def load_test_pairs() -> list[dict]:
    test_ids = set(json.loads((DATA_DIR / "splits" / "test_ids.json").read_text()))
    pairs = []
    with (DATA_DIR / "processed" / "pairs.jsonl").open(encoding="utf-8") as f:
        for line in f:
            pair = json.loads(line)
            if pair["rule_id"] in test_ids:
                pairs.append(pair)
    return pairs


def ablation_no_repair(pairs, asim_schema, extraction_agent, ir_builder):
    return [
        run_system_b(p["nl_description"], asim_schema, extraction_agent, ir_builder, max_attempts=1)
        for p in pairs
    ]


def ablation_monolithic_extraction(pairs, asim_schema, monolithic_agent):
    results = []
    for p in pairs:
        fields = asim_schema.get(p["asim_event_type"], {}).get("fields", [])
        ir = monolithic_agent.build(p["nl_description"], fields)
        validation = validate_ir(ir, asim_schema)
        kql = generate_kql(ir) if validation.passed else None
        results.append({"pair_id": p["pair_id"], "ir_valid": validation.passed, "kql": kql})
    return results


def ablation_no_schema_grounding(pairs, asim_schema, extraction_agent, ir_builder):
    """IR Builder receives an empty field reference — selects fields from
    its own training knowledge, same as a vanilla LLM would."""
    results = []
    for p in pairs:
        extraction = extraction_agent.extract(p["nl_description"])
        ir = ir_builder.build(extraction, asim_field_list=[])
        validation = validate_ir(ir, asim_schema)
        kql = generate_kql(ir) if validation.passed else None
        results.append({"pair_id": p["pair_id"], "ir_valid": validation.passed, "kql": kql})
    return results


def main() -> None:
    asim_schema = json.loads((DATA_DIR / "schema" / "asim_field_reference.json").read_text())
    pairs = load_test_pairs()

    extraction_agent = ExtractionAgent()
    ir_builder = IRBuilderAgent()
    monolithic_agent = MonolithicAgent()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    no_repair = ablation_no_repair(pairs, asim_schema, extraction_agent, ir_builder)
    (RESULTS_DIR / "no_repair.jsonl").write_text(
        "\n".join(json.dumps({"success": r.success, "kql": r.kql}) for r in no_repair),
        encoding="utf-8",
    )

    monolithic = ablation_monolithic_extraction(pairs, asim_schema, monolithic_agent)
    (RESULTS_DIR / "monolithic_extraction.jsonl").write_text(
        "\n".join(json.dumps(r) for r in monolithic), encoding="utf-8"
    )

    no_grounding = ablation_no_schema_grounding(pairs, asim_schema, extraction_agent, ir_builder)
    (RESULTS_DIR / "no_schema_grounding.jsonl").write_text(
        "\n".join(json.dumps(r) for r in no_grounding), encoding="utf-8"
    )

    print(f"ran 3 ablations over {len(pairs)} test pairs")


if __name__ == "__main__":
    main()
