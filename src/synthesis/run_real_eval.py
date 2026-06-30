"""Runs the project's existing hand-built REAL ground-truth cases
(tests/integration/test_live_e2e_execution_validation.py) through the
same execution-validated metric the synthesis eval uses, producing a
directly comparable real-accuracy number alongside the synthetic-
accuracy one (PROJECT_STATUS.md §4Z follow-up).

Why these 5 specific cases: they are this project's only real (not
generator-produced) NL descriptions that already have hand-built,
multi-axis should-fire/should-not-fire fixtures — built BEFORE this
script existed, for a different purpose (regression anchoring), so
using them here is not circular (they weren't tuned against this
metric). Each is repeated several times since the system is not fully
deterministic even at temperature 0 (PROJECT_STATUS.md §4T).

Run as a script (real LLM calls):
    PYTHONPATH=. python src/synthesis/run_real_eval.py [reps]
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
from src.pipeline.system_b import run_system_b

_CASES = [
    {
        "name": "lolbin_recycle_bin",
        "nl": "Identifies malware that has been hidden in the recycle bin.",
        "fire": [{
            "CommandLine": "C:\\RECYCLER\\$Recycle.Bin\\S-1-5-21\\svchost.exe", "Process": "svchost.exe",
            "ProcessCommandLine": "C:\\RECYCLER\\$Recycle.Bin\\S-1-5-21\\svchost.exe", "TargetFilename": "svchost.exe",
            "FilePath": "C:\\RECYCLER\\$Recycle.Bin\\S-1-5-21\\svchost.exe", "ActingProcessName": "svchost.exe",
            "FileName": "svchost.exe",
        }],
        "nofire": [{
            "CommandLine": "C:\\Program Files\\Notepad++\\notepad++.exe readme.txt", "Process": "notepad++.exe",
            "ProcessCommandLine": "C:\\Program Files\\Notepad++\\notepad++.exe readme.txt",
            "TargetFilename": "notepad++.exe", "FilePath": "C:\\Program Files\\Notepad++\\notepad++.exe",
            "ActingProcessName": "notepad++.exe", "FileName": "notepad++.exe",
        }],
    },
    {
        "name": "sdelete_evasion",
        "nl": (
            "This detection looks for command line parameters associated with the use of Sysinternals "
            "sdelete to delete multiple files on a host's C drive. A threat actor may re-name the tool "
            "to avoid detection."
        ),
        "fire": [{
            "CommandLine": "svc_update.exe -accepteula -s -r -q C:\\Users\\victim\\Documents",
            "ProcessCommandLine": "svc_update.exe -accepteula -s -r -q C:\\Users\\victim\\Documents",
            "Process": "svc_update.exe", "ActingProcessName": "svc_update.exe",
        }],
        "nofire": [{
            "CommandLine": "sdelete.exe -accepteula -s -r -q C:\\Users\\victim\\Documents",
            "ProcessCommandLine": "sdelete.exe -accepteula -s -r -q C:\\Users\\victim\\Documents",
            "Process": "sdelete.exe", "ActingProcessName": "sdelete.exe",
        }],
    },
    {
        "name": "dga_anomaly",
        "nl": (
            "This rule makes use of the series decompose anomaly method to detect clients with a high "
            "NXDomain response count, which could be indicative of a DGA. An alert is generated when "
            "new IP address DNS activity is identified as an outlier when compared to the baseline."
        ),
        "fire": (
            [{"DnsResponseCodeName": "NXDOMAIN", "DnsQueryTypeName": "NXDOMAIN", "SrcIpAddr": "10.0.0.7",
              "TimeGenerated": f"2026-06-{17+i}T12:00:00Z", "DnsQuery": "stable-domain.invalid"}
             for i in range(6) for _ in range(2)]
            + [{"DnsResponseCodeName": "NXDOMAIN", "DnsQueryTypeName": "NXDOMAIN", "SrcIpAddr": "10.0.0.7",
                "TimeGenerated": "2026-06-23T12:00:00Z", "DnsQuery": f"dga{i:03d}.invalid"}
               for i in range(40)]
        ),
        "nofire": [
            {"DnsResponseCodeName": "NXDOMAIN", "DnsQueryTypeName": "NXDOMAIN", "SrcIpAddr": "10.0.0.7",
             "TimeGenerated": f"2026-06-{17+i}T12:00:00Z", "DnsQuery": "stable-domain.invalid"}
            for i in range(7) for _ in range(2)
        ],
    },
    {
        "name": "or_list_url_extensions",
        "nl": (
            "This rule detects web requests made to URLs containing file types such as .ps1, .bat, "
            ".vbs, .scr etc. which have the potential to be harmful if downloaded."
        ),
        "fire": [{"Url": "http://evil.example.com/payload.ps1"}],
        "nofire": [{"Url": "http://contoso.com/report.pdf"}],
    },
    {
        "name": "cve_id_not_literal",
        "nl": (
            "This hunting query looks for potential command injection attempts via the vulnerable "
            "third-party driver against Azure IR with Managed VNet or SHIR processes. "
            "Reference: CVE-2022-29972."
        ),
        "fire": None,  # no realistic fire fixture for this one (its NL doesn't specify the exploit's own command syntax) — nofire-only check
        "nofire": [{"CommandLine": "powershell -enc CVE-2022-29972 exploit.ps1"}],
    },
]


def main():
    reps = int(sys.argv[1]) if len(sys.argv) > 1 else 5

    asim_schema = json.loads(open("data/schema/asim_field_reference.json", encoding="utf-8").read())
    extraction_agent = ExtractionAgent()
    ir_builder = IRBuilderAgent()

    per_case = {}
    rows_out = []
    total = len(_CASES) * reps
    i = 0

    for case in _CASES:
        stats = per_case.setdefault(case["name"], {
            "n": 0, "completed": 0, "fire_ok": 0, "fire_total": 0,
            "nofire_ok": 0, "nofire_total": 0, "total_tokens": 0, "elapsed_s": 0.0,
        })
        for _ in range(reps):
            i += 1
            t0 = time.perf_counter()
            with get_openai_callback() as cb:
                result = run_system_b(case["nl"], asim_schema, extraction_agent, ir_builder, max_attempts=3)
            elapsed_s = time.perf_counter() - t0

            stats["n"] += 1
            stats["total_tokens"] += cb.total_tokens
            stats["elapsed_s"] += elapsed_s
            record = {"case": case["name"], "completed": result.success, "total_tokens": cb.total_tokens, "elapsed_s": round(elapsed_s, 2)}

            if result.success and result.ir is not None:
                stats["completed"] += 1
                if case["fire"]:
                    stats["fire_total"] += 1
                    ok = pipeline_fires(result.ir, case["fire"])
                    stats["fire_ok"] += int(ok)
                    record["fire_ok"] = ok
                if case["nofire"]:
                    stats["nofire_total"] += 1
                    ok = not pipeline_fires(result.ir, case["nofire"])
                    stats["nofire_ok"] += int(ok)
                    record["nofire_ok"] = ok

            rows_out.append(record)
            print(f"[{i}/{total}] {case['name']}: completed={result.success} fire_ok={record.get('fire_ok')} nofire_ok={record.get('nofire_ok')} tokens={cb.total_tokens} elapsed_s={elapsed_s:.1f}")

    with open("eval/results/real_eval_raw.jsonl", "w", encoding="utf-8") as f:
        for r in rows_out:
            f.write(json.dumps(r) + "\n")

    print("\n=== per-case execution-validated accuracy on REAL ground truth ===")
    for name, s in sorted(per_case.items()):
        completion_pct = s["completed"] / s["n"] * 100 if s["n"] else 0
        fire_pct = s["fire_ok"] / s["fire_total"] * 100 if s["fire_total"] else float("nan")
        nofire_pct = s["nofire_ok"] / s["nofire_total"] * 100 if s["nofire_total"] else float("nan")
        avg_tokens = s["total_tokens"] / s["n"] if s["n"] else 0
        avg_s = s["elapsed_s"] / s["n"] if s["n"] else 0
        print(
            f"{name:28s} n={s['n']:3d} completion={completion_pct:5.1f}%  "
            f"fire={fire_pct:5.1f}%  nofire={nofire_pct:5.1f}%  avg_tokens={avg_tokens:6.0f}  avg_s={avg_s:4.1f}"
        )

    all_fire_ok = sum(s["fire_ok"] for s in per_case.values())
    all_fire_total = sum(s["fire_total"] for s in per_case.values())
    all_nofire_ok = sum(s["nofire_ok"] for s in per_case.values())
    all_nofire_total = sum(s["nofire_total"] for s in per_case.values())
    print(
        f"\noverall real-ground-truth execution-validated rate: "
        f"fire={all_fire_ok}/{all_fire_total} ({all_fire_ok/all_fire_total*100:.1f}%)  "
        f"nofire={all_nofire_ok}/{all_nofire_total} ({all_nofire_ok/all_nofire_total*100:.1f}%)"
    )


if __name__ == "__main__":
    main()
