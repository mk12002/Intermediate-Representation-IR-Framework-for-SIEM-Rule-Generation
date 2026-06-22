# Dataset Construction — Deep Dive

The [README](../README.md) covers dataset construction at landing-page depth. This document is the full methodology — this is, deliberately, the most important document in this repository. A weak or small dataset undermines every downstream metric regardless of how well the architecture in [`architecture.md`](architecture.md) is built, so this gets the most procedural detail of any deep-dive.

## Table of Contents

- [Why the Azure-Sentinel Repository](#why-the-azure-sentinel-repository)
- [Repository Structure — Full Detail](#repository-structure-full-detail)
- [Step-by-Step Construction Procedure](#step-by-step-construction-procedure)
- [Paraphrasing Guidelines](#paraphrasing-guidelines)
- [Manual Verification Rubric](#manual-verification-rubric)
- [Complexity Tagging Criteria](#complexity-tagging-criteria)
- [Train/Test Split Discipline](#traintest-split-discipline)
- [Schema Reference Extraction](#schema-reference-extraction)
- [Dataset File Formats](#dataset-file-formats)
- [Known Risks](#known-risks)
- [Licensing and Attribution](#licensing-and-attribution)

---

## Why the Azure-Sentinel Repository

The core structural reason this repository is suitable, stated precisely: it does not just contain example logs — it contains thousands of production-quality, peer-reviewed detection rule *definitions*, and each definition already pairs a natural-language `description` field with an executable `query` field. That pairing is exactly the ground-truth structure this project needs, and it already exists at scale, written by people who actually work with Sentinel, rather than needing to be synthesized from scratch.

This matters more than it might first appear. The alternative — writing (NL, KQL) pairs from scratch — has two failure modes this project specifically avoids by using the repo instead:

- **Ground truth that's subtly wrong.** A single researcher hand-writing 100+ KQL queries from imagined scenarios is likely to introduce the same kinds of errors the project is trying to measure in LLM output, just less frequently. The Azure-Sentinel repo's rules have gone through Microsoft's own PR review and validation pipeline.
- **Unrealistic distribution.** Hand-imagined detection scenarios tend to cluster around what's easy to imagine (failed logins, suspicious processes) rather than the actual distribution of real detection logic, which includes a lot of more mechanically awkward cases (multi-stage correlation, rare aggregation functions, edge-case time windows) that are exactly where hallucination is most interesting to study.

---

## Repository Structure — Full Detail

```
Azure-Sentinel/
├── Detections/
│   ├── MultipleDataSources/
│   ├── AzureActiveDirectory/
│   ├── SecurityEvent/              ← Windows Security Event log-based rules
│   ├── Syslog/
│   ├── ASimAuthentication/         ← rules already written against ASIM, highest priority for this project
│   ├── ASimNetworkSession/
│   ├── ASimProcessEvent/
│   ├── ASimDns/
│   └── ... (40+ data-source folders)
├── Hunting Queries/
│   └── (same data-source folder structure, less rigid templating)
├── Sample Data/
│   └── (scrubbed CSV/JSON sample rows per connector)
├── ASIM/
│   ├── ASimSchemas/                 ← schema documentation per normalized event type
│   └── ASimParsers/                 ← KQL parser functions, raw field → ASIM field mapping
└── Parsers/
```

### What a `Detections/` YAML file actually looks like

```yaml
id: 12ab34cd-5678-90ef-ghij-klmnopqrstuv
name: Multiple authentication failures followed by a success
description: |
  Identifies a brute force pattern where a single account experiences
  multiple authentication failures within a short window, followed by
  a successful authentication from the same or a related source.
severity: Medium
requiredDataConnectors:
  - connectorId: AzureActiveDirectory
    dataTypes:
      - SigninLogs
queryFrequency: 5m
queryPeriod: 1h
triggerOperator: gt
triggerThreshold: 0
tactics:
  - CredentialAccess
relevantTechniques:
  - T1110
query: |
  let threshold = 5;
  AADSignInEventsBeta
  | where ResultType != "0"
  | summarize FailCount = count() by UserPrincipalName, bin(TimeGenerated, 1h)
  | where FailCount > threshold
  | join kind=inner (
      AADSignInEventsBeta
      | where ResultType == "0"
  ) on UserPrincipalName
```

The fields this project consumes directly are `description` and `query`. `tactics` and `relevantTechniques` are **not** consumed in the current scope (MITRE mapping is out of scope for this project — see the README's [Future Extensions](../README.md#future-extensions) section) but are preserved in the raw data pull in case they become useful later.

---

## Step-by-Step Construction Procedure

### Step 1 — Bulk pull

```bash
git clone --depth 1 https://github.com/Azure/Azure-Sentinel.git /tmp/azure-sentinel
python src/data/pull_detections.py \
  --source /tmp/azure-sentinel/Detections \
  --filter-asim-only \
  --output data/raw/detections_raw.jsonl
```

The `--filter-asim-only` flag restricts the first pass to rules already written against ASIM-normalized tables (the `ASim*` subfolders, plus any rule elsewhere in the repo whose `query` references an `im*` or `Asim*` table name). This keeps the dataset's schema grounding consistent with the project's single-schema scope decision — see the [Schema Reference Extraction](#schema-reference-extraction) section below for why this consistency matters mechanically, not just conceptually.

Rules **not** ASIM-normalized (e.g. raw `SecurityEvent` or `Syslog` table queries) are pulled into a separate `detections_raw_non_asim.jsonl` and held in reserve — not discarded — in case the dataset needs supplementing later, but they are out of scope for the primary dataset because validating them would require a second schema reference (the raw table schema, not ASIM), which the project's scope decision (see [README](../README.md#limitations)) explicitly defers.

### Step 2 — Field extraction and basic filtering

```python
# src/data/build_dataset.py (excerpt)
import yaml, json

def extract_pair(yaml_path: str) -> dict | None:
    with open(yaml_path) as f:
        rule = yaml.safe_load(f)

    description = rule.get("description", "").strip()
    query = rule.get("query", "").strip()

    # basic exclusion filters
    if len(description) < 20:               # too terse to be useful ground truth
        return None
    if "{{" in query or "{{" in description: # templated/parameterized rules, skip
        return None
    if not any(t in query for t in ("Asim", "im")):  # not ASIM-normalized
        return None

    return {
        "source_file": yaml_path,
        "rule_id": rule.get("id"),
        "description_raw": description,
        "query": query,
        "tactics": rule.get("tactics", []),       # preserved, not yet used
        "techniques": rule.get("relevantTechniques", []),  # preserved, not yet used
    }
```

This step is intentionally conservative — it's a coarse filter, not the final quality gate. Its job is to cheaply discard obviously unusable rules (templated queries with unfilled placeholders, descriptions too short to paraphrase meaningfully) before the much more expensive manual review step.

### Step 3 — Paraphrasing

See [Paraphrasing Guidelines](#paraphrasing-guidelines) below for the full methodology. Output: 2–3 NL variants per retained rule, each tagged with its paraphrase style.

### Step 4 — Manual verification

See [Manual Verification Rubric](#manual-verification-rubric) below. This is the step that should consume the most calendar time in this phase — budget for it honestly rather than treating it as a formality, since it's the single biggest determinant of whether the final results are trustworthy.

### Step 5 — Complexity tagging

See [Complexity Tagging Criteria](#complexity-tagging-criteria) below.

### Step 6 — Split assignment

See [Train/Test Split Discipline](#traintest-split-discipline) below. This step happens **last**, and once done, the test split file is not touched again until final evaluation.

---

## Paraphrasing Guidelines

The original `description` fields in the Azure-Sentinel repo are themselves fairly structured and somewhat formal — closer to documentation prose than to how an analyst actually talks. The project's real target use case is messier, so each retained pair gets 2–3 paraphrased variants, each in a distinct register:

| Style | Characteristics | Example (from the worked example in `architecture.md`) |
|---|---|---|
| **Casual / shorthand** | Short, may drop articles, closer to a Slack message or ticket note | *"acct getting bruteforced — 15+ fails in under 10 min, flag it"* |
| **SOP-imperative** | Procedural, instructive tone, as if written into a runbook | *"If a single account records more than 15 failed login attempts within a 10-minute window, raise an alert."* |
| **Threat-report-style** | Descriptive, third-person, narrative framing as if summarizing observed adversary behavior | *"The attacker repeatedly attempted authentication against a single account, generating over fifteen failures inside a ten-minute span."* |

### Process

1. Start from `description_raw`.
2. Generate 2–3 candidate paraphrases (light LLM assistance is acceptable here — this is not the ground-truth KQL, it's the *input* side, so imperfection in phrasing is fine and even desirable for realism).
3. **Manually read every paraphrase** against the original `query` and confirm the detection logic is unchanged — paraphrasing must not silently alter thresholds, time windows, or filter conditions. This is a common and easy-to-miss failure mode: an LLM asked to "make this more casual" will sometimes round "15" to "a bunch" or drop the time window entirely, which corrupts the ground truth.
4. Tag each paraphrase with its style label and a reference back to `rule_id`, so degenerate paraphrases can be traced back and regenerated rather than the whole pair being discarded.

### What NOT to do

- Do not fully automate paraphrasing without review — see Step 3 above. This is the single highest-risk step in the entire dataset pipeline for silently corrupting ground truth.
- Do not paraphrase so aggressively that the threshold/time-window information is lost entirely (e.g. *"detect brute forcing"* with no number or window) — these provide no signal for evaluating whether the system correctly extracts threshold/temporal logic, which is a core part of what's being measured (see the [failure taxonomy](../README.md#the-problem)).

---

## Manual Verification Rubric

Every retained `(NL, KQL)` pair — across all paraphrase variants — passes through this checklist before being added to the final dataset:

- [ ] **KQL still parses.** Run the candidate KQL Syntax Validator (see [`architecture.md`](architecture.md#kql-syntax-validator-specification)) against `query` directly. If the *ground truth* itself doesn't parse, something is wrong with the extraction (e.g. a multi-statement `let`-prefixed query that needs special handling) — fix the extraction or discard the pair, do not "fix" the ground-truth KQL by hand, since that risks introducing exactly the kind of subtle ground-truth error the repo source was chosen to avoid.
- [ ] **Description genuinely matches query logic.** Read the NL description and the KQL side by side. Specifically check: does the described event type match the table queried; does the described threshold match the `where`/`threshold` comparison value; does the described time window match the `bin()` argument; does the described aggregation direction (e.g. "many distinct X" vs "total count of X") match the aggregation function used.
- [ ] **No orphaned complexity.** If the query contains a `join` or multi-stage correlation that the description doesn't mention at all, either the description is incomplete (paraphrase it to include that detail) or the pair should be tagged appropriately in [Complexity Tagging](#complexity-tagging-criteria) and flagged for closer review, since unstated complexity in the ground truth makes Logic Correctness scoring (see [`evaluation.md`](evaluation.md#metrics-exact-definitions)) unreliable for that case.
- [ ] **Field names exist in the current ASIM schema.** Cross-check `query`'s referenced fields against the extracted [schema reference](#schema-reference-extraction) — the Azure-Sentinel repo evolves, and a small number of rules may reference deprecated or renamed ASIM fields. Discard these rather than trying to "fix" them, since the project's schema validator should be checked against the same schema version used to build the ground truth.

Pairs that fail any checkbox are either fixed (if the fix is unambiguous — e.g. a clearly outdated field rename) or discarded. **Discard, don't force-fix, ambiguous cases** — a slightly smaller, cleaner dataset is strictly better for this project's validity than a larger dataset with disputed ground truth.

---

## Complexity Tagging Criteria

Each verified pair is tagged with exactly one tier, used for the [stratified analysis](evaluation.md#stratified-analysis) that tests H4.

| Tier | Criteria (all must hold) | Target Share |
|---|---|---|
| **Simple** | Single ASIM event type · 1–2 filters · no `aggregation` · no `join` | ~35% |
| **Moderate** | Single ASIM event type · `aggregation` + `threshold` present · single `time_window` · no `join` | ~35% |
| **Complex** | Multiple filters (3+) **or** a `join`/multi-event correlation **or** multiple aggregations/group-by keys **or** nested time logic | ~30% |

Tagging is done programmatically from the parsed `query` structure (count filters, detect presence of `summarize`, `join`, `let` chains) and then **spot-checked manually** on a 20% sample per tier to confirm the automated tag matches human judgment — a query can technically have only one filter but still be conceptually complex (e.g. a single filter against a computed/derived field), so automated tagging alone is not fully trusted.

```python
def tag_complexity(query: str) -> str:
    filter_count = query.count("| where")
    has_join = "| join" in query
    has_aggregation = "| summarize" in query
    has_multi_groupby = query.count(",") > 2 and has_aggregation  # rough heuristic, refine during spot-check

    if has_join or has_multi_groupby or filter_count >= 3:
        return "complex"
    elif has_aggregation:
        return "moderate"
    else:
        return "simple"
```

---

## Train/Test Split Discipline

- **20% held out as the test split**, stratified by complexity tier (so the test split has roughly the same 35/35/30 distribution as the full dataset, not a skewed sample).
- The split is generated **once**, written to `data/splits/test_ids.json` (a list of `rule_id`s), and committed to version control immediately — this makes the split itself auditable and prevents silent re-shuffling.
- **No development, prompt engineering, threshold tuning, or MVP testing (see [`architecture.md`](architecture.md)) touches the test split.** The MVP's 10 hand-picked cases (mentioned in the README's Getting Started) are drawn exclusively from the training portion.
- The test split is only run once both System A and System B are finalized, for the [primary comparison](evaluation.md#primary-comparison) and all three [ablations](evaluation.md#ablations).

This is basic methodological discipline, but it is the single most commonly skipped step in small individual research projects under time pressure — and skipping it is also the single most common reason a result doesn't survive scrutiny, so it's called out explicitly here rather than assumed.

---

## Schema Reference Extraction

The ASIM field reference used by the [Schema Validator](architecture.md#schema-validator-specification) and the [IR Builder Agent](architecture.md#ir-builder-agent-specification) is extracted directly from the `ASIM/ASimSchemas/` folder, not hand-maintained separately — this is important because it guarantees the schema used for validation is the same version the ground-truth queries in `Detections/` were written against (both come from the same repo clone/commit).

```python
# src/data/extract_asim_schema.py (excerpt)
def extract_schema(asim_schemas_dir: str) -> dict:
    schema = {}
    for schema_file in glob(f"{asim_schemas_dir}/*.md"):
        event_type, fields = parse_asim_schema_doc(schema_file)
        schema[event_type] = {
            "fields": fields,            # list of field names
            "field_types": {...},        # field name -> type, where documented
            "source_file": schema_file,
        }
    return schema
```

**Versioning note:** record the exact commit hash of the `Azure-Sentinel` clone used (`git rev-parse HEAD` at pull time) in `data/raw/SOURCE_ATTRIBUTION.md`, alongside the schema extraction. ASIM schemas do evolve, and being able to say precisely "this dataset and this schema reference were built against commit `abc1234`" is what makes the [Manual Verification Rubric](#manual-verification-rubric)'s "field names exist in the current ASIM schema" check meaningful and reproducible.

---

## Dataset File Formats

```
data/
├── raw/
│   ├── detections_raw.jsonl              # all ASIM-normalized rules, unfiltered
│   ├── detections_raw_non_asim.jsonl      # held in reserve, out of scope
│   └── SOURCE_ATTRIBUTION.md              # commit hash, pull date, licensing note
├── processed/
│   ├── pairs.jsonl                        # final verified (NL, KQL) pairs, one per paraphrase variant
│   └── pairs_schema.md                    # field-by-field description of pairs.jsonl
├── schema/
│   └── asim_field_reference.json          # extracted ASIM schema, versioned to a commit hash
└── splits/
    ├── test_ids.json                      # held-out rule_ids, generated once
    └── train_ids.json
```

### `pairs.jsonl` record format

```json
{
  "pair_id": "12ab34cd-variant-2",
  "rule_id": "12ab34cd-5678-90ef-ghij-klmnopqrstuv",
  "nl_description": "If a single account records more than 15 failed login attempts within a 10-minute window, raise an alert.",
  "paraphrase_style": "sop_imperative",
  "ground_truth_kql": "AuthenticationEvent\n| where EventResult == \"Failure\"\n| summarize FailCount = count() by TargetUsername, bin(TimeGenerated, 10m)\n| where FailCount > 15",
  "complexity_tier": "moderate",
  "asim_event_type": "AuthenticationEvent",
  "split": "train",
  "verified_by": "manual_review_2026_06",
  "source_file": "Detections/ASimAuthentication/MultipleAuthFailures.yaml"
}
```

---

## Known Risks

- **Source descriptions are sometimes terse or loosely correlated with query logic.** This is exactly what the [Manual Verification Rubric](#manual-verification-rubric) exists to screen for — budget real calendar time for this, it is not a formality. Expect to discard a non-trivial fraction (informally, 15–25% is a reasonable planning assumption) of the initial pull at this step.
- **ASIM field/table renames between repo versions.** Mitigated by pinning the schema extraction to the same commit hash as the data pull (see [Schema Reference Extraction](#schema-reference-extraction)).
- **Paraphrasing drift corrupting ground truth.** Mitigated by the mandatory manual read-through in [Paraphrasing Guidelines](#paraphrasing-guidelines) Step 3 — this is not optional even when paraphrasing is LLM-assisted.
- **No mature open-source KQL parser/linter readily available**, which affects both the Manual Verification Rubric's "KQL still parses" check and the project's primary [SVR metric](evaluation.md#metrics-exact-definitions). This is the single largest open technical risk in the project and should be resolved (or explicitly scoped down, with the scoping documented as a stated limitation) before Step 4 of the construction procedure, not discovered partway through.

---

## Licensing and Attribution

`Azure/Azure-Sentinel` is [MIT-licensed](https://github.com/Azure/Azure-Sentinel/blob/master/LICENSE) and explicitly intended for community reuse — the repository's own `Sample Data/` contribution guidelines require pre-scrubbing of sensitive information specifically to enable this kind of downstream reuse.

Every record in `pairs.jsonl` retains a `source_file` pointer back to the originating YAML in the upstream repo. `data/raw/SOURCE_ATTRIBUTION.md` records the commit hash, pull date, and a short note that `nl_description` fields are paraphrased/derived (not verbatim Microsoft content) while `ground_truth_kql` fields are taken directly from the upstream `query` field and should be attributed as such if reproduced in a paper or report.
