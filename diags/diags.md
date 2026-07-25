# System Diagrams — IR Framework for SIEM Rule Generation

These diagrams describe **what is actually built**: a KQL/ASIM-only
System B pipeline (two LLM calls, everything else deterministic) with a
bounded repair loop, refuse-to-emit abstention, a clarification loop for
missing information, and a dedicated post-build ambiguity-scan for
genuine structural forks (§4AH).

> **Corrected from the original set.** The previous version of this file
> depicted an aspirational multi-agent, multi-target design (Threat
> Intelligence / Metadata / MITRE agents; Sigma / Splunk-SPL generators;
> OCSF normalization; HDFS / CTI-REALM telemetry execution) that the
> codebase never implemented and that is explicitly out of scope
> (`PROJECT_STATUS.md` §1.1, "KQL/ASIM-only scope"). Every diagram below
> now matches the real modules in `src/`.

## Rendered SVGs

Source `.mmd` files live in [`src/`](src/); rendered SVGs in
[`svg/`](svg/). Re-render all with:

```bash
for f in diags/src/*.mmd; do
  npx -y @mermaid-js/mermaid-cli \
    -i "$f" -o "diags/svg/$(basename "${f%.mmd}").svg" \
    -c diags/src/mermaid-config.json -p diags/src/puppeteer.json -b white
done
```

| # | Diagram | SVG |
|---|---------|-----|
| 1 | High-Level End-to-End System Architecture | [svg](svg/01_high_level_architecture.svg) |
| 2 | Agent & Stage Workflow (2 LLM calls) | [svg](svg/02_agent_workflow.svg) |
| 3 | IR Internal Structure (KqlPipeline AST) | [svg](svg/03_ir_internal_structure.svg) |
| 4 | NL → IR → KQL Transformation Flow | [svg](svg/04_transformation_flow.svg) |
| 5 | ASIM Schema Grounding | [svg](svg/05_asim_schema_grounding.svg) |
| 6 | Validation & Bounded Repair Loop | [svg](svg/06_validation_repair_loop.svg) |
| 7 | Abstention · Clarification · Disambiguation | [svg](svg/07_abstention_clarification_disambiguation.svg) |
| 8 | System A (direct) vs System B (IR-mediated) | [svg](svg/08_system_a_vs_system_b.svg) |
| 9 | Research Evaluation Pipeline | [svg](svg/09_evaluation_pipeline.svg) |
| 10 | Actual Repository Structure | [svg](svg/10_repository_structure.svg) |

**Colour legend** (consistent across all diagrams): blue = LLM /
generative step · green = deterministic code (no LLM) · amber = decision
· purple = data / output · red = abstain / refuse-to-emit.

---

## 1. High-Level End-to-End System Architecture

The real System B path, from a natural-language description to a
validated KQL detection. Only two steps are LLM calls (Extraction, IR
Builder); the validator, compiler, and syntax check are deterministic.

```mermaid
flowchart TD
  A["Natural-language detection description<br/>(rule intent / SOP)"] --> EX["Extraction Agent<br/>LLM call 1"]
  EX --> EO["ExtractionOutput<br/>event type · actors · action ·<br/>threshold &amp; time language · candidate fields"]
  EO --> IB["IR Builder Agent<br/>LLM call 2 · optional RAG grounding"]
  IB --> IR["KqlPipeline AST<br/>source_table · stages · caveats ·<br/>abstained · ambiguities"]
  IR --> VAL["Schema Validator<br/>22 hard checks + constraint traceability"]
  VAL --> DEC{"Valid?"}
  DEC -- "no · attempt &lt; 3" --> RB["Repair Loop<br/>structured error → re-prompt"]
  RB --> IB
  DEC -- "no · 3 attempts used" --> ABS["Abstain<br/>refuse to emit a runnable query"]
  DEC -- "yes" --> CMP["Deterministic Compiler<br/>no LLM — cannot hallucinate fields"]
  CMP --> SYN["Syntax Validator"]
  SYN --> VER["Verifier Agent · optional<br/>semantic intent check · advisory"]
  VER --> OUT["Validated KQL detection<br/>+ caveats / ambiguities if any"]
  OUT --> POST["Clarification &amp; Disambiguation<br/>if gaps or forks remain"]
  OUT --> DEPLOY["SIEM deployment / SOC usage"]
```

## 2. Agent & Stage Workflow — 2 LLM calls, everything else deterministic

There are exactly two generative agents on the build path (Extraction,
IR Builder), plus a post-build Ambiguity-Scan agent (§4AH) and an
optional advisory Verifier. The validator, compiler, syntax check, and
gap checker are ordinary code.

```mermaid
flowchart TD
  NL["NL detection description"] --> EX["Extraction Agent"]
  EX --> IB["IR Builder Agent"]
  IB --> VAL["Schema Validator<br/>22 checks"]
  VAL --> CMP["KQL Compiler"]
  CMP --> SYN["Syntax Validator"]
  SYN --> KQL["Validated KQL"]

  KQL --> VER["Verifier Agent<br/>semantic intent · advisory"]
  KQL --> SCAN["Ambiguity-Scan Agent<br/>post-build fork detection · §4AH"]
  KQL --> GAP["Gap Checker<br/>find_gaps() from caveats"]

  VER -. "flag (non-blocking)" .-> KQL
  SCAN -. "closed-option questions" .-> CLAR["Clarification UI"]
  GAP -. "open questions" .-> CLAR
```

