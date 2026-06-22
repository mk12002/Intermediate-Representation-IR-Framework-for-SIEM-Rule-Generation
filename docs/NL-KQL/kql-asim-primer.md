# KQL & ASIM Technical Primer

A scoped technical reference for the KQL operators and ASIM schema concepts this project actually touches. This is **not** a complete KQL or ASIM reference — it deliberately covers only what's needed to understand the [Security IR](architecture.md#the-security-ir-full-schema), the [KQL Generator templates](architecture.md#kql-generator-template-compiler), and the [failure taxonomy](../README.md#the-problem) this project measures against. For the full language reference, see the [official KQL documentation](https://learn.microsoft.com/en-us/kusto/query/) and [ASIM documentation](https://learn.microsoft.com/en-us/azure/sentinel/normalization-schema).

## Table of Contents

- [KQL Fundamentals](#kql-fundamentals)
- [Operators Used by This Project's Templates](#operators-used-by-this-projects-templates)
- [Common KQL Mistakes This Project Measures](#common-kql-mistakes-this-project-measures)
- [What ASIM Is, in Practical Terms](#what-asim-is-in-practical-terms)
- [ASIM Schemas in Scope](#asim-schemas-in-scope)
- [ASIM Field Naming Conventions](#asim-field-naming-conventions)
- [Why KQL Is Distinct from SQL and SPL (and Why That Matters Here)](#why-kql-is-distinct-from-sql-and-spl-and-why-that-matters-here)

---

## KQL Fundamentals

KQL is a **pipe-based, read-only query language**. Data flows through a left-to-right sequence of operators, each separated by `|`, where each operator transforms the tabular result of the previous one:

```kql
TableName
| where <condition>
| summarize <aggregation> by <grouping>
| project <columns>
```

There is no `SELECT`, no `GROUP BY` keyword, no `JOIN ... ON` in the SQL sense (KQL has `join`, but with different syntax — see below). This surface-level resemblance to SQL, combined with real but different semantics, is precisely why naive LLM generation tends to produce hybrid SQL/KQL/SPL syntax — see [Common KQL Mistakes](#common-kql-mistakes-this-project-measures).

---

## Operators Used by This Project's Templates

These are the operators that appear in the [KQL Generator's Jinja2 templates](architecture.md#kql-generator-template-compiler) — i.e., the complete operator surface this project's generated queries can use, by construction.

### `where` — row filtering

```kql
| where EventResult == "Failure"
| where TargetUsername contains "admin"
| where SrcIpAddr in ("1.2.3.4", "5.6.7.8")
```

Maps directly from `SecurityIR.filters` — each `Filter.field`, `Filter.operator`, `Filter.value` becomes one `where` clause. Multiple filters chain as sequential `where` lines (implicit AND), matching how `SecurityIR.filters` is a flat list rather than a nested boolean expression tree — this is a **deliberate scope limit**: the current IR cannot express OR-combined filters or nested boolean groups, which is a known restriction (see [Limitations](../README.md#limitations)).

### `summarize ... by` — aggregation

```kql
| summarize FailCount = count() by TargetUsername
| summarize DistinctUsers = dcount(TargetUsername) by SrcIpAddr, bin(TimeGenerated, 5m)
```

Maps from `SecurityIR.aggregation` + `SecurityIR.group_by` + `SecurityIR.time_window`. Note `dcount()` is KQL's distinct-count function — the IR's `AggregationFunction.DISTINCT_COUNT` enum value maps to `dcount`, not `distinct_count`, in the actual generated KQL; the Jinja2 template's `aggregation_function_map` filter handles this translation. This is exactly the kind of small-but-fatal mapping detail that, if hand-coded wrong, would not show up as a [Schema Validator](architecture.md#schema-validator-specification) failure (the IR is well-formed) but *would* show up as a [KQL Syntax Validator](architecture.md#kql-syntax-validator-specification) failure if the template emitted `distinct_count()` instead of `dcount()` — worth keeping in mind when debugging template-bug-attributed failures.

### `bin()` — time bucketing

```kql
| summarize count() by bin(TimeGenerated, 5m)
```

`bin()` is how KQL expresses a time window inside an aggregation — it is **not** a separate clause, it's an argument inside `summarize ... by`. This is a common source of confusion when generating from a mental model borrowed from SQL (`GROUP BY time_bucket(...)` doesn't have a direct SQL equivalent at all, which is part of why "missing temporal logic" is a distinct, common failure mode — see below).

Duration literals: `5m` (5 minutes), `1h` (1 hour), `1d` (1 day) — no quotes, no `INTERVAL` keyword. The IR's `time_window` field stores ISO 8601 duration strings (`"PT5M"`) specifically because that's an unambiguous, parseable standard; the `kql_duration` Jinja2 filter converts `PT5M` → `5m` at generation time.

### `project` — column selection

```kql
| project SrcIpAddr, DistinctUsers, TimeGenerated
```

Maps from `SecurityIR.output_fields`. KQL also has `project-away` (exclude specific columns) and `project-rename`, neither of which the current IR/template supports — another deliberate scope limit.

### `join` — combining tables

```kql
LeftTable
| join kind=inner (RightTable) on JoinKey
```

**Not currently in the IR schema** (see [The Security IR — Full Schema](architecture.md#the-security-ir-full-schema), which has no `join` field). Detection rules requiring a join are tagged `complex` in the [dataset's complexity tiering](dataset.md#complexity-tagging-criteria) and are included in the evaluation set specifically so System B's failure on join-requiring cases is *measured*, not hidden — the current IR scope is expected to underperform on these cases by design, which is itself useful signal for [H4](evaluation.md#what-would-falsify-each-hypothesis) and for prioritizing the IR schema's next iteration (see [Future Extensions](../README.md#future-extensions)).

---

## Common KQL Mistakes This Project Measures

These map directly onto the [failure taxonomy](../README.md#the-problem) in the README, with the specific KQL mechanics behind each:

| Mistake | What It Looks Like | Why It Happens |
|---|---|---|
| **SQL-style `GROUP BY`** | `\| summarize count() GROUP BY TargetUsername` | KQL uses `by` after the aggregation function, not a separate `GROUP BY` clause — models trained heavily on SQL default to the more common pattern |
| **Standalone `CONTAINS`** | `\| CONTAINS "admin"` instead of `\| where TargetUsername contains "admin"` | `contains` is a string operator used *within* a `where` clause, not a clause itself |
| **Missing `bin()` in time-windowed aggregation** | `\| summarize count() by TargetUsername` with no time bucketing at all, when the description implies "within 10 minutes" | The temporal constraint exists only in the NL description's phrasing, not as an obvious separate clause — easy to drop entirely if not explicitly modeled, which is exactly why the IR schema makes `time_window` **required** whenever `aggregation` is set (see [the IR schema's field-level notes](architecture.md#field-level-notes)) |
| **SPL-style pipe syntax leakage** | `\| stats count by TargetUsername` (Splunk SPL's `stats`, not KQL's `summarize`) | Cross-platform syntax bleed — most likely when a model has been exposed to multiple SIEM query languages and the surface-level "pipe + aggregation" pattern is similar enough to blur together |
| **Field name plausible-but-wrong** | `SourceIP` instead of `SrcIpAddr`; `Username` instead of `TargetUsername` | The hallucinated name is a reasonable guess at what the field *should* be called, generically — but ASIM has its own specific naming convention (see below) that doesn't always match intuition |

---

## What ASIM Is, in Practical Terms

ASIM (Advanced Security Information Model) solves a specific problem: raw log data arrives from dozens of different products (Azure AD, Windows Security Events, Syslog-based firewalls, etc.), each with its own field names for conceptually the same thing — a source IP address might be `SourceIP`, `src_ip`, `c-ip`, or `ClientIP` depending on the connector. ASIM defines a **normalized schema** per event category, and **parsers** (KQL functions, found in the `ASIM/ASimParsers/` folder of the source repo) that map each raw connector's fields into the normalized schema.

The practical consequence for this project: writing detection logic against `imAuthentication` (the ASIM authentication view) instead of, say, raw `SigninLogs` means the same KQL query works regardless of which underlying connector produced the data — which is also exactly why ASIM is a good fit as this project's single schema standard (see the [README's scope decision](../README.md#overview)): it's the schema layer practitioners are actually encouraged to write against, not a raw, connector-specific schema.

```
Raw connector data (SigninLogs, OktaSSO, etc.)
        │
        ▼
   ASIM Parser  (maps raw fields → normalized fields)
        │
        ▼
   imAuthentication  (normalized, queryable view)
```

---

## ASIM Schemas in Scope

This project's `ASIMEventType` enum (see [the IR schema](architecture.md#the-security-ir-full-schema)) currently covers:

| ASIM Schema | Normalized View Name | Typical Use Case |
|---|---|---|
| `AuthenticationEvent` | `imAuthentication` | Login attempts, success/failure, MFA events |
| `NetworkSessionEvent` | `imNetworkSession` | Firewall/network flow logs, connection attempts |
| `ProcessEvent` | `imProcessCreate` | Process execution, command-line activity |
| `FileEvent` | `imFileEvent` | File creation, modification, deletion |
| `DnsEvent` | `imDns` | DNS query/response activity |
| `WebSessionEvent` | `imWebSession` | HTTP/web proxy traffic |
| `RegistryEvent` | `imRegistry` | Windows registry modifications |

This list intentionally mirrors the [`Detections/ASim*` folders](dataset.md#repository-structure-full-detail) prioritized during dataset construction — the IR's schema coverage and the dataset's source coverage are kept in lockstep so every `ASIMEventType` the IR can express has corresponding ground-truth examples in the dataset, and vice versa.

---

## ASIM Field Naming Conventions

A few naming patterns worth knowing, since they're a frequent source of the "plausible-but-wrong" field hallucination described above:

- **`Src` / `Dst` prefixes**, not `Source` / `Destination`: `SrcIpAddr`, `DstIpAddr`, `SrcUserId`.
- **`TargetUsername`** (not `Username` or `User`) is the standard field for the account being acted upon in authentication events.
- **`EventResult`** is a normalized success/failure indicator (`"Success"` / `"Failure"`), distinct from product-specific result codes — a common error is filtering on a raw underlying result code (e.g. `ResultType != "0"`, which is Azure AD-specific) instead of the normalized `EventResult` field, which defeats the purpose of using the ASIM-normalized view at all.
- **`TimeGenerated`** is the standard timestamp field across all ASIM views, used inside `bin()` for time bucketing.
- Field names are **PascalCase**, consistently — `SrcIpAddr`, not `src_ip_addr` or `srcIpAddr`.

These conventions are exactly what the [ASIM field reference extracted in `dataset.md`](dataset.md#schema-reference-extraction) encodes programmatically — this section exists so a human reader (you, or anyone reviewing this project) has the same mental model the [Schema Validator](architecture.md#schema-validator-specification) is mechanically enforcing.

---

## Why KQL Is Distinct from SQL and SPL (and Why That Matters Here)

| | SQL | Splunk SPL | KQL |
|---|---|---|---|
| Aggregation | `SELECT COUNT(*) ... GROUP BY x` | `\| stats count by x` | `\| summarize count() by x` |
| Filtering | `WHERE x = 'y'` | `search x="y"` or `\| where x="y"` | `\| where x == "y"` |
| Time bucketing | `DATE_TRUNC` / vendor-specific | `bin _time span=5m` | `bin(TimeGenerated, 5m)` |
| String equality | `=` | `=` | `==` |
| Structure | Declarative, clause order fixed (`SELECT...FROM...WHERE...GROUP BY`) | Pipe-based, search-first | Pipe-based, source-table-first |

The pipe-based structure superficially aligns KQL with SPL more than SQL, but the specific keywords and operator semantics differ from both — which is precisely the gap that produces hybrid, invalid output when a model pattern-matches on "pipe-based query language" without tracking which specific dialect it's in. This table is the concrete version of the claim made in the [README's Background section](../README.md#why-an-intermediate-representation) and in [`architecture.md`'s design philosophy](architecture.md#design-philosophy): KQL's syntax surface is genuinely confusable with adjacent query languages, which is exactly the failure mode the [Schema Validator and KQL Syntax Validator](architecture.md#system-b-ir-mediated-pipeline) are built to catch before it reaches a SOC analyst.
