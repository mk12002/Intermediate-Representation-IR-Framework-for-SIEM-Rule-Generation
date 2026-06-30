"""Closes the reverse-generation loop end to end (PROJECT_STATUS.md §4Z):

  generate IR (ir_generator) -> compile to KQL (deterministic, already
  valid) -> back-translate to NL (back_translate) -> feed the NL through
  the REAL system (extraction + IR builder) -> execution-validate the
  SYSTEM's regenerated IR against the SAME auto-generated should-fire/
  should-not-fire fixtures (fixture_generator + ir_interpreter).

This produces an execution-validated accuracy number PER CONSTRUCT
TEMPLATE — the column CONSTRUCT_COVERAGE.md mostly still marks
"Untested" — without hand-writing a rubric or a fixture per case.
Defaults to generate_mixed_batch (single-construct + 2-3-construct
CHAINS) rather than single-construct templates alone: real failures
live at the seams between constructs, not inside any one of them in
isolation (found live via the let-subqueries fixturability check,
which surfaced that real ground truth's hardest shapes are
compositions, not individual stages) — use --single-only to restrict
to the original single-construct pool for a direct before/after
comparison against earlier rounds.

Cost/latency tracking (per query, via langchain_community's OpenAI
token-usage callback — works for any ChatOpenAI-compatible provider,
including azure_foundry, since both ride the same client under the
hood; PROJECT_STATUS.md §4Z): every accuracy gain so far has come from
longer prompts and more repair attempts, and nobody had measured what
that costs. Logged per query and summarized at the end so the eventual
claim is "N% accurate at M seconds / K tokens per rule," not just N%.

Run as a script (real LLM calls — back-translation + the full system):
    PYTHONPATH=. python src/synthesis/run_synthesis_eval.py [n] [seed] [--single-only] [--combo-fraction=F]

--combo-fraction (default 0.5, ignored with --single-only): the
per-draw probability of a combination (2-3 construct chain) template.
Real failures live at construct SEAMS, not inside any one construct in
isolation (the field_ref gap, §4AA, was found exactly this way) — a
combination-weighted batch is a more efficient way to spend a fixed
eval budget hunting for the next seam-only gap than an even 50/50 split.
"""
import json
import sys
import time

from dotenv import load_dotenv

load_dotenv()

from langchain_community.callbacks import get_openai_callback