## 3. Intermediate Representation — KqlPipeline AST

The real schema (`src/ir_engine/ir_schema.py`): a single source table
(one of 7 ASIM event types), an ordered list of 11 possible stage types,
plus the self-disclosure fields `caveats`, `abstained`, and
`ambiguities`.

```mermaid
flowchart TD
  A["KqlPipeline (AST root)"]
  A --> ST["source_table<br/>1 of 7 ASIM event types"]
  A --> STG["stages[] · ordered pipeline"]
  A --> CV["caveats[]<br/>self-disclosed omissions"]
  A --> AB["abstained: bool<br/>refuse-to-emit flag"]
  A --> AM["ambiguities[]<br/>structural forks"]

  STG --> S1["WhereStage"]
  STG --> S2["SummarizeStage"]
  STG --> S3["ExtendStage"]
  STG --> S4["JoinStage"]
  STG --> S5["UnionStage · ProjectStage"]
  STG --> S6["TopStage · MvExpandStage"]
  STG --> S7["MakeSeriesStage · SeriesAnomalyStage"]
  STG --> S8["ParseStage"]

  S1 --> F["Filter / FilterGroup / AndGroup<br/>field · operator · value | field_ref"]
  S2 --> AG["Aggregation(s) · group_by ·<br/>time_window · arg_max / arg_min"]
```

## 4. NL → IR → KQL Transformation Flow

Single target: KQL over ASIM. Sigma/SPL translation is shown dashed to
mark it explicitly as *not implemented* (the IR is target-agnostic in
principle, but only the KQL compiler exists).

```mermaid
flowchart LR
  A["Natural-language SOP"] --> B["Semantic parsing<br/>Extraction Agent"]
  B --> C["Structured signal<br/>event type · entities · thresholds · time"]
  C --> D["AST construction<br/>IR Builder Agent"]
  D --> E["Security IR<br/>(KqlPipeline)"]
  E --> F["Deterministic compile<br/>+ schema &amp; syntax validation"]
  F --> G["Executable ASIM / KQL rule"]
  G -. "out of scope (KQL/ASIM-only build)" .-> H["Sigma / SPL translation<br/>(not implemented)"]
```

## 5. ASIM Schema Grounding

Field names proposed by the IR Builder are grounded against the ASIM
field reference for the chosen event type; any field not in that event's
schema raises `FIELD_NOT_FOUND` (with a closest-match hint) and routes to
repair. An optional TF-IDF RAG index can additionally ground the prompt
(off by default, §4AE).

```mermaid
flowchart TD
  IB["IR Builder Agent<br/>proposes field references"] --> REF["ASIM Field Reference<br/>asim_field_reference.json"]
  RAG["RAG schema index · optional<br/>TF-IDF, off by default"] -. "grounds prompt" .-> IB

  REF --> E1["imAuthentication"]
  REF --> E2["imNetworkSession"]
  REF --> E3["imProcessCreate"]
  REF --> E4["imFileEvent"]
  REF --> E5["imDns"]
  REF --> E6["imWebSession"]
  REF --> E7["imRegistry"]

  E1 --> VAL["Schema Validator"]
  E2 --> VAL
  E3 --> VAL
  E4 --> VAL
  E5 --> VAL
  E6 --> VAL
  E7 --> VAL

  VAL --> OK["All fields exist for the<br/>chosen event type → pass"]
  VAL --> ERR["FIELD_NOT_FOUND<br/>(with closest-match hint) → repair"]
```

## 6. Validation & Bounded Repair Loop

The actual loop: max 3 attempts, structured error messages fed back into
the prompt, temperature escalation when the model repeats an identical
failing output, and abstention (not an infinite retry) on exhaustion.

```mermaid
flowchart TD
  A["IR attempt (from IR Builder)"] --> B["Schema Validator · 22 checks"]
  B --> C{"Valid?"}
  C -- "yes" --> I["Constraint-traceability check<br/>threshold number matches the NL"]
  I --> J["Compile → syntax validate"]
  J --> DONE["Validated KQL"]
  C -- "no" --> D{"attempt &lt; 3?"}
  D -- "no" --> Z["Abstain<br/>MAX_REPAIR_ATTEMPTS_EXCEEDED"]
  D -- "yes" --> E["Repair prompt<br/>structured error + previous IR +<br/>compiled-KQL preview"]
  E --> F{"identical output<br/>to last attempt?"}
  F -- "yes" --> G["Escalate temperature<br/>0 → 0.3 → 0.7"]
  F -- "no" --> H["Re-build IR"]
  G --> H
  H --> A
```

## 7. Abstention · Clarification · Disambiguation

