import json
import sys

src_file = sys.argv[3] if len(sys.argv) > 3 else "data/processed/survivors.json"
data = json.load(open(src_file, encoding="utf-8"))
start, end = int(sys.argv[1]), int(sys.argv[2])

for i, p in enumerate(data[start:end], start=start):
    desc = p["description"].strip().strip("'").replace("\n", " ")[:300]
    query = p["query"][:900]
    truncated = "...[TRUNCATED]" if len(p["query"]) > 900 else ""
    print(f"=== [{i}] {p['rule_id'][:8]} tier={p['complexity_tier']} flags={p['syntax_flags']}")
    print(f"DESC: {desc}")
    print(f"KQL: {query}{truncated}")
    print()
