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

**Status note (re-synced §4AB against the actual shipped code, not
re-asserted from memory):** every prior version of this section through
§4Z described an earlier, smaller snapshot of `src/ir_engine/ir_schema.py`
— missing `AndGroup` (§4O), `Filter.field_ref` (§4AA), the `EQ_CI`/
`NEQ_CI`/`_cs` operator family (§4AB), `MvExpandStage`/`MakeSeriesStage`/
`SeriesAnomalyStage`/`ParseStage` (§4X/§4Z), `ArgMaxMin` (§4Z), the full
9-member `JoinKind` (§4N), and `KqlPipeline.caveats` (§1.8). The listing
below is current as of §4AB — but per this project's own repeatedly-
learned lesson about inlined copies of source drifting stale, treat
`src/ir_engine/ir_schema.py` itself as the actual source of truth the
next time this section is read, not this file. Defined as a Pydantic
model — an Abstract Syntax Tree (AST) pipeline of KQL tabular operators.

```python
from enum import Enum
from typing import List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    HAS_ALL = "has_all"               # §4X — AND-equivalent of has_any
    MATCHES_REGEX = "matches regex"
    GT = ">"
    LT = "<"
    GTE = ">="
    LTE = "<="
    IN_CI = "in~"                     # §4X — case-insensitive in/!in
    NOT_IN_CI = "!in~"
    EQ_CI = "=~"                      # §4AB — case-insensitive ==/!=
    NEQ_CI = "!~"                     # NOT "!=~" — its own irregular pair, like ==/!=
    CONTAINS_CS = "contains_cs"       # §4AB — case-SENSITIVE forms of the
    NOT_CONTAINS_CS = "!contains_cs"  # case-insensitive-by-default contains/
    STARTSWITH_CS = "startswith_cs"   # startswith/endswith/has
    NOT_STARTSWITH_CS = "!startswith_cs"
    ENDSWITH_CS = "endswith_cs"
    NOT_ENDSWITH_CS = "!endswith_cs"
    HAS_CS = "has_cs"
    NOT_HAS_CS = "!has_cs"

class Filter(BaseModel):
    type: Literal["filter"] = "filter"
    field: str
    operator: FilterOperator
    # List[Union[str, int, float]], not List[str]: a list-valued filter
    # against a numeric field (e.g. "DstPortNumber in (139, 445)") needs
    # an int list — List[str]-only rejected that and cascaded into a
    # confusing multi-error union-match failure. Found live during §4K.
    value: Optional[Union[str, int, float, bool, List[Union[str, int, float]]]] = None
    # §4AA — compares `field` against ANOTHER COLUMN instead of a literal
    # (e.g. bracketing a process event's time against a joined auth
    # event's time window). Mutually exclusive with `value`.
    field_ref: Optional[str] = None

    @model_validator(mode="after")
    def _exactly_one_of_value_or_field_ref(self) -> "Filter":
        if (self.value is None) == (self.field_ref is None):
            raise ValueError("Filter must set exactly one of `value` or `field_ref`, not both/neither")
        return self

class AndGroup(BaseModel):
    """§4O — an AND-ed sub-condition, usable only INSIDE a FilterGroup,
    so a FilterGroup can express "(A and B) or (C and D)", not just a
    flat OR of single atoms."""
    type: Literal["and_group"] = "and_group"
    conditions: List[Filter] = Field(min_length=2)

class FilterGroup(BaseModel):
    """A parenthesized OR block — "(A or B)". Still AND-ed with every
    other item in the same WhereStage's filters list; only the conditions
    *inside* the group are OR-ed. Needs >= 2 conditions to be meaningful."""
    type: Literal["group"] = "group"
    conditions: List[Union[Filter, AndGroup]] = Field(min_length=2)

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
    STDEV = "stdev"      # §4N
    VARIANCE = "variance"

class Aggregation(BaseModel):
    function: AggregationFunction
    field: Optional[str] = None
    result_alias: str = "AggregatedValue"
    percentile: Optional[float] = None  # required, 0-100, iff function="percentile"
    limit: Optional[int] = None         # optional cap for make_set/make_list

class ArgMaxMin(BaseModel):
    """§4Z — `arg_max(order_field, *)`/`arg_min(...)`: "the full row at
    the max/min value of order_field, per group." Each carried field
    becomes its OWN output column (not reduced under one result_alias
    like a plain Aggregation) — structurally different, so it's its own
    model rather than a variant of Aggregation."""
    order_field: str
    carry_fields: List[str] = Field(min_length=1)  # ["*"] = every remaining column
    result_alias: Optional[str] = None             # renames order_field's OWN column only

class ComputedField(BaseModel):
    alias: str
    expression: str  # raw KQL expression — see Schema Validator section
                      # below for how this is checked despite being a string

class JoinKind(str, Enum):
    INNER = "inner"
    INNERUNIQUE = "innerunique"  # §4N — widened from 3 to all 9 real KQL join kinds
    LEFTOUTER = "leftouter"
    RIGHTOUTER = "rightouter"
    FULLOUTER = "fullouter"
    LEFTANTI = "leftanti"
    RIGHTANTI = "rightanti"
    LEFTSEMI = "leftsemi"
    RIGHTSEMI = "rightsemi"

class WhereStage(BaseModel):
    type: Literal["where"] = "where"
    filters: List[Union[Filter, FilterGroup]] = Field(default_factory=list)

class SummarizeStage(BaseModel):
    type: Literal["summarize"] = "summarize"
    aggregations: List[Aggregation] = Field(default_factory=list)
    group_by: Optional[List[str]] = None
    time_window: Optional[str] = None
    arg_max: Optional[ArgMaxMin] = None  # §4Z — combines freely with aggregations/group_by
    arg_min: Optional[ArgMaxMin] = None

class ExtendStage(BaseModel):
    type: Literal["extend"] = "extend"
    computed_fields: List[ComputedField] = Field(default_factory=list)

class JoinStage(BaseModel):
    type: Literal["join"] = "join"
    kind: JoinKind = JoinKind.INNER
    # Forward ref, not Any: right_pipeline must be a real, Pydantic-
    # validated KqlPipeline. With Any (the original migration's typing),
    # a malformed nested pipeline parsed "successfully" as a raw dict and
    # crashed validate_ir's recursive call with AttributeError instead of
    # failing validation cleanly — found live, fixed in §4K round 1.
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

class MvExpandStage(BaseModel):    # §4X
    type: Literal["mv_expand"] = "mv_expand"
    fields: List[str] = Field(min_length=1)  # multi-field = lockstep expansion
    as_type: Optional[str] = None            # `to typeof(...)` — single-field only

class MakeSeriesStage(BaseModel):  # §4X — one row per group, each aggregation
    type: Literal["make_series"] = "make_series"  # a DYNAMIC ARRAY of per-bucket values
    aggregations: List[Aggregation] = Field(min_length=1)
    group_by: Optional[List[str]] = None
    from_time: str       # literal KQL time expression, e.g. "ago(14d)"
    to_time: str = "now()"
    step: str            # ISO 8601 bin width, e.g. "PT1H"

class SeriesAnomalyStage(BaseModel):  # §4X — series_decompose_anomalies()
    type: Literal["series_anomaly"] = "series_anomaly"
    series_field: str  # an array-valued aggregation alias from MakeSeriesStage
    score_threshold: float = 1.5
    flag_alias: str = "AnomalyFlag"
    score_alias: str = "AnomalyScore"
    baseline_alias: str = "Baseline"

class ParseToken(BaseModel):  # §4Z — one token in a `parse ... with ...` clause
    type: Literal["literal", "column", "wildcard"]
    value: Optional[str] = None

class ParseStage(BaseModel):  # §4Z — simple/positional `parse` mode only
    type: Literal["parse"] = "parse"
    source_field: str
    tokens: List[ParseToken] = Field(min_length=1)

Stage = Union[
    WhereStage, SummarizeStage, ExtendStage, JoinStage,
    UnionStage, ProjectStage, TopStage,
    MvExpandStage, MakeSeriesStage, SeriesAnomalyStage, ParseStage,
]

class KqlPipeline(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_table: Union[ASIMEventType, str]
    stages: List[Stage] = Field(default_factory=list)
    # §1.8 — self-disclosed abstentions: one short string per filter the
    # IR Builder deliberately omitted because the description referenced
    # data it couldn't concretely ground. Rendered as leading `// CAVEAT:`
    # comments by the compiler.
    caveats: List[str] = Field(default_factory=list)

