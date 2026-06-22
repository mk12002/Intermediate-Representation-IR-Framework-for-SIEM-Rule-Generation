import json
import os
import sys

os.environ.setdefault("LLM_PROVIDER", "ollama")
os.environ.setdefault("EXTRACTION_LLM_MODEL", "qwen3.5:2b")
os.environ.setdefault("IR_BUILDER_LLM_MODEL", "qwen3.5:4b")

from src.agents.extraction_agent import ExtractionAgent
from src.agents.ir_builder_agent import IRBuilderAgent
from src.pipeline.system_b import run_system_b

asim_schema = json.load(open("data/schema/asim_field_reference.json", encoding="utf-8"))
mvp_cases = json.load(open("data/processed/mvp_cases.json", encoding="utf-8"))

extraction_agent = ExtractionAgent()
ir_builder = IRBuilderAgent()

start = int(sys.argv[1]) if len(sys.argv) > 1 else 0
end = int(sys.argv[2]) if len(sys.argv) > 2 else len(mvp_cases)

results = []
for i, case in enumerate(mvp_cases[start:end], start=start):
    nl = case["description_raw"].strip().strip("'")
    print(f"\n===== MVP CASE {i} [{case['complexity_tier']}] {case['rule_id'][:8]} =====", flush=True)
    print("NL:", nl[:200], flush=True)
    try:
        result = run_system_b(nl, asim_schema, extraction_agent, ir_builder, max_attempts=3)
        print("success:", result.success, "attempts_used:", result.attempts_used, "reason:", result.reason, flush=True)
        if result.ir:
            print("IR:", result.ir.model_dump_json(), flush=True)
        if result.kql:
            print("KQL:", result.kql, flush=True)
        results.append({
            "rule_id": case["rule_id"], "tier": case["complexity_tier"], "success": result.success,
            "attempts_used": result.attempts_used, "reason": result.reason,
            "ir": result.ir.model_dump() if result.ir else None, "kql": result.kql,
            "ground_truth_kql": case["query"],
        })
    except Exception as e:
        print("CRASHED:", repr(e), flush=True)
        results.append({"rule_id": case["rule_id"], "tier": case["complexity_tier"], "crashed": str(e)})

with open(f"data/processed/mvp_results_{start}_{end}.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=1)
print("\nDONE")
