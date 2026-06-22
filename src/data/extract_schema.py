"""Build the ASIM field reference used by the Schema Validator and IR Builder
Agent.

IMPORTANT — this does NOT parse the Azure-Sentinel repo's ASIM/schemas/*.yaml
files. Those use a declarative format with `Include:` directives and
`<<Role>>` placeholder substitution (e.g. entities/ASimUser.yaml defines
`<<Role>>Username`, resolved per schema to `TargetUsername`, `ActorUsername`,
etc.) — correctly resolving that format requires reimplementing ASIM's own
schema compiler, which is out of scope here. There is also no ASIM/ASimSchemas/
markdown folder in the repo (an earlier assumption in this file was wrong).

Instead, this parses the authoritative human-readable field reference docs
published at learn.microsoft.com/en-us/azure/sentinel/normalization-schema-*,
saved locally under data/raw/asim_docs/ (one .md per ASIM event type, plus
common_fields.md). Each doc was fetched directly from Microsoft Learn and
condensed to "| **FieldName** | Class |" tables — field names are verbatim
from the live docs; the source URLs and the docs' git_commit_id are recorded
in data/raw/SOURCE_ATTRIBUTION.md.

Usage:
    python -m src.data.extract_schema --source data/raw/asim_docs \
        --output data/schema/asim_field_reference.json
"""
import argparse
import json
import re
from pathlib import Path

from src.ir_engine.ir_schema import ASIMEventType

_FIELD_ROW = re.compile(r"^\|\s*\*\*([A-Za-z0-9]+)\*\*\s*\|")

# Doc filename (under data/raw/asim_docs/) per ASIMEventType. WebSession is a
# documented superset of NetworkSession, so it additionally includes those fields.
_DOC_BY_EVENT_TYPE = {
    ASIMEventType.AUTHENTICATION: "authentication.md",
    ASIMEventType.NETWORK_SESSION: "network_session.md",
    ASIMEventType.PROCESS: "process_event.md",
    ASIMEventType.FILE: "file_event.md",
    ASIMEventType.DNS: "dns.md",
    ASIMEventType.WEB_SESSION: "web_session.md",
    ASIMEventType.REGISTRY: "registry_event.md",
}
_COMMON_FIELDS_DOC = "common_fields.md"
_WEB_SESSION_INCLUDES_NETWORK_SESSION = True


def parse_field_doc(path: Path) -> list[str]:
    fields: list[str] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            match = _FIELD_ROW.match(line.strip())
            if match:
                fields.append(match.group(1))
    return fields


def build_field_reference(docs_dir: str) -> dict:
    docs_dir = Path(docs_dir)
    common_fields = parse_field_doc(docs_dir / _COMMON_FIELDS_DOC)

    schema = {}
    for event_type, doc_name in _DOC_BY_EVENT_TYPE.items():
        fields = set(common_fields) | set(parse_field_doc(docs_dir / doc_name))
        if event_type == ASIMEventType.WEB_SESSION and _WEB_SESSION_INCLUDES_NETWORK_SESSION:
            fields |= set(parse_field_doc(docs_dir / _DOC_BY_EVENT_TYPE[ASIMEventType.NETWORK_SESSION]))
        schema[event_type.value] = {
            "fields": sorted(fields),
            "source_doc": doc_name,
        }
    return schema


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, help="path to data/raw/asim_docs/ folder")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    schema = build_field_reference(args.source)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    for event_type, data in schema.items():
        print(f"{event_type}: {len(data['fields'])} fields")


if __name__ == "__main__":
    main()