# Resolves the JoinStage.right_pipeline forward reference now that
# KqlPipeline itself is defined.
JoinStage.model_rebuild()
KqlPipeline.model_rebuild()
```

### Why a Pipeline AST?

Real-world KQL is a sequential pipeline of tabular operators (`| where ... | summarize ... | extend ... | join ... | summarize ...`). By moving from a flat JSON object to a composable AST, the framework gains the flexibility to express chained joins, multi-stage aggregations, computed fields, and unions. It supports arbitrary `source_table` strings as well as predefined `ASIMEventType` enums.

---

## Extraction Agent — Specification

**Input:** raw NL description string.
**Output:** a structured (but not yet schema-validated) extraction object — looser than the IR in every field EXCEPT `likely_event_type`, which is now pinned to an exact ASIM type name (see status note below).

```python
class ExtractionOutput(BaseModel):
    likely_event_type: str            # an exact ASIM type name as of §4P — see status note
    actors: list[str]                 # e.g. ["attacker", "source IP"]
    action_description: str           # e.g. "attempts logins with many different usernames"
    threshold_language: Optional[str] # e.g. "many different usernames" — not yet a number
    time_language: Optional[str]      # e.g. "within a short window" — not yet a duration
    candidate_fields: list[str]       # field names the model believes are relevant, pre-validation
