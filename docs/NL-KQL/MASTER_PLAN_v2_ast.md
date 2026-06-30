# Master Plan — Schema-Grounded Natural Language to KQL Translation

**A complete planning and implementation reference for an independent research project on reducing syntax and field hallucination in LLM-generated Microsoft Sentinel detection rules.**

> **Author:** Mohit — B.Tech, Electronics & Computer Engineering, VIT Chennai
> **Status:** Active — dataset construction phase
> **Document purpose:** This is the single, exhaustive reference for this project — covering motivation, architecture, dataset methodology, evaluation design, and execution planning in one continuous document. The repository's `README.md` is a shorter landing page; the `docs/` folder splits this same material into separately-navigable files for day-to-day reference. This document is the complete version, intended to be read top to bottom once and then used as a lookup reference throughout the project.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Motivation](#2-motivation)
3. [Background — KQL, ASIM, and Intermediate Representations](#3-background-kql-asim-and-intermediate-representations)
4. [Formal Problem Statement](#4-formal-problem-statement)
5. [Failure Taxonomy](#5-failure-taxonomy)
6. [Research Questions](#6-research-questions)
7. [Hypotheses](#7-hypotheses)
8. [Related Work and Positioning](#8-related-work-and-positioning)
9. [System Architecture](#9-system-architecture)
10. [The Security IR — Full Specification](#10-the-security-ir-full-specification)
11. [Agent Specifications](#11-agent-specifications)
12. [Validators and the Repair Loop](#12-validators-and-the-repair-loop)
13. [KQL Generation — Template Compiler](#13-kql-generation-template-compiler)
14. [Worked End-to-End Example](#14-worked-end-to-end-example)
15. [KQL and ASIM Technical Reference](#15-kql-and-asim-technical-reference)
16. [Dataset Construction](#16-dataset-construction)
17. [Evaluation Methodology](#17-evaluation-methodology)
18. [Ablation Studies](#18-ablation-studies)
19. [Statistical Treatment](#19-statistical-treatment)
20. [Technology Stack](#20-technology-stack)
21. [Repository Structure](#21-repository-structure)
22. [Project Timeline](#22-project-timeline)
23. [Risks and Mitigations](#23-risks-and-mitigations)
24. [Claimed Contributions](#24-claimed-contributions)
25. [Limitations](#25-limitations)
26. [Future Extensions](#26-future-extensions)
27. [Execution Checklist](#27-execution-checklist)

---

## 1. Executive Summary

Security Operations Center (SOC) analysts routinely translate natural-language detection requirements — a line in a Standard Operating Procedure, a sentence in a threat intelligence report, a verbal ask from a senior analyst — into executable Kusto Query Language (KQL) rules for Microsoft Sentinel. Direct large language model (LLM) generation of KQL from such descriptions is unreliable: single-prompt generation produces syntactically invalid queries, hallucinated field names, and logically incorrect filters at rates high enough to make unsupervised use unsafe in a SOC context.

This project investigates whether inserting an explicit, schema-validated **Intermediate Representation (IR)** between natural language input and KQL output — combined with a small multi-agent extraction pipeline and a closed-loop syntax/field repair mechanism — measurably reduces hallucination compared to direct single-prompt generation.

The system is evaluated against a baseline (direct LLM-to-KQL) on a purpose-built dataset of natural-language detection descriptions paired with ground-truth KQL, sourced and adapted from Microsoft's public Azure-Sentinel GitHub repository, using syntax validity, field validity against the Microsoft Sentinel/ASIM schema, and structural similarity to ground truth (CodeBLEU) as primary metrics.

The project is scoped to one target platform (KQL / Microsoft Sentinel), one schema standard (ASIM), and a 2–3 agent pipeline — narrow enough to evaluate with genuine statistical rigor: a real dataset, a fair baseline, three targeted ablations, and significance testing, completable as an individual research effort within a single research cycle (approximately 4–6 months part-time).

**The central claim being tested:** an explicit intermediate representation between natural language and executable query syntax reduces hallucination relative to direct generation — and this project measures *how much*, *where* (which complexity tiers), and *why* (which specific design decision — schema grounding, agent decomposition, or repair — actually drives the result).

---

## 2. Motivation

### 2.1 Why This Problem Matters

Detection engineering is a persistent bottleneck in SOC operations. Threat intelligence and SOPs arrive continuously as prose; converting that prose into deployable detection logic is slow, requires KQL fluency that not every analyst has, and is highly error-prone even for experienced engineers because Sentinel's underlying tables and field names are not memorized — they are looked up. This creates a natural opportunity for AI assistance, but also a natural trap: KQL has just enough surface similarity to SQL that LLMs frequently produce confident, fluent, and wrong queries.

This is not a hypothetical concern. Microsoft's own Sentinel repository pull-request pipeline runs an automated KQL syntax validator and a detection-schema validator against every submitted rule — specifically because hand-written and AI-assisted rules alike frequently fail to compile or reference tables that don't exist in a given workspace. This confirms that field- and syntax-level errors are a recognized, persistent problem even among engineers contributing to the canonical reference repository, not just naive LLM output.

### 2.2 Why a Narrow, Rigorous Scope

The instinct when designing a system like this is to generalize immediately: support every SIEM platform, every schema normalization standard, every validation stage, autonomous repair, threat-intel ingestion, MITRE mapping, and so on. That instinct produces a strong product roadmap and a weak research project. A research contribution is judged by how rigorously a specific claim is tested, not by how many features are present.

This project deliberately commits to:

- **One platform** — KQL / Microsoft Sentinel
- **One schema standard** — ASIM (Advanced Security Information Model)
- **One core scientific question** — does an explicit, schema-validated IR reduce hallucination relative to direct generation?

so that the evaluation can be deep rather than superficial. The trade-off is explicit and intentional: breadth is sacrificed for evaluation rigor. A reviewer should be able to look at the dataset, the baseline, the ablations, and the metrics, and conclude that the central claim was actually tested — not merely demonstrated.

Extensions such as additional target platforms, additional schema standards, deeper agent decomposition, and full telemetry execution validation are real and valuable directions — they are documented in [Section 26: Future Extensions](#26-future-extensions) as explicit next steps, not folded into this project's scope.

---

## 3. Background — KQL, ASIM, and Intermediate Representations

### 3.1 What KQL Is and Why It Is Hard to Generate

Kusto Query Language (KQL) is the query language used by Microsoft Sentinel, Azure Monitor, and Azure Data Explorer. It is a pipe-based, read-only query language: data flows through a sequence of operators (`where`, `summarize`, `project`, `join`, `extend`, `bin`, etc.) separated by the pipe character. Although it superficially resembles SQL in places, its operator set, aggregation syntax, and time-window handling are distinct, and naive generation frequently produces a hybrid of KQL, SQL, and Splunk SPL syntax that parses in none of the three.

KQL generation difficulty has three independent sources of error, treated as separate, separately-measured failure modes throughout this project (see [Section 5](#5-failure-taxonomy)):

- **Syntax errors** — invalid operators, wrong clause ordering, or SQL/SPL syntax bleeding into KQL (e.g., using `CONTAINS` as a standalone clause, or `GROUP BY` instead of `summarize ... by`).
- **Field/table errors** — referencing a table or column name that does not exist in the target schema, often a plausible-sounding name borrowed from a different table or a different SIEM platform entirely.
- **Logic errors** — syntactically valid, schema-valid queries that nonetheless do not implement the described detection logic correctly (wrong enum value, missing time window, wrong aggregation direction).

### 3.2 What ASIM Is

The Advanced Security Information Model (ASIM) is Microsoft's normalization layer for Sentinel: it defines a set of standard schemas (e.g., `AuthenticationEvent`, `NetworkSessionEvent`, `ProcessEvent`) with standardized field names, so that detection content can be written once against the normalized schema and work across many underlying data connectors. ASIM solves a specific practical problem: raw log data arrives from dozens of different products (Azure AD, Windows Security Events, Syslog-based firewalls, etc.), each with its own field names for conceptually the same thing — a source IP address might be `SourceIP`, `src_ip`, `c-ip`, or `ClientIP` depending on the connector.

```
Raw connector data (SigninLogs, OktaSSO, etc.)
        │
        ▼
   ASIM Parser  (maps raw fields → normalized fields)
        │
        ▼
   imAuthentication  (normalized, queryable view)
```

ASIM gives this project a citable, versioned, machine-checkable source of truth for "does this field exist," which is exactly what's needed to measure field hallucination objectively rather than subjectively. It is also the schema layer practitioners are actually encouraged to write detection content against — not a raw, connector-specific schema — which is part of why it is the right single-schema choice for this project's scope.

### 3.3 Why an Intermediate Representation, Borrowed from Compiler Design

In compiler design, source code is not translated directly to machine code. It first passes through an intermediate representation (IR) — a structured, language-agnostic form that captures the program's logic independently of both the source syntax and the target instruction set. This separation is what allows one compiler frontend (e.g., a C parser) to target many backends (x86, ARM, WASM) without re-implementing language understanding for each target, and it is also what makes optimization and validation tractable: it's far easier to check an IR for well-formedness than to check generated assembly.

This project borrows that idea directly: instead of asking an LLM to go straight from "detect credential stuffing" to a KQL string, the system first asks it to produce a structured, typed, schema-checkable JSON object — the **Security IR** — describing the detection logic (event type, filters, aggregation, threshold, time window) in a vendor-neutral form. Only once that IR has been validated against the ASIM schema is it deterministically compiled into KQL via templates.

**The bet:** this separates "does the model understand the threat" from "does the model remember KQL syntax," and the second problem is better solved by deterministic code than by free-form generation.

| | Compiler Pipeline | This Project |
|---|---|---|
| Source | C / Java / Rust source code | Natural language detection description |
| Intermediate Layer | LLVM IR, JVM bytecode — structured, target-agnostic | Security IR — typed JSON, ASIM-schema validated |
| Target | x86, ARM, WASM machine code | Executable KQL for Microsoft Sentinel |

---

## 4. Formal Problem Statement

> **Given** a natural-language description of a detection requirement (a sentence or short paragraph drawn from an SOP, a threat intelligence report, or analyst shorthand), and the ASIM/Sentinel schema as a ground-truth field reference, **generate** a KQL query that is syntactically valid, uses only fields that exist in the target schema, and correctly implements the described detection logic — while requiring less correction effort than direct single-prompt LLM generation.

The two gaps this problem spans are made explicit in the diagram below. The IR layer lives between them and is the system's testable artifact:

```
LAYER 1 — NATURAL LANGUAGE
  "Detect when an attacker attempts logins with many different
   usernames from a single IP address"
          │
          │  GAP 1 — Threat → Detection Logic
          │  (which event, which aggregation, which threshold)
          ▼
LAYER 2 — SECURITY IR  (this project's core contribution)
  { "source_table": "AuthenticationEvent",
    "stages": [
      { "type": "summarize",
        "aggregations": [{"function": "distinct_count", "field": "TargetUsername", "result_alias": "DistinctUsers"}],
        "group_by": ["SrcIpAddr"],
        "time_window": "PT5M" },
      { "type": "where",
        "filters": [{"field": "DistinctUsers", "operator": ">", "value": 20}] }
    ] }
          │
          │  GAP 2 — Logic → KQL Syntax
          │  (field names, operators, time bins)
          ▼
LAYER 3 — EXECUTABLE KQL
  imAuthentication
  | where EventResult == "Failure"
  | summarize DistinctUsers = dcount(TargetUsername)
      by SrcIpAddr, bin(TimeGenerated, 5m)
  | where DistinctUsers > 20
```

---

## 5. Failure Taxonomy

Rather than treating "hallucination" as one phenomenon, the evaluation separates it into independently measurable dimensions. Each has its own metric and can be caught at a different stage of the pipeline:

| Failure Dimension | Concrete Example | Caught By | Metric |
|---|---|---|---|
| **Syntax invalidity** | Using `CONTAINS` as a standalone clause; SQL-style `GROUP BY` | KQL Syntax Validator | SVR |
| **Field hallucination** | `SourceIP` instead of `SrcIpAddr` | Schema Validator (on the IR) | FVR |
| **Table hallucination** | Querying a table that doesn't exist in Sentinel/ASIM | Schema Validator | FVR |
| **Missing temporal logic** | Aggregation with no `bin()`/time window — scans the entire dataset | Schema Validator (explicit `time_window` rule) | SVR (indirect), manual |
| **Logic/semantic error** | `EventResult == "Success"` when the rule means failed logins | Manual review only | Logic Correctness |

**Why this taxonomy matters:** collapsing all five into one metric would make it impossible to tell which failure mode dominates, which is the exact information needed to decide whether the IR's schema grounding, its structural output, or the repair loop is driving observed improvements. The taxonomy is one of the project's own contributions when applied empirically rather than just asserted.

---

## 6. Research Questions

| ID | Research Question |
|---|---|
| **RQ1** | Does inserting a schema-validated intermediate representation between natural language and KQL reduce syntax and field hallucination rates compared to direct single-prompt LLM generation? |
| **RQ2** | Does decomposing extraction into separate agents (entity/behavior extraction → IR construction) improve IR correctness compared to a single monolithic extraction prompt? |
| **RQ3** | Does a closed-loop syntax/field repair mechanism (re-prompting with the specific validation error) meaningfully improve final success rate within a small, bounded number of iterations (≤ 3)? |
| **RQ4** | How does performance vary across detection-logic complexity — simple single-filter rules vs. rules requiring aggregation, multi-field correlation, or temporal windows? |

---

## 7. Hypotheses

| ID | Hypothesis | Rationale | Would Be Falsified By |
|---|---|---|---|
| **H1** | IR-mediated generation achieves materially higher syntax validity than direct generation (target: ≥ 90% vs. an expected 55–75% baseline) | Deterministic templates cannot produce invalid syntax by construction; only template-filling can fail, which is a narrower, more checkable task | System B's SVR is not meaningfully higher than System A's, or No-Repair IR (Ablation 1) performs no better than System A on SVR |
| **H2** | IR-mediated generation achieves higher field validity than direct generation | Schema grounding turns an open-ended recall task into a constrained selection task | System B's FVR is not meaningfully higher than System A's, or No Schema Grounding (Ablation 3) performs comparably to full System B on FVR |
| **H3** | The closed-loop repair step recovers ≥ 50% of initially-failing cases within 3 iterations, with diminishing returns after iteration 2 | Most syntax/field errors are local and mechanical (one wrong token), which targeted re-prompting with the exact validator error message is well-suited to fix | Repair Recovery Rate is below 50%, or recovery doesn't show diminishing returns |
| **H4** | The performance gap between IR-mediated and direct generation widens as detection-logic complexity increases (aggregations, joins, temporal correlation) | Complex logic requires holding more constraints in working memory simultaneously during single-shot generation; an explicit IR offloads that bookkeeping | The System B − System A gap is flat or shrinking across Simple → Moderate → Complex tiers |

All four hypotheses are falsifiable and are stated as such. A clean negative or mixed finding — e.g., schema grounding helps but agent decomposition specifically does not (H2 holds, RQ2 resolves no) — is a valid, reportable, and useful result. The evaluation is structured to produce that kind of granular attribution, not just one aggregate before/after number.

---

## 8. Related Work and Positioning

### 8.1 Existing Tools

| Tool / Platform | Approach | Gap This Project Addresses |
|---|---|---|
| **Microsoft Copilot for Security** | General-purpose AI assistant embedded in Sentinel; can draft KQL conversationally | Not detection-rule-focused specifically; no published systematic hallucination evaluation; closed system, not independently benchmarkable |
| **Uncoder AI (SOC Prime)** | Converts IOCs and rules across SIEM platforms | Primarily syntax-translation between existing rules, not NL-to-rule generation from prose; proprietary |
| **Sigma CLI / pySigma** | Converts pre-written Sigma rules into platform-specific queries (including KQL) | Requires a human to already have written a structured Sigma rule; does not solve the NL understanding problem this project targets |
| **Direct LLM prompting (GPT-4, etc.)** | Single-prompt generation of detection rules from text | This is the baseline this project compares against, not a solved alternative |

### 8.2 Academic Context

**Text-to-SQL research** is the closest published analogue. A substantial body of work has explored schema-grounded generation for SQL — showing that grounding generation in an explicit schema representation reduces invalid-column and invalid-table errors relative to ungrounded generation. This project's contribution is testing whether the same effect holds for KQL against the ASIM schema — a different query paradigm (pipe-based, not declarative-relational) and a different schema model (event-normalization schema, not a relational database schema) — and additionally testing whether a closed validation-repair loop further improves results within a small iteration budget.

**Code generation** research (Codex, StarCoder, CodeBLEU as an evaluation metric) establishes that structural-similarity metrics for generated code are tractable; this project applies CodeBLEU to KQL specifically, which has not been a standard target language in this literature.

**Cybersecurity NLP** work (CyBERT, SecBERT, CyNER-style entity/IOC extraction models) addresses entity recognition, not end-to-end rule generation. The Extraction Agent in this project's pipeline is a narrower, simpler version of this idea, used in service of IR construction rather than as an end goal.

**Compiler intermediate representations** (LLVM IR, JVM bytecode as a target-agnostic middle layer) are the conceptual ancestor of the Security IR. The application of this pattern to detection-rule generation has not been published in the work known to the author at time of writing.

### 8.3 Positioning Statement

This project sits at the intersection of text-to-SQL schema-grounding research and cybersecurity NLP. Its specific novel claim is: *the IR-as-intermediate-layer pattern, combined with schema-validated generation and bounded repair, measurably reduces the specific failure modes of syntax invalidity and field hallucination in KQL generation, and the benefit concentrates in higher-complexity detection logic.* That claim has not been tested for KQL specifically, with the ASIM schema, and with the level of evaluation rigor (fair baseline, stratified analysis, significance testing) this project provides.

---

## 9. System Architecture

### 9.1 Design Principles

Three architectural commitments run through every component, and every design decision traces back to one of them:

1. **Push correctness left.** Every error category should be caught as early in the pipeline as the information needed to catch it becomes available. Field hallucination can be caught the moment the IR references a field, against a schema that's already loaded — not after KQL is generated.
2. **Generative steps should be narrow; everything else should be deterministic.** The only two LLM calls in System B are extraction and IR construction. Compilation from IR to KQL is template substitution — zero degrees of freedom, zero hallucination surface.
3. **Every validator failure should produce a structured, actionable error, not a pass/fail boolean.** `"field 'SourceIP' not found in schema AuthenticationEvent; did you mean 'SrcIpAddr'?"` is repairable. `False` is not.

### 9.2 System A — Baseline (Direct Generation)

A single prompt containing the natural-language detection description, a brief KQL syntax primer, and a list of relevant ASIM schema fields is sent to the LLM, which is asked to return a KQL query directly. This mirrors how a SOC analyst would naively use a general-purpose assistant today.

```
NL input + ASIM field reference + KQL syntax primer (few-shot)
        │
        ▼
   [Single LLM call]
        │
        ▼
   Raw KQL string output  →  scored post-hoc by validators
```

System A makes exactly **one LLM call per case**. No validation, no repair. Its raw output is scored by the Syntax Validator and Field Validator post-hoc, purely for measurement.

### 9.3 System B — IR-Mediated Generation

```
  NL input
     │
     ▼
  [Extraction Agent]  ──reads──>  ASIM field reference (read-only)
     │
     │  produces: structured extraction
     │  (entities, behaviors, threshold/time language)
     ▼
  [IR Builder Agent] ──> Security IR (JSON, Pydantic-validated)
     │
     ▼
  [Schema Validator] ──fail──> structured error
     │ pass                          │
     ▼                               │  fed back to IR Builder
  [KQL Generator]                    │  Agent (≤ 3 attempts)
  (Jinja2, deterministic,            │
   zero LLM calls)                   │
     │                               │
     ▼                               │
  [KQL Syntax Validator] ──fail──────┘
     │ pass
     ▼
  Validated KQL output
```

Six discrete stages, **two generative** (Extraction Agent, IR Builder Agent), **four deterministic** (Schema Validator, KQL Generator, KQL Syntax Validator, and the repair loop's retry logic).

### 9.4 Why Exactly 2–3 Agents

More agents — separate threat-intel extraction, metadata generation, MITRE mapping, orchestration — decompose along organizational lines that matter for a production system but are not independently testable research variables at this scope. This project keeps exactly the decomposition needed to answer RQ2 (does splitting extraction from IR construction help) and no more. The number of generative steps is the variable being studied, not the engineering overhead.

### 9.5 The Baseline Fairness Contract

A weak baseline produces a paper that doesn't survive scrutiny, however good System B's numbers look in isolation. System A is kept fair by ensuring:

- **Same schema access** — System A receives the same ASIM field reference in its prompt that System B's IR Builder Agent receives. The comparison is about IR-mediation vs. direct generation, not about who has schema access.
- **Same underlying LLM, same provider, same temperature** across both systems.
- **Few-shot, not zero-shot** — System A's prompt includes 2–3 worked NL→KQL examples, matching how a reasonably careful real-world user would actually prompt a general-purpose assistant.
- **System A's failures are qualitatively reviewed, not just counted** — the failure taxonomy is applied to a sample of System A's specific failures and reported with examples.

---

## 10. The Security IR — Full Specification

### 10.1 Design Goals

The IR schema is designed with four properties that directly serve the project's goals:

1. **Vendor-neutral** — no KQL-specific field names or syntax appear in the IR itself. The same IR could, in principle, be compiled to Sigma or SPL by adding a new template.
2. **Machine-checkable** — every field has a type, every referenced field name can be validated against the ASIM schema at IR-validation time.
3. **Minimal but complete** — enough fields to express the detection logic in real Sentinel analytics rules; not so many that the schema itself becomes a burden.
4. **Closed to unknown fields** — `extra = "forbid"` in Pydantic rejects any hallucinated field at parse time, converting a silent failure into an immediate, catchable error.

### 10.2 Pydantic Schema

**Status note (see `PROJECT_STATUS.md` §4K):** this is the actual shipped
schema (`src/ir_engine/ir_schema.py`) after a hardening pass found and
fixed a crash bug and a missing-operator-support bug in the version
originally drafted here — not the original sketch.

```python
from enum import Enum
from typing import List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

class ASIMEventType(str, Enum):
    AUTHENTICATION = "AuthenticationEvent"
    NETWORK_SESSION = "NetworkSessionEvent"
    PROCESS = "ProcessEvent"
    FILE = "FileEvent"
    DNS = "DnsEvent"
    WEB_SESSION = "WebSessionEvent"
    REGISTRY = "RegistryEvent"

class FilterOperator(str, Enum):
    EQ = "=="
    NEQ = "!="
    CONTAINS = "contains"
    NOT_CONTAINS = "!contains"
    STARTSWITH = "startswith"
    NOT_STARTSWITH = "!startswith"
    ENDSWITH = "endswith"
    NOT_ENDSWITH = "!endswith"
    IN = "in"
    NOT_IN = "!in"
    HAS = "has"
    NOT_HAS = "!has"
    HAS_ANY = "has_any"
    MATCHES_REGEX = "matches regex"
    GT = ">"
    LT = "<"
    GTE = ">="
    LTE = "<="

class Filter(BaseModel):
    type: Literal["filter"] = "filter"
    field: str
    operator: FilterOperator
    # List[Union[str, int, float]], not List[str]: rejecting a numeric
    # list (e.g. "DstPortNumber in (139, 445)") cascaded into a confusing
    # multi-error union-match failure — found live, fixed in §4K.
    value: Union[str, int, float, bool, List[Union[str, int, float]]]

class FilterGroup(BaseModel):
    """A parenthesized OR block, still AND-ed with everything else in the
    same WhereStage. Carried over from the original flat IR unchanged."""
    type: Literal["group"] = "group"
    conditions: List[Filter] = Field(min_length=2)

class AggregationFunction(str, Enum):
    COUNT = "count"
    DISTINCT_COUNT = "distinct_count"
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    PERCENTILE = "percentile"
    MAKE_SET = "make_set"
    MAKE_LIST = "make_list"

class Aggregation(BaseModel):
    function: AggregationFunction
    field: Optional[str] = None
    result_alias: str = "AggregatedValue"
    percentile: Optional[float] = None  # required, 0-100, iff function="percentile"
    limit: Optional[int] = None         # optional cap for make_set/make_list

class ComputedField(BaseModel):
    alias: str
    expression: str  # raw KQL expression — see §12.1 for how this is
                      # checked despite being an unstructured string

class JoinKind(str, Enum):
    INNER = "inner"
    LEFTANTI = "leftanti"
    LEFTOUTER = "leftouter"

class WhereStage(BaseModel):
    type: Literal["where"] = "where"
    filters: List[Union[Filter, FilterGroup]] = Field(default_factory=list)

class SummarizeStage(BaseModel):
    type: Literal["summarize"] = "summarize"
    aggregations: List[Aggregation] = Field(default_factory=list)
    group_by: Optional[List[str]] = None
    time_window: Optional[str] = None

class ExtendStage(BaseModel):
    type: Literal["extend"] = "extend"
    computed_fields: List[ComputedField] = Field(default_factory=list)

class JoinStage(BaseModel):
    type: Literal["join"] = "join"
    kind: JoinKind = JoinKind.INNER
    # Forward ref, not Any: with Any, a malformed nested pipeline parsed
    # "successfully" as a raw dict and crashed the recursive validator
    # with AttributeError instead of failing validation cleanly — found
    # live, fixed in §4K.
    right_pipeline: "KqlPipeline"
    join_on: List[str] = Field(min_length=1)

class UnionStage(BaseModel):
    type: Literal["union"] = "union"
    tables: List[str]

class ProjectStage(BaseModel):
    type: Literal["project"] = "project"
    fields: List[str]

class TopStage(BaseModel):
    type: Literal["top"] = "top"
    limit: int
    by_field: str
    desc: bool = True

Stage = Union[
    WhereStage, SummarizeStage, ExtendStage, JoinStage,
    UnionStage, ProjectStage, TopStage,
]

class KqlPipeline(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_table: Union[ASIMEventType, str]
    stages: List[Stage] = Field(default_factory=list)

# Resolves the JoinStage.right_pipeline forward reference now that
# KqlPipeline itself is defined.
JoinStage.model_rebuild()
KqlPipeline.model_rebuild()
```

### 10.3 Why a Pipeline AST?

Real-world KQL is a sequential pipeline of tabular operators (`| where ... | summarize ... | extend ... | join ... | summarize ...`). By moving from a flat JSON object to a composable AST, the framework gains the flexibility to express chained joins, multi-stage aggregations, computed fields, and unions. It supports arbitrary `source_table` strings as well as predefined `ASIMEventType` enums.

### 10.4 Why `extra = "forbid"` Matters

If the IR Builder Agent hallucinates a field name that isn't part of the schema (e.g., `"severity_score"` instead of using a known key), Pydantic rejects the object outright at parse time rather than silently accepting it. This converts a category of error that would otherwise surface much later into an immediate, catchable validation failure. This is consistent with the "push correctness left" design principle.

### 10.5 What Is Explicitly Excluded from This IR

The following are real, useful extensions — excluded now because they are orthogonal to the hallucination question this project tests:

- MITRE ATT&CK technique/tactic mapping fields
- Cross-platform vendor mapping tags
- Confidence/severity metadata

The schema is designed so all of these can be added as new optional fields later without breaking the existing template compiler.

---

## 11. Agent Specifications

### 11.1 Extraction Agent

**Purpose:** parse the natural-language input into candidate entities, behaviors, and detection intent — in a loose, pre-schema form.

**Input:** raw NL description string.

**Output:** a structured (but not yet schema-validated) extraction object:

```python
class ExtractionOutput(BaseModel):
    likely_event_type:    str             # free-text guess, not yet constrained to enum
    actors:               list[str]       # e.g. ["attacker", "source IP"]
    action_description:   str             # e.g. "attempts logins with many different usernames"
    threshold_language:   Optional[str]   # e.g. "many different" — not yet a number
    time_language:        Optional[str]   # e.g. "within a short window" — not yet a duration
    candidate_fields:     list[str]       # field names the model believes are relevant, pre-validation
```

**Prompt sketch:**

```
SYSTEM: You are a security analyst extracting structured signal from a
natural language detection description. Do NOT guess at exact ASIM field
names or KQL syntax — that happens in a later step. Your job is only to
identify: the type of event being described, the actors involved, the
core action/behavior, any threshold language (e.g. "many", "more than
10"), any time-window language (e.g. "within five minutes",
"repeatedly"), and field names you believe are relevant.

USER: {nl_description}
```

**Why intentionally under-constrained:** the separation between this agent and the IR Builder Agent is the variable being tested by RQ2. The Extraction Agent is deliberately loose — it surfaces candidate signal, not a schema-conformant structure. The IR Builder Agent commits to the schema. Whether splitting these two tasks helps is what Ablation 2 (Monolithic Extraction) tests directly.

**Status note:** the sketch above is the original design intent and still holds structurally, but the real, shipping `_SYSTEM_PROMPT` in `src/agents/extraction_agent.py` has grown two more live-found rules beyond it: (1) `likely_event_type` must name the technical event *category* (e.g. "process execution"), never the attacker's technique/outcome (e.g. "file wiping") — a framing bug that was steering the IR Builder to the wrong ASIM table even when the description's own technical details pointed elsewhere; (2) when the description names a specific, well-known tool (e.g. "Sysinternals sdelete") without spelling out its exact command-line flags, the agent should recall the tool's real, documented flags from its own knowledge rather than leaving the IR Builder to improvise (and invent a plausible-but-wrong one) — found live tracing the `5b6ae038` sdelete case's `-original` paraphrase, where the raw text never states the flags at all. Read the source file for the current, exact wording rather than this sketch.

### 11.2 IR Builder Agent

**Purpose:** convert the extraction output into a typed, Pydantic-valid `KqlPipeline` object (not `SecurityIR` — see [§10.2](#102-the-kqlpipeline-ast-schema) for the migration history), selecting fields only from the supplied ASIM field reference rather than free recall.

**Input:** `ExtractionOutput` + the ASIM field reference for the candidate event type + (on repair) a structured validator error.

**Status note:** the prompt sketches below capture the original shape (system prompt + field reference + schema + repair-on-error) and that shape still holds, but they are illustrative only — they predate the AST migration and never described the real prompt even at the time. The real, shipping prompt in `src/agents/ir_builder_agent.py` is dramatically larger: a ~200-line `_COMMON_MISTAKES` block (shared with `monolithic_agent.py`) encoding every live-found failure mode this project's rounds caught — source-table disambiguation (DNS/HTTP/process), schema-mutation rules for `summarize`/`extend`, FilterGroup-vs-AND semantics, tautology avoidance, JoinStage usage per kind, and several fully worked examples (disguised-tool evasion, baseline-vs-current, percentile-across-groups). Reproducing it here would just be a second copy that drifts out of sync the way this section already did once — read the source file directly.

**Prompt sketch (first attempt, illustrative shape only):**

```
SYSTEM: You are converting a structured extraction into an AST-based
Security IR KqlPipeline object that conforms exactly to the schema below.
You may ONLY use field names that appear in the provided ASIM field
reference — do not infer or guess field names from general knowledge of
similar platforms.

ASIM field reference for {likely_event_type}:
{asim_field_list}

[... the full _COMMON_MISTAKES guidance block ...]

{format_instructions}

Return ONLY the JSON object. No explanation.

USER: {extraction_output}
```

**Prompt sketch (repair attempt, ≤ 3 total):**

```
SYSTEM: Your previous IR failed validation with this error:
{structured_validator_error}

Correct ONLY the issue described. Do not change other parts of the IR
unless necessary to fix this specific error.

Previous IR:
{previous_ir_json}

ASIM field reference for {likely_event_type}:
{asim_field_list}

[... the same _COMMON_MISTAKES guidance block ...]

Return ONLY the corrected JSON object.

USER: Correct the IR.
```

**Why the repair prompt is narrow:** "fix this specific error" rather than "try again" prevents the model from re-generating the IR from scratch on each repair attempt, which risks introducing a new error while fixing the old one. Targeted re-prompting is also what makes Repair Recovery Rate (H3) interpretable: if the model fixes a field-not-found error, that's a direct, mechanical response to a precise instruction — not a statistical artifact of random regeneration.

---

## 12. Validators and the Repair Loop

### 12.1 Schema Validator

**Status note (see `PROJECT_STATUS.md` §4K–§4P):** the version originally
drafted here had three checks; live-testing after the AST migration
shipped found that was a small fraction of what the original flat
`SecurityIR` validator had, plus one bug it documented
(`MISSING_TIME_WINDOW`) that didn't actually exist in the shipped code.
The table below is the real, current check set in
`src/ir_engine/ir_validator.py` — 15 hard-error types plus one advisory
warning, exhaustively cross-checked against the source file by
`tests/unit/test_validator_inventory.py`.

Pure Python, no LLM call. A **stateful schema tracker**: walks the AST
stage by stage, maintaining `available_schema` (which fields exist at
this point in the pipeline) and `count_like_aliases` (which came from a
`count`/`distinct_count` aggregation, for the degenerate-threshold check).
Checks run in order, short-circuiting on the first failure:

| Error type | What it catches |
|---|---|
| `INVALID_SOURCE_TABLE` | `source_table` isn't a recognized ASIM event type — checked before any field check |
| `FIELD_NOT_FOUND` | A field reference not in the schema available *at that point* — including inside an `extend` expression's referenced identifiers and an `AndGroup`'s conditions. The suggested closest match now includes a value-type hint (e.g. "expects a port number, e.g. 443") when the field name matches a recognized ASIM naming convention |
| `FUNCTION_CALL_AS_LITERAL_VALUE` | A filter value that looks like a KQL function call (`"ago(1h)"`) but is compared as literal text, never evaluated (§4O) |
| `DEGENERATE_THRESHOLD` | A where-filter on a count/dcount result that's trivially true for any existing group (`> 0`, `>= 1`) |
| `TAUTOLOGICAL_FILTER_GROUP` | An OR-group that's always true — all-negated conditions on the same field with different values, or a direct complementary pair (`X in (...) or X !in (...)`) |
| `DUPLICATE_AGGREGATION_ALIAS` | Two aggregations in one summarize sharing a result_alias |
| `AGGREGATION_MISSING_FIELD` | A non-count function with no field |
| `INVALID_PERCENTILE_VALUE` | `function="percentile"` with a missing/out-of-range percentile |
| `MISSING_TIME_WINDOW` | A summarize with aggregations but no time_window |
| `INVALID_TIME_WINDOW` | A time_window that isn't a valid ISO 8601 duration |
| `AGGREGATE_FUNCTION_IN_EXTEND` | An aggregation function (`stdev`, `count`, ...) called inside `extend` — only valid inside `summarize` in real KQL (§4N) |
| `UNKNOWN_FUNCTION_IN_EXPRESSION` | An `extend` expression calling a function outside the ~120-entry real-KQL-function whitelist |
| `JOIN_KEY_NOT_FOUND_LEFT`/`_RIGHT` | A join_on key missing from either side's schema |
| `EMPTY_UNION` | A union with no tables |

**Advisory only (§4P):** a literal-value provenance warning flags a
string `Filter.value` absent from the original NL text and not a common
status word or DNS RCODE — added to `ValidationResult.warnings`, never
blocking. Deliberately advisory: an empirical trial run found only 1 of
11 flagged values was a genuine invented literal; the rest were
legitimate recalled domain knowledge a hard error would have wrongly
rejected.

`ExtendStage.computed_fields[].expression` is the one field this
validator can't fully check the structured way — it's a raw KQL
expression string. A best-effort identifier extractor strips string
literals, treats any identifier followed by `(` as a function call, and
checks every remaining identifier against `available_schema`. Not a full
parser, but real where the original shipped migration had nothing at all
— the single largest field-hallucination gap the AST design introduced,
closed in §4K.

`AndGroup` (§4O) lets a `FilterGroup` express "(A and B) or (C and D)" —
a disjunction of conjunctions a flat OR of plain atoms cannot represent.

`closest_match()` is a small fuzzy-match helper (Levenshtein distance
against the schema field list) whose purpose is solely to make repair
prompts more actionable. The validator never auto-corrects; it only
suggests, and the IR Builder Agent decides.

### 12.2 KQL Syntax Validator

Parses the generated KQL string against a KQL grammar/linter. Interface is independent of the underlying parser choice:

```python
def validate_kql_syntax(kql: str) -> ValidationResult:
    try:
        parse_result = kql_parser.parse(kql)
        return ValidationResult(passed=True)
    except KqlParseError as e:
        return ValidationResult(
            passed=False,
            error_type="SYNTAX_ERROR",
            message=f"KQL syntax error at position {e.position}: {e.message}",
            offending_token=e.token
        )
```

**Critical distinction:** if `kql` was produced by the deterministic KQL Generator (System B), a syntax failure here indicates a **template bug**, not a model hallucination — and should be logged separately from System A's syntax failures, since conflating them would understate how clean System B's syntax failure mode actually is. Template bugs should be fixed in the template, not re-prompted through the repair loop.

### 12.3 The Repair Loop

**Status note:** an earlier version of this pseudocode used
`for attempt in range(max_attempts):`, which has an off-by-one bug found
live in §4I: with `max_attempts=3`, the loop makes 4 total builds (1
initial + 3 repairs) but only validates the first 3 — the *final* rebuild
is returned as `MAX_REPAIR_ATTEMPTS_EXCEEDED` without ever being checked.
The corrected version below (`range(max_attempts + 1)`) validates every
build while keeping the total model-call count unchanged.

```python
def run_with_repair(
    extraction: ExtractionOutput,
    asim_schema: dict,
    max_attempts: int = 3
) -> PipelineResult:

    ir, build_error = build_ir(ir_builder_agent, extraction, asim_schema)

    for attempt in range(max_attempts + 1):
        ir_validation = build_error or validate_ir(ir, asim_schema)
        if ir_validation.passed:
            kql = generate_kql(ir)
            syntax_validation = validate_kql_syntax(kql)
            if not syntax_validation.passed:
                # syntax failure on deterministic KQL = template bug, not IR problem
                log_template_bug(ir, kql, syntax_validation)
                return PipelineResult(success=False, reason="TEMPLATE_BUG")
            return PipelineResult(
                success=True, ir=ir, kql=kql,
                attempts_used=attempt + 1
            )

        if attempt == max_attempts:
            break  # every build made so far WAS checked

        ir, build_error = build_ir(
            ir_builder_agent, extraction, asim_schema,
            repair_error=ir_validation, previous_ir=ir
        )

    return PipelineResult(
        success=False, reason="MAX_REPAIR_ATTEMPTS_EXCEEDED",
        ir=ir
    )
```

**Three key design decisions:**

1. The loop re-prompts only on IR validation failure, not KQL syntax failure. Since KQL generation is deterministic template substitution, a syntax failure at that stage means the template is wrong — re-prompting the IR Builder would not fix a template bug.
2. `attempts_used` is recorded on every success, not just failures. This is what makes Repair Recovery Rate and "average iterations needed" (H3) measurable at all.
3. `range(max_attempts + 1)`, not `range(max_attempts)` — every build gets validated, including the last one, without increasing the total number of model calls.

---

## 13. KQL Generation — Recursive Pipeline Compiler

**Status note:** this section originally described a Jinja2 template per
`ASIMEventType` — that was the flat `SecurityIR` model's compiler
(`src/generator/compiler.py` before the AST migration). The actual
current compiler (same file path, rewritten) is a pure-Python recursive
function over the AST, with no per-event-type templates at all — it
doesn't need one, since the pipeline's *stages* drive the output, not the
source table.

The only non-LLM transformation step that produces the final artifact. It recursively compiles each stage in the AST (`where`/`summarize`/`extend`/`join`/`union`/`project`/`top`) and concatenates them with the pipe `|` operator — genuinely recursive for `JoinStage`, which compiles its own `right_pipeline` the same way.

### 13.1 Pipeline Compilation

**Status note:** this section's pseudocode previously omitted
`extend`/`union`/`project`/`top` entirely (marked "... other stages") and
didn't map `source_table` through `ASIM_TABLE_NAMES`. Filled in below to
match the actual shipped compiler (`src/generator/compiler.py`).

```python
def compile_pipeline(pipeline: KqlPipeline) -> str:
    source_name = getattr(pipeline.source_table, "value", str(pipeline.source_table))
    source_table = ASIM_TABLE_NAMES.get(pipeline.source_table, source_name)
    kql = [source_table]
    for stage in pipeline.stages:
        if stage.type == "where":
            for f in stage.filters:
                if f.type == "group":
                    conditions = " or ".join(f"{c.field} {c.operator} {kql_literal(c.value)}" for c in f.conditions)
                    kql.append(f"| where ({conditions})")
                else:
                    kql.append(f"| where {f.field} {f.operator} {kql_literal(f.value)}")
        elif stage.type == "summarize":
            aggs = [f"{a.result_alias} = {kql_agg_call(a)}" for a in stage.aggregations]
            clause = f"| summarize {', '.join(aggs)}"
            by_parts = (stage.group_by or []) + ([f"bin(TimeGenerated, {kql_duration(stage.time_window)})"] if stage.time_window else [])
            if by_parts:
                clause += f" by {', '.join(by_parts)}"
            kql.append(clause)
        elif stage.type == "extend":
            comps = [f"{c.alias} = {c.expression}" for c in stage.computed_fields]
            kql.append(f"| extend {', '.join(comps)}")
        elif stage.type == "join":
            right_kql = compile_pipeline(stage.right_pipeline).replace("\n", "\n    ")
            kql.append(f"| join kind={stage.kind.value} (\n    {right_kql}\n) on {', '.join(stage.join_on)}")
        elif stage.type == "union":
            kql.append(f"| union {', '.join(stage.tables)}")
        elif stage.type == "project":
            kql.append(f"| project {', '.join(stage.fields)}")
        elif stage.type == "top":
            kql.append(f"| top {stage.limit} by {stage.by_field} {'desc' if stage.desc else 'asc'}")
    return "\n".join(kql)
```

Note this is plain, recursive Python — not a Jinja2 template, and there is
no per-`ASIMEventType` template the way the flat `SecurityIR` model used.
The pipeline's own stages drive the output structure entirely; the source
table is just the first line.

### 13.2 Helper Functions

**Status note:** these are plain Python functions
(`src/generator/filters.py`), not Jinja2 filters — the AST compiler
doesn't use Jinja2 at all. `kql_literal`'s list handling previously
quoted every item as a string unconditionally, which crashed on a numeric
`in` filter (e.g. `DstPortNumber in (139, 445)`) once `Filter.value` was
widened to accept numeric lists — fixed below, and `kql_agg_fn` is
replaced by `kql_agg_call`, which knows about the two functions
(`percentile`, `make_set`/`make_list`) that take a second argument.

```python
def _scalar_literal(value) -> str:
    if isinstance(value, str):
        return f'"{_escape_kql_string(value)}"'
    return str(value)  # numbers/bools render unquoted

def kql_literal(value) -> str:
    """Format a Python value as a KQL literal — each list item rendered
    per its own type, not unconditionally quoted as a string."""
    if isinstance(value, list):
        return f"({', '.join(_scalar_literal(v) for v in value)})"
    return _scalar_literal(value)

def kql_duration(iso8601: str) -> str:
    """Convert ISO 8601 duration to KQL duration literal (PT5M -> 5m)."""
    ...

KQL_AGG_FUNCTIONS = {
    "count": "count", "distinct_count": "dcount", "sum": "sum",
    "avg": "avg", "min": "min", "max": "max",
    "percentile": "percentile", "make_set": "make_set", "make_list": "make_list",
}

def kql_agg_call(aggregation) -> str:
    """Render a full aggregation call, including arguments — percentile()
    needs (field, N); make_set()/make_list() take an optional (field, limit);
    every other function takes zero or one argument."""
    fn_name = KQL_AGG_FUNCTIONS[aggregation.function]
    if aggregation.function == "percentile":
        return f"{fn_name}({aggregation.field}, {aggregation.percentile})"
    if aggregation.function in ("make_set", "make_list") and aggregation.limit is not None:
        return f"{fn_name}({aggregation.field}, {aggregation.limit})"
    return f"{fn_name}({aggregation.field or ''})"
```

These are small, independently unit-testable functions. Every bug here affects every generated query, so they should be thoroughly tested before the full dataset is processed.

### 13.3 ASIM Table Name Mapping

```python
ASIM_TABLE_NAMES = {
    "AuthenticationEvent":  "imAuthentication",
    "NetworkSessionEvent":  "imNetworkSession",
    "ProcessEvent":         "imProcessCreate",
    "FileEvent":            "imFileEvent",
    "DnsEvent":             "imDns",
    "WebSessionEvent":      "imWebSession",
    "RegistryEvent":        "imRegistry",
}
```

### 13.4 Unit Test Approach

Each template should have at minimum:

- A test for a Simple IR (filters only, no aggregation)
- A test for a Moderate IR (aggregation + threshold + time window)
- A test with `output_fields` specified
- A test that confirms the `dcount`/`count` distinction renders correctly
- A test that confirms `kql_duration("PT5M")` → `"5m"` and `kql_duration("P1D")` → `"1d"`

These tests run deterministically without any LLM calls and should be the first things built before any agent work begins.

---

## 14. Worked End-to-End Example

**Input:** *"Flag when a single account fails to log in more than 15 times within ten minutes."*

### Step 1 — Extraction Agent Output

```json
{
  "likely_event_type": "AuthenticationEvent",
  "actors": ["single account"],
  "action_description": "fails to log in repeatedly",
  "threshold_language": "more than 15 times",
  "time_language": "within ten minutes",
  "candidate_fields": ["TargetUsername", "EventResult"]
}
```

### Step 2 — IR Builder Agent, Attempt 1 (contains an error)

```json
{
  "source_table": "AuthenticationEvent",
  "stages": [
    {
      "type": "where",
      "filters": [{"field": "EventResult", "operator": "==", "value": "Failure"}]
    },
    {
      "type": "summarize",
      "aggregations": [{"function": "count", "field": null, "result_alias": "FailCount"}],
      "group_by": ["TargetUsername"],
      "time_window": null
    },
    {
      "type": "where",
      "filters": [{"field": "FailCount", "operator": ">", "value": 15}]
    }
  ]
}
```

### Step 3 — Schema Validator Result

```
FAIL — MISSING_TIME_WINDOW:
summarize stage has aggregations but time_window is null —
this would scan the entire table with no time bound
```

### Step 4 — IR Builder Agent, Repair Attempt 2

```json
{
  "source_table": "AuthenticationEvent",
  "stages": [
    {
      "type": "where",
      "filters": [{"field": "EventResult", "operator": "==", "value": "Failure"}]
    },
    {
      "type": "summarize",
      "aggregations": [{"function": "count", "field": null, "result_alias": "FailCount"}],
      "group_by": ["TargetUsername"],
      "time_window": "PT10M"
    },
    {
      "type": "where",
      "filters": [{"field": "FailCount", "operator": ">", "value": 15}]
    }
  ]
}
```

### Step 5 — Schema Validator Result: PASS

### Step 6 — KQL Generator Output

```kql
imAuthentication
| where EventResult == "Failure"
| summarize FailCount = count()
    by TargetUsername, bin(TimeGenerated, 10m)
| where FailCount > 15
```

### Step 7 — KQL Syntax Validator Result: PASS

**Logged result:** `success=True, attempts_used=2`

This case contributes one data point to the Repair Recovery Rate metric: it recovered on attempt 2. The specific error (MISSING\_TIME\_WINDOW) and the specific repair action (adding `time_window: "PT10M"`) are both logged for the qualitative error analysis section of the write-up.

---

## 15. KQL and ASIM Technical Reference

This section documents the KQL operators and ASIM schema concepts this project directly uses. It is a scoped reference, not a complete language guide.

### 15.1 KQL vs. SQL vs. SPL — Why Confusion Happens

| Feature | SQL | Splunk SPL | KQL |
|---|---|---|---|
| Aggregation | `SELECT COUNT(*) ... GROUP BY x` | `\| stats count by x` | `\| summarize count() by x` |
| Row filtering | `WHERE x = 'y'` | `\| where x="y"` | `\| where x == "y"` |
| Time bucketing | `DATE_TRUNC` / vendor-specific | `bin _time span=5m` | `bin(TimeGenerated, 5m)` inside summarize |
| String equality operator | `=` | `=` | `==` (double equals) |
| Structure | Declarative, fixed clause order | Pipe-based, search-first | Pipe-based, source-table-first |

The pipe-based structure aligns KQL superficially with SPL more than SQL, but the specific keywords and operator semantics differ from both. This is precisely the gap that produces hybrid, invalid output when a model pattern-matches on "pipe-based query language" without tracking which dialect it is in. The double-equals (`==`) requirement is a particularly common failure: SQL and SPL both use `=`, and a model that produces `where EventResult = "Failure"` is syntactically wrong in KQL.

### 15.2 Operators Used by This Project's Templates

**Status note:** this whole section predates the AST migration (§10.2/§4K)
and described the flat `SecurityIR` model's mapping. The specific claim
that "the current IR cannot express OR-combined filters or nested boolean
groups" is now actively wrong, not just outdated — `FilterGroup` exists
precisely to express OR, with two dedicated validator checks
(`TAUTOLOGICAL_FILTER_GROUP`, both variants) catching the most common way
models misuse it. The mappings below are corrected to the current
`KqlPipeline` model; see [§12.1](#121-schema-validator) and
[§13](#13-kql-generation--recursive-pipeline-compiler) for the full,
current validator/compiler.

#### `where` — Row Filtering

```kql
| where EventResult == "Failure"
| where TargetUsername contains "admin"
| where SrcIpAddr in ("1.2.3.4", "5.6.7.8")
| where (ActingProcessName in ("a.exe", "b.exe") or CommandLine contains "x")
```

Maps from a `WhereStage`'s `filters` list — a mix of plain `Filter` entries (AND-ed together as sequential conditions on one `where` line) and `FilterGroup` entries (OR-ed conditions, compiled to one parenthesized `where` line per group). A required-together set of conditions (e.g. four command-line flags that must ALL be present) stays as separate plain `Filter` entries; only a genuine OR needs a `FilterGroup`.

#### `summarize ... by` — Aggregation

```kql
| summarize FailCount = count()
    by TargetUsername, bin(TimeGenerated, 10m)

| summarize DistinctUsers = dcount(TargetUsername), Spread = stdev(DistinctUsers)
    by SrcIpAddr, bin(TimeGenerated, 5m)
```

Maps from a `SummarizeStage`'s `aggregations` (a list, not a single field — multiple aggregation columns in one clause are native) + `group_by` + `time_window`. `KQL_AGG_FUNCTIONS` (`src/ir_engine/ir_schema.py`) maps each `AggregationFunction` enum value to its real KQL name — most map 1:1 (`count`, `sum`, `avg`, `min`, `max`, `percentile`, `make_set`, `make_list`, `stdev`, `variance`); `DISTINCT_COUNT` is the one exception, mapping to `dcount`. `kql_agg_call()` (`src/generator/filters.py`, not a Jinja2 filter) renders the full call including arguments — `percentile()` and the two collection functions take a second argument the others don't.

#### `bin()` — Time Bucketing

```kql
bin(TimeGenerated, 5m)
```

`bin()` is an argument *inside* `summarize ... by`, not a separate clause. This is a common source of confusion: there is no equivalent of SQL's `GROUP BY time_bucket(...)` as a standalone clause. The IR's `time_window` field (ISO 8601 string) gets compiled to `bin(TimeGenerated, <kql_duration>)` by `compile_pipeline()`, via the `kql_duration()` helper — making it structurally impossible for the compiler to produce a time-windowed aggregation without the `bin()` call.

#### `project` — Column Selection

```kql
| project SrcIpAddr, DistinctUsers, TimeGenerated
```

Maps from a `ProjectStage`'s `fields` list. Unlike the old flat model, this is always an explicit stage the IR Builder chooses to add — there's no IR-level default field set to fall back to when it's omitted; the validator narrows `available_schema` down to exactly the listed fields wherever a `ProjectStage` appears in the pipeline.

### 15.3 ASIM Field Naming Conventions

These naming patterns are a common source of the "plausible-but-wrong" field hallucination described in the failure taxonomy. Knowing them helps both in dataset verification and in evaluating whether the schema validator is catching the right errors:

| Convention | Examples |
|---|---|
| `Src`/`Dst` prefixes, not `Source`/`Destination` | `SrcIpAddr`, `DstIpAddr`, `SrcUserId`, `DstHostname` |
| `TargetUsername` for acted-upon account | Not `Username`, `User`, or `AccountName` |
| `EventResult` for success/failure | `"Success"` or `"Failure"` — not a numeric code like `0` or `200` |
| `TimeGenerated` for timestamp | Used inside `bin()` for time bucketing |
| PascalCase throughout | `SrcIpAddr` not `src_ip_addr` not `srcIpAddr` |

### 15.4 ASIM Schemas in Scope

| ASIM Schema | Normalized View Name | Typical Use Case |
|---|---|---|
| `AuthenticationEvent` | `imAuthentication` | Login attempts, MFA events, success/failure |
| `NetworkSessionEvent` | `imNetworkSession` | Firewall/network flow logs, connection attempts |
| `ProcessEvent` | `imProcessCreate` | Process execution, command-line activity |
| `FileEvent` | `imFileEvent` | File creation, modification, deletion |
| `DnsEvent` | `imDns` | DNS query/response activity |
| `WebSessionEvent` | `imWebSession` | HTTP/web proxy traffic |
| `RegistryEvent` | `imRegistry` | Windows registry modifications |

This list mirrors the `Detections/ASim*` folders prioritized during dataset construction — the IR's schema coverage and the dataset's source coverage are kept in lockstep so every `ASIMEventType` the IR can express has corresponding ground-truth examples in the dataset.

### 15.5 The Azure-Sentinel Repository as a Resource

The `Azure/Azure-Sentinel` GitHub repository (MIT license) contains more than just sample logs. For this project, the relevant folders are:

| Folder | Contents | This Project's Use |
|---|---|---|
| `Detections/ASim*/` | Production YAML analytics rules with `description` + `query` fields | **Primary ground-truth source** for (NL, KQL) pairs |
| `Hunting Queries/` | Less rigidly templated KQL hunting queries | Secondary source for complexity diversity |
| `Sample Data/` | Scrubbed per-connector log rows | Sanity-checking referenced fields; future execution-validation fixtures |
| `ASIM/ASimSchemas/` | ASIM schema field documentation | Direct source for the schema reference used by validators |
| `ASIM/ASimParsers/` | KQL parser functions mapping raw→ASIM fields | Reference for raw-to-ASIM field mapping understanding |

A sample YAML rule from `Detections/` illustrates why this source is structurally ideal:

```yaml
id: 12ab34cd-5678-90ef-ghij-klmnopqrstuv
name: Multiple authentication failures followed by success
description: |
  Identifies a pattern where a single account experiences multiple
  authentication failures within a short window, followed by a
  successful authentication from the same source.
severity: Medium
tactics: [CredentialAccess]
relevantTechniques: [T1110]
query: |
  let threshold = 5;
  imAuthentication
  | where EventResult == "Failure"
  | summarize FailCount = count()
      by TargetUsername, bin(TimeGenerated, 1h)
  | where FailCount > threshold
```

The `description` field is the NL source. The `query` field is the KQL ground truth. Both exist in the same file, peer-reviewed by Microsoft, at scale. This is the core structural reason this repository is the right dataset source.

---

## 16. Dataset Construction

This is the most important section in the entire document. A weak or small dataset undermines every downstream metric regardless of how well the architecture is built. More calendar time should be spent here than anywhere else in the project. Rushing this section is the single most common reason a small research project's results don't survive scrutiny.

### 16.1 Why the Azure-Sentinel Repository

The core structural reason: the `Detections/` folder already pairs a `description` (NL ground truth) with a `query` (KQL ground truth) in every YAML rule file. The alternatives — writing (NL, KQL) pairs from scratch, or sourcing only raw logs — have specific failure modes this source avoids:

- **Writing pairs from scratch** risks introducing the same kinds of errors being measured in LLM output, just at lower frequency. The Azure-Sentinel rules have gone through Microsoft's own PR review and validation pipeline.
- **Hand-imagined scenarios** cluster around easy-to-imagine cases and miss the real distribution, which includes many mechanically awkward detections (multi-stage correlation, unusual aggregations, edge-case time windows) — exactly where hallucination is most interesting.
- **Raw logs only** don't give a natural-language description to pair the KQL with.

### 16.2 Dataset Construction, Step by Step

#### Step 1 — Bulk Pull

```bash
git clone --depth 1 https://github.com/Azure/Azure-Sentinel.git /tmp/azure-sentinel

# Record the exact commit hash for reproducibility
git -C /tmp/azure-sentinel rev-parse HEAD > data/raw/SOURCE_ATTRIBUTION.md

python src/data/pull_detections.py \
  --source /tmp/azure-sentinel/Detections \
  --filter-asim-only \
  --output data/raw/detections_raw.jsonl
```

The `--filter-asim-only` flag restricts the first pass to rules that already target ASIM-normalized tables (the `ASim*` subfolders, plus any rule elsewhere whose `query` references an `im*` or `ASim*` table name). Rules against raw tables (e.g., `SecurityEvent`, `Syslog`) are saved to a separate file — not discarded — but are out of scope for the primary dataset because validating them would require a second schema reference.

#### Step 2 — Field Extraction and Basic Filtering

```python
def extract_pair(yaml_path: str) -> dict | None:
    with open(yaml_path) as f:
        rule = yaml.safe_load(f)

    description = rule.get("description", "").strip()
    query       = rule.get("query",       "").strip()

    # Basic coarse exclusion filters:
    if len(description) < 20:
        return None   # too terse to be useful as NL ground truth
    if "{{" in query or "{{" in description:
        return None   # templated/parameterized rule, skip
    if not any(t in query for t in ("Asim", "im")):
        return None   # not ASIM-normalized

    return {
        "source_file":  yaml_path,
        "rule_id":      rule.get("id"),
        "description_raw": description,
        "query":        query,
        "tactics":      rule.get("tactics",            []),  # preserved, not used
        "techniques":   rule.get("relevantTechniques", []),  # preserved, not used
    }
```

This step is intentionally conservative — a coarse filter, not the final quality gate. Its job is to cheaply discard obviously unusable rules before the more expensive manual review step.

#### Step 3 — Paraphrasing

Each retained raw description is paraphrased into 2–3 natural-language variants, each in a distinct register that mirrors realistic analyst input:

| Style | Characteristics | Example |
|---|---|---|
| **Casual / shorthand** | Short, may drop articles, like a Slack message or ticket note | *"acct getting bruteforced — 15+ fails in under 10 min, flag it"* |
| **SOP-imperative** | Procedural, instructive, as if written into a runbook | *"If a single account records more than 15 failed login attempts within a 10-minute window, raise an alert."* |
| **Threat-report-style** | Descriptive, third-person, narrative framing | *"The attacker repeatedly attempted authentication against a single account, generating over fifteen failures inside a ten-minute span."* |

**Process:** Light LLM assistance is acceptable for generating candidate paraphrases. Manual review of every paraphrase is **not optional**, specifically to catch paraphrasing drift — the single highest-risk step for silently corrupting ground truth. An LLM asked to "make this more casual" will sometimes round "15" to "a bunch" or drop the time window entirely. Both corrupt the ground truth and must be caught before the pair enters the dataset.

What NOT to do:
- Do not fully automate paraphrasing without review.
- Do not paraphrase so aggressively that the threshold/time-window information is lost.
- Do not change the semantic content — only the style.

#### Step 4 — Manual Verification

Every retained (NL, KQL) pair — across all paraphrase variants — passes through this checklist before inclusion:

- [ ] **KQL still parses.** Run the KQL Syntax Validator against `query` directly. If the ground-truth KQL itself doesn't parse (e.g., a multi-statement `let`-prefixed query needing special handling), fix the extraction or discard the pair. Do not "fix" the ground-truth KQL by hand, as that risks introducing the exact class of subtle errors the project is built to measure.
- [ ] **Description genuinely matches query logic.** Read the NL description and the KQL side by side and check: correct event type; correct threshold value; correct time window; correct aggregation direction (e.g., "many distinct X" vs. "total count of X").
- [ ] **No orphaned complexity.** If the query contains a `join` or multi-stage correlation that the description doesn't mention, either update the description or tag the pair as complex and flag it for closer review.
- [ ] **Field names exist in the current ASIM schema.** Cross-check `query`'s referenced fields against the extracted schema reference. The Azure-Sentinel repo evolves, and a small number of rules may reference deprecated or renamed ASIM fields. Discard these.

Pairs that fail any checkbox are either fixed (only if the fix is unambiguous) or discarded. Discard, don't force-fix, ambiguous cases.

**Expected discard rate:** approximately 15–25% of the initial pull. Budget for this rather than treating the manual review as a formality that will pass everything.

#### Step 5 — Complexity Tagging

```python
def tag_complexity(query: str) -> str:
    filter_count   = query.count("| where")
    has_join       = "| join" in query
    has_aggregation= "| summarize" in query
    # rough heuristic — spot-check manually on 20% sample
    has_multi_groupby = query.count(",") > 2 and has_aggregation

    if has_join or has_multi_groupby or filter_count >= 3:
        return "complex"
    elif has_aggregation:
        return "moderate"
    else:
        return "simple"
```

Automated tagging is spot-checked manually on a 20% sample per tier, because a query can technically have only one filter but still be conceptually complex (e.g., a single filter against a computed/derived field).

**Target distribution:**

| Tier | Definition | Target Share |
|---|---|---|
| Simple | Single event type, 1–2 filters, no aggregation | ~35% |
| Moderate | Single event type, aggregation + threshold, single time window | ~35% |
| Complex | Multiple filters (3+) OR a join OR multiple aggregation keys | ~30% |

This stratification directly supports RQ4 (does the IR's advantage grow with complexity) and gives the evaluation something more interesting to report than a single aggregate number.

#### Step 6 — Train/Test Split

- **20% held out as the test split**, stratified by complexity tier so the test split has roughly the same 35/35/30 distribution as the full dataset.
- The split is generated **once**, written to `data/splits/test_ids.json`, and committed to version control immediately.
- **No development, prompt engineering, threshold tuning, or MVP testing touches the test split** until final evaluation.

This is the single most commonly skipped discipline in small individual research projects under time pressure, and skipping it is also the most common reason a result doesn't survive scrutiny.

### 16.3 ASIM Schema Reference Extraction

The ASIM field reference used by the Schema Validator and the IR Builder Agent is extracted directly from `ASIM/ASimSchemas/` in the same repository clone, at the same commit, as the data pull. This guarantees the schema used for validation is consistent with the schema the ground-truth queries were written against.

```python
def extract_schema(asim_schemas_dir: str) -> dict:
    schema = {}
    for schema_file in glob(f"{asim_schemas_dir}/*.md"):
        event_type, fields = parse_asim_schema_doc(schema_file)
        schema[event_type] = {
            "fields":      fields,        # list of field names
            "field_types": {...},         # name → type, where documented
            "source_file": schema_file,
        }
    return schema
```

The commit hash is recorded in `data/raw/SOURCE_ATTRIBUTION.md` alongside the pull date and licensing note.

### 16.4 Dataset File Formats

```
data/
├── raw/
│   ├── detections_raw.jsonl           # all ASIM-normalized rules, post-coarse-filter
│   ├── detections_raw_non_asim.jsonl  # held in reserve, out of scope
│   └── SOURCE_ATTRIBUTION.md          # commit hash, pull date, licensing note
├── processed/
│   ├── pairs.jsonl                    # final verified pairs, one record per paraphrase variant
│   └── pairs_schema.md                # field-by-field description
├── schema/
│   └── asim_field_reference.json      # extracted ASIM schema, versioned to commit hash
└── splits/
    ├── test_ids.json                  # held-out rule_ids, generated once, never changed
    └── train_ids.json
```

**`pairs.jsonl` record format:**

```json
{
  "pair_id":           "12ab34cd-variant-2",
  "rule_id":           "12ab34cd-5678-90ef-ghij-klmnopqrstuv",
  "nl_description":    "If a single account records more than 15 failed login...",
  "paraphrase_style":  "sop_imperative",
  "ground_truth_kql":  "imAuthentication\n| where EventResult == \"Failure\"...",
  "complexity_tier":   "moderate",
  "asim_event_type":   "AuthenticationEvent",
  "split":             "train",
  "verified_by":       "manual_review_2026_06",
  "source_file":       "Detections/ASimAuthentication/MultipleAuthFailures.yaml"
}
```

### 16.5 MVP Dataset — First Deliverable

Before building the full pipeline, hand-pick **10 (NL, KQL) pairs** spanning all three complexity tiers from the training set. These 10 cases are:

- Used to validate the pipeline mechanics end-to-end (see [Section 22: Timeline](#22-project-timeline))
- Manually inspected at every step (extraction, IR, generated KQL) — this is where schema/template bugs get caught cheaply, before they're buried in aggregate statistics over 100+ cases
- **Not part of any evaluation** — they are a development fixture only

Only after the MVP pipeline produces sensible IRs and KQL on all 10 cases should the full dataset be processed through both System A and System B.

---

## 17. Evaluation Methodology

### 17.1 Metric Definitions

#### Syntax Validity Rate (SVR)

$$\text{SVR} = \frac{\text{queries that parse against the KQL grammar}}{\text{total queries generated}}$$

Computed independently per system and per ablation configuration. For System B, measured on the final output after the repair loop completes. A separate metric (RRR, below) measures the repair loop's contribution.

#### Field Validity Rate (FVR)

$$\text{FVR} = \frac{\text{queries where every referenced field/table exists in the ASIM schema}}{\text{total queries generated}}$$

Computed by parsing field/table references from the generated KQL string and checking each against the extracted ASIM schema reference. This is measured on the **final KQL output**, independent of which pipeline produced it — not on the IR's internal validation status — so FVR is comparable across System A and System B.

#### Logic Correctness (Manual)

$$\text{Logic Correctness} = \frac{\text{syntax-valid AND field-valid queries judged logically correct}}{\text{syntax-valid AND field-valid queries}}$$

The denominator is conditional: this metric answers "given that a query is mechanically sound, does it mean the right thing?" rather than "what fraction of all attempts are perfect?" — the latter conflates mechanical and semantic failure in a way that makes it impossible to tell which problem dominates.

**Scoring rubric (3-point checklist):**

1. Event type / table correct
2. Comparison direction correct (e.g., not inverted: `== "Success"` when the rule means failed logins)
3. Aggregation/grouping correct (function, field, and `group_by` set match the ground truth's intent)

A query passes only if **all three** checklist items pass. A query that gets the event type and grouping right but inverts the comparison is not "67% correct" — it would produce the opposite alerting behavior in production, which is a binary-consequence error.

#### CodeBLEU

A weighted combination of n-gram match, keyword-weighted n-gram match, AST match, and data-flow match — adapted from the code generation literature with a KQL-specific keyword list (`where`, `summarize`, `extend`, `join`, `bin`, etc.) substituted for the original language-specific keywords. Reported as a continuous score in [0, 1] against `ground_truth_kql`, computed for every generated query including ones that fail SVR/FVR (how close was it, even if not valid?).

#### Repair Recovery Rate (RRR)

$$\text{RRR} = \frac{\text{cases failing on attempt 1 that pass by attempt} \leq 3}{\text{cases failing on attempt 1}}$$

Reported alongside the **mean and median number of attempts used** among recovered cases, and a breakdown of recovery by attempt number (attempt 2 vs. attempt 3) to characterize diminishing returns.

#### Pipeline Latency / Token Cost

Wall-clock seconds and total LLM input+output tokens per query, both systems. Reported as **median and 90th percentile** (not mean — latency distributions are right-skewed due to occasional slow repair chains).

### 17.2 Primary Comparison

System A vs. System B on the full held-out test split, same underlying LLM, same temperature.

On determinism: if temperature is set near 0 (recommended), a single run per case is acceptable. If a non-trivial temperature is used, System A should be run 3× per case with majority-vote scoring on SVR/FVR, since its single LLM call is more variable than System B's repair-loop-smoothed output. This asymmetry, if applied, should be stated plainly in the write-up as a fairness accommodation.

### 17.3 Logic Correctness — Inter-Rater Reliability

If a second reviewer familiar with KQL is available, independently score a 20-case sample from the test set and report Cohen's κ. This is optional given the project is primarily single-researcher, but even a small inter-rater sample meaningfully strengthens the credibility of the manual metric. Its absence should be listed as a limitation if not done.

---

## 18. Ablation Studies

Each ablation removes exactly one of System B's three design decisions so the result can be attributed to a specific mechanism:

### Ablation 1 — No-Repair IR

**Configuration:** System B with `max_attempts=1` — one attempt, no re-prompting on failure.

**Isolates:** how much of System B's advantage comes from schema-grounded IR construction itself, independent of the repair mechanism.

**Tests:** H1 and H2 in a repair-free setting.

**Expected pattern if H1/H2 hold independent of repair:** No-Repair IR should still outperform System A on SVR/FVR, by a smaller margin than full System B. If No-Repair IR performs no better than System A, it would mean the IR's apparent advantage is coming entirely from the repair loop — an important finding that changes the conclusion significantly.

### Ablation 2 — Monolithic Extraction

**Configuration:** Merge the Extraction Agent and IR Builder Agent into a single prompt that goes directly from NL input to a `KqlPipeline` JSON object, skipping the intermediate `ExtractionOutput` structure. Implemented in `src/agents/monolithic_agent.py`, sharing `_COMMON_MISTAKES` with the IR Builder Agent rather than duplicating it.

**Isolates:** whether agent decomposition itself helps, independent of schema grounding (both configurations have schema grounding; only the decomposition differs).

**Tests:** RQ2 directly.

**Expected pattern if RQ2 resolves "yes":** Monolithic Extraction should underperform full System B on Logic Correctness specifically — the hypothesis is that decomposition helps most with *understanding* the threat correctly, more than with *syntax* mechanics (already handled by the deterministic generator). Read Ablation 2's results primarily against Logic Correctness, not SVR.

### Ablation 3 — No Schema Grounding

**Configuration:** IR Builder Agent receives no ASIM field reference and must select field names from its own training knowledge, same as a vanilla LLM would.

**Isolates:** the specific contribution of explicit schema grounding, separated from the general benefit of producing structured intermediate output.

**Tests:** H2 directly, and partially H1.

**Expected pattern if H2 holds:** No Schema Grounding should show FVR much closer to System A's FVR than to full System B's FVR. If FVR stays high even without grounding, the benefit is coming from IR *structure* itself (forcing the model to commit to a typed object) rather than from schema access specifically — a meaningfully different conclusion.

### Ablation Reporting

All three ablations are reported both in aggregate and broken down by complexity tier, matching the primary comparison's stratified analysis. The ablation × tier interaction is where the most actionable findings typically live.

---

## 19. Statistical Treatment

With a test set of approximately 20–30 pairs (20% of 100–150):

- **Bootstrap confidence intervals** (10,000 resamples, 95% level) on every aggregate metric, reported as `[lower, upper]` alongside the point estimate. Point estimates without CIs overstate precision at this sample size.
- **McNemar's test** for binary outcome metrics (SVR, FVR), since System A and System B are run on the *same* underlying NL inputs (paired design). Unpaired tests (chi-squared) would be less appropriate and less powerful.
- **Wilcoxon signed-rank test** for CodeBLEU, preferred over a paired t-test because the score distribution is likely non-normal at this sample size.
- All p-values reported alongside **effect sizes** (Cohen's h for proportions, rank-biserial correlation for Wilcoxon), not as the sole basis for a claim. Statistical significance and practical significance can diverge at this sample size, and the write-up discusses both.

```python
from statsmodels.stats.contingency_tables import mcnemar
import numpy as np
from scipy.stats import wilcoxon

def mcnemar_svr_test(a_results: list[bool], b_results: list[bool]) -> dict:
    both_pass = sum(a and b     for a, b in zip(a_results, b_results))
    a_only    = sum(a and not b for a, b in zip(a_results, b_results))
    b_only    = sum(b and not a for a, b in zip(a_results, b_results))
    both_fail = sum(not a and not b for a, b in zip(a_results, b_results))

    table = [[both_pass, a_only], [b_only, both_fail]]
    result = mcnemar(table, exact=(a_only + b_only < 25))
    return {"p_value": result.pvalue, "a_only": a_only, "b_only": b_only}

def bootstrap_ci(values: list[float], n=10000, ci=0.95) -> tuple[float, float]:
    means = [np.mean(np.random.choice(values, len(values), replace=True))
             for _ in range(n)]
    lo = (1 - ci) / 2 * 100
    return np.percentile(means, lo), np.percentile(means, 100 - lo)
```

---

## 20. Technology Stack

**Status note:** as originally planned vs. as actually shipped diverged on
two rows below (LLM access, KQL templating) — both corrected here to match
the real code, with the original plan kept visible for context since the
divergence itself is informative (a hand-rolled recursive compiler turned
out to need less machinery than a templating engine once the IR became an
AST of typed stages rather than one flat object).

| Layer | Choice | Rationale |
|---|---|---|
| LLM access | OpenAI's `gpt-4.1-mini` via Azure AI Foundry (`langchain_openai.ChatOpenAI` pointed at the Foundry endpoint) — see `src/agents/base_agent.py`'s `build_chat_model()`, which also supports `anthropic`/`openai`/`ollama` behind the same `LLM_PROVIDER` switch, used for local MVP runs | One provider fixed for the whole study, selected via env var rather than hardcoded — avoids a cross-provider confound while keeping local (Ollama) runs possible for fast iteration |
| Agent orchestration | Plain Python function calls (`run_system_b()` → `run_with_repair()`), not LangGraph | The repair loop is a single bounded retry cycle, not a multi-node graph — a `for` loop with explicit attempt counting turned out to be more inspectable and easier to unit-test than a graph abstraction for this shape |
| IR schema definition | Pydantic v2 | Type validation and JSON schema export come for free; `extra = "forbid"` enforces schema discipline |
| KQL generation | A plain recursive Python compiler (`compile_pipeline()` in `src/generator/compiler.py`), not Jinja2 | The AST migration (§10.2/§4K) replaced the old one-template-per-`ASIMEventType` design with a sequence of typed stages each stage type can recurse into (notably `JoinStage.right_pipeline`, itself a full `KqlPipeline`) — a per-event-type template can't express that recursion, but a function that walks `pipeline.stages` and recurses on `join` naturally does. Still deterministic, inspectable, and unit-testable without LLM calls, same as the original rationale intended |
| KQL syntax validation | A scoped hand-rolled grammar check (`src/validation/syntax_validators.py`) | No mature open-source KQL parser was found suitable (the originally-flagged risk in §23 materialized as expected) — the shipped checker covers the operator/clause subset this project's generator and System A's baseline actually produce, explicitly not full-grammar coverage |
| ASIM schema reference | Parsed from `ASIM/ASimSchemas/` at same commit as data pull | Authoritative, versioned, guaranteed consistent with the dataset |
| Evaluation scripting | Python: `pandas` for result aggregation, `scipy`/`statsmodels` for significance testing | Standard, reproducible, easy to share with a supervisor for independent inspection |
| Dataset processing | Python + PyYAML | Straightforward for the YAML rule files |

---

## 21. Repository Structure

**Status note:** this tree was never updated to match the as-built repo,
even before the AST migration — it described the original plan's intended
layout. Replaced below with the real, current structure.

```
.
├── README.md
├── app.py                          # Streamlit demo UI (System A vs. System B)
├── docs/
│   └── NL-KQL/
│       ├── MASTER_PLAN_v2_ast.md   # this file
│       ├── architecture_v2_ast.md # pipeline deep-dive, current AST design
│       ├── PROJECT_STATUS.md      # living history — every round, bug, fix, live result
│       ├── RESULTS_DRAFT.md       # current numbers, both architectures
│       ├── dataset.md             # dataset methodology deep-dive
│       ├── evaluation.md          # evaluation methodology deep-dive
│       └── kql-asim-primer.md     # scoped KQL/ASIM reference
├── data/
│   ├── raw/
│   │   ├── detections_raw.jsonl
│   │   ├── detections_raw_non_asim.jsonl
│   │   └── SOURCE_ATTRIBUTION.md
│   ├── processed/
│   │   ├── pairs.jsonl            # all (NL, KQL) pairs incl. paraphrases
│   │   ├── pairs_verified.json    # the 81 manually-verified pairs
│   │   ├── paraphrases_test.json  # casual/sop_imperative paraphrases, test split
│   │   └── manual_verdicts.json   # keep/discard verification decisions
│   ├── schema/
│   │   └── asim_field_reference.json
│   └── splits/
│       ├── test_ids.json
│       └── train_ids.json
├── src/
│   ├── ir_engine/
│   │   ├── ir_schema.py           # Pydantic KqlPipeline AST + supporting models
│   │   └── ir_validator.py        # stateful Schema Validator (validate_ir)
│   ├── agents/
│   │   ├── extraction_agent.py    # Extraction Agent prompt + call
│   │   ├── ir_builder_agent.py    # IR Builder Agent prompt + call (incl. repair); owns _COMMON_MISTAKES
│   │   ├── monolithic_agent.py    # Ablation 2 — merges extraction + IR building into one call
│   │   └── base_agent.py          # build_chat_model() provider switch + shared _invoke() retry logic
│   ├── generator/
│   │   ├── compiler.py            # compile_pipeline() — plain recursive Python, no templating
│   │   └── filters.py             # kql_literal, kql_duration, kql_agg_call
│   ├── validation/
│   │   └── syntax_validators.py   # validate_kql_syntax() — scoped hand-rolled grammar check
│   ├── baseline/
│   │   ├── prompt.py              # System A prompt construction
│   │   ├── few_shot_examples.py
│   │   └── run.py                 # System A inference loop (BaselineRunner)
│   └── pipeline/
│       ├── system_b.py            # run_system_b() — Extraction Agent -> IR Builder (+ repair) -> KQL
│       └── repair_loop.py         # run_with_repair(), _check_constraint_traceability()
├── eval/
│   ├── metrics.py                 # SVR, FVR, RRR, etc.
│   ├── run_comparison.py          # primary A/B comparison
│   ├── run_ablations.py           # all 3 ablations
│   ├── stats.py                   # bootstrap CI, McNemar
│   └── results/
│       ├── primary/
│       └── ablations/
├── scripts/
│   ├── run_mvp.py
│   └── compute_results_v2.py
└── tests/
    ├── unit/
    │   ├── test_ir_schema.py       # Pydantic schema validation tests
    │   ├── test_schema_validator.py # field-not-found, tautology, hallucinated-function, etc.
    │   ├── test_constraint_traceability.py
    │   ├── test_repair_loop.py     # mocked IR Builder, repair-loop logic in isolation
    │   └── test_templates.py       # compiler output per stage type
    └── integration/
        ├── test_pipeline_validation_compilation.py # real validator + compiler together
        ├── test_repair_loop_pipeline.py             # real validator/compiler, stubbed IR Builder
        └── test_live_e2e.py                         # real LLM calls, skipped without credentials
```

---

## 22. Project Timeline

| Phase | Duration | Milestone / Output |
|---|---|---|
| **Phase 1 — Dataset** | 3–4 weeks | 100–150 verified (NL, KQL) pairs, complexity-tagged; ASIM schema extracted; train/test split committed |
| **Phase 2 — MVP pipeline** | 2–3 weeks | System B pipeline running end-to-end on 10 hand-picked cases; all template unit tests passing; KQL validator approach decided |
| **Phase 3 — Baseline** | 1 week | System A implemented and producing output on the MVP cases; prompt finalized |
| **Phase 4 — Full evaluation** | 2 weeks | Primary comparison + all 3 ablations run on the full test set; raw results saved |
| **Phase 5 — Analysis** | 2 weeks | Stratified results by complexity tier; bootstrap CIs + McNemar/Wilcoxon computed; Logic Correctness manual scoring complete |
| **Phase 6 — Write-up** | 3–4 weeks | Paper / report draft, following standard structure: Abstract, Introduction, Background, Related Work, Method, Dataset, Experiments, Results, Discussion, Conclusion |
| **Total** | **13–17 weeks** | Part-time alongside full-time employment |

**Where timelines actually slip:** Phase 1 (dataset) and Phase 2 (MVP). Do not cut these phases short by rushing manual verification or skipping MVP inspection. Every hour saved in Phase 1 costs two hours in Phase 5 when data quality problems surface in the results.

---

## 23. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **No mature open-source KQL parser/linter** readily available, forcing a hand-rolled or partial syntax checker | Medium | High — SVR is the cleanest metric in the study | Spend a focused day evaluating `pyKQL`, `kqlmagic`'s parser, and any other options before committing. If nothing suitable exists, scope the syntax checker to the operator subset actually used by the dataset and document this scoping explicitly as a stated limitation — do not overclaim full-grammar coverage |
| **Dataset descriptions in the Azure-Sentinel repo** are sometimes terse or loosely correlated with query logic | Medium | Medium — affects ground-truth quality | The manual verification rubric in Step 4 exists specifically to screen for this. Budget real time; expect to discard 15–25% of the initial pull |
| **Paraphrasing drift corrupts ground truth** | Medium | Medium | Mandatory manual read of every paraphrase against the original KQL (Step 3). Not optional even when LLM-assisted |
| **LLM API cost/rate limits** during full evaluation (System B makes up to 8 calls per case across extraction, IR building, and repair) | Low–Medium | Low | Cache all prompts and responses during evaluation; use a smaller/cheaper model for the Extraction Agent specifically if cost becomes a constraint; batch where the API allows |
| **Manual logic-correctness scoring is slow and subjective** at 100+ cases | Medium | Medium | Write and freeze the scoring rubric before starting (event type correct / comparison direction correct / aggregation field correct). Score in one sitting if possible to maintain consistency. Report the rubric explicitly in the write-up |
| **Train/test contamination** — prompt-tuning or MVP testing accidentally touches the test set | Low | High — invalidates all results | `test_ids.json` is committed immediately after generation. The test split file is never opened during development. Any tuning uses only the training split. This discipline is enforced at the tooling level where possible (the evaluation scripts should load `test_ids.json` independently of anything used during development) |

---

## 24. Claimed Contributions

Stated narrowly and defensibly — matching what the scoped study can actually support:

1. **An empirical comparison of direct LLM KQL generation vs. IR-mediated, ASIM-schema-grounded generation**, measured on syntax validity, field validity, and structural similarity to ground truth, with statistical significance testing on paired outcomes.

2. **A reusable, ASIM-grounded Security IR schema** for Sentinel detection logic, directly validated against real Sentinel analytics rules rather than designed speculatively. The schema is vendor-neutral by construction.

3. **A complexity-stratified analysis** showing where (if H4 holds) the benefit of schema grounding and IR-mediation concentrates — simple rules vs. rules requiring aggregation, grouping, and temporal logic.

4. **A small, reusable benchmark dataset** of (NL description, KQL) pairs derived and adapted from Microsoft's public Azure-Sentinel repository, complexity-tagged and schema-tagged, released alongside the paper for reproducibility.

5. **An ablation-based attribution** of which specific design decision (schema grounding, agent decomposition, or the repair loop) contributes most to the overall result — rather than a single entangled before/after comparison.

---

## 25. Limitations

Stated up front, not discovered in review:

- **Single platform (KQL/Sentinel) and single schema standard (ASIM).** Generalization to other SIEM platforms or schema standards is future work, not demonstrated here.
- **Syntax validation, not full telemetry execution validation.** The study measures whether a query parses and references real fields — not whether it produces correct results against live or synthetic data. This is a deliberate scope boundary, not an oversight.
- **Dataset size (100–150 pairs)** is appropriate for a scoped individual project but is small relative to large-scale code-generation benchmarks. Results are reported with confidence intervals rather than as bare point estimates.
- **Manual logic-correctness scoring** introduces some subjectivity even with a rubric. Inter-rater reliability (Cohen's κ) should be attempted if a second KQL-familiar reviewer is available.
- **Dataset is cleaner than real-world analyst language.** The source (Microsoft-authored analytics rules) is more structured and precise than genuine field-collected analyst SOPs or threat-report excerpts. Paraphrasing partially addresses this but does not fully replicate the messiness of real-world input.
- **Or-logic and multi-condition filters** are not expressible in the current IR (the filter list is a flat AND chain). Detection rules requiring complex boolean filter logic will systematically underperform in System B and should be identified and disclosed in the results.

---

## 26. Future Extensions

Not part of this project's scope — documented here so they can be added without redesigning the architecture:

| Extension | What It Adds | Key Design Condition |
|---|---|---|
| Multi-platform generation (Sigma, SPL) | New Jinja2 templates consuming the same vendor-neutral IR | IR must remain free of KQL-specific fields — the `ASIMEventType` enum and ASIM field names are the only platform-specific elements, and they live in the schema reference, not the IR |
| OCSF as a second normalization layer | Cross-platform field mapping (OCSF → ASIM) | Only necessary once a second platform is in scope |
| Telemetry execution validation | Running generated KQL against synthetic data (`Sample Data/` is the natural source) for real precision/recall | Requires a query execution sandbox or a Log Analytics workspace; the natural next research question once syntax/field hallucination is well-characterized |
| MITRE ATT&CK mapping | Automatic technique/tactic tagging on generated rules | An orthogonal extraction problem; adds fields to the IR without changing the existing template compiler |
| OR-logic in filters | Boolean-combined filter groups | Requires extending the IR's `filters` field from a flat list to a tree structure, plus corresponding template changes |
| Production hardening | RBAC/approval workflows, containerization, observability, scaling | Pure engineering concerns; appropriate once there is a validated core to harden |

---

## 27. Execution Checklist

A concrete, ordered list of "done" states for each project phase. Use this as a daily reference.

### Phase 1 — Dataset

- [ ] Azure-Sentinel repo cloned; commit hash recorded in `SOURCE_ATTRIBUTION.md`
- [ ] `pull_detections.py` written and run; `detections_raw.jsonl` generated
- [ ] ASIM schema extracted to `asim_field_reference.json` from same commit
- [ ] Manual verification rubric written and frozen before any review begins
- [ ] 100+ pairs manually verified and passing all 4 rubric checks
- [ ] Each pair paraphrased into 2–3 variants; every variant manually reviewed for drift
- [ ] Complexity tagging applied; automated tags spot-checked on 20% sample per tier
- [ ] Train/test split generated and committed as `test_ids.json` / `train_ids.json`
- [ ] `pairs.jsonl` finalized and ready for pipeline consumption

### Phase 2 — MVP Pipeline

- [ ] Pydantic IR schema (`schema.py`) complete; `extra = "forbid"` enabled
- [ ] All template unit tests written and passing (Simple, Moderate, Complex × per-schema)
- [ ] `kql_literal`, `kql_duration`, `kql_agg_fn` filters unit-tested
- [ ] KQL Syntax Validator approach decided and implemented
- [ ] Schema Validator written and tested (FIELD\_NOT\_FOUND, MISSING\_TIME\_WINDOW cases)
- [ ] Extraction Agent prompt finalized and producing sensible `ExtractionOutput` on MVP cases
- [ ] IR Builder Agent prompt (first attempt + repair variant) finalized
- [ ] `run_with_repair()` implemented and logging `attempts_used`
- [ ] LangGraph graph wired end-to-end
- [ ] All 10 MVP cases manually inspected at every stage: extraction, IR, generated KQL
- [ ] No template bugs remaining in MVP cases

### Phase 3 — Baseline

- [ ] System A prompt finalized (NL + ASIM field reference + few-shot KQL primer)
- [ ] System A inference loop implemented and producing KQL on MVP cases
- [ ] Both systems confirmed to use identical underlying LLM and temperature

### Phase 4 — Full Evaluation

- [ ] System A run on all test cases; outputs saved
- [ ] System B run on all test cases; outputs + `attempts_used` per case saved
- [ ] Ablation 1 (No-Repair) run and saved
- [ ] Ablation 2 (Monolithic Extraction) run and saved
- [ ] Ablation 3 (No Schema Grounding) run and saved
- [ ] Raw results committed to `eval/results/`

### Phase 5 — Analysis

- [ ] SVR, FVR, CodeBLEU, RRR, latency computed for all configurations
- [ ] Bootstrap CIs computed for all aggregate metrics
- [ ] McNemar's test run for SVR and FVR (System A vs. System B)
- [ ] Wilcoxon signed-rank run for CodeBLEU
- [ ] All metrics broken down by complexity tier (Simple / Moderate / Complex)
- [ ] Logic Correctness manual scoring complete using the pre-defined rubric
- [ ] Qualitative error analysis: 4–6 representative System A failure examples annotated against the taxonomy
- [ ] Results tables finalized and ready to drop into the write-up

### Phase 6 — Write-up

- [ ] Abstract drafted (≤ 200 words; should be derivable almost verbatim from Section 1 of this document)
- [ ] Introduction drafted (motivation + contributions)
- [ ] Background drafted (KQL, ASIM, IR analogy)
- [ ] Related Work drafted
- [ ] Method drafted (System A, System B, Security IR, agents, validators, repair loop)
- [ ] Dataset section drafted (construction procedure, complexity distribution, licensing note)
- [ ] Experimental Setup drafted (metrics, ablations, baseline fairness, statistical treatment)
- [ ] Results tables inserted
- [ ] Discussion drafted (which hypotheses held, which didn't, what the ablations reveal, limitations)
- [ ] Conclusion + Future Extensions drafted
- [ ] Limitations section complete — stated as explicit scope decisions, not apologetically
- [ ] Paper reviewed by at least one person familiar with KQL or detection engineering
- [ ] Final submission ready