from src.agents.extraction_agent import ExtractionAgent
from src.agents.ir_builder_agent import IRBuilderAgent
from src.execution.ir_interpreter import pipeline_fires
from src.generator.compiler import generate_kql
from src.pipeline.system_b import run_system_b
from src.synthesis.back_translate import BackTranslator
from src.synthesis.fixture_generator import should_fire_rows, should_not_fire_rows
from src.synthesis.ir_generator import generate_batch, generate_mixed_batch


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    single_only = "--single-only" in sys.argv
    style = "terse" if "--terse" in sys.argv else "rich"
    n = int(args[0]) if len(args) > 0 else 30
    seed = int(args[1]) if len(args) > 1 else 42
    combo_fraction = 0.5
    for a in sys.argv[1:]:
        if a.startswith("--combo-fraction="):
            combo_fraction = float(a.split("=", 1)[1])

    asim_schema = json.loads(open("data/schema/asim_field_reference.json", encoding="utf-8").read())
    extraction_agent = ExtractionAgent()
    ir_builder = IRBuilderAgent()
    translator = BackTranslator()

    batch = generate_batch(n, seed=seed) if single_only else generate_mixed_batch(n, seed=seed, combination_fraction=combo_fraction)
    per_template = {}
    rows_out = []

    for i, (gen_ir, meta) in enumerate(batch):
        gen_kql = generate_kql(gen_ir)
        nl = translator.translate(gen_kql, meta, style=style)

        t0 = time.perf_counter()
        with get_openai_callback() as cb:
            result = run_system_b(nl, asim_schema, extraction_agent, ir_builder, max_attempts=3)
        elapsed_s = time.perf_counter() - t0

        stats = per_template.setdefault(meta.template, {
            "n": 0, "completed": 0, "fire_ok": 0, "fire_total": 0,
            "nofire_ok": 0, "nofire_total": 0, "field_mismatch": 0,
            "total_tokens": 0, "elapsed_s": 0.0,
        })
        stats["n"] += 1
        stats["total_tokens"] += cb.total_tokens
        stats["elapsed_s"] += elapsed_s

        record = {
            "template": meta.template, "nl": nl, "generated_kql": gen_kql, "system_kql": result.kql,
            "completed": result.success, "total_tokens": cb.total_tokens, "elapsed_s": round(elapsed_s, 2),
        }

        if result.success and result.ir is not None:
            stats["completed"] += 1
            # Field-identity decoupling: build the fixture around
            # whichever field the SYSTEM'S OWN IR actually uses for
            # templates where that field's name carries no semantic
            # weight of its own (see fixture_generator.py's module
            # docstring) — found live in the first synthesis eval run
            # that NOT doing this scored a correct, differently-named
            # query as a crash, not a logic check.
            fire_rows = should_fire_rows(meta, system_ir=result.ir)
            no_fire_rows = should_not_fire_rows(meta, system_ir=result.ir)
            # A residual field_mismatch can still occur for templates
            # where field identity IS the semantic content under test
            # (e.g. simple_filter) or when the system's IR lacks the
            # expected stage entirely — a real, distinct outcome, not a
            # crash to suppress silently.
            try:
                if fire_rows:
                    stats["fire_total"] += 1
                    ok = pipeline_fires(result.ir, fire_rows)
                    stats["fire_ok"] += int(ok)
                    record["fire_ok"] = ok
                if no_fire_rows:
                    stats["nofire_total"] += 1
                    ok = not pipeline_fires(result.ir, no_fire_rows)
                    stats["nofire_ok"] += int(ok)
                    record["nofire_ok"] = ok
            except (KeyError, ValueError) as e:
                stats["field_mismatch"] += 1
                record["field_mismatch"] = str(e)

        rows_out.append(record)
        print(
            f"[{i+1}/{n}] {meta.template}: completed={result.success} fire_ok={record.get('fire_ok')} "
            f"nofire_ok={record.get('nofire_ok')} tokens={cb.total_tokens} elapsed_s={elapsed_s:.1f}"
        )

    with open("eval/results/synthesis_eval_raw.jsonl", "w", encoding="utf-8") as f:
        for r in rows_out:
            f.write(json.dumps(r) + "\n")

    print("\n=== per-construct-template execution-validated accuracy ===")
    for template, s in sorted(per_template.items()):
        completion_pct = s["completed"] / s["n"] * 100 if s["n"] else 0
        fire_pct = s["fire_ok"] / s["fire_total"] * 100 if s["fire_total"] else float("nan")
        nofire_pct = s["nofire_ok"] / s["nofire_total"] * 100 if s["nofire_total"] else float("nan")
        avg_tokens = s["total_tokens"] / s["n"] if s["n"] else 0
        avg_s = s["elapsed_s"] / s["n"] if s["n"] else 0
        print(
            f"{template:28s} n={s['n']:3d} completion={completion_pct:5.1f}%  "
            f"fire={fire_pct:5.1f}%  nofire={nofire_pct:5.1f}%  field_mismatch={s['field_mismatch']}  "
            f"avg_tokens={avg_tokens:6.0f}  avg_s={avg_s:4.1f}"
        )

    total_n = sum(s["n"] for s in per_template.values())
    total_tokens = sum(s["total_tokens"] for s in per_template.values())
    total_s = sum(s["elapsed_s"] for s in per_template.values())
    print(f"\noverall: n={total_n}  avg_tokens={total_tokens / total_n:.0f}  avg_elapsed_s={total_s / total_n:.1f}  total_elapsed_s={total_s:.0f}")


if __name__ == "__main__":
    main()