```

**Status note (§4P):** `likely_event_type` was originally a loose
descriptive phrase ("process execution", "DNS query") — but
`run_with_repair` looks this value up *as a dictionary key* into the ASIM
schema to narrow the field reference the IR Builder sees. A loose phrase
never matches a real key, so schema narrowing was silently falling back
to the full union of every event type's fields on essentially every
request — exactly the larger, more hallucination-prone field list schema
grounding exists to avoid. Fixed by moving the event-type disambiguation
rules (previously only in the IR Builder's prompt) upstream into this
agent, with `likely_event_type` now required to be one of the 7 exact
ASIM type names. The IR Builder keeps its own copy of the same rules as a
fallback for the case where extraction's value isn't a real match — not
as the primary path anymore.

**Prompt sketch (abbreviated — see `src/agents/extraction_agent.py` for the
exact, current text):**

```
SYSTEM: You are a security analyst extracting structured signal from a natural
language detection description. Do not guess at exact ASIM field names or KQL
syntax — that happens in a later step.

likely_event_type MUST be the exact ASIM event type name, one of:
AuthenticationEvent, NetworkSessionEvent, ProcessEvent, FileEvent, DnsEvent,
WebSessionEvent, RegistryEvent — never a loose phrase and never the attacker's
technique or outcome (e.g. "file wiping"). Pin the choice with keyword
anchors: DNS lookup/query/NXDOMAIN -> DnsEvent; HTTP/URL/status code/User-
Agent -> WebSessionEvent; process/command-line execution -> ProcessEvent
(even when the description's goal sounds like a file event); sign-in/login
-> AuthenticationEvent; registry key changes -> RegistryEvent; generic
port/protocol/byte-count with no DNS/HTTP specificity -> NetworkSessionEvent.
[See PROJECT_STATUS.md §4K for the original event-type-confusion bug this
guidance fixes, and §4P for why it was moved to this agent specifically.]

If the description names a well-known tool (e.g. "Sysinternals sdelete")
without spelling out its exact syntax, recall the tool's real, documented
flags from your own knowledge rather than leaving them for the next step
to invent. [§4N — found live tracing a case whose raw text never states
the tool's actual flags at all.]

USER: {nl_description}
```

This agent is deliberately under-constrained relative to the final IR — except for `likely_event_type`, as of §4P. The separation exists specifically to test **RQ2** — whether splitting "understand the threat" from "commit to a schema-valid structure" measurably helps, independent of schema grounding itself (which is tested by the Schema Validator regardless of how the IR was built). See the [Monolithic Extraction ablation](evaluation.md#ablations) for the controlled comparison.

---

## IR Builder Agent — Specification

**Input:** `ExtractionOutput` + the ASIM field reference for the candidate event type + (on repair) a structured validator error.
**Output:** a `KqlPipeline` object (not `SecurityIR` — see the schema section above for the migration history).

**Status note:** the real prompt (`src/agents/ir_builder_agent.py`,
`_COMMON_MISTAKES`) is several pages of accumulated, live-evidence-based
guidance — far longer than the sketch below, which shows the prompt's
*structure*, not its full content. Reproducing the full text here would
duplicate the actual source of truth and inevitably drift out of sync with
it again, the same failure mode that caused most of §4K's findings in the
first place. Read the source file directly for the current, exact wording.

**Prompt sketch (first attempt):**

```
SYSTEM: You are converting a structured extraction into an AST-based Security IR
KqlPipeline that conforms exactly to the following schema. You may ONLY use
field names that appear in the provided ASIM field reference below, or
aliases you defined in an earlier summarize/extend stage of the SAME pipeline.

ASIM field reference for {likely_event_type}:
{asim_field_list}

[... several pages of "common mistakes to avoid," each one traceable to a
specific live failure found during this study — pipeline stage ordering;
schema mutation across summarize/project; Src*/Dst* field direction; DNS/
HTTP/Process event-type disambiguation; FilterGroup vs. AND-ed filters,
including the specific "(X1, ..., or Xn) is/does Y" sentence-shape trap;
disguised/renamed-tool evasion (a full worked example); percentile usage;
multi-column summarize; real-vs-invented KQL function names in extend
expressions — plus three full worked examples (baseline-vs-current,
disguised-tool evasion, percentile-of-aggregates) ...]

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

[... same "common mistakes" content as the first-attempt prompt ...]
```

The repair prompt is intentionally narrow — "fix this specific error" rather than "try again" — because broad re-generation risks introducing a *new* error while fixing the old one, which would make the repair loop's recovery rate (H3) harder to interpret cleanly.

---

## Schema Validator — Specification

**Status note:** this section originally documented a 5-check sketch.
Live-testing after the AST migration shipped found the sketch's checks
were a small fraction of what the original flat `SecurityIR` validator
had, and one of the sketch's own documented checks (`MISSING_TIME_WINDOW`)
didn't actually exist in the shipped code at all. The list below is the
real, current check set in `src/ir_engine/ir_validator.py` — see
`PROJECT_STATUS.md` §4K–§4P for which of these were restored, genuinely
new, or added in the latest hardening round. There are now 15 hard-error
types plus one advisory (non-blocking) warning class; both are exhaustively
covered by `tests/unit/test_validator_inventory.py`, which cross-checks
this exact list against every `error_type="..."` literal the source file
actually contains — the insurance against this table (or the code) silently
drifting out of sync again.

Pure Python, no LLM call. The validator is a **stateful schema tracker**:
it walks the AST stage by stage, maintaining `available_schema` (which
fields actually exist at this point in the pipeline) and
`count_like_aliases` (which of those came from a `count`/`distinct_count`
aggregation, for the degenerate-threshold check below). Checks run in
order, short-circuiting on the first failure so a repair prompt always
addresses exactly one issue:

| Error type | What it catches | Stage(s) |
|---|---|---|
| `INVALID_SOURCE_TABLE` | `source_table` isn't a recognized ASIM event type — checked first, before any field check, so a free-text label doesn't cascade into confusing downstream errors | (pipeline-level) |
| `FIELD_NOT_FOUND` | A field reference (filter, `AndGroup` condition, group_by, aggregation field, project field, top by_field, or an `extend` expression's referenced identifier) not in the schema available *at that point* in the pipeline. The suggested closest field name now also carries a one-line value-type hint when the name matches a recognized ASIM naming convention (e.g. `DstPortNumber (expects a port number, e.g. 443)`) | where, summarize, extend, project, top |
| `FUNCTION_CALL_AS_LITERAL_VALUE` | A `Filter.value` string that looks like a KQL function call (`"ago(1h)"`) — compared as literal text, never evaluated; added §4O | where |
| `DEGENERATE_THRESHOLD` | A where-filter on a `count`/`distinct_count` result with a threshold that's trivially true for any existing group (`> 0`, `>= 1`) — restored, dropped by the original migration | where (after summarize) |
| `TAUTOLOGICAL_FILTER_GROUP` | A `FilterGroup` (OR) whose conditions are either (a) all negated operators on the same field with different values, or (b) a direct complementary pair (`X in (...) or X !in (...)`) — both are always-true tautologies that filter nothing | where |
| `DUPLICATE_AGGREGATION_ALIAS` | Two aggregations in the same `SummarizeStage` sharing a `result_alias` | summarize |
| `AGGREGATION_MISSING_FIELD` | A function other than `count` with no field (only `count()` takes zero arguments in KQL) | summarize |
| `INVALID_PERCENTILE_VALUE` | `function="percentile"` with a missing or out-of-[0,100] `percentile` value | summarize |
| `MISSING_TIME_WINDOW` | A `SummarizeStage` with aggregations but no time_window — would scan the whole table | summarize |
| `INVALID_TIME_WINDOW` | A time_window string that isn't a valid ISO 8601 duration | summarize |
| `AGGREGATE_FUNCTION_IN_EXTEND` | An aggregation function (`stdev`, `count`, `percentile`, ...) called inside an `ExtendStage` expression — these only exist inside `summarize` in real KQL; added §4N after live-tracing a silently-degenerate query (a single-row stdev is always 0/null) | extend |
| `UNKNOWN_FUNCTION_IN_EXPRESSION` | An `ExtendStage` expression calling a function name not in the ~120-entry real-KQL-function whitelist | extend |
| `JOIN_KEY_NOT_FOUND_LEFT` / `_RIGHT` | A `join_on` key missing from either side's available schema at that point | join |
| `EMPTY_UNION` | A `UnionStage` with no tables | union |

**Advisory warning (non-blocking) — `ValidationResult.warnings`:** a
literal-value provenance check, added §4P, flags any string `Filter.value`
that doesn't appear (case-insensitively, allowing a common `.exe`/`.dll`-
style suffix) anywhere in the original NL description and isn't a common
status word or a real DNS RCODE. Deliberately advisory, not a hard error
— measured empirically on a live trial run before shipping: of 11 flagged
values across 42 successful cases, only 1 was a genuine invented literal
(a fabricated `$Recycle.Bin` path); the rest were legitimate recalled
domain knowledge (a named tool's real flags, a DNS enum value, a trivial
`.exe` suffix) that a hard error would have wrongly rejected. See
`PROJECT_STATUS.md` §4P for the full trial breakdown.

`ExtendStage.computed_fields[].expression` is the one field this
validator cannot fully check the way it checks everything else — it's a
raw KQL expression string, not a structured field reference. A best-effort
identifier extractor strips string literals, treats any identifier
immediately followed by `(` as a function call rather than a field
reference, and checks every remaining identifier against
`available_schema`. Not a full KQL parser — false positives on an unusual
constant-like token are possible — but a real check where there was
previously none at all (the original migration shipped this as a
completely unchecked string, the single largest field-hallucination gap
the AST design introduced).

`AndGroup` (added §4O) lets a `FilterGroup` express a disjunction of
conjunctions — `(A and B) or (C and D)` — which a flat OR of plain atoms
structurally cannot. Its conditions are checked for field existence the
same way plain `Filter` entries are; the two `TAUTOLOGICAL_FILTER_GROUP`
checks deliberately only reason about plain `Filter` entries (an
`AndGroup` branch makes the group not-tautological by construction, since
`all(c.type == "filter" ...)` naturally excludes it) — confirmed safe on
mixed lists by a dedicated regression test rather than just asserted.

`right_pipeline` on a `JoinStage` is validated recursively (`validate_ir`
calling itself on the nested pipeline) — this also requires
`right_pipeline` to actually be a `KqlPipeline` object, not a raw `dict`;
see the crash-bug note on the schema definition above.

A `WhereStage` attempting to filter on a raw field *after* a
`SummarizeStage` that dropped it correctly fails `FIELD_NOT_FOUND` —
pushing the correctness check as far left as possible, and the mechanism
behind a real, live-found AST-specific failure class (a model filtering on
a field after the stage that already dropped it, rather than before).

---

## KQL Generator — Recursive Pipeline Compiler

The non-LLM transformation step that produces the final artifact
(`src/generator/compiler.py`). It recursively compiles each stage in the
AST and concatenates them with the pipe `|` operator — genuinely
recursive for `JoinStage`, which compiles its `right_pipeline` the same
way and indents the result as a parenthesized sub-block.

Two bugs were found live after the migration shipped, both now fixed:
`kql_literal` (in `src/generator/filters.py`) crashed with an
`AttributeError` on a non-string list item — confirmed by a numeric `in`
filter like `DstPortNumber in (139, 445)`, which needs each list item
rendered unquoted, not run through string-escaping logic that assumes
every item is a string. `percentile()`/`make_set()`/`make_list()` need a
dedicated render path (`kql_agg_call`) since they take a second argument
most aggregation functions don't.

This step makes zero LLM calls. The shift to fragment-based compilation
eliminates single-template mismatch bugs and allows infinite chaining of
tabular operators — confirmed live on the percentile-of-aggregates
pattern (a constant-key self-join plus a second `SummarizeStage` with no
group_by, reducing to one global scalar row), which the original flat
`SecurityIR` could never express at all.

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

**Status note:** an earlier version of this pseudocode used
`for attempt in range(max_attempts):`, which has an off-by-one bug found
live in §4I: with `max_attempts=3`, the loop makes 4 total builds (1
initial + 3 repairs) but only validates the first 3 — the *final* rebuild
is returned as `MAX_REPAIR_ATTEMPTS_EXCEEDED` without ever being checked,
even when it was actually valid. The corrected version below
(`range(max_attempts + 1)`, only rebuilding while `attempt < max_attempts`)
validates every build while keeping the total number of model calls
unchanged. The real implementation (`src/pipeline/repair_loop.py`) also
runs a constraint-traceability check after a passing schema validation
(catching a threshold/percentile/top-N/extend-derived value that silently
drifted from the description), escalates temperature after two
consecutive identical failures, threads the original `nl_description`
through to `validate_ir()` for the literal-value provenance warning
(§4P), and passes the previous IR's best-effort compiled KQL into the
repair prompt alongside the structured error (§4P) — all omitted below
for brevity.

```python
def run_with_repair(extraction: ExtractionOutput, asim_schema: dict,
                     max_attempts: int = 3) -> PipelineResult:
    ir, build_error = build_ir(ir_builder_agent, extraction, asim_schema)

    for attempt in range(max_attempts + 1):
        ir_validation = build_error or validate_ir(ir, asim_schema)
        if ir_validation.passed:
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

        if attempt == max_attempts:
            break  # out of rebuild budget — every build so far WAS checked

        ir, build_error = build_ir(ir_builder_agent, extraction, asim_schema,
                                     repair_error=ir_validation, previous_ir=ir)

    return PipelineResult(success=False, reason="MAX_REPAIR_ATTEMPTS_EXCEEDED",
                            ir=ir)
```

Three design choices worth calling out explicitly:

1. **The repair loop only re-prompts on IR validation failure, not KQL syntax failure.** Since KQL generation is deterministic template substitution, a syntax failure at that stage means the *template* is wrong, not the IR — re-prompting the IR Builder Agent would not fix a template bug, so the loop correctly routes that failure to template-bug logging instead of wasting a repair attempt.
2. **`attempts_used` is recorded on every success**, not just failures — this is what makes [Repair Recovery Rate](evaluation.md#metrics-exact-definitions) and "average iterations needed" (H3) measurable at all.
3. **`range(max_attempts + 1)`, not `range(max_attempts)`** — every build the loop makes gets validated, including the last one, without increasing the total number of model calls (rebuilds still only happen while `attempt < max_attempts`).

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

**3. Schema Validator result:** `FAIL — MISSING_TIME_WINDOW: summarize stage has aggregations but time_window is null`

**4. IR Builder Agent, repair attempt 2:**
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

**5. Schema Validator result:** `PASS`

**6. Generated KQL:**
```kql
imAuthentication
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
