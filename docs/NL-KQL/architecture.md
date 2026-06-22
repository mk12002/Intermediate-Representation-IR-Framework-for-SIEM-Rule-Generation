# Architecture — Deep Dive

This document is the full technical specification of the two systems under test, the Security IR schema, the agent prompts, and the repair loop. The [README](../README.md) covers this at landing-page depth; this document covers it at implementation depth.

## Table of Contents

- [Design Philosophy](#design-philosophy)
- [System A — Baseline Pipeline](#system-a-baseline-pipeline)
- [System B — IR-Mediated Pipeline](#system-b-ir-mediated-pipeline)
- [The Security IR — Full Schema](#the-security-ir-full-schema)
- [Extraction Agent — Specification](#extraction-agent-specification)
- [IR Builder Agent — Specification](#ir-builder-agent-specification)
- [Schema Validator — Specification](#schema-validator-specification)
- [KQL Generator — Template Compiler](#kql-generator-template-compiler)
- [KQL Syntax Validator — Specification](#kql-syntax-validator-specification)
- [The Repair Loop](#the-repair-loop)
- [Worked Example — End to End](#worked-example-end-to-end)
- [Failure Modes and How Each Stage Catches Them](#failure-modes-and-how-each-stage-catches-them)
- [Why Not a Single Mega-Prompt](#why-not-a-single-mega-prompt)

---

## Design Philosophy

Three architectural commitments run through every component below, and every design decision in this document traces back to one of them:

1. **Push correctness left.** Every error category (syntax, field, logic) should be caught as early in the pipeline as the information needed to catch it becomes available. Field hallucination doesn't need to wait until KQL is generated to be caught — it can be caught the moment the IR references a field, against a schema that's already loaded. This is why the Schema Validator runs on the IR, not on the final KQL string.
2. **Generative steps should be narrow; everything else should be deterministic.** The only two LLM calls in System B are extraction and IR construction. Compilation from IR to KQL is template substitution — zero degrees of freedom, zero hallucination surface. This is the single biggest structural difference from System A, where the entire NL→KQL mapping happens inside one unconstrained generative step.
3. **Every validator failure should produce a structured, actionable error**, not a pass/fail boolean. `"field 'SourceIP' not found in schema AuthenticationEvent; did you mean 'SrcIpAddr'?"` is repairable by a re-prompt. `False` is not. This shapes the Schema Validator and KQL Syntax Validator output formats below.

---

## System A — Baseline Pipeline

```
NL input + ASIM field reference + KQL syntax primer (few-shot)
        │
        ▼
   [Single LLM call]
        │
        ▼
   Raw KQL string output
```

**Prompt structure** (see [`src/baseline/prompt.py`](../src/baseline/prompt.py) once implemented):

```
SYSTEM: You are a Microsoft Sentinel detection engineer. Given a natural language
description of a detection requirement, write a single KQL query that implements it.

You have access to the following ASIM schema fields for the relevant event type:
{asim_field_reference}

Here are two examples of natural language descriptions and their correct KQL:
{few_shot_example_1}
{few_shot_example_2}

Return only the KQL query, no explanation.

USER: {nl_description}
```

This is deliberately the **strongest reasonable baseline**, not a strawman — see [Baseline Fairness](evaluation.md#baseline-fairness) in the evaluation doc for why this matters and what would make it unfair if cut.

System A makes exactly **one LLM call per case**. No validation, no repair. Its raw output is what gets scored by the Syntax Validator and Field Validator post-hoc, purely for measurement — System A does not see or react to those scores.

---

## System B — IR-Mediated Pipeline

```
  NL input
     │
     ▼
  [Extraction Agent]  ──reads──>  ASIM field reference (read-only)
     │
     │  produces: structured extraction (entities, behaviors, intent)
     ▼
  [IR Builder Agent] ──> Security IR (JSON, Pydantic-validated)
     │
     ▼
  [Schema Validator] ──fail──┐
     │ pass                  │
     ▼                       │  structured error
  [KQL Generator]             │  fed back to
  (Jinja2, deterministic,     │  IR Builder Agent
   zero LLM calls)            │  (≤3 attempts)
     │                        │
     ▼                        │
  [KQL Syntax Validator] ──fail──┘
     │ pass
     ▼
  Validated KQL output
```

Six discrete stages, two of which are generative (Extraction, IR Builder), four of which are deterministic (Schema Validator, KQL Generator, KQL Syntax Validator, and the repair loop's retry logic itself).

---

## The Security IR — Full Schema

Defined as a Pydantic model. This is the authoritative schema; the table below is a human-readable view of it.

```python
from pydantic import BaseModel, Field
from typing import Literal, Optional
from enum import Enum

class ASIMEventType(str, Enum):
    AUTHENTICATION = "AuthenticationEvent"
    NETWORK_SESSION = "NetworkSessionEvent"
    PROCESS = "ProcessEvent"
    FILE = "FileEvent"
    DNS = "DnsEvent"
    WEB_SESSION = "WebSessionEvent"
    REGISTRY = "RegistryEvent"
    # extend as additional ASIM schemas are brought into scope

class FilterOperator(str, Enum):
    EQ = "=="
    NEQ = "!="
    CONTAINS = "contains"
    STARTSWITH = "startswith"
    IN = "in"
    GT = ">"
    LT = "<"
    GTE = ">="
    LTE = "<="

class Filter(BaseModel):
    field: str                      # must exist in the ASIM schema for event_type
    operator: FilterOperator
    value: str | int | list[str]

class AggregationFunction(str, Enum):
    COUNT = "count"
    DISTINCT_COUNT = "distinct_count"
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"

class Aggregation(BaseModel):
    function: AggregationFunction
    field: Optional[str] = None     # null for plain `count`

class ThresholdOperator(str, Enum):
    GT = ">"
    GTE = ">="
    LT = "<"
    LTE = "<="
    EQ = "=="

class Threshold(BaseModel):
    operator: ThresholdOperator
    value: int | float

class SecurityIR(BaseModel):
    event_type: ASIMEventType
    filters: list[Filter] = Field(default_factory=list)
    aggregation: Optional[Aggregation] = None
    group_by: Optional[list[str]] = None
    threshold: Optional[Threshold] = None
    time_window: Optional[str] = None   # ISO 8601 duration, e.g. "PT5M"
    output_fields: Optional[list[str]] = None

    class Config:
        extra = "forbid"   # reject unknown fields outright rather than silently dropping them
```

### Field-level notes

| Field | Required When | Validation Rule |
|---|---|---|
| `event_type` | Always | Must be a member of `ASIMEventType` |
| `filters` | Optional, can be empty list | Each `filter.field` must exist in the ASIM schema dump for `event_type` |
| `aggregation` | Optional | If present, `time_window` becomes **required** — this is enforced explicitly, not left to chance (see [H4 rationale](evaluation.md#what-would-falsify-each-hypothesis)) |
| `group_by` | Optional | Each entry must exist in the ASIM schema for `event_type`; only meaningful if `aggregation` is set |
| `threshold` | Optional | Only meaningful if `aggregation` is set; the validator flags (but does not hard-fail) a threshold with no aggregation, since it's a likely extraction error worth surfacing |
| `time_window` | **Required if `aggregation` is set** | Must parse as a valid ISO 8601 duration |
| `output_fields` | Optional | If omitted, the KQL Generator defaults to projecting all `group_by` fields plus the aggregation result |

### Why `extra = "forbid"`

This is a small but important decision. If the IR Builder Agent hallucinates a field name that isn't part of the schema (e.g. `"severity_score"` instead of using `threshold`), Pydantic rejects the object outright at parse time rather than silently accepting it. This converts a category of error that would otherwise surface much later (in the KQL Generator, or worse, not at all) into an immediate, catchable validation failure — consistent with the "push correctness left" principle.

---

## Extraction Agent — Specification

**Input:** raw NL description string.
**Output:** a structured (but not yet schema-validated) extraction object — looser than the IR, intentionally, since its job is to surface candidate signal, not commit to a final schema-conformant structure.

```python
class ExtractionOutput(BaseModel):
    likely_event_type: str            # free-text guess, not yet constrained to the enum
    actors: list[str]                 # e.g. ["attacker", "source IP"]
    action_description: str           # e.g. "attempts logins with many different usernames"
    threshold_language: Optional[str] # e.g. "many different usernames" — not yet a number
    time_language: Optional[str]      # e.g. "within a short window" — not yet a duration
    candidate_fields: list[str]       # field names the model believes are relevant, pre-validation
```

**Prompt sketch:**

```
SYSTEM: You are a security analyst extracting structured signal from a natural
language detection description. Do not guess at exact ASIM field names or KQL
syntax — that happens in a later step. Your job is only to identify: the type
of event being described, the actors involved, the core action/behavior, any
threshold language (e.g. "many", "more than 10"), any time-window language
(e.g. "within five minutes", "repeatedly"), and field names you believe are
relevant based on the description.

USER: {nl_description}
```

This agent is deliberately under-constrained relative to the final IR. The separation exists specifically to test **RQ2** — whether splitting "understand the threat" from "commit to a schema-valid structure" measurably helps, independent of schema grounding itself (which is tested by the Schema Validator regardless of how the IR was built). See the [Monolithic Extraction ablation](evaluation.md#ablations) for the controlled comparison.

---

## IR Builder Agent — Specification

**Input:** `ExtractionOutput` + the ASIM field reference for the candidate event type + (on repair) a structured validator error.
**Output:** a `SecurityIR` object.

**Prompt sketch (first attempt):**

```
SYSTEM: You are converting a structured extraction into a Security IR object
that conforms exactly to the following schema. You may ONLY use field names
that appear in the provided ASIM field reference below — do not infer or
guess field names from general knowledge of similar platforms.

ASIM field reference for {likely_event_type}:
{asim_field_list}

Security IR schema:
{ir_json_schema}

USER: {extraction_output}
```

**Prompt sketch (repair attempt, ≤3 total):**

```
SYSTEM: Your previous IR failed validation with the following error:
{structured_validator_error}

Correct ONLY the issue described above. Do not change other parts of the IR
unless necessary to fix this specific error.

Previous IR:
{previous_ir_json}

ASIM field reference for {likely_event_type}:
{asim_field_list}
```

The repair prompt is intentionally narrow — "fix this specific error" rather than "try again" — because broad re-generation risks introducing a *new* error while fixing the old one, which would make the repair loop's recovery rate (H3) harder to interpret cleanly.

---

## Schema Validator — Specification

Pure Python, no LLM call. Runs three checks in order, short-circuiting on the first failure (so the repair prompt always addresses exactly one issue):

```python
def validate_ir(ir: SecurityIR, asim_schema: dict) -> ValidationResult:
    # 1. Field existence — filters
    schema_fields = asim_schema[ir.event_type.value]["fields"]
    for f in ir.filters:
        if f.field not in schema_fields:
            return ValidationResult(
                passed=False,
                error_type="FIELD_NOT_FOUND",
                message=f"field '{f.field}' not found in schema "
                        f"'{ir.event_type.value}'; closest match: "
                        f"{closest_match(f.field, schema_fields)}"
            )

    # 2. Field existence — group_by
    if ir.group_by:
        for gb in ir.group_by:
            if gb not in schema_fields:
                return ValidationResult(
                    passed=False, error_type="FIELD_NOT_FOUND",
                    message=f"group_by field '{gb}' not found in schema "
                            f"'{ir.event_type.value}'"
                )

    # 3. Required time_window when aggregation present
    if ir.aggregation and not ir.time_window:
        return ValidationResult(
            passed=False, error_type="MISSING_TIME_WINDOW",
            message="aggregation present but time_window is null — "
                    "this would scan the entire table with no time bound"
        )

    return ValidationResult(passed=True)
```

`closest_match()` is a small fuzzy-match helper (e.g. Levenshtein distance against the schema field list) — its purpose is purely to make repair prompts more actionable, not to silently auto-correct. The validator never guesses on the system's behalf; it only suggests, and the IR Builder Agent decides.

---

## KQL Generator — Template Compiler

The only non-LLM transformation step that produces the final artifact. A Jinja2 template per `ASIMEventType`, parameterized by the validated IR.

```jinja2
{# templates/authentication_event.kql.j2 #}
{{ asim_table_name }}
{%- for f in filters %}
| where {{ f.field }} {{ f.operator }} {{ f.value | kql_literal }}
{%- endfor %}
{%- if aggregation %}
| summarize {{ aggregation.result_alias }} = {{ aggregation.function }}({{ aggregation.field }})
    by {{ group_by | join(", ") }}{% if time_window %}, bin(TimeGenerated, {{ time_window | kql_duration }}){% endif %}
{%- endif %}
{%- if threshold %}
| where {{ aggregation.result_alias }} {{ threshold.operator }} {{ threshold.value }}
{%- endif %}
{%- if output_fields %}
| project {{ output_fields | join(", ") }}
{%- endif %}
```

`kql_literal` and `kql_duration` are custom Jinja2 filters handling KQL-specific value formatting (string quoting, `5m`/`1h` duration syntax) — small, independently unit-testable functions, which matters because every bug here is a bug that affects *every* generated query, not just one case.

**This step makes zero LLM calls.** Its only failure mode is a template/IR mismatch (e.g. an IR field combination the template doesn't handle), which should be caught by unit tests against the IR schema, not by the runtime Syntax Validator — if it reaches the Syntax Validator, that's a gap in template test coverage worth fixing directly.

---

## KQL Syntax Validator — Specification

Parses the generated KQL string against a KQL grammar. See [Known Risks](dataset.md#known-risks) for the open question of which parser/linter to use — this section assumes that decision has been made and documents the validator's *interface*, which is independent of the underlying parser choice:

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

If `kql` was produced by the deterministic KQL Generator (System B), a syntax failure here indicates a **template bug**, not a model hallucination — and should be logged separately from System A's syntax failures, since conflating the two would understate how clean System B's syntax failure mode actually is. This distinction matters for honestly reporting [SVR](evaluation.md#metrics-exact-definitions) per system.

---

## The Repair Loop

```python
def run_with_repair(extraction: ExtractionOutput, asim_schema: dict,
                     max_attempts: int = 3) -> PipelineResult:
    ir = ir_builder_agent(extraction, asim_schema)

    for attempt in range(max_attempts):
        ir_validation = validate_ir(ir, asim_schema)
        if not ir_validation.passed:
            ir = ir_builder_agent(extraction, asim_schema,
                                    repair_error=ir_validation)
            continue

        kql = generate_kql(ir)
        syntax_validation = validate_kql_syntax(kql)
        if not syntax_validation.passed:
            # syntax failure on deterministically-generated KQL means a
            # template bug, not an IR problem — log distinctly, do not
            # spend a repair attempt re-prompting the IR Builder for this
            log_template_bug(ir, kql, syntax_validation)
            return PipelineResult(success=False, reason="TEMPLATE_BUG")

        return PipelineResult(success=True, ir=ir, kql=kql,
                                attempts_used=attempt + 1)

    return PipelineResult(success=False, reason="MAX_REPAIR_ATTEMPTS_EXCEEDED",
                            final_ir=ir)
```

Two design choices worth calling out explicitly:

1. **The repair loop only re-prompts on IR validation failure, not KQL syntax failure.** Since KQL generation is deterministic template substitution, a syntax failure at that stage means the *template* is wrong, not the IR — re-prompting the IR Builder Agent would not fix a template bug, so the loop correctly routes that failure to template-bug logging instead of wasting a repair attempt.
2. **`attempts_used` is recorded on every success**, not just failures — this is what makes [Repair Recovery Rate](evaluation.md#metrics-exact-definitions) and "average iterations needed" (H3) measurable at all.

---

## Worked Example — End to End

**Input:** *"Flag when a single account fails to log in more than 15 times within ten minutes."*

**1. Extraction Agent output:**
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

**2. IR Builder Agent output (first attempt — contains an error):**
```json
{
  "event_type": "AuthenticationEvent",
  "filters": [{"field": "EventResult", "operator": "==", "value": "Failure"}],
  "aggregation": {"function": "count", "field": null},
  "group_by": ["TargetUsername"],
  "threshold": {"operator": ">", "value": 15},
  "time_window": null,
  "output_fields": null
}
```

**3. Schema Validator result:** `FAIL — MISSING_TIME_WINDOW: aggregation present but time_window is null`

**4. IR Builder Agent, repair attempt 2:**
```json
{
  "event_type": "AuthenticationEvent",
  "filters": [{"field": "EventResult", "operator": "==", "value": "Failure"}],
  "aggregation": {"function": "count", "field": null},
  "group_by": ["TargetUsername"],
  "threshold": {"operator": ">", "value": 15},
  "time_window": "PT10M",
  "output_fields": null
}
```

**5. Schema Validator result:** `PASS`

**6. Generated KQL:**
```kql
AuthenticationEvent
| where EventResult == "Failure"
| summarize FailCount = count() by TargetUsername, bin(TimeGenerated, 10m)
| where FailCount > 15
```

**7. KQL Syntax Validator result:** `PASS`

**Logged result:** `success=True, attempts_used=2` — this case contributes one data point to the Repair Recovery Rate metric.

---

## Failure Modes and How Each Stage Catches Them

| Failure Mode | Caught By | Why Not Earlier / Later |
|---|---|---|
| Hallucinated field name | Schema Validator (on the IR) | Could not be caught at extraction time — extraction output is intentionally pre-schema; could be caught later at KQL string time, but that's strictly worse since the IR is structured and cheaper to check |
| Wrong KQL operator syntax | KQL Syntax Validator | Cannot occur in System B's deterministic generation step except via template bugs (see above); this is the *only* meaningful syntax failure surface in System A |
| Missing time window on aggregation | Schema Validator (explicit rule) | Deliberately enforced as a hard IR-level rule rather than left to the KQL Generator to silently omit a `bin()` clause — this exact failure mode is in [the failure taxonomy](../README.md#the-problem) the project is built to reduce |
| Wrong aggregation direction (e.g. `min` vs `max`) | Logic Correctness manual review only | Neither the Schema Validator nor Syntax Validator can detect this — both the field and the syntax are valid; this is precisely why manual logic review exists as a separate metric rather than being folded into FVR/SVR |
| Threshold present with no aggregation | Schema Validator (soft warning, not hard fail) | Ambiguous — could be a legitimate filter pattern in rare cases — so it's surfaced rather than auto-rejected |

---

## Why Not a Single Mega-Prompt

A natural question: why not just give a single LLM call the ASIM schema, the IR schema, *and* the KQL syntax rules, and ask it to produce correct KQL directly with all that context loaded? Two reasons this isn't System B, and isn't expected to perform as well:

1. **No deterministic compilation step.** Even with perfect context, a single generative step can still produce a syntactically invalid string — there's no template-substitution backstop. This is structurally identical to System A with a longer prompt, not a different system, and is in fact a reasonable variant of System A worth testing as an additional baseline if time permits (see [Future Work](dataset.md) considerations).
2. **No separable validation signal.** If the single call fails, there's no structured way to know *which* part failed (schema grounding vs. syntax) — which is exactly the diagnostic information the [ablations](evaluation.md#ablations) are designed to produce. Collapsing the pipeline collapses the experiment's ability to attribute results to a specific mechanism.
