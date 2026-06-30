"""A/B compares System B with RAG retrieval OFF vs ON, on the frozen
held-out set (eval/held_out_test.json, 18 rules never used to build the
RAG worked-examples index, the prompt's worked examples, or any tuning
round) — the comparison PROJECT_STATUS.md repeatedly flagged as needed
before RAG could be honestly claimed to help: "RAG built without a
frozen comparison has nothing honest to prove against."

Reports completion (SVR) and field validity (FVR, via eval/metrics.py's
existing implementation) for both conditions, plus the raw generated
KQL for both so a manual logic-correctness spot-check can be done
afterward — this script does not itself score Logic Correctness.

Run (real LLM calls, 2x the held-out set's size):
    PYTHONPATH=. python eval/run_rag_ab.py
"""
import json
import sys

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, ".")

from eval.metrics import field_validity_rate
from src.agents.extraction_agent import ExtractionAgent
from src.agents.ir_builder_agent import IRBuilderAgent
from src.pipeline.system_b import run_system_b

ASIM_SCHEMA = json.loads(open("data/schema/asim_field_reference.json", encoding="utf-8").read())
_KNOWN_FIELDS = {f for event in ASIM_SCHEMA.values() for f in event["fields"]}


def run_condition(use_rag: bool, cases: list) -> dict:
    extraction_agent = ExtractionAgent()
    ir_builder = IRBuilderAgent(use_rag=use_rag)
    results = []
    for case in cases:
        r = run_system_b(case["nl_description"], ASIM_SCHEMA, extraction_agent, ir_builder, max_attempts=3)
        results.append({
            "rule_id": case["rule_id"], "nl": case["nl_description"], "ground_truth_kql": case["ground_truth_kql"],
            "success": r.success, "kql": r.kql, "attempts_used": getattr(r, "attempts_used", None),
        })
        print(f"  [{'RAG' if use_rag else 'base'}] {case['rule_id']}: success={r.success}")
    completed_kqls = [x["kql"] for x in results if x["success"] and x["kql"]]
    svr = sum(x["success"] for x in results) / len(results) * 100
    fvr = field_validity_rate(completed_kqls, _KNOWN_FIELDS) * 100 if completed_kqls else 0.0
    return {"results": results, "svr": svr, "fvr": fvr}


def main():
    cases = json.loads(open("eval/held_out_test.json", encoding="utf-8").read())
    print(f"Running {len(cases)} held-out cases x 2 conditions (base, then RAG)...")

    print("\n=== Condition: base (RAG off, the existing measured default) ===")
    base = run_condition(use_rag=False, cases=cases)

    print("\n=== Condition: RAG on ===")
    rag = run_condition(use_rag=True, cases=cases)

    with open("eval/results/rag_ab_raw.json", "w", encoding="utf-8") as f:
        json.dump({"base": base["results"], "rag": rag["results"]}, f, indent=2)

    print("\n=== Summary ===")
    print(f"base : SVR={base['svr']:.1f}%  FVR={base['fvr']:.1f}%")
    print(f"rag  : SVR={rag['svr']:.1f}%  FVR={rag['fvr']:.1f}%")
    print("\nFull generated KQL saved to eval/results/rag_ab_raw.json for manual logic-correctness review.")


if __name__ == "__main__":
    main()
