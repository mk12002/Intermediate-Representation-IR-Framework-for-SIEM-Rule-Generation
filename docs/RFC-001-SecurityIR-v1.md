# RFC-001: Security Intermediate Representation (SecurityIR) v1.0

**Status:** Draft  
**Version:** 1.0  
**Authors:** IR Framework Architecture Team  

---

## 1. Abstract

This document defines **SecurityIR**, a vendor-agnostic Intermediate Representation (IR) designed to bridge the semantic gap between natural language cyber threat descriptions and executable SIEM detection logic (e.g., Sigma, KQL, SPL). The primary goal of this specification is to provide a deterministic, schema-validated contract that isolates language-model reasoning from syntactic query generation.

---

## 2. Motivation

In AI-driven detection engineering, Large Language Models (LLMs) struggle to simultaneously reason about cybersecurity semantics and write syntactically flawless query logic. By targeting this formal IR, the LLM only needs to produce standard JSON. The translation to executable queries is handled deterministically by programmatic generators.

---

## 3. The Contract & Invariants

SecurityIR operates under a strict set of invariants to guarantee deterministic generation:
1. **No Vendor Specifics:** The IR must never contain vendor-specific query keywords (e.g., `distinct_count` for Kusto, `stats count` for Splunk).
2. **Schema Compliance:** The IR must strictly adhere to the Pydantic schema defined below. Extraneous fields will trigger validation failures.
3. **Temporal Completeness:** Any `AggregationConfig` or correlation logic **must** be accompanied by a `TimeframeConfig`.
4. **Field Abstraction:** Field names must map to the Open Cybersecurity Schema Framework (OCSF) standard or a declared entity map, rather than platform-specific column names.

---

## 4. Specification & Enums

### 4.1 Base Enums
- **Severity Enum:** `informational` | `low` | `medium` | `high` | `critical`
- **Filter Operator Enum:** `equals` | `not_equals` | `contains` | `starts_with` | `in` | `not_in` | `in_cidr` | `not_in_cidr` | `regex` | `greater_than` | `less_than` | `exists`
- **Threshold Operator Enum:** `greater_than` | `less_than` | `equals` | `gte` | `lte`
- **Aggregation Function Enum:** `count` | `sum` | `distinct_count` | `min` | `max` | `avg`
- **Timeframe Unit Enum:** `seconds` | `minutes` | `hours` | `days`
- **Timeframe Type Enum:** `sliding_window` | `fixed_window` | `session_window`

### 4.2 Core Object Types (Field Types)

#### `FilterCondition`
Defines a specific constraint to filter events.
- `field` (string): The OCSF or generic field name.
- `operator` (Filter Operator Enum): The comparison logic.
- `value` (string | int | float | list): The value to compare against.
- `confidence` (float): 0.0 to 1.0. 
- `note` (string, optional): Context for the filter.

#### `AggregationConfig`
Defines grouping and mathematical thresholds.
- `function` (Aggregation Function Enum): The aggregation type.
- `target_field` (string, optional): Field to aggregate (required for sum/avg).
- `group_by` (list[string]): Fields to group the aggregation by (e.g., `user`).
- `threshold` (ThresholdConfig): The threshold condition that triggers the rule.

#### `TimeframeConfig`
Defines the temporal window for aggregations or sequences.
- `duration` (integer): The numerical span.
- `unit` (Timeframe Unit Enum): The unit of time.
- `type` (Timeframe Type Enum): The windowing mechanism.

---

## 5. SecurityIR Root Schema

The root JSON object must conform to this exact structure:

```json
{
  "ir_version": "1.0",
  "rule_id": "<uuid-string>",
  "created_at": "<iso-8601-datetime>",
  "source_document": "<optional-reference-string>",
  "confidence_overall": 0.0 - 1.0,
  "repair_count": "<integer>",
  
  "metadata": {
    "rule_name": "<string>",
    "description": "<string>",
    "severity": "<Severity Enum>",
    "tags": ["<string>"],
    "author": "<string>"
  },
  
  "detection_logic": {
    "event_type": "<string>",
    "filters": [
      {
        "field": "<string>",
        "operator": "<Filter Operator Enum>",
        "value": "<mixed>"
      }
    ],
    "aggregation": {
      "function": "<Aggregation Function Enum>",
      "group_by": ["<string>"],
      "threshold": {
        "operator": "<Threshold Operator Enum>",
        "value": "<number>"
      }
    },
    "timeframe": {
      "duration": "<integer>",
      "unit": "<Timeframe Unit Enum>",
      "type": "<Timeframe Type Enum>"
    }
  },
  
  "entity_mapping": {
    "entities": {
      "user": "<string>",
      "ip": "<string>"
    }
  },
  
  "mitre_mapping": [
    {
      "tactic": "<string>",
      "tactic_id": "TA0000",
      "technique": "<string>",
      "technique_id": "T0000",
      "confidence": 0.0 - 1.0,
      "rationale": "<string>"
    }
  ],
  
  "output_config": {
    "target_platforms": ["sigma", "kql", "spl"]
  }
}
```

---

## 6. Compatibility Guarantees

SecurityIR v1.0 guarantees:
1. **Forward Compatibility:** Any fields added in future 1.x versions will be strictly optional and will not break existing v1.0 generators.
2. **Lossless Generation:** The properties defined in the IR are sufficient to generate functionally equivalent rules across Sigma, Microsoft Sentinel KQL, and Splunk SPL without manual intervention or data loss.
3. **Pydantic Serialization:** The schema maps 1:1 with Python Pydantic V2 models, allowing robust `model_validate_json()` operations.

---

## 7. JSON Examples

### 7.1 Example: Impossible Travel
```json
{
  "ir_version": "1.0",
  "rule_id": "8f3a9e22-1b4d...",
  "created_at": "2026-05-19T10:00:00Z",
  "metadata": {
    "rule_name": "Impossible Travel Detected",
    "description": "Detects a user logging in from two distinct countries within 2 hours.",
    "severity": "high",
    "tags": ["authentication", "impossible_travel"]
  },
  "detection_logic": {
    "event_type": "authentication_success",
    "filters": [
      {
        "field": "status",
        "operator": "equals",
        "value": "success"
      }
    ],
    "aggregation": {
      "function": "distinct_count",
      "target_field": "src_country",
      "group_by": ["user"],
      "threshold": {
        "operator": "greater_than",
        "value": 1
      }
    },
    "timeframe": {
      "duration": 2,
      "unit": "hours",
      "type": "sliding_window"
    }
  },
  "output_config": {
    "target_platforms": ["sigma", "kql"]
  }
}
```