The honest-uncertainty story. Missing information becomes open questions
(`find_gaps` → `resolve_clarification`); a genuine structural fork
becomes a closed-option question (`scan_ambiguities` → `resolve_ambiguity`);
a totally ungroundable description sets `abstained=True`, and the
compiler refuses to emit any runnable query.

```mermaid
flowchart TD
  A["Built KqlPipeline"] --> Q{"How much can be grounded<br/>from the description?"}
  Q -- "nothing groundable" --> ABS["abstained = True<br/>compiler emits no query ·<br/>pipeline_fires() = False"]
  Q -- "some filters omitted" --> CAV["caveats[] · partial abstention"]
  Q -- "fully grounded" --> OK["Runnable KQL"]

  ABS --> GAP["find_gaps() → Gap[]"]
  CAV --> GAP
  GAP --> CQ["Open questions<br/>missing info + real-data defaults"]
  CQ --> RC["resolve_clarification()<br/>merge answers → rebuild"]

  A --> SCAN["Ambiguity-Scan Agent<br/>scan_ambiguities()"]
  OK --> SCAN
  SCAN --> AMB{"Genuine structural fork?"}
  AMB -- "yes" --> CC["Closed-option question<br/>2+ readings · committed one preselected"]
  CC --> RA["resolve_ambiguity()<br/>rebuild on chosen option"]
  AMB -- "no (common case)" --> NONE["No disambiguation needed"]

  RC --> REBUILD["Re-validated pipeline"]
  RA --> REBUILD
```

## 8. Direct LLM (System A) vs IR-Mediated Pipeline (System B)

The core comparison, with the measured headline numbers: direct
generation reaches ~6.7% Field Validity Rate on fresh inputs; the
IR-mediated pipeline reaches ~86.7%.

```mermaid
flowchart TD
  subgraph SA["System A — direct generation"]
    direction TB
    A1["NL description"] --> A2["Single LLM prompt"]
    A2 --> A3["KQL string"]
    A3 --> A4["No validation · no repair<br/>Field Validity Rate ≈ 6.7%"]
  end

  subgraph SB["System B — IR-mediated"]
    direction TB
    B1["NL description"] --> B2["Extraction Agent"]
    B2 --> B3["IR Builder Agent"]
    B3 --> B4["Schema Validator + bounded repair"]
    B4 --> B5["Deterministic Compiler"]
    B5 --> B6["Validated KQL<br/>Field Validity Rate ≈ 86.7%"]
  end
```

## 9. Research Evaluation Pipeline

Held-out real Sentinel rules (18 locked from day 1, run N=5 for
variance), System A vs System B, scored on the metrics actually used —
including Logic Correctness on a 0–3 scale by two independent raters
(Cohen's κ), reported as a distribution rather than a single pass/fail
cutoff (§4AE). The 50-case real-data clarification eval validates the
clarification design separately.

```mermaid
flowchart TD
  A["Held-out real Sentinel rules<br/>18 locked from day 1 · N=5 runs"] --> B1["System A · direct LLM"]
  A --> B2["System B · IR-mediated"]
  B1 --> C["Metric harness"]
  B2 --> C

  C --> M1["Syntax Validity Rate (SVR)"]
  C --> M2["Field Validity Rate (FVR)"]
  C --> M3["Completion rate"]
  C --> M4["Repair recovery rate"]
  C --> M5["Logic Correctness 0–3<br/>two independent raters · Cohen's κ"]

  M1 --> R["Comparative analysis"]
  M2 --> R
  M3 --> R
  M4 --> R
  M5 --> R

  R --> RD["Reported as a score distribution,<br/>not a single pass/fail cutoff (§4AE)"]

  D2["Real-data clarification eval<br/>50 fresh cases · 80% under-specified ·<br/>60% abstention"] -. "validates the<br/>clarification design" .-> R
```

## 10. Actual Repository Structure

The real module layout under `src/` (plus `tests/`, `eval/`, `data/`,
`docs/`, and the Streamlit `app.py`).

```mermaid
flowchart TD
  ROOT["repo root"] --> SRC["src/"]
  ROOT --> TST["tests/ · unit + live integration"]
  ROOT --> EVL["eval/ · harnesses + results"]
  ROOT --> DAT["data/ · schema · processed pairs · rag_indexes"]
  ROOT --> DOC["docs/ · PROJECT_STATUS · architecture"]
  ROOT --> APP["app.py · Streamlit demo"]

  SRC --> AG["agents/<br/>extraction · ir_builder ·<br/>ambiguity_scan · verifier"]
  SRC --> IE["ir_engine/<br/>ir_schema · ir_validator"]
  SRC --> GN["generator/<br/>compiler · filters"]
  SRC --> VD["validation/<br/>syntax_validators"]
  SRC --> PL["pipeline/<br/>system_b · repair_loop"]
  SRC --> CL["clarification/<br/>gap_checker · clarify"]
  SRC --> EXE["execution/<br/>ir_interpreter"]
  SRC --> RT["retrieval/<br/>TF-IDF RAG · opt-in"]
  SRC --> BL["baseline/<br/>System A · direct gen"]
```
