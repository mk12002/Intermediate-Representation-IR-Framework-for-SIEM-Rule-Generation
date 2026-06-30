"""The 3 ablations — docs/NL-KQL/MASTER_PLAN.md §18. Same data prerequisites
as run_comparison.py (Phase 1 dataset construction must be complete first).
"""
import json
import logging
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from src.agents.extraction_agent import ExtractionAgent
from src.agents.ir_builder_agent import IRBuilderAgent
from src.agents.monolithic_agent import MonolithicAgent
from src.generator.compiler import generate_kql
from src.ir_engine.ir_validator import validate_ir
from src.pipeline.system_b import run_system_b

logger = logging.getLogger(__name__)

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
    results = []
    for p in pairs:
        try:
            # max_attempts=0, not 1: with the repair loop's off-by-one fix
            # (every build is now validated, including the last), passing 1
            # here would grant one genuine, validated repair attempt instead
            # of measuring true zero-repair first-attempt success. 0 means
            # exactly one build, checked once, never rebuilt.
            r = run_system_b(p["nl_description"], asim_schema, extraction_agent, ir_builder, max_attempts=0)
            results.append({"pair_id": p["pair_id"], "success": r.success, "kql": r.kql})
        except Exception as e:
            logger.warning("no_repair ablation crashed on %s: %s", p["pair_id"], e)
            results.append({"pair_id": p["pair_id"], "success": False, "kql": None, "error": str(e)})
    return results


def ablation_monolithic_extraction(pairs, asim_schema, monolithic_agent):
    results = []
    for p in pairs:
        try:
            # Use union-fallback, same as repair_loop.py — falling back to []
            # would silently reproduce the No-Schema-Grounding ablation (§1.4 item 14).
            event_type_key = p.get("asim_event_type", "")
            if event_type_key in asim_schema:
                fields = asim_schema[event_type_key]["fields"]
            else:
                fields = sorted({f for event in asim_schema.values() for f in event["fields"]})
            ir = monolithic_agent.build(p["nl_description"], fields)
            validation = validate_ir(ir, asim_schema)
            kql = generate_kql(ir) if validation.passed else None
            results.append({"pair_id": p["pair_id"], "ir_valid": validation.passed, "kql": kql})
        except Exception as e:
            logger.warning("monolithic ablation crashed on %s: %s", p["pair_id"], e)
            results.append({"pair_id": p["pair_id"], "ir_valid": False, "kql": None, "error": str(e)})
    return results


def ablation_no_schema_grounding(pairs, asim_schema, extraction_agent, ir_builder):
    """IR Builder receives an empty field reference — selects fields from
    its own training knowledge, same as a vanilla LLM would."""
    results = []
    for p in pairs:
        try:
            extraction = extraction_agent.extract(p["nl_description"])
            ir = ir_builder.build(extraction, asim_field_list=[])
            validation = validate_ir(ir, asim_schema)
            kql = generate_kql(ir) if validation.passed else None
            results.append({"pair_id": p["pair_id"], "ir_valid": validation.passed, "kql": kql})
        except Exception as e:
            logger.warning("no_schema_grounding ablation crashed on %s: %s", p["pair_id"], e)
            results.append({"pair_id": p["pair_id"], "ir_valid": False, "kql": None, "error": str(e)})
    return results


def main() -> None:
    asim_schema = json.loads((DATA_DIR / "schema" / "asim_field_reference.json").read_text())
    pairs = load_test_pairs()

    extraction_agent = ExtractionAgent()
    ir_builder = IRBuilderAgent()
    monolithic_agent = MonolithicAgent()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"running no_repair ablation over {len(pairs)} pairs...", flush=True)
    no_repair = ablation_no_repair(pairs, asim_schema, extraction_agent, ir_builder)
    (RESULTS_DIR / "no_repair.jsonl").write_text(
        "\n".join(json.dumps(r) for r in no_repair), encoding="utf-8"
    )

    print(f"running monolithic_extraction ablation over {len(pairs)} pairs...", flush=True)
    monolithic = ablation_monolithic_extraction(pairs, asim_schema, monolithic_agent)
    (RESULTS_DIR / "monolithic_extraction.jsonl").write_text(
        "\n".join(json.dumps(r) for r in monolithic), encoding="utf-8"
    )

    print(f"running no_schema_grounding ablation over {len(pairs)} pairs...", flush=True)
    no_grounding = ablation_no_schema_grounding(pairs, asim_schema, extraction_agent, ir_builder)
    (RESULTS_DIR / "no_schema_grounding.jsonl").write_text(
        "\n".join(json.dumps(r) for r in no_grounding), encoding="utf-8"
    )

    print(f"ran 3 ablations over {len(pairs)} test pairs")


if __name__ == "__main__":
    main()
