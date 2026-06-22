# Schema-Grounded Natural Language to KQL Translation

**Reducing syntax and field hallucination in LLM-generated Microsoft Sentinel detection rules via an explicit, schema-validated intermediate representation.**

> Independent personal research project. Not affiliated with any employer.
> Status: 🚧 Active development — dataset construction phase

---

## Table of Contents

- [Overview](#overview)
- [The Problem](#the-problem)
- [Why an Intermediate Representation](#why-an-intermediate-representation)
- [Architecture](#architecture)
- [The Security IR Schema](#the-security-ir-schema)
- [Research Questions & Hypotheses](#research-questions-hypotheses)
- [Dataset](#dataset)
- [Evaluation](#evaluation)
- [Repository Structure](#repository-structure)
- [Getting Started](#getting-started)
- [Project Status & Roadmap](#project-status-roadmap)
- [Limitations](#limitations)
- [Acknowledgements & Data Sources](#acknowledgements-data-sources)
- [License](#license)

### Deep-Dive Documentation

This README is a landing page. Full technical depth lives in `docs/`:

| Document | Covers |
|---|---|
| [`docs/NL-KQL/MASTER_PLAN.md`](docs/NL-KQL/MASTER_PLAN.md) | **Start here for full depth.** Complete planning + implementation reference in one file — motivation through future work |
| [`docs/NL-KQL/architecture.md`](docs/NL-KQL/architecture.md) | Full pipeline specs, agent prompts, IR schema, repair loop logic, a worked end-to-end example |
| [`docs/NL-KQL/dataset.md`](docs/NL-KQL/dataset.md) | Full construction methodology, paraphrasing guidelines, verification rubric, complexity tagging |
| [`docs/NL-KQL/evaluation.md`](docs/NL-KQL/evaluation.md) | Exact metric definitions, ablation protocol, statistical methodology, logic-correctness rubric |
| [`docs/NL-KQL/kql-asim-primer.md`](docs/NL-KQL/kql-asim-primer.md) | KQL/ASIM technical reference scoped to what this project uses |

---

## Overview

Security Operations Center (SOC) analysts routinely need to translate natural-language detection requirements — a line in an SOP, a sentence in a threat intel report, an analyst's shorthand — into executable [Kusto Query Language (KQL)](https://learn.microsoft.com/en-us/kusto/query/) rules for Microsoft Sentinel.

Direct LLM generation of KQL from such descriptions is unreliable: single-prompt generation produces syntactically invalid queries, hallucinated field names, and logically incorrect filters at rates too high for unsupervised use in a SOC context.

This project tests a specific hypothesis: **inserting an explicit, schema-validated Intermediate Representation (IR) between natural language input and KQL output reduces hallucination compared to direct generation** — and measures *how much*, *where*, and *why*, using a purpose-built dataset derived from Microsoft's public [`Azure/Azure-Sentinel`](https://github.com/Azure/Azure-Sentinel) repository.

The project is intentionally scoped to one platform (KQL / Microsoft Sentinel) and one schema standard (ASIM), with a small 2–3 agent pipeline — narrow enough to evaluate rigorously, with a real dataset, real baselines, and statistical testing, within a single research cycle. Extensions such as additional target platforms or full telemetry execution validation are noted as future work in [Limitations](#limitations), but are not part of this project's scope.

---

## The Problem

> 📄 For the full KQL/ASIM technical background behind this taxonomy — operators, naming conventions, and why KQL is easily confused with SQL/SPL — see [`docs/NL-KQL/kql-asim-primer.md`](docs/NL-KQL/kql-asim-primer.md).

> **Given** a natural-language description of a detection requirement, and the ASIM/Sentinel schema as a ground-truth field reference, **generate** a KQL query that is syntactically valid, uses only fields that exist in the target schema, and correctly implements the described detection logic — **while requiring less correction effort than direct single-prompt LLM generation.**

KQL generation fails along (at least) three independent dimensions, which this project measures separately rather than as one bucket called "hallucination":

| Failure Dimension | Example | How It's Measured |
|---|---|---|
| **Syntax invalidity** | Using `CONTAINS` as a standalone clause; SQL-style `GROUP BY` | Parse against KQL grammar (pass/fail) |
| **Field hallucination** | Referencing `SourceIP` when the ASIM field is `SrcIpAddr` | Field-existence check against ASIM schema dump |
| **Table hallucination** | Querying a table that doesn't exist in Sentinel/ASIM | Table-existence check against schema catalogue |
| **Missing temporal logic** | Aggregation with no `bin()`/time window — scans the entire dataset | Static check for required IR temporal field |
| **Logic/semantic error** | Filtering `EventResult == "Success"` when the rule means failed logins | Manual review against held-out ground truth |

```
LAYER 1 — Natural Language
  "Detect when an attacker attempts logins with many different
   usernames from a single IP address"
          │
          │  GAP 1 — Threat → Detection Logic
          ▼
LAYER 2 — Security IR  (★ this project's core contribution)
  { "event_type": "AuthenticationFailure",
    "aggregation": "distinct_count(TargetUsername)",
    "group_by": "SourceIpAddress", "threshold": 20,
    "window": "5m", "schema": "ASIM" }
          │
          │  GAP 2 — Logic → KQL syntax
          ▼
LAYER 3 — Executable KQL
  imAuthentication
  | where EventResult == "Failure"
  | summarize DistinctUsers = dcount(TargetUsername) by SrcIpAddr, bin(TimeGenerated, 5m)
  | where DistinctUsers > 20
```

---

## Why an Intermediate Representation

Borrowed directly from compiler design: source code isn't translated straight to machine code — it passes through an IR, a structured, language-agnostic form that captures program logic independently of source syntax and target instruction set. This is what lets one frontend target many backends, and what makes validation tractable (checking an IR for well-formedness is far easier than checking generated assembly).

This project applies the same idea: instead of asking an LLM to go straight from *"detect credential stuffing"* to a raw KQL string, the system first produces a structured, typed, schema-checkable JSON object — the **Security IR** — describing the detection logic in a vendor-neutral form. Only once validated against the ASIM schema is it deterministically compiled into KQL via templates.

**The bet:** this separates *"does the model understand the threat"* from *"does the model remember KQL syntax,"* and the second problem is better solved by deterministic code than free-form generation.

---

## Architecture

> 📄 Full specification — agent prompts, schema validator logic, the repair loop's code, and a worked end-to-end example — in [`docs/NL-KQL/architecture.md`](docs/NL-KQL/architecture.md).

Two complete pipelines are run on identical inputs so all measured differences are attributable to the IR layer, not incidental implementation differences.

### System A — Baseline (Direct Generation)

A single prompt with the NL description, a KQL syntax primer, and relevant ASIM fields → LLM returns KQL directly. Mirrors naive real-world usage of a general-purpose assistant today.

### System B — IR-Mediated Generation (this project's contribution)

```
  NL input
     │
     ▼
  [Extraction Agent]  ──uses──>  ASIM field reference (read-only)
     │
     ▼
  [IR Builder Agent] ──> Security IR (JSON)
     │
     ▼
  [Schema Validator] ──fail──> back to IR Builder (≤3x) ──┐
     │ pass                                                │
     ▼                                                     │
  [KQL Generator]  (deterministic, template-based, no LLM call)
     │                                                      │
     ▼                                                      │
  [KQL Syntax Validator] ──fail──> back to IR Builder (≤3x)─┘
     │ pass
     ▼
  Validated KQL output
```

| Stage | Role |
|---|---|
| **Extraction Agent** | Parses NL input into candidate entities, behaviors, and detection intent (event type, actor, action, threshold/time language) |
| **IR Builder Agent** | Converts extraction output into a typed Security IR (Pydantic-validated), selecting fields only from the supplied ASIM reference — not free recall |
| **Schema Validator** | Deterministically checks every referenced field exists in the ASIM schema; required fields (event type, time window) are present |
| **KQL Generator** | Deterministically compiles a validated IR into KQL via Jinja2 templates — **no LLM call** |
| **KQL Syntax Validator** | Parses generated KQL against a grammar/linter |
| **Repair Loop** | On validator failure, feeds the specific structured error back to the IR Builder Agent (≤3 attempts) before marking a failure |

**Why exactly 2–3 agents:** more agents (e.g. separate threat-intel extraction, metadata generation, MITRE mapping, orchestration) would decompose along organizational lines that matter for a production system but aren't independently testable research variables at this scope. This project keeps exactly the decomposition needed to answer RQ2 (does splitting extraction from IR construction help) and no more.

---

## The Security IR Schema

A deliberately reduced subset of the original IR design — enough to express the detection logic in real Sentinel analytics rules, not a general-purpose schema covering every SIEM construct.

| Field | Type | Purpose |
|---|---|---|
| `event_type` | `string` (enum, ASIM schema name) | Which normalized ASIM table/schema, e.g. `AuthenticationEvent` |
| `filters` | `list[{field, operator, value}]` | Row-level filters, each field validated against ASIM schema for `event_type` |
| `aggregation` | `{function, field} \| null` | Optional aggregation, e.g. distinct count over a field |
| `group_by` | `list[string] \| null` | Grouping keys for aggregation |
| `threshold` | `{operator, value} \| null` | Comparison applied after aggregation, e.g. `> 20` |
| `time_window` | `string (ISO 8601 duration) \| null` | **Required** whenever `aggregation` is present — enforced by the schema validator |
| `output_fields` | `list[string] \| null` | Fields to project in the final result |

```python
# Example IR — credential stuffing detection
{
  "event_type": "AuthenticationEvent",
  "filters": [
    {"field": "EventResult", "operator": "==", "value": "Failure"}
  ],
  "aggregation": {"function": "distinct_count", "field": "TargetUsername"},
  "group_by": ["SrcIpAddr"],
  "threshold": {"operator": ">", "value": 20},
  "time_window": "PT5M",
  "output_fields": ["SrcIpAddr", "DistinctUsers", "TimeGenerated"]
}
```

Deliberately **excluded** from this scoped IR (reserved for productization — see [Roadmap](#project-status-roadmap)): MITRE ATT&CK mapping, multi-event correlation chains, cross-platform vendor mapping tags, confidence/severity metadata. The schema is designed so these can be added as new optional fields later without breaking the template compiler.

---

## Research Questions & Hypotheses

| # | Research Question |
|---|---|
| **RQ1** | Does a schema-validated IR reduce syntax and field hallucination vs. direct single-prompt generation? |
| **RQ2** | Does decomposing extraction into separate agents improve IR correctness vs. a monolithic extraction prompt? |
| **RQ3** | Does a closed-loop repair mechanism meaningfully improve final success rate within ≤3 iterations? |
| **RQ4** | How does performance vary across detection-logic complexity (simple filters vs. aggregation/correlation/temporal windows)? |

| # | Hypothesis | Rationale |
|---|---|---|
| **H1** | IR-mediated generation achieves materially higher syntax validity (target ≥90% vs. an expected 55–75% baseline) | Deterministic templates can't produce invalid syntax by construction |
| **H2** | IR-mediated generation achieves higher field validity | Schema grounding turns open-ended recall into constrained selection |
| **H3** | The repair loop recovers ≥50% of initially-failing cases within 3 iterations, with diminishing returns after iteration 2 | Most syntax/field errors are local and mechanical, well suited to targeted re-prompting |
| **H4** | The IR-vs-direct gap widens as detection-logic complexity increases | Complex logic requires holding more constraints in working memory during single-shot generation; the IR offloads that into a checkable step |

---

## Dataset

> 📄 Full methodology — step-by-step procedure, paraphrasing guidelines, the manual verification rubric, and complexity-tagging criteria — in [`docs/NL-KQL/dataset.md`](docs/NL-KQL/dataset.md).

Built primarily from Microsoft's public [`Azure/Azure-Sentinel`](https://github.com/Azure/Azure-Sentinel) repository — not just for sample logs, but because its `Detections/` folder contains hundreds of production-quality YAML analytics rules that already pair a `description` (NL ground truth) with a working `query` (KQL ground truth).

### Repository folders used

| Folder | Contents | Use Here |
|---|---|---|
| `Detections/` | YAML rules per data source: name, description, query | **Primary source** of (NL, KQL) ground-truth pairs |
| `Hunting Queries/` | KQL hunting queries, less rigidly templated | Secondary source for complexity diversity |
| `Sample Data/` | Scrubbed sample log rows per connector | Sanity-checking referenced fields; future execution-validation fixtures |
| `ASIM/` | ASIM schema definitions and field documentation | Direct source for the schema reference used by the validator |
| `Parsers/` | KQL parser functions mapping raw → ASIM-normalized fields | Reference for understanding raw-to-ASIM field mapping |

### Construction procedure

1. Pull all `Detections/*.yaml` targeting Sentinel/ASIM-normalized tables.
2. Extract `description` (NL) and `query` (KQL) per rule.
3. Paraphrase each description into 2–3 analyst-style variants (casual, SOP-imperative, threat-report-style) — manual or lightly LLM-assisted, **with manual review**.
4. Manually verify each pair: KQL still parses, description genuinely matches query logic; discard/fix loose correspondences.
5. Tag each pair with a complexity tier and source ASIM schema.
6. Hold out a fixed **20% test split** before any development or prompt engineering begins.

### Target composition

~100–150 verified pairs after filtering:

| Tier | Definition | Target Share |
|---|---|---|
| Simple | Single event type, 1–2 filters, no aggregation | ~35% |
| Moderate | Single event type, aggregation + threshold, single time window | ~35% |
| Complex | Multiple filters, group-by aggregation, explicit window, possible join/correlation | ~30% |

> **Licensing note:** `Azure/Azure-Sentinel` is MIT-licensed and explicitly designed for community reuse. This repository credits it as the data source; any paraphrased descriptions or modified queries are clearly marked as derived/adapted, not original Microsoft content.

---

## Evaluation

> 📄 Exact metric formulas, the full ablation protocol, statistical methodology (bootstrap CIs, McNemar's test), and the logic-correctness scoring rubric — in [`docs/NL-KQL/evaluation.md`](docs/NL-KQL/evaluation.md).

| Metric | Definition | Tests |
|---|---|---|
| **Syntax Validity Rate (SVR)** | % of generated queries that parse against a KQL grammar/linter | H1 |
| **Field Validity Rate (FVR)** | % of queries where every referenced table/field exists in the ASIM schema | H2 |
| **Logic Correctness** (manual) | % of syntax/schema-valid queries judged to correctly implement the described logic, scored against held-out ground truth | catches errors SVR/FVR can't |
| **CodeBLEU** | Structural/token similarity to ground-truth KQL | continuous proxy metric |
| **Repair Recovery Rate** | % of initially-failing cases passing after ≤3 repair iterations | H3 |
| **Latency / Token Cost** | Wall-clock time and LLM tokens per query, both systems | honest cost accounting |

### Ablations

| Ablation | Configuration | Isolates |
|---|---|---|
| No-repair IR | System B, repair loop disabled | IR/schema-grounding effect alone (H1/H2 independent of H3) |
| Monolithic extraction | Extraction + IR Builder merged into one prompt | Whether agent decomposition itself helps (RQ2) |
| No schema grounding | IR Builder without the ASIM field reference | The specific contribution of explicit schema grounding |

All metrics are reported **in aggregate and stratified by complexity tier** (tests H4), with confidence intervals (bootstrap) and paired significance testing (e.g. McNemar's test for SVR/FVR, since both systems run on identical NL inputs).

**Baseline fairness:** System A receives the same ASIM field reference, same underlying LLM, and a few-shot KQL syntax primer — the comparison is about IR-mediation vs. direct generation, not about who has schema access.

---

## Repository Structure

```
.
├── README.md                      # this file — landing page
├── docs/
│   ├── MASTER_PLAN.md              # complete planning + implementation reference, single file
│   ├── architecture.md            # full pipeline spec, agent prompts, IR schema, repair loop
│   ├── dataset.md                 # full dataset construction methodology
│   ├── evaluation.md              # full evaluation methodology and statistics
│   └── kql-asim-primer.md         # scoped KQL/ASIM technical reference
├── data/
│   ├── raw/                       # pulled Detections/ and Hunting Queries/ YAML
│   ├── processed/                 # cleaned, paraphrased, complexity-tagged (NL, KQL) pairs
│   ├── schema/                    # extracted ASIM field reference
│   └── splits/                    # train/dev/test split definitions
├── src/
│   ├── ir/                        # Pydantic IR schema + validator
│   ├── agents/                    # extraction agent, IR builder agent
│   ├── generator/                 # Jinja2 KQL templates + compiler
│   ├── validators/                # KQL syntax validator, field validator
│   ├── baseline/                  # System A (direct generation)
│   └── pipeline/                  # System B orchestration (LangGraph) + repair loop
├── eval/
│   ├── metrics.py                 # SVR, FVR, CodeBLEU, etc.
│   ├── run_comparison.py          # primary A/B comparison
│   ├── run_ablations.py           # the 3 ablations
│   └── results/                   # raw + aggregated results, by complexity tier
├── notebooks/                     # exploratory analysis, stratified breakdowns
└── tests/                         # unit tests for IR schema, templates, validators
```

> Folder layout is a working plan, not yet fully implemented — see [Project Status](#project-status-roadmap).

---

## Getting Started

```bash
git clone https://github.com/<your-username>/nl-to-kql-research.git
cd nl-to-kql-research

python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Pull and process the dataset from Azure/Azure-Sentinel
python src/data/build_dataset.py

# Run the MVP pipeline on a small hand-picked slice (10 cases)
python src/pipeline/run_mvp.py --n 10

# Run the full comparison once the dataset and pipeline are validated
python eval/run_comparison.py
```

> Requires an LLM API key (Anthropic or OpenAI — pick one and hold it fixed across the whole study to avoid a cross-provider confound). Set via `.env` (see `.env.example`).

---

## Project Status & Roadmap

**Current phase:** Dataset construction (see [timeline](#indicative-timeline) below).

### Indicative timeline

| Phase | Duration | Output |
|---|---|---|
| Dataset construction + ASIM schema extraction | 3–4 weeks | 100–150 verified pairs, complexity-tagged, test split held out |
| MVP pipeline + KQL validator scoping | 2–3 weeks | Working System B pipeline validated on 10 hand-picked cases |
| Baseline (System A) implementation | 1 week | Fairly-prompted direct-generation baseline |
| Full evaluation: primary comparison + 3 ablations | 2 weeks | Raw results, all metrics, all configurations |
| Stratified/statistical analysis | 2 weeks | Final tables, significance tests, complexity breakdowns |
| Write-up | 3–4 weeks | Paper/report draft |

### Known risks

- **No mature open-source KQL parser/linter** may be readily available — may require scoping the syntax checker to the operator subset actually used in the dataset rather than full grammar coverage (documented explicitly as a limitation, not glossed over).
- Dataset descriptions in the source repo are sometimes terse or loosely correlated with query logic — manual review step exists specifically to screen for this.
- Manual logic-correctness scoring needs a concrete rubric (event type correct / comparison direction correct / aggregation field correct) to stay consistent across 100+ cases.

---

## Limitations

Stated up front, not discovered later:

- **Single platform, single schema standard.** KQL/Sentinel + ASIM only. Sigma, SPL, and OCSF are future work, not demonstrated here.
- **Syntax validation, not full telemetry execution validation.** The study measures whether a query parses and references real fields — not whether it produces correct results against live data. This is a deliberate scope boundary.
- **Dataset size (100–150 pairs)** is appropriate for a scoped individual project but small relative to large-scale code-gen benchmarks. Results are reported with confidence intervals, not bare point estimates.
- **Manual logic-correctness scoring** introduces some subjectivity even with a rubric.
- **Source data is cleaner than real-world analyst language.** Paraphrasing partially addresses this but doesn't fully replicate field-collected SOC prose.

### Future Extensions

Not part of this project's scope, but natural next steps once the core result is established:

| Extension | What It Would Add | Why It's Out of Scope Now |
|---|---|---|
| Multi-platform generation (Sigma, SPL) | New Jinja2 templates consuming the same IR | Each platform needs its own schema reference and dataset slice to evaluate fairly |
| OCSF as a second normalization layer | Cross-platform field mapping | Only necessary once a second platform is in scope |
| Telemetry execution validation | Running generated KQL against synthetic data (`Sample Data/` is a natural source) for real precision/recall | Substantially larger engineering lift than syntax/field validation |
| MITRE ATT&CK mapping | Automatic technique/tactic tagging on generated rules | Orthogonal to the core hallucination question this project tests |
| Production hardening | RBAC, containerization, observability, scaling | Pure engineering, no research content |

**Design discipline:** the IR is kept vendor-neutral on purpose — no KQL-specific fields, even though KQL is the only consumer today — so that a future platform extension would require only a new template and schema reference, not a rewrite of the IR or the agents.

---

## Acknowledgements & Data Sources

- Dataset derived and adapted from [`Azure/Azure-Sentinel`](https://github.com/Azure/Azure-Sentinel) (MIT License), Microsoft's public Sentinel content repository — `Detections/`, `Hunting Queries/`, `Sample Data/`, and `ASIM/` folders specifically.
- [ASIM (Advanced Security Information Model)](https://learn.microsoft.com/en-us/azure/sentinel/normalization-schema) documentation, Microsoft.
- [Kusto Query Language documentation](https://learn.microsoft.com/en-us/kusto/query/), Microsoft.

---

## License

This repository's original code and written content: [MIT](LICENSE).

Dataset content adapted from `Azure/Azure-Sentinel` retains attribution to Microsoft per the [upstream MIT license](https://github.com/Azure/Azure-Sentinel/blob/master/LICENSE). See [`data/raw/SOURCE_ATTRIBUTION.md`](data/raw/SOURCE_ATTRIBUTION.md) for per-file provenance once the dataset pipeline is populated.
