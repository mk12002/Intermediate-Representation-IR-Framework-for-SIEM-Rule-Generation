"""Primary System A vs. System B comparison on the held-out test split.

Requires data/processed/pairs.jsonl and data/splits/test_ids.json to exist
(Phase 1 — dataset construction) and data/schema/asim_field_reference.json
(Phase 1 — ASIM schema extraction). Not runnable until those are built.
"""
import json
import logging
from pathlib import Path

from src.agents.extraction_agent import ExtractionAgent
from src.agents.ir_builder_agent import IRBuilderAgent
from src.baseline.few_shot_examples import FEW_SHOT_EXAMPLE_1, FEW_SHOT_EXAMPLE_2
from src.baseline.run import BaselineRunner
from src.pipeline.system_b import run_system_b

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
RESULTS_DIR = Path(__file__).parent / "results" / "primary"


def load_test_pairs() -> list[dict]:
    test_ids = set(json.loads((DATA_DIR / "splits" / "test_ids.json").read_text()))
    pairs = []
    with (DATA_DIR / "processed" / "pairs.jsonl").open(encoding="utf-8") as f:
        for line in f:
            pair = json.loads(line)
            if pair["rule_id"] in test_ids:
                pairs.append(pair)
    return pairs


def run_one_pair(pair, asim_schema, baseline, extraction_agent, ir_builder) -> dict:
    base = {
        "pair_id": pair["pair_id"],
        "complexity_tier": pair["complexity_tier"],
        "ground_truth_kql": pair["ground_truth_kql"],
    }
    try:
        system_a_kql = baseline.run(
            nl_description=pair["nl_description"],
            asim_field_reference=json.dumps(asim_schema.get(pair["asim_event_type"], {})),
            few_shot_example_1=f"{FEW_SHOT_EXAMPLE_1['nl_description']}\n{FEW_SHOT_EXAMPLE_1['kql']}",
            few_shot_example_2=f"{FEW_SHOT_EXAMPLE_2['nl_description']}\n{FEW_SHOT_EXAMPLE_2['kql']}",
        )
    except Exception as e:
        logger.warning("System A crashed on %s: %s", pair["pair_id"], e)
        system_a_kql = None
        base["system_a_error"] = str(e)

    try:
        system_b_result = run_system_b(pair["nl_description"], asim_schema, extraction_agent, ir_builder)
        base.update(
            system_b_kql=system_b_result.kql,
            system_b_success=system_b_result.success,
            system_b_attempts_used=system_b_result.attempts_used,
            system_b_reason=system_b_result.reason,
        )
    except Exception as e:
        logger.warning("System B crashed on %s: %s", pair["pair_id"], e)
        base.update(system_b_kql=None, system_b_success=False, system_b_error=str(e))

    base["system_a_kql"] = system_a_kql
    return base


def main() -> None:
    asim_schema = json.loads((DATA_DIR / "schema" / "asim_field_reference.json").read_text())
    pairs = load_test_pairs()

    baseline = BaselineRunner()
    extraction_agent = ExtractionAgent()
    ir_builder = IRBuilderAgent()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "comparison_raw.jsonl"

    results = []
    with out_path.open("w", encoding="utf-8") as f:
        for i, pair in enumerate(pairs):
            print(f"[{i + 1}/{len(pairs)}] {pair['pair_id']}", flush=True)
            result = run_one_pair(pair, asim_schema, baseline, extraction_agent, ir_builder)
            results.append(result)
            f.write(json.dumps(result) + "\n")
            f.flush()

    print(f"ran {len(results)} test pairs through System A and System B")


if __name__ == "__main__":
    main()
