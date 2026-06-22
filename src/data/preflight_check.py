"""Mechanical pre-flight checks ahead of manual verification —
docs/NL-KQL/MASTER_PLAN.md §16.2 Step 4 calls for "KQL still parses" and
"field names exist in current ASIM schema" as the first two of four rubric
checks. Those two are mechanical; this script runs them on every raw pair
and flags likely failures so manual review time goes to genuinely judgment-
based checks (description-matches-logic, orphaned complexity) instead of
re-deriving what a script can already tell us.

This does NOT replace manual verification — it only triages it. A pair
passing both checks here still needs a human read against the other two
rubric items before being marked verified.

Usage:
    python -m src.data.preflight_check \
        --input data/processed/pairs_tagged_unverified.jsonl \
        --schema data/schema/asim_field_reference.json \
        --output data/processed/preflight_report.jsonl
"""
import argparse
import json
import re
from pathlib import Path

from eval.metrics import referenced_identifiers
from src.validation.syntax_validators import validate_kql_syntax

_TABLE_PATTERNS = {
    "AuthenticationEvent": re.compile(r"\b(im|ASim|_Im_)Authentication\b", re.IGNORECASE),
    "NetworkSessionEvent": re.compile(r"\b(im|ASim|_Im_)NetworkSession\b", re.IGNORECASE),
    "ProcessEvent": re.compile(r"\b(im|ASim|_Im_)Process(Create|Terminate|Event)?\b", re.IGNORECASE),
    "FileEvent": re.compile(r"\b(im|ASim|_Im_)FileEvent\b", re.IGNORECASE),
    "DnsEvent": re.compile(r"\b(im|ASim|_Im_)Dns\b", re.IGNORECASE),
    "WebSessionEvent": re.compile(r"\b(im|ASim|_Im_)WebSession\b", re.IGNORECASE),
    "RegistryEvent": re.compile(r"\b(im|ASim|_Im_)Registry(Event)?\b", re.IGNORECASE),
}


def detect_event_type(query: str) -> str | None:
    for event_type, pattern in _TABLE_PATTERNS.items():
        if pattern.search(query):
            return event_type
    return None


def check_fields(query: str, known_fields: set[str]) -> list[str]:
    return sorted(referenced_identifiers(query) - known_fields)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    asim_schema = json.loads(Path(args.schema).read_text(encoding="utf-8"))
    pairs = [json.loads(line) for line in open(args.input, encoding="utf-8")]

    report = []
    counts = {"syntax_fail": 0, "no_event_type_detected": 0, "unknown_fields": 0, "clean": 0}
    for pair in pairs:
        query = pair["query"]
        syntax_result = validate_kql_syntax(query)
        event_type = detect_event_type(query)
        unknown_fields = []
        if event_type:
            known_fields = set(asim_schema[event_type]["fields"])
            unknown_fields = check_fields(query, known_fields)

        flags = []
        if not syntax_result.passed:
            flags.append(f"SYNTAX: {syntax_result.message}")
            counts["syntax_fail"] += 1
        if not event_type:
            flags.append("NO_EVENT_TYPE_DETECTED")
            counts["no_event_type_detected"] += 1
        if unknown_fields:
            flags.append(f"UNKNOWN_TOKENS: {unknown_fields}")
            counts["unknown_fields"] += 1
        if not flags:
            counts["clean"] += 1

        report.append(
            {
                "rule_id": pair["rule_id"],
                "source_file": pair["source_file"],
                "complexity_tier": pair.get("complexity_tier"),
                "detected_event_type": event_type,
                "flags": flags,
            }
        )

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for r in report:
            f.write(json.dumps(r) + "\n")

    total = len(report)
    print(f"checked {total} pairs:")
    for k, v in counts.items():
        print(f"  {k}: {v} ({v/total:.0%})")


if __name__ == "__main__":
    main()
