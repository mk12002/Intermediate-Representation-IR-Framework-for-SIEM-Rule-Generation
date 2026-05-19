# Natural Language to Executable Detection Logic
## A Multi-Agent Intermediate Representation Framework for Autonomous SIEM Rule Generation and Validation
### Complete Project Planning, Architecture & Implementation Reference

---

> **Document Version:** 1.0  
> **Last Updated:** May 2026  
> **Status:** Active Development  
> **Classification:** Research Prototype — Academic + Portfolio

---

## Table of Contents

  - [A Multi-Agent Intermediate Representation Framework for Autonomous SIEM Rule Generation and Validation](#a-multi-agent-intermediate-representation-framework-for-autonomous-siem-rule-generation-and-validation)
- [PART I — FOUNDATION & CONTEXT](#part-i-foundation-context)
  - [1. Executive Summary](#1-executive-summary)
  - [2. Introduction & Motivation](#2-introduction-motivation)
  - [3. Real-World Cybersecurity Background](#3-real-world-cybersecurity-background)
  - [4. Understanding SIEM Systems](#4-understanding-siem-systems)
  - [5. Detection Engineering Fundamentals](#5-detection-engineering-fundamentals)
  - [6. SOC Architecture & Operational Workflows](#6-soc-architecture-operational-workflows)
- [PART II — PROBLEM STATEMENT & RESEARCH GAP](#part-ii-problem-statement-research-gap)
  - [7. Problem Statement](#7-problem-statement)
  - [8. Why Current LLM Approaches Fail](#8-why-current-llm-approaches-fail)
  - [9. Literature Review & Related Work](#9-literature-review-related-work)
  - [10. Core Research Objectives](#10-core-research-objectives)
- [PART III — SYSTEM ARCHITECTURE](#part-iii-system-architecture)
  - [11. High-Level System Architecture](#11-high-level-system-architecture)
  - [12. Multi-Agent Architecture Design](#12-multi-agent-architecture-design)
  - [13. LangGraph Workflow Design](#13-langgraph-workflow-design)
- [PART IV — INTERMEDIATE REPRESENTATION (IR)](#part-iv-intermediate-representation-ir)
  - [14. IR Theory & Compiler Analogy](#14-ir-theory-compiler-analogy)
  - [15. Security IR Schema Design](#15-security-ir-schema-design)
  - [16. IR Design Rationale](#16-ir-design-rationale)
  - [17. Worked Examples — NL to IR Transformation](#17-worked-examples-nl-to-ir-transformation)
- [PART V — SCHEMA NORMALIZATION](#part-v-schema-normalization)
  - [18. Schema Normalization Theory](#18-schema-normalization-theory)
  - [19. OCSF Deep Dive](#19-ocsf-deep-dive)
  - [20. ASIM Deep Dive](#20-asim-deep-dive)
  - [21. Cross-Platform Field Mapping Tables](#21-cross-platform-field-mapping-tables)
  - [22. Custom Vendor Mapper Design](#22-custom-vendor-mapper-design)
- [PART VI — RULE GENERATION PIPELINE](#part-vi-rule-generation-pipeline)
  - [23. Rule Generation Architecture](#23-rule-generation-architecture)
  - [24. Sigma Rules Deep Dive](#24-sigma-rules-deep-dive)
  - [25. KQL Deep Dive](#25-kql-deep-dive)
  - [26. Splunk SPL Deep Dive](#26-splunk-spl-deep-dive)
  - [27. Generator Implementation Strategy](#27-generator-implementation-strategy)
- [PART VII — VALIDATION & REPAIR PIPELINE](#part-vii-validation-repair-pipeline)
  - [28. Validation Pipeline Architecture](#28-validation-pipeline-architecture)
  - [29. Stage 1 — Syntax Validation](#29-stage-1-syntax-validation)
  - [30. Stage 2 — Semantic Validation](#30-stage-2-semantic-validation)
  - [31. Stage 3 — Telemetry Execution Validation](#31-stage-3-telemetry-execution-validation)
  - [32. Closed-Loop Repair System](#32-closed-loop-repair-system)
  - [33. False Positive Reduction Strategies](#33-false-positive-reduction-strategies)
- [PART VIII — PROMPT ENGINEERING & HALLUCINATION CONTROL](#part-viii-prompt-engineering-hallucination-control)
  - [34. Prompt Engineering Strategy](#34-prompt-engineering-strategy)
  - [35. Hallucination Reduction Techniques](#35-hallucination-reduction-techniques)
  - [36. Security NLP Concepts](#36-security-nlp-concepts)
- [PART IX — DATASETS & EVALUATION](#part-ix-datasets-evaluation)
  - [37. Datasets](#37-datasets)
  - [38. Evaluation Metrics](#38-evaluation-metrics)
  - [39. Experiment Design](#39-experiment-design)
  - [40. Benchmarking Methodology](#40-benchmarking-methodology)
- [PART X — IMPLEMENTATION](#part-x-implementation)
  - [41. Technology Stack](#41-technology-stack)
  - [42. Folder Structure & Software Architecture](#42-folder-structure-software-architecture)
  - [43. Detailed Module Breakdown](#43-detailed-module-breakdown)
  - [44. API Design](#44-api-design)
  - [45. Database & Storage Design](#45-database-storage-design)
  - [46. Configuration Management](#46-configuration-management)
- [PART XI — THREAT INTELLIGENCE & MITRE INTEGRATION](#part-xi-threat-intelligence-mitre-integration)
  - [47. Threat Intelligence Integration](#47-threat-intelligence-integration)
  - [48. MITRE ATT&CK Mapping Pipeline](#48-mitre-attck-mapping-pipeline)
  - [49. Temporal Correlation Logic](#49-temporal-correlation-logic)
  - [50. Aggregation & Threshold Logic](#50-aggregation-threshold-logic)
- [PART XII — DEPLOYMENT & OPERATIONS](#part-xii-deployment-operations)
  - [51. Containerization](#51-containerization)
  - [52. Testing Strategy](#52-testing-strategy)
  - [53. Observability & Monitoring](#53-observability-monitoring)
  - [54. Security & Compliance](#54-security-compliance)
- [PART XIII — RESEARCH ROADMAP](#part-xiii-research-roadmap)
  - [55. Research Contributions](#55-research-contributions)
  - [56. Related Work](#56-related-work)
  - [57. Research Timeline](#57-research-timeline)
- [PART XIV — FUTURE WORK & EXTENSIBILITY](#part-xiv-future-work-extensibility)
  - [58. Short-Term Extensions (3–6 Months)](#58-short-term-extensions-36-months)
  - [59. Medium-Term Research Directions (6–18 Months)](#59-medium-term-research-directions-618-months)
  - [60. Long-Term Vision (18+ Months)](#60-long-term-vision-18-months)
  - [61. Known Limitations & Mitigation Plans](#61-known-limitations-mitigation-plans)
  - [62. Summary of Key Design Decisions](#62-summary-of-key-design-decisions)
- [PART XV — SUPPLEMENTARY SECTIONS](#part-xv-supplementary-sections)
  - [63. Research Paper Structure](#63-research-paper-structure)
  - [64. Minimum Viable Prototype (MVP)](#64-minimum-viable-prototype-mvp)
  - [65. Advanced Features (Post-MVP)](#65-advanced-features-post-mvp)
  - [66. Risks and Challenges](#66-risks-and-challenges)
  - [67. Scalability Considerations](#67-scalability-considerations)
  - [68. Learning Resources](#68-learning-resources)
  - [69. Final Recommendations](#69-final-recommendations)
- [CONCLUSION](#conclusion)



# PART I — FOUNDATION & CONTEXT

---

## 1. Executive Summary

This project builds an AI-assisted detection engineering framework that converts unstructured natural language cybersecurity documents — Standard Operating Procedures (SOPs), Cyber Threat Intelligence (CTI) reports, and analyst notes — into validated, deployment-ready SIEM detection rules across multiple platforms (Microsoft Sentinel KQL, Sigma YAML, Splunk SPL).

The core innovation is a **schema-aware Intermediate Representation (IR)** layer positioned between natural language understanding and platform-specific code generation. Drawing from compiler theory (source code → IR → machine code), the Security IR captures detection semantics — filters, thresholds, aggregations, temporal correlations, entity mappings, and MITRE ATT&CK references — in a vendor-neutral JSON structure. This IR is then deterministically compiled into executable detection rules for any supported SIEM platform.

A **multi-agent architecture** orchestrated via LangGraph decomposes the complex reasoning task into specialized, modular agents: threat intelligence extraction, entity recognition, metadata generation, MITRE mapping, IR construction, validation, and autonomous repair. This separation of concerns eliminates the failure mode of single-prompt LLM generation, where one model must simultaneously reason about cybersecurity semantics, query syntax, schema mappings, and temporal logic.

A **closed-loop validation and repair pipeline** executes generated rules against benchmark telemetry datasets (SigmaHQ, HDFS logs, synthetic enterprise logs), measures precision/recall/false-positive rates, and autonomously repairs failing rules through iterative refinement — all before human review.

### What This Project IS

| Attribute | Description |
|---|---|
| AI-assisted detection rule compiler | Converts NL → IR → executable SIEM rules |
| Research prototype | Demonstrates novel IR-based approach with empirical evaluation |
| Cybersecurity AI systems framework | Multi-agent pipeline with validation and repair |
| Cross-platform rule generator | Produces Sigma, KQL, and SPL from a single IR |

### What This Project IS NOT

| Attribute | Description |
|---|---|
| Not a SIEM platform | Does not ingest, store, or query logs at scale |
| Not a chatbot | Not a conversational assistant for SOC analysts |
| Not an autonomous SOC | Does not perform incident response or remediation |
| Not a threat intelligence platform | Does not aggregate or distribute threat feeds |

### Key Differentiators

1. **IR-based abstraction** eliminates hallucinated syntax by separating semantic reasoning from code generation
2. **Multi-agent decomposition** distributes cognitive load across specialized agents
3. **Schema-aware generation** via OCSF/ASIM normalization ensures cross-platform field compatibility
4. **Closed-loop validation** with telemetry execution catches errors before deployment
5. **Autonomous repair** iteratively fixes syntax, logic, and false-positive issues

---

## 2. Introduction & Motivation

### 2.1 The Detection Engineering Crisis

Modern Security Operations Centers (SOCs) are drowning in data. Enterprise environments generate millions of log events per day across endpoints, cloud infrastructure, network devices, identity providers, and SaaS applications. The only way SOC analysts can find malicious activity in this ocean of telemetry is through **detection rules** — structured queries that run continuously against ingested logs and trigger alerts when suspicious patterns are observed.

The problem: **writing these rules is extraordinarily difficult.**

A single detection rule requires the author to simultaneously understand:
- The **attacker behavior** being detected (e.g., credential stuffing, lateral movement, data staging)
- The **log sources** that would contain evidence of that behavior (e.g., Windows Security Event Log, Azure AD Sign-In Logs, CloudTrail)
- The **exact field names** used by the target SIEM platform (e.g., `AccountName` in Sentinel vs. `user` in Splunk vs. `userIdentity.arn` in AWS)
- The **query syntax** of the target language (KQL, SPL, Sigma YAML, YARA-L)
- The **temporal and statistical logic** needed to reduce false positives (time windows, count thresholds, baseline deviations)
- The **MITRE ATT&CK mapping** for the behavior to ensure coverage tracking

This multidimensional complexity means that even experienced detection engineers spend **2–8 hours per rule**, and the resulting rules are often platform-specific, brittle, and difficult to maintain.

### 2.2 The Promise and Failure of LLM-Based Approaches

Large Language Models (LLMs) like GPT-4, Claude, and Gemini have demonstrated impressive code generation capabilities. Naturally, the cybersecurity community has attempted to leverage these models for detection rule generation — prompting them with threat descriptions and asking for KQL or Sigma output directly.

**This approach fails systematically.** When a single LLM prompt must handle all dimensions simultaneously, the model faces an impossible cognitive load:

```
┌─────────────────────────────────────────────────┐
│           SINGLE-PROMPT FAILURE MODE            │
│                                                 │
│  Natural Language Description                   │
│         ↓                                       │
│  [ Single LLM Prompt ]                          │
│    Must simultaneously:                         │
│    ✗ Parse threat semantics                     │
│    ✗ Map to MITRE ATT&CK                       │
│    ✗ Resolve platform-specific field names      │
│    ✗ Generate valid query syntax                │
│    ✗ Encode temporal/aggregation logic          │
│    ✗ Minimize false positives                   │
│         ↓                                       │
│  Hallucinated / Invalid Rule                    │
│    • Wrong field names (e.g., "SourceIP"        │
│      instead of "SrcIpAddr")                    │
│    • Invalid YAML structure                     │
│    • Missing time windows                       │
│    • Incorrect ATT&CK technique IDs             │
│    • Overly broad logic → alert storms          │
└─────────────────────────────────────────────────┘
```

### 2.3 The Compiler Analogy — Why an IR Solves This

The solution comes from a 60-year-old idea in computer science: **intermediate representations**.

No modern compiler translates Python directly to x86 machine code in one step. Instead:

```
Python Source Code  →  Abstract Syntax Tree  →  Bytecode (IR)  →  Machine Code
```

The IR decouples **what the program means** (semantics) from **how it executes on hardware** (platform-specific implementation). This separation enables:
- Better optimization at the IR level
- Portability across target architectures (x86, ARM, RISC-V)
- Modular compiler design (frontend and backend can evolve independently)

This project applies the same principle to detection engineering:

```
Natural Language SOP  →  Multi-Agent Parsing  →  Security IR (JSON)  →  KQL / Sigma / SPL
```

The Security IR captures **what to detect** (attack behavior, entities, thresholds, time windows) without committing to **how to express it** in any specific query language. The IR becomes the single source of truth from which any number of platform-specific rules can be deterministically generated.

### 2.4 Project Scope and Boundaries

| In Scope | Out of Scope |
|---|---|
| NL → IR → Rule generation pipeline | Real-time log ingestion or SIEM deployment |
| Multi-agent orchestration via LangGraph | Training custom LLMs from scratch |
| Sigma, KQL, SPL output formats | YARA, Snort, Suricata rule formats (future work) |
| OCSF and ASIM schema normalization | Proprietary vendor schema reverse-engineering |
| Telemetry-grounded validation | Production SOC integration |
| Autonomous repair with max-retry bounds | Fully unsupervised operation without human review |
| Benchmark evaluation (SigmaHQ, SigmaHQ, HDFS) | Real-world SOC deployment metrics |

---

## 3. Real-World Cybersecurity Background

### 3.1 What Happens Inside a SOC

A Security Operations Center (SOC) is the nerve center of an organization's cybersecurity defense. It operates 24/7 with tiered analyst teams monitoring, detecting, investigating, and responding to security incidents. Understanding SOC operations is essential because this project's output — detection rules — is the primary tool SOC analysts rely on.

#### SOC Tier Structure

| Tier | Role | Responsibilities |
|---|---|---|
| **Tier 1** | Alert Triage Analyst | Monitors dashboards, triages incoming alerts, escalates true positives |
| **Tier 2** | Incident Responder | Investigates escalated alerts, performs forensic analysis, contains threats |
| **Tier 3** | Threat Hunter / Detection Engineer | Proactively hunts for threats, writes and tunes detection rules |
| **SOC Manager** | Operations Lead | Oversees SOC operations, manages staffing, reports to CISO |

**Detection engineers (Tier 3)** are the primary users of this project's output. They are the ones who currently spend hours manually crafting detection rules — the exact task this framework automates.

### 3.2 Types of Security Telemetry

SOCs ingest telemetry from diverse sources. Each source type provides different visibility into attacker behavior:

| Telemetry Source | What It Captures | Example Log Fields | Volume |
|---|---|---|---|
| **Windows Event Logs** | Authentication, process creation, service installation | EventID, AccountName, ProcessName, LogonType | High |
| **Azure AD / Entra ID** | Cloud identity events, sign-ins, MFA, conditional access | UserPrincipalName, IPAddress, ResultType, AppDisplayName | Medium |
| **AWS CloudTrail** | API calls across AWS services | userIdentity, eventName, sourceIPAddress, requestParameters | High |
| **Firewall Logs** | Network connections allowed/denied | src_ip, dst_ip, dst_port, action, protocol | Very High |
| **DNS Logs** | Domain resolution requests | QueryName, QueryType, ResponseCode, ClientIP | Very High |
| **Endpoint Detection (EDR)** | Process trees, file modifications, registry changes | ProcessCommandLine, ParentProcessName, FileHash | High |
| **Email Gateway Logs** | Inbound/outbound email metadata, attachment hashes | SenderAddress, Subject, AttachmentName, ThreatType | Medium |
| **Proxy / Web Logs** | HTTP requests, URL categories, user-agent strings | URL, UserAgent, BytesTransferred, ResponseCode | Very High |

### 3.3 What SOC Analysts Are Trying to Detect

The threats SOC analysts look for map directly to the MITRE ATT&CK framework's tactical categories:

| MITRE Tactic | Example Behavior | Detection Approach |
|---|---|---|
| **Initial Access (TA0001)** | Phishing email with malicious attachment | Email gateway + endpoint correlation |
| **Execution (TA0002)** | PowerShell downloading and executing payload | Process creation logs with command-line analysis |
| **Persistence (TA0003)** | Scheduled task created for backdoor | Windows Event ID 4698 monitoring |
| **Privilege Escalation (TA0004)** | Token impersonation or UAC bypass | Process token and integrity level monitoring |
| **Defense Evasion (TA0005)** | Disabling Windows Defender | Registry modification + service stop events |
| **Credential Access (TA0006)** | Brute force login attempts | Authentication failure count thresholds |
| **Discovery (TA0007)** | Network scanning or AD enumeration | Unusual volume of LDAP/SMB queries |
| **Lateral Movement (TA0008)** | Remote service creation via PsExec | Service installation on remote hosts |
| **Collection (TA0009)** | Staging files in temp directories before exfil | File creation patterns in known staging paths |
| **Exfiltration (TA0010)** | Large data transfer to external IP | Outbound traffic volume anomaly detection |
| **Command & Control (TA0011)** | Beaconing to C2 server | Periodic DNS/HTTP request pattern analysis |

### 3.4 The Detection Rule Lifecycle

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  1. Threat   │───▸│  2. Rule     │───▸│  3. Testing  │───▸│  4. Deploy   │───▸│  5. Tuning   │
│  Research    │    │  Authoring   │    │  & Validation│    │  to SIEM     │    │  & Maintenance│
│              │    │              │    │              │    │              │    │              │
│ • CTI feeds  │    │ • Write KQL/ │    │ • Run against│    │ • Push to    │    │ • Monitor FP │
│ • ATT&CK    │    │   Sigma/SPL  │    │   test logs  │    │   production │    │   rates      │
│ • Threat     │    │ • Map fields │    │ • Check FP   │    │ • Enable     │    │ • Adjust     │
│   reports    │    │ • Set        │    │   rates      │    │   alerting   │    │   thresholds │
│ • Vendor     │    │   thresholds │    │ • Peer review│    │ • Configure  │    │ • Update for │
│   advisories │    │ • Add MITRE  │    │              │    │   automation │    │   new TTPs   │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
     │                    │                   │                                        │
     │          ┌─────────┘                   │                                        │
     │          ▼                             │                                        │
     │   THIS PROJECT AUTOMATES              │                                        │
     │   STEPS 1 THROUGH 3                   │                                        │
     └────────────────────────────────────────┘────────────────────────────────────────┘
```

**This project targets steps 1–3**: automating the conversion of threat intelligence into validated detection rules. Steps 4–5 (deployment and tuning) remain human-driven in the current scope.

---

## 4. Understanding SIEM Systems

### 4.1 What Is a SIEM?

A **Security Information and Event Management (SIEM)** system is the central nervous system of enterprise security monitoring. It collects, normalizes, correlates, and analyzes log data from across an organization's IT infrastructure to detect threats, support investigations, and satisfy compliance requirements.

### 4.2 Major SIEM Platforms

| Platform | Vendor | Query Language | Cloud/On-Prem | Market Position |
|---|---|---|---|---|
| **Microsoft Sentinel** | Microsoft | KQL (Kusto Query Language) | Cloud-native (Azure) | Leader in cloud-native SIEM |
| **Splunk Enterprise Security** | Cisco/Splunk | SPL (Search Processing Language) | Hybrid | Largest market share overall |
| **Elastic Security** | Elastic | EQL, ES|QL, Lucene | Hybrid | Strong in open-source community |
| **IBM QRadar** | IBM | AQL (Ariel Query Language) | Hybrid | Legacy enterprise stronghold |
| **Google Chronicle/SecOps** | Google | YARA-L 2.0 | Cloud-native | Growing with Google Cloud |
| **CrowdStrike Falcon LogScale** | CrowdStrike | LQL | Cloud-native | Emerging with EDR integration |

### 4.3 SIEM Architecture and Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SIEM ARCHITECTURE                                │
│                                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │  Windows     │  │  Cloud       │  │  Network     │  │  Endpoint    │       │
│  │  Event Logs  │  │  Logs        │  │  Devices     │  │  Agents      │       │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘       │
│         │                │                │                │               │
│         ▼                ▼                ▼                ▼               │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │                    LOG COLLECTION LAYER                         │       │
│  │     Syslog, CEF, JSON, Windows Event Forwarding, APIs          │       │
│  └────────────────────────────┬────────────────────────────────────┘       │
│                               ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │                    NORMALIZATION LAYER                          │       │
│  │     Field mapping, timestamp normalization, enrichment          │       │
│  └────────────────────────────┬────────────────────────────────────┘       │
│                               ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │                    STORAGE / INDEX LAYER                        │       │
│  │     Hot storage (recent) ←→ Cold storage (archived)            │       │
│  └────────────────────────────┬────────────────────────────────────┘       │
│                               ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │                 DETECTION / ANALYTICS ENGINE                    │       │
│  │     ★ DETECTION RULES EXECUTE HERE ★                           │       │
│  │     Scheduled queries, real-time correlation, ML models         │       │
│  └────────────────────────────┬────────────────────────────────────┘       │
│                               ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │                    ALERT / INCIDENT LAYER                       │       │
│  │     Alert generation, incident grouping, severity scoring       │       │
│  └────────────────────────────┬────────────────────────────────────┘       │
│                               ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │                    RESPONSE / SOAR LAYER                        │       │
│  │     Automated playbooks, analyst investigation, remediation     │       │
│  └─────────────────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.4 How Detection Rules Execute in a SIEM

Detection rules are the **core value driver** of any SIEM deployment. Without rules, a SIEM is just an expensive log warehouse.

**Execution Model — Scheduled Query Rules (most common):**

1. **Schedule**: The rule runs on a fixed interval (e.g., every 5 minutes)
2. **Lookback**: Each execution queries a defined time window of logs (e.g., last 15 minutes)
3. **Query**: The detection logic (KQL/SPL/Sigma) filters and aggregates log data
4. **Threshold**: If the query returns results meeting a threshold condition, an alert fires
5. **Entity Mapping**: Alert results are enriched with entity information (users, IPs, hosts)
6. **Incident Grouping**: Related alerts are grouped into incidents for investigation

### 4.5 The Query Language Problem

Each SIEM platform uses a **completely different query language** with different syntax, operators, and field naming conventions. The same detection logic — "detect more than 5 failed logins from a single IP within 10 minutes" — looks entirely different across platforms:

**Sigma (vendor-neutral):**
```yaml
title: Brute Force Login Detection
logsource:
  product: windows
  service: security
detection:
  selection:
    EventID: 4625
  condition: selection | count(SourceIP) > 5
  timeframe: 10m
level: high
tags:
  - attack.credential_access
  - attack.t1110
```

**KQL (Microsoft Sentinel):**
```kql
SecurityEvent
| where TimeGenerated > ago(10m)
| where EventID == 4625
| summarize FailedAttempts = count() by IpAddress
| where FailedAttempts > 5
```

**SPL (Splunk):**
```spl
index=wineventlog EventCode=4625 earliest=-10m
| stats count as FailedAttempts by src_ip
| where FailedAttempts > 5
```

**This is exactly why the IR layer exists** — to capture the detection intent once and translate it to any platform automatically.

---

## 5. Detection Engineering Fundamentals

### 5.1 What Is Detection Engineering?

Detection engineering is the discipline of designing, implementing, testing, and maintaining automated rules that identify malicious or suspicious activity within security telemetry. It sits at the intersection of:

- **Threat intelligence** (understanding what attackers do)
- **Data engineering** (understanding what logs are available and their schemas)
- **Software engineering** (writing correct, efficient, maintainable query code)
- **Statistics** (setting thresholds that balance detection vs. false positives)

### 5.2 Anatomy of a Detection Rule

Every detection rule, regardless of platform, contains these conceptual components:

| Component | Purpose | Example |
|---|---|---|
| **Metadata** | Human-readable context | Title: "Brute Force Login", Severity: High |
| **Log Source** | Which data to query | Windows Security Event Log, product: windows |
| **Filter Conditions** | Narrow to relevant events | EventID = 4625 (failed login) |
| **Aggregation** | Group events for pattern detection | Count by source IP address |
| **Threshold** | Define when pattern is suspicious | Count > 5 in 10 minutes |
| **Temporal Logic** | Time-based constraints | Within 10-minute sliding window |
| **Correlation** | Multi-event pattern matching | Failed logins followed by successful login |
| **Entity Mapping** | Identify affected assets/users | Map source IP, target username, target host |
| **MITRE Mapping** | Framework alignment | T1110 (Brute Force), TA0006 (Credential Access) |
| **Response Action** | What happens when rule fires | Generate alert, create incident, trigger playbook |

### 5.3 Detection Quality Dimensions

| Dimension | Description | Failure Mode |
|---|---|---|
| **Syntax Validity** | Rule parses without errors | Typos, wrong operators, invalid YAML |
| **Semantic Correctness** | Rule detects the intended behavior | Wrong EventID, incorrect field names |
| **Schema Compliance** | Field names match the target SIEM | Using `SourceIP` when platform expects `SrcIpAddr` |
| **Precision** | Low false positive rate | Overly broad filters triggering on benign activity |
| **Recall** | Detects actual attacks | Overly narrow filters missing attack variants |
| **Performance** | Executes efficiently at scale | Unbounded time ranges, expensive joins |
| **Maintainability** | Easy to understand and update | No comments, hardcoded values, no documentation |

### 5.4 Why Detection Engineering Is Hard for AI

The fundamental challenge is that detection rule generation is a **multi-constraint satisfaction problem**. The AI must satisfy ALL of these constraints simultaneously:

1. **Linguistic constraint**: Correctly interpret the natural language threat description
2. **Cybersecurity constraint**: Map the description to the correct attack technique and telemetry
3. **Schema constraint**: Use the exact field names for the target SIEM platform
4. **Syntactic constraint**: Produce grammatically valid KQL/SPL/Sigma
5. **Logical constraint**: Encode correct temporal, aggregation, and threshold logic
6. **Operational constraint**: Produce a rule that works in practice without excessive false positives

Failure in **any single dimension** renders the rule unusable. This is why single-prompt LLM approaches have unacceptably high failure rates — and why the IR-based decomposition is necessary.

---

## 6. SOC Architecture & Operational Workflows

### 6.1 End-to-End SOC Pipeline

```
┌────────────────────────────────────────────────────────────────────────┐
│                    SOC OPERATIONAL PIPELINE                            │
│                                                                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐│
│  │   LOG    │  │ DETECTION│  │  ALERT   │  │ INCIDENT │  │ RESPONSE ││
│  │INGESTION │─▸│  ENGINE  │─▸│  TRIAGE  │─▸│  INVEST. │─▸│  ACTION  ││
│  │          │  │          │  │          │  │          │  │          ││
│  │ • Collect│  │ • Run    │  │ • T1     │  │ • T2/T3  │  │ • Contain││
│  │ • Parse  │  │   rules  │  │   reviews│  │   deep   │  │ • Eradic.││
│  │ • Enrich │  │ • Match  │  │ • Filter │  │   dive   │  │ • Recover││
│  │ • Store  │  │   patterns│  │   noise  │  │ • Scope  │  │ • Report ││
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘│
│                     ▲                                                  │
│                     │                                                  │
│          ┌──────────┴───────────┐                                      │
│          │  DETECTION RULES     │                                      │
│          │  ★ THIS PROJECT ★    │                                      │
│          │  Generates these     │                                      │
│          └──────────────────────┘                                      │
└────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Current SOC Bottlenecks

| Bottleneck | Impact | Scale |
|---|---|---|
| **Manual rule authoring** | 2–8 hours per rule, requires Tier 3 expertise | Enterprise SOC manages 500–2000+ rules |
| **Platform-specific syntax** | Rules must be rewritten for each SIEM | Organizations often run 2–3 SIEM/EDR platforms |
| **Schema inconsistency** | Field names differ across log sources and platforms | Hundreds of unique field names per environment |
| **High false positive rates** | 40–60% of alerts are false positives in typical SOCs | Analyst fatigue, burnout, missed real threats |
| **Slow detection onboarding** | Days to weeks from threat report to deployed detection | Attackers exploit detection gaps during this lag |
| **Limited coverage** | Most SOCs cover <25% of MITRE ATT&CK techniques | Vast blind spots in defensive posture |

### 6.3 Detection Lag — The Critical Metric

**Detection lag** is the time between a new threat being publicly disclosed and a corresponding detection rule being deployed in the SOC. Industry data shows:

| Detection Lag Phase | Typical Duration |
|---|---|
| Threat intelligence published | Day 0 |
| SOC team reads and prioritizes the report | 1–3 days |
| Detection engineer writes the rule | 1–5 days |
| Rule is tested in staging environment | 1–2 days |
| Rule is deployed to production | 0.5–1 day |
| **Total detection lag** | **3–11 days** |

This project aims to reduce the **rule writing + testing** phases from days to **minutes** by automating the NL → IR → Rule → Validation pipeline.

### 6.4 The Business Case for Automated Detection Engineering

| Metric | Manual Process | With This Framework |
|---|---|---|
| Time per rule (authoring) | 2–8 hours | 2–5 minutes |
| Rules per analyst per week | 3–5 | 50–100+ |
| Cross-platform deployment | Rewrite per platform | Automatic from single IR |
| False positive rate (initial) | 40–60% | Target: <15% (via validation loop) |
| MITRE ATT&CK coverage growth | 2–5 techniques/month | 20–50 techniques/month |
| Detection lag (report → deployed rule) | 3–11 days | <1 day |

---

*End of Part I. Part II continues below.*

---
---

# PART II — PROBLEM STATEMENT & RESEARCH GAP

---

## 7. Problem Statement

### 7.1 Core Research Problem

The central problem this project addresses is:

> **How can we reliably convert unstructured natural language cybersecurity documents into syntactically valid, semantically correct, and operationally effective SIEM detection rules across multiple platforms — while minimizing hallucinations, false positives, and manual intervention?**

This problem is fundamentally a **structured code generation problem under multi-domain constraints**. Unlike general code generation (e.g., "write a Python function to sort a list"), detection rule generation requires simultaneous satisfaction of cybersecurity domain knowledge, platform-specific syntax, schema compliance, temporal logic, and operational effectiveness.

### 7.2 The Semantic Disconnect

The root cause of failure in AI-driven detection engineering is the **semantic disconnect** between three layers of abstraction:

```
LAYER 1: Human Intent (Natural Language)
  "Detect when an attacker performs credential stuffing by attempting
   logins with many different usernames from a single IP address"
          │
          │  ← SEMANTIC GAP #1: Threat → Telemetry Mapping
          │     Which logs? Which fields? Which event IDs?
          ▼
LAYER 2: Detection Logic (Abstract)
  - Event type: authentication failure
  - Aggregation: count distinct usernames per source IP
  - Threshold: distinct_users > 20 within 5 minutes
  - Correlation: followed by at least 1 successful auth
  - MITRE: T1110.004 (Credential Stuffing)
          │
          │  ← SEMANTIC GAP #2: Logic → Platform Syntax
          │     KQL syntax? SPL syntax? Field name mappings?
          ▼
LAYER 3: Executable Rule (Platform-Specific Code)
  SigninLogs
  | where TimeGenerated > ago(5m)
  | where ResultType == "50126"
  | summarize DistinctUsers = distinct_count(UserPrincipalName) by IPAddress
  | where DistinctUsers > 20
```

**The IR layer sits at Layer 2**, bridging both semantic gaps. Multi-agent extraction handles Gap #1, and template-based generation handles Gap #2.

### 7.3 Dimensions of Failure

When current approaches attempt direct NL → Rule generation, they fail across multiple dimensions simultaneously:

| Failure Dimension | Description | Frequency | Severity |
|---|---|---|---|
| **Syntax Hallucination** | Invalid query syntax (wrong operators, malformed YAML) | 25–40% of generated rules | Critical — rule won't parse |
| **Field Hallucination** | Invented field names that don't exist in any schema | 30–50% of generated rules | Critical — rule won't execute |
| **Logic Errors** | Wrong aggregation, missing time windows, incorrect joins | 20–35% of generated rules | High — rule produces wrong results |
| **ATT&CK Mismap** | Incorrect MITRE technique or tactic assignment | 15–25% of generated rules | Medium — incorrect coverage tracking |
| **Over-Broad Detection** | Missing filters causing massive false positive rates | 40–60% of generated rules | High — alert fatigue |
| **Platform Confusion** | Mixing syntax from different SIEM platforms | 10–20% of generated rules | Critical — rule won't parse |

### 7.4 Formal Problem Definition

**Given:**
- A natural language document D (SOP, threat report, or analyst note) describing one or more attack behaviors
- A target SIEM platform P ∈ {Sentinel, Splunk, Sigma}
- A schema mapping S defining available fields for platform P

**Produce:**
- A set of detection rules R = {r₁, r₂, ..., rₙ} where each rule rᵢ:
  1. Is **syntactically valid** in platform P's query language
  2. Is **semantically correct** with respect to the described attack behavior
  3. Uses only **valid field names** from schema S
  4. Includes appropriate **temporal constraints** and **aggregation logic**
  5. Maps to the correct **MITRE ATT&CK techniques**
  6. Achieves acceptable **precision** (low false positive rate) when executed against representative telemetry
  7. Achieves acceptable **recall** (detects actual instances of the described behavior)

**Subject to:**
- Minimizing human intervention (autonomous operation)
- Providing explainable reasoning at each stage
- Supporting iterative refinement through validation feedback

---

## 8. Why Current LLM Approaches Fail

### 8.1 The Single-Prompt Paradigm

The dominant approach in 2024–2025 has been to prompt a general-purpose LLM with a natural language threat description and request direct rule output:

```
Prompt: "Generate a Microsoft Sentinel KQL detection rule for 
         brute force SSH login attempts on Linux servers."

Expected: A valid KQL query targeting Syslog/AuthLog data
Actual:   Multiple failure modes (see below)
```

### 8.2 Taxonomy of LLM Failure Modes

#### Failure Mode 1: Syntax Hallucination
```kql
// LLM generates invalid KQL syntax
Syslog
| where Facility == "auth" AND ProcessName == "sshd"
| where SyslogMessage CONTAINS "Failed password"     // ✗ CONTAINS not valid in KQL
| summarize count() by SourceIP GROUP BY bin(TimeGenerated, 5m)  // ✗ GROUP BY not KQL syntax
| having count_ > 5                                   // ✗ HAVING not valid in KQL
```

**Root cause:** The LLM confuses KQL syntax with SQL or SPL syntax, producing a hybrid that won't parse on any platform.

#### Failure Mode 2: Field Name Hallucination
```kql
// LLM invents field names that don't exist
SecurityEvent
| where EventID == 4625
| where SourceIP != ""           // ✗ Field is "IpAddress" not "SourceIP"
| summarize count() by UserName  // ✗ Field is "TargetUserName" not "UserName"
```

**Root cause:** The LLM doesn't have grounded knowledge of the exact schema for each SIEM table. Field names vary by table, platform version, and normalization layer.

#### Failure Mode 3: Logic Errors
```kql
// LLM produces syntactically valid but logically wrong rule
SigninLogs
| where ResultType == "0"    // ✗ ResultType "0" = SUCCESS, not failure!
| summarize count() by UserPrincipalName
| where count_ > 10
```

**Root cause:** The LLM doesn't understand the semantic meaning of enumerated values in specific log schemas.

#### Failure Mode 4: Missing Temporal Logic
```yaml
# LLM generates Sigma rule without time constraints
title: Brute Force Detection
logsource:
  product: windows
  service: security
detection:
  selection:
    EventID: 4625
  condition: selection | count() > 5   # ✗ No timeframe!
level: high
```

**Root cause:** Without an explicit timeframe, this rule would count ALL failed logins in the entire dataset, not within a meaningful window.

#### Failure Mode 5: Over-Broad Detection
```kql
// LLM generates rule that will fire on every single login event
SecurityEvent
| where EventID == 4624 or EventID == 4625
// ✗ No filtering, no aggregation, no threshold
// This will generate millions of alerts per day
```

**Root cause:** The LLM prioritizes recall (catching everything) without considering precision (avoiding false positives).

### 8.3 Why Multi-Agent + IR Solves These Failures

| Failure Mode | How IR Framework Prevents It |
|---|---|
| Syntax hallucination | IR captures logic in JSON; syntax is generated by deterministic templates per platform |
| Field hallucination | Schema mapper validates all fields against OCSF/ASIM before rule generation |
| Logic errors | Dedicated agents reason about attack behavior separately from code generation |
| Missing temporal logic | IR schema has mandatory `temporal_logic` section; validation rejects rules without it |
| Over-broad detection | Telemetry validation measures false positive rate; repair agent adds filters if FPR is too high |
| Platform confusion | Each platform has a dedicated generator; no cross-contamination of syntax |

---

## 9. Literature Review & Related Work

### 9.1 Existing Tools and Platforms

| Tool/Platform | Approach | Limitations |
|---|---|---|
| **Uncoder AI (SOC Prime)** | Converts IOCs and threat reports into detection rules across platforms | Proprietary, limited to IOC-based detections, no behavioral reasoning |
| **RulePilot** | LLM-based autonomous rule generation (GPT-4o, DeepSeek, Llama-3) | Single-prompt generation, no IR layer, limited validation |
| **Splunk AI Assistant** | Natural language to SPL conversion within Splunk ecosystem | Single-platform only, no cross-platform portability |
| **Microsoft Copilot for Security** | AI assistant integrated into Microsoft Sentinel | Microsoft ecosystem only, general-purpose (not detection-focused) |
| **Sigma CLI (pySigma)** | Sigma rule → platform-specific rule conversion | Requires pre-written Sigma rules, no NL understanding |
| **CISA Decider** | Assists in MITRE ATT&CK technique mapping | Mapping only, no rule generation |
| **Detection Studio (Splunk 2025)** | Unified detection lifecycle interface with AI assistance | Splunk-only, no IR abstraction |

### 9.2 Academic Research Landscape

| Research Area | Key Papers/Projects | Gap This Project Fills |
|---|---|---|
| LLM-based code generation | CodeBERT, Codex, StarCoder | These generate general code, not domain-specific detection logic |
| Cybersecurity NLP | CyBERT, SecBERT, CyNER | Focus on NER/classification, not end-to-end rule generation |
| Sigma rule analysis | SigmaHQ community research | Focus on rule management, not automated generation |
| Multi-agent AI systems | AutoGen, CrewAI, LangGraph | General frameworks, not applied to detection engineering |
| CTI operationalization | SigmaHQ benchmark (Microsoft) | Provides evaluation methodology but not a generation framework |
| Intermediate representations | Compiler theory (LLVM IR, JVM bytecode) | Not applied to cybersecurity detection logic |

### 9.3 Research Gap Summary

**No existing work combines all of the following:**

1. ✗ Multi-agent NLP extraction from unstructured cybersecurity text
2. ✗ Structured Intermediate Representation for detection logic
3. ✗ Schema-aware generation via OCSF/ASIM normalization
4. ✗ Cross-platform rule generation (Sigma + KQL + SPL) from a single IR
5. ✗ Closed-loop telemetry validation with autonomous repair
6. ✗ Empirical evaluation against benchmark datasets (SigmaHQ, SigmaHQ, HDFS)

**This project fills this exact gap** by unifying all six capabilities into a single, coherent framework.

---

## 10. Core Research Objectives

### 10.1 Primary Objectives

| # | Objective | Success Criteria |
|---|---|---|
| **O1** | Design a schema-aware Intermediate Representation (IR) for security detection logic | IR schema covers filters, aggregations, thresholds, temporal logic, entities, MITRE mappings, and output configuration |
| **O2** | Build a multi-agent NLP pipeline that converts natural language SOPs/CTRs into structured IRs | Extraction accuracy > 85% on entity, behavior, and MITRE mapping tasks |
| **O3** | Implement cross-platform rule generators (Sigma, KQL, SPL) from a single IR | Syntax validity > 95% across all three platforms |
| **O4** | Develop a closed-loop validation and repair pipeline | Rules pass telemetry validation within ≤3 repair iterations |
| **O5** | Reduce hallucinations compared to direct LLM generation | ≥40% reduction in syntax/field hallucination rate vs. baseline |
| **O6** | Achieve cross-platform schema interoperability via OCSF/ASIM normalization | Field mapping accuracy > 90% across Sentinel, Splunk, and Sigma |

### 10.2 Secondary Objectives

| # | Objective | Success Criteria |
|---|---|---|
| **O7** | Minimize false positive rates in generated rules | FPR < 15% on benchmark telemetry datasets |
| **O8** | Provide explainable reasoning at each pipeline stage | Each IR includes provenance trace from source text to generated fields |
| **O9** | Demonstrate empirical superiority over baseline (direct LLM) | Statistically significant improvement on Precision, Recall, CodeBLEU, and Execution Success Rate |
| **O10** | Produce a reproducible research prototype | Open-source codebase with documented API, configuration, and evaluation scripts |

### 10.3 Research Questions

| # | Research Question |
|---|---|
| **RQ1** | Does an intermediate representation reduce hallucination rates in AI-generated SIEM detection rules compared to direct LLM generation? |
| **RQ2** | Does multi-agent decomposition improve extraction accuracy for cybersecurity entities, behaviors, and MITRE mappings? |
| **RQ3** | Can schema-aware generation via OCSF/ASIM normalization achieve >90% field mapping accuracy across heterogeneous SIEM platforms? |
| **RQ4** | Does closed-loop validation with autonomous repair improve the operational effectiveness (precision/recall) of generated rules? |
| **RQ5** | What is the comparative performance of the proposed framework against direct LLM baselines on standardized benchmarks (SigmaHQ, SigmaHQ)? |

### 10.4 Hypotheses

| # | Hypothesis | Rationale |
|---|---|---|
| **H1** | IR-based generation will achieve ≥95% syntax validity vs. <70% for direct LLM | Separating semantics from syntax eliminates cross-language confusion |
| **H2** | Multi-agent extraction will improve MITRE mapping accuracy by ≥30% over single-agent | Dedicated MITRE agent can focus exclusively on technique identification |
| **H3** | Schema normalization will reduce field hallucination rate by ≥50% | OCSF/ASIM grounding eliminates invented field names |
| **H4** | Closed-loop repair will fix ≥80% of initially failing rules within 3 iterations | Targeted error messages enable focused repairs |
| **H5** | The complete framework will achieve ≥0.7 CodeBLEU score against SigmaHQ reference rules | IR-guided generation produces structurally similar output to human-written rules |

---

*End of Part II. Part III continues below.*

---
---

# PART III — SYSTEM ARCHITECTURE

---

## 11. High-Level System Architecture

### 11.1 End-to-End Pipeline Overview

The complete system transforms a natural language document into a validated, deployment-ready detection rule through six major stages:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    END-TO-END SYSTEM PIPELINE                                  │
│                                                                                 │
│  ┌─────────────┐                                                                │
│  │   INPUT     │  SOP document / CTI report / Analyst note (plain text)        │
│  │   LAYER     │  Accepts: .txt, .pdf, .md, .docx, plain string               │
│  └──────┬──────┘                                                                │
│         ▼                                                                       │
│  ┌─────────────┐                                                                │
│  │  PREPROCESS │  Text cleaning, chunking, language detection                  │
│  │  LAYER      │  Outputs: normalized text chunks                              │
│  └──────┬──────┘                                                                │
│         ▼                                                                       │
│  ┌─────────────────────────────────────────────────────┐                       │
│  │              MULTI-AGENT EXTRACTION LAYER           │                       │
│  │                                                     │                       │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌──────────┐                │
│  │  │  Threat   │  │ Metadata  │  │  Entity   │  │  MITRE   │                │
│  │  │  Intel    │  │  Agent    │  │ Extractor │  │  Mapper  │                │
│  │  │  Agent    │  │           │  │  Agent    │  │  Agent   │                │
│  │  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └────┬─────┘                │
│  │        └──────────────┴───────────────┴─────────────┘                      │
│  │                               ▼                                             │
│  │                      IR Builder Agent                                       │
│  └───────────────────────────────┬─────────────────────────────────────────────┘
│                                  ▼                                              │
│  ┌─────────────┐                                                                │
│  │  SECURITY   │  Structured JSON intermediate representation                  │
│  │  IR OBJECT  │  Vendor-neutral, fully annotated detection logic              │
│  └──────┬──────┘                                                                │
│         ▼                                                                       │
│  ┌─────────────┐                                                                │
│  │   SCHEMA    │  OCSF / ASIM normalization                                   │
│  │   MAPPER    │  Field name resolution per target platform                   │
│  └──────┬──────┘                                                                │
│         ▼                                                                       │
│  ┌──────────────────────────────────────────┐                                  │
│  │            RULE GENERATOR LAYER          │                                  │
│  │  ┌──────────┐  ┌──────────┐  ┌────────┐ │                                  │
│  │  │  Sigma   │  │   KQL    │  │  SPL   │ │                                  │
│  │  │Generator │  │Generator │  │ Gen.   │ │                                  │
│  │  └──────────┘  └──────────┘  └────────┘ │                                  │
│  └──────────────────────┬───────────────────┘                                  │
│                         ▼                                                       │
│  ┌──────────────────────────────────────────┐                                  │
│  │           VALIDATION ENGINE              │                                  │
│  │  Syntax Check → Semantic Check →         │                                  │
│  │  Telemetry Execution                     │                                  │
│  └──────────┬───────────────────────────────┘                                  │
│             │ FAIL                                                              │
│             ▼                                                                   │
│  ┌─────────────┐    ┌──────────────────────────┐                               │
│  │   REPAIR    │───▶│  Retry → IR Builder      │  (max 3 iterations)          │
│  │   AGENT     │    └──────────────────────────┘                               │
│  └─────────────┘                                                                │
│             │ PASS                                                              │
│             ▼                                                                   │
│  ┌─────────────┐                                                                │
│  │  VALIDATED  │  Final rules + IR + provenance + metrics                     │
│  │  OUTPUT     │  Ready for SIEM deployment or human review                   │
│  └─────────────┘                                                                │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 11.2 Major Components Summary

| Component | Responsibility | Technology |
|---|---|---|
| **Input Preprocessor** | Text cleaning, chunking, format normalization | Python, pdfminer, python-docx |
| **Coordinator Agent** | Workflow orchestration, state management, routing | LangGraph StateGraph |
| **Threat Intel Agent** | Attack behavior and IOC extraction | LangChain + GPT-4o / Claude |
| **Metadata Agent** | Severity, tags, description generation | LangChain |
| **Entity Extraction Agent** | NER for IPs, users, hosts, processes | LangChain + CyNER patterns |
| **MITRE Mapping Agent** | ATT&CK tactic/technique identification | LangChain + MITRE API |
| **IR Builder Agent** | Assembles structured Security IR JSON | LangChain + Pydantic |
| **Schema Mapper** | OCSF/ASIM field normalization | Python + schema YAML files |
| **Sigma Generator** | IR → Sigma YAML | Jinja2 templates |
| **KQL Generator** | IR → Microsoft Sentinel KQL | Jinja2 templates |
| **SPL Generator** | IR → Splunk SPL | Jinja2 templates |
| **Validation Engine** | Syntax + semantic + telemetry checks | pySigma, pandas, synthetic logs |
| **Repair Agent** | Autonomous rule refinement from error feedback | LangChain |
| **Storage Layer** | IR caching, rule versioning, audit logs | SQLite / PostgreSQL |
| **REST API** | Programmatic access to the pipeline | FastAPI |

### 11.3 Data Flow Between Components

```
Input Text
    │
    ▼
[Preprocessor] → clean_text: str, chunks: List[str]
    │
    ▼
[Coordinator Agent] → routes chunks to specialist agents
    │
    ├──▶ [Threat Intel Agent]   → behaviors: List[Behavior], iocs: List[IOC]
    ├──▶ [Metadata Agent]       → severity: str, description: str, tags: List[str]
    ├──▶ [Entity Agent]         → entities: EntityMap {users, ips, hosts, processes}
    └──▶ [MITRE Mapping Agent]  → mitre: List[{tactic, technique, id}]
                │
                ▼
         [IR Builder Agent]
                │
                ▼
         SecurityIR (JSON)   ← canonical representation
                │
                ▼
         [Schema Mapper]     → normalized_ir: SecurityIR with platform fields resolved
                │
         ┌──────┼──────┐
         ▼      ▼      ▼
      [Sigma] [KQL]  [SPL]  generators
         │      │      │
         └──────┴──────┘
                │
                ▼
         [Validation Engine]
                │
         ┌──────┴──────────────────────────┐
         │ PASS                 │ FAIL      │
         ▼                      ▼           │
      [Output]          [Repair Agent]      │
                               │            │
                               └────────────┘
                                (retry loop, max 3x)
```

---

## 12. Multi-Agent Architecture Design

### 12.1 Why Multi-Agent?

Detection rule generation fails when a single model handles all reasoning simultaneously. Multi-agent design distributes cognitive load across **specialized, focused agents**, each with:
- A narrow, well-defined task
- A targeted system prompt optimized for its domain
- Clear input/output contracts enforced by Pydantic schemas
- Independent validation of its output before handoff

This mirrors how expert human teams work: a threat analyst, a detection engineer, a platform specialist, and a QA engineer — each owning one piece of the pipeline.

### 12.2 Agent Communication via Shared State

All agents communicate through a **shared LangGraph state object** — a typed Python dict that flows through the graph. No agent calls another directly; they read from and write to this shared state, enabling:
- Parallel execution of independent agents
- Full auditability of every state transition
- Easy addition of new agents without modifying existing ones
- Checkpoint-based recovery if an agent fails

**State Schema (TypedDict):**
```python
from typing import TypedDict, Annotated, List, Optional
from operator import add

class PipelineState(TypedDict):
    # Input
    raw_input: str
    chunks: List[str]

    # Agent outputs (populated progressively)
    behaviors: List[dict]           # Threat Intel Agent
    iocs: List[dict]                # Threat Intel Agent
    severity: str                   # Metadata Agent
    description: str                # Metadata Agent
    tags: List[str]                 # Metadata Agent
    entities: dict                  # Entity Extraction Agent
    mitre_mappings: List[dict]      # MITRE Mapping Agent

    # IR
    security_ir: Optional[dict]     # IR Builder Agent
    normalized_ir: Optional[dict]   # Schema Mapper

    # Generated rules
    sigma_rule: Optional[str]
    kql_rule: Optional[str]
    spl_rule: Optional[str]

    # Validation
    validation_results: dict
    repair_count: int               # tracks repair iterations
    errors: Annotated[List[str], add]  # accumulated errors

    # Final output
    validated_rules: Optional[dict]
    provenance: dict                # trace of source text → IR field
```

### 12.3 Agent 1 — Coordinator Agent

**Role:** Master orchestrator. Receives raw input, routes work, manages retry logic, and decides when the pipeline is complete.

**Responsibilities:**
- Parse and chunk input documents
- Determine which specialist agents to invoke (and in what order)
- Monitor state for errors and trigger repair loops
- Enforce max retry limit (default: 3)
- Finalize and package output

**LangGraph Role:** Acts as the graph entry point and conditional router. Uses `conditional_edges` to decide the next node based on validation results.

```python
def coordinator_router(state: PipelineState) -> str:
    if state["repair_count"] >= 3:
        return "output_failed"
    if state["validation_results"].get("passed"):
        return "output_success"
    if state["validation_results"].get("errors"):
        return "repair_agent"
    return "extraction_agents"
```

**System Prompt Strategy:** The coordinator uses a minimal, structural prompt — it orchestrates, it doesn't reason about cybersecurity content.

---

### 12.4 Agent 2 — Threat Intelligence Agent

**Role:** Extracts attack behaviors and indicators of compromise from natural language threat descriptions.

**Input:** Raw text chunks from the input document  
**Output:** `behaviors: List[Behavior]`, `iocs: List[IOC]`

**Behavior Schema:**
```python
class Behavior(BaseModel):
    description: str          # Human-readable behavior description
    event_type: str           # e.g., "authentication_failure", "process_creation"
    action: str               # e.g., "brute_force", "lateral_movement"
    conditions: List[str]     # e.g., ["EventID == 4625", "count > 5"]
    attacker_goal: str        # e.g., "credential_access", "persistence"

class IOC(BaseModel):
    type: str                 # "ip", "domain", "hash", "username_pattern"
    value: str
    confidence: float         # 0.0 to 1.0
```

**Extraction Examples:**

| Input Text | Extracted Behavior |
|---|---|
| "attacker attempts login with multiple passwords" | event_type: auth_failure, action: brute_force, attacker_goal: credential_access |
| "PowerShell downloads and executes remote script" | event_type: process_creation, action: remote_execution, attacker_goal: execution |
| "large file copied to USB drive" | event_type: file_copy, action: data_staging, attacker_goal: exfiltration |

**System Prompt:**
```
You are a cybersecurity threat intelligence analyst. Your ONLY job is to extract 
attack behaviors from the provided text. For each behavior, identify:
1. The specific action the attacker performs
2. The event type that would appear in logs
3. The attacker's tactical goal
4. Any observable indicators

Output ONLY valid JSON matching the Behavior schema. Do not generate any rules.
Do not reason about platforms or query syntax.
```

---

### 12.5 Agent 3 — Metadata Agent

**Role:** Generates rule metadata — severity, human-readable description, tags, and categorization — from the extracted behaviors.

**Input:** `behaviors`, `iocs`  
**Output:** `severity`, `description`, `tags`, `rule_name`

**Severity Classification Logic:**

| Severity | Criteria | Examples |
|---|---|---|
| **Critical** | Direct system compromise, data exfiltration, ransomware | C2 beacon, data staging + exfil, ransomware execution |
| **High** | Credential theft, privilege escalation, lateral movement | Brute force, pass-the-hash, PsExec |
| **Medium** | Reconnaissance, suspicious but not confirmed malicious | Port scan, failed login spike, unusual process |
| **Low** | Informational, policy violations, minor anomalies | Login outside hours, new admin account |
| **Informational** | Baseline deviation, audit events | First-time access, configuration change |

**Output Schema:**
```python
class Metadata(BaseModel):
    rule_name: str            # e.g., "Brute Force Login - Windows Auth"
    severity: str             # critical / high / medium / low / informational
    description: str          # 2-3 sentence explanation of what the rule detects
    tags: List[str]           # e.g., ["brute_force", "credential_access", "windows"]
    author: str               # "IR-Framework Auto-Generated"
    status: str               # "experimental" (always for generated rules)
    false_positives: List[str] # known benign scenarios that could trigger this rule
```

---

### 12.6 Agent 4 — Entity Extraction Agent

**Role:** Performs Named Entity Recognition (NER) specific to cybersecurity entities mentioned in the source text.

**Input:** Raw text chunks  
**Output:** `entities: EntityMap`

**Entity Types Extracted:**

| Entity Type | Examples | IR Usage |
|---|---|---|
| `user` | "administrator", "service account", "domain user" | Filter on account name patterns |
| `ip_address` | "192.168.1.0/24", "external IP", "VPN range" | Source/destination IP filters |
| `hostname` | "DC01", "web server", "Linux endpoint" | Target host conditions |
| `process` | "powershell.exe", "cmd.exe", "svchost.exe" | Process name filters |
| `port` | "SSH (22)", "RDP (3389)", "SMB (445)" | Network port filters |
| `file_path` | "C:\Windows\Temp", "%APPDATA%" | File path conditions |
| `registry_key` | "HKLM\Software\...", "Run key" | Registry monitoring |
| `domain` | "malicious-domain.com", "*.onion" | DNS/network filtering |
| `event_id` | "Event ID 4625", "4688", "4698" | Direct EventID filters |

**Entity Map Schema:**
```python
class EntityMap(BaseModel):
    users: List[str]
    ip_ranges: List[str]
    hostnames: List[str]
    processes: List[str]
    ports: List[int]
    file_paths: List[str]
    registry_keys: List[str]
    domains: List[str]
    event_ids: List[int]
```

**System Prompt:**
```
You are a cybersecurity entity extraction specialist. Extract ONLY specific 
named entities from the text: usernames, IP addresses/ranges, hostnames, 
process names, port numbers, file paths, registry keys, domain names, 
and Windows Event IDs.

Output ONLY a JSON object matching the EntityMap schema.
Do not infer entities — extract only what is explicitly mentioned or 
strongly implied by specific technical context.
```

---

### 12.7 Agent 5 — MITRE Mapping Agent

**Role:** Maps extracted behaviors to the MITRE ATT&CK framework's tactics and techniques.

**Input:** `behaviors`, `iocs`  
**Output:** `mitre_mappings: List[MITREMapping]`

**MITRE Mapping Schema:**
```python
class MITREMapping(BaseModel):
    tactic: str           # e.g., "Credential Access"
    tactic_id: str        # e.g., "TA0006"
    technique: str        # e.g., "Brute Force"
    technique_id: str     # e.g., "T1110"
    sub_technique: Optional[str]    # e.g., "Password Spraying"
    sub_technique_id: Optional[str] # e.g., "T1110.003"
    confidence: float     # 0.0 to 1.0
    rationale: str        # Brief explanation of the mapping
```

**Mapping Reference Table (Common Patterns):**

| Behavior | Tactic | Technique | ID |
|---|---|---|---|
| Multiple failed logins from one IP | Credential Access | Brute Force | T1110 |
| Multiple failed logins with different users from one IP | Credential Access | Credential Stuffing | T1110.004 |
| Multiple failed logins with one user, many passwords | Credential Access | Password Spraying | T1110.003 |
| Remote service creation (PsExec, SC.exe) | Lateral Movement | Remote Services | T1021 |
| New scheduled task created | Persistence | Scheduled Task/Job | T1053 |
| PowerShell execution with encoded commands | Defense Evasion | Obfuscated Files/Info | T1027 |
| Large outbound data transfer | Exfiltration | Exfiltration Over C2 Channel | T1041 |
| DNS requests to suspicious domains | Command & Control | Application Layer Protocol | T1071 |

**System Prompt:**
```
You are a MITRE ATT&CK specialist. Map each provided behavior to the most 
precise ATT&CK technique, including sub-techniques where applicable.

Use ONLY official MITRE ATT&CK technique IDs (format: T####.###).
For each mapping, provide:
- The exact tactic name and ID (TA####)
- The exact technique name and ID (T####)
- Sub-technique if applicable (T####.###)
- Confidence level (0.0-1.0)
- Brief rationale for the mapping

Do not invent technique IDs. If uncertain, use a broader technique rather 
than guessing a specific sub-technique.
```

---

### 12.8 Agent 6 — IR Builder Agent *(Most Critical)*

**Role:** Assembles all extracted information into the structured Security IR JSON object. This is the most important agent in the system — it synthesizes all upstream outputs into the canonical intermediate representation.

**Input:** All outputs from agents 2–5  
**Output:** `security_ir: SecurityIR`

**Responsibilities:**
1. Validate that all required IR fields can be populated from available agent outputs
2. Resolve conflicts or ambiguities across agent outputs
3. Infer missing fields with appropriate defaults and confidence scores
4. Construct the complete, valid Security IR JSON
5. Add provenance metadata linking each IR field back to the source text

**Key Design Decisions:**
- The IR Builder does NOT generate detection rules — it only structures data
- All field values come from upstream agents; the IR Builder synthesizes, not generates
- Missing required fields trigger a clarification request back through the pipeline
- Confidence scores on inferred fields inform the repair agent's priorities

**System Prompt:**
```
You are a detection logic architect. Your ONLY job is to assemble the 
provided extracted information into a structured Security IR JSON.

You receive:
- Behaviors from the Threat Intel Agent
- Metadata from the Metadata Agent  
- Entities from the Entity Extraction Agent
- MITRE mappings from the MITRE Mapping Agent

Construct a valid Security IR JSON matching the provided schema exactly.
Do not add information not present in the inputs.
Do not generate any detection rules or query syntax.
Set confidence scores accurately — do not overclaim certainty.
```

---

### 12.9 Agent 7 — Validation Agent

**Role:** Executes multi-stage validation on generated rules and produces structured error reports for the Repair Agent.

**Validation Stages:**
1. **Syntax Validation** — Parses rule for valid syntax
2. **Semantic Validation** — Checks field names, value ranges, schema compliance
3. **Telemetry Validation** — Executes rule against benchmark logs

**Output:**
```python
class ValidationResult(BaseModel):
    passed: bool
    stage_results: dict  # {syntax: bool, semantic: bool, telemetry: bool}
    errors: List[ValidationError]
    metrics: dict        # {precision, recall, fpr, execution_time_ms}
    recommendations: List[str]  # Actionable repair suggestions
```

---

### 12.10 Agent 8 — Repair Agent

**Role:** Receives structured error reports from the Validation Agent and produces targeted fixes to the Security IR, which is then re-processed through the Rule Generators.

**Key Design:** The Repair Agent modifies the **IR** (not the generated rule directly). This ensures the fix propagates correctly through all rule generators and maintains IR as the single source of truth.

**Repair Strategies by Error Type:**

| Error Type | Repair Strategy |
|---|---|
| Invalid field name | Replace with OCSF/ASIM-validated field from schema |
| Syntax error in generated rule | Adjust IR template hint; regenerate |
| High false positive rate | Tighten threshold values or add exclusion filters |
| Low recall / missed attacks | Broaden event type filters, lower threshold |
| Missing temporal window | Add default `timeframe: 10m` to IR temporal section |
| Invalid MITRE mapping | Re-query MITRE agent with additional context |

**Max Repair Iterations:** 3 (configurable). After 3 failed attempts, the pipeline marks the rule as `FAILED_VALIDATION` and routes to human review queue.

---

## 13. LangGraph Workflow Design

### 13.1 Why LangGraph

LangGraph was chosen over simpler LangChain chains or single-pass pipelines because:

| Requirement | LangGraph Feature |
|---|---|
| Cyclic repair loops | Native support for graph cycles (unlike DAG-only frameworks) |
| Shared state across agents | StateGraph with TypedDict state passed through all nodes |
| Conditional routing | `conditional_edges` based on validation results |
| Parallel agent execution | Multiple nodes can execute simultaneously on independent state keys |
| Checkpointing | Built-in persistence; resume failed pipelines without restarting |
| Human-in-the-loop | `interrupt_before` / `interrupt_after` hooks for human review gates |
| Observability | Native LangSmith integration for tracing every agent decision |

### 13.2 Graph Topology

```python
from langgraph.graph import StateGraph, END

workflow = StateGraph(PipelineState)

# Add nodes (agents)
workflow.add_node("preprocess",        preprocess_node)
workflow.add_node("threat_intel",      threat_intel_node)
workflow.add_node("metadata",          metadata_node)
workflow.add_node("entity_extraction", entity_extraction_node)
workflow.add_node("mitre_mapping",     mitre_mapping_node)
workflow.add_node("ir_builder",        ir_builder_node)
workflow.add_node("schema_mapper",     schema_mapper_node)
workflow.add_node("sigma_generator",   sigma_generator_node)
workflow.add_node("kql_generator",     kql_generator_node)
workflow.add_node("spl_generator",     spl_generator_node)
workflow.add_node("validator",         validator_node)
workflow.add_node("repair_agent",      repair_agent_node)
workflow.add_node("output",            output_node)

# Entry point
workflow.set_entry_point("preprocess")

# Sequential edges
workflow.add_edge("preprocess", "threat_intel")

# Parallel extraction (fan-out from threat_intel)
workflow.add_edge("threat_intel",      "metadata")
workflow.add_edge("threat_intel",      "entity_extraction")
workflow.add_edge("threat_intel",      "mitre_mapping")

# Fan-in to IR builder
workflow.add_edge("metadata",          "ir_builder")
workflow.add_edge("entity_extraction", "ir_builder")
workflow.add_edge("mitre_mapping",     "ir_builder")

# IR → Schema → Generators
workflow.add_edge("ir_builder",   "schema_mapper")
workflow.add_edge("schema_mapper","sigma_generator")
workflow.add_edge("schema_mapper","kql_generator")
workflow.add_edge("schema_mapper","spl_generator")

# Generators → Validator
workflow.add_edge("sigma_generator", "validator")
workflow.add_edge("kql_generator",   "validator")
workflow.add_edge("spl_generator",   "validator")

# Conditional routing from validator
workflow.add_conditional_edges(
    "validator",
    route_after_validation,
    {
        "pass":          "output",
        "repair":        "repair_agent",
        "max_retries":   "output",   # output with FAILED status
    }
)

# Repair loops back to IR builder
workflow.add_edge("repair_agent", "ir_builder")
workflow.add_edge("output", END)

app = workflow.compile(checkpointer=MemorySaver())
```

### 13.3 Routing Logic

```python
def route_after_validation(state: PipelineState) -> str:
    results = state["validation_results"]
    repair_count = state.get("repair_count", 0)

    if repair_count >= 3:
        return "max_retries"
    if results.get("passed"):
        return "pass"
    return "repair"
```

### 13.4 Parallel Execution Strategy

Agents 3 (Metadata), 4 (Entity Extraction), and 5 (MITRE Mapping) all operate on the same input and are **fully independent** — they can run in parallel:

```
[Threat Intel Agent]
        │
        ├──▶ [Metadata Agent]          ─┐
        ├──▶ [Entity Extraction Agent] ──┤ Run in parallel
        └──▶ [MITRE Mapping Agent]    ──┘
                                        │
                                        ▼
                               [IR Builder Agent]
                               (waits for all three)
```

In LangGraph, this is achieved by having all three nodes write to different keys in the shared state. The IR Builder node reads all three keys, blocking until all are populated (LangGraph handles this synchronization automatically via state dependencies).

### 13.5 Human-in-the-Loop Gate

For production-grade use, a human review gate is inserted before final output:

```python
# Interrupt before output node — human can approve/reject/modify
app = workflow.compile(
    checkpointer=MemorySaver(),
    interrupt_before=["output"]
)

# Resume after human review
thread = {"configurable": {"thread_id": "rule_gen_001"}}
result = app.invoke(initial_state, thread)
# ... human reviews state["validated_rules"] ...
app.invoke(None, thread)  # resume from checkpoint
```

### 13.6 State Persistence and Recovery

LangGraph's `MemorySaver` (in-memory) or `SqliteSaver` (persistent) checkpointers enable:

- **Resume on failure**: If an agent crashes, restart from the last checkpoint
- **Audit trail**: Full state at every step is stored and inspectable
- **Multi-turn refinement**: Analysts can interrupt, provide feedback, and resume
- **Batch processing**: Process multiple documents with isolated state per thread

```python
from langgraph.checkpoint.sqlite import SqliteSaver

# Persistent checkpointing across restarts
with SqliteSaver.from_conn_string("pipeline_checkpoints.db") as checkpointer:
    app = workflow.compile(checkpointer=checkpointer)
    result = app.invoke(state, {"configurable": {"thread_id": doc_id}})
```

---

*End of Part III. Part IV continues below.*

---
---

# PART IV — INTERMEDIATE REPRESENTATION (IR)

---

## 14. IR Theory & Compiler Analogy

### 14.1 What Is an Intermediate Representation?

An Intermediate Representation (IR) is a data structure that sits between a high-level source language and a low-level target language. It is the lingua franca of compilers — a form that is simultaneously:

- **Richer than the target language** (carries semantic annotations, provenance, confidence)
- **Simpler than the source language** (structured, typed, machine-processable)
- **Target-independent** (can be compiled to multiple output formats)

IRs are used in every serious language toolchain:

| Toolchain | Source | IR | Target |
|---|---|---|---|
| LLVM / Clang | C / C++ | LLVM IR (SSA form) | x86, ARM, RISC-V |
| JVM | Java / Kotlin / Scala | JVM Bytecode | Platform machine code |
| Python CPython | Python source | AST → Code objects | CPython bytecode |
| WebAssembly | C / Rust / Go | Wasm IR | Browser native code |
| **This project** | **NL SOP / CTI** | **Security IR (JSON)** | **Sigma / KQL / SPL** |

### 14.2 Why an IR for Detection Engineering?

Without an IR, the pipeline looks like this:

```
NL Input ──→ [Agent reasons about semantics + syntax + schema + logic simultaneously] ──→ KQL
```

Every concern is entangled. A mistake in semantic interpretation contaminates syntax. A wrong field name breaks execution. There is no intermediate checkpoint.

With an IR, the pipeline decomposes cleanly:

```
NL Input ──→ [Semantic Extraction] ──→ Security IR ──→ [Syntax Generation] ──→ KQL
                                                     └──→ [Syntax Generation] ──→ Sigma
                                                     └──→ [Syntax Generation] ──→ SPL
```

**Benefits of IR decomposition:**

| Benefit | Explanation |
|---|---|
| **Hallucination reduction** | Syntax generators use templates, not LLM free-form generation |
| **Portability** | One IR compiles to any number of target platforms |
| **Explainability** | Every IR field traces back to source text (provenance) |
| **Modularity** | Add new target platforms without touching extraction logic |
| **Validation checkpoint** | Validate IR correctness before any rules are generated |
| **Repair targeting** | Error messages point to specific IR fields, not opaque query text |

### 14.3 IR Design Principles

The Security IR was designed according to these principles:

1. **Completeness** — Every concept needed to generate a valid detection rule must be representable in the IR
2. **Minimality** — No field exists without a direct use in at least one generator
3. **Vendor neutrality** — No platform-specific syntax or field names in the IR itself
4. **Typed and validated** — Every field has a defined type; invalid values are caught at IR construction time
5. **Versioned** — IR schema carries a version field for forward compatibility
6. **Provenance-aware** — Each field carries a source reference linking it to the originating text span

---

## 15. Security IR Schema Design

### 15.1 Complete IR JSON Schema

The full Security IR is a JSON object with six top-level sections. Below is the complete schema with every field documented:

```json
{
  "ir_version": "1.0",
  "rule_id": "uuid-v4-string",
  "created_at": "ISO-8601 timestamp",
  "source_document": "filename or identifier of input document",
  "confidence_overall": 0.87,

  "metadata": { ... },
  "detection_logic": { ... },
  "entity_mapping": { ... },
  "temporal_logic": { ... },
  "mitre_mapping": [ ... ],
  "output_config": { ... },
  "provenance": { ... }
}
```

---

### 15.2 Section 1 — Metadata

Carries human-readable context and administrative information about the rule.

```json
"metadata": {
  "rule_name": "Brute Force Login - Windows Authentication",
  "severity": "high",
  "description": "Detects potential brute force attacks by identifying more than 5 failed Windows authentication events from a single source IP within a 10-minute window.",
  "author": "IR-Framework v1.0 (Auto-Generated)",
  "status": "experimental",
  "tags": [
    "brute_force",
    "credential_access",
    "windows",
    "authentication"
  ],
  "false_positives": [
    "Legitimate users who mistype passwords repeatedly",
    "Password synchronization services",
    "IT helpdesk bulk account resets"
  ],
  "references": [
    "https://attack.mitre.org/techniques/T1110/",
    "https://docs.microsoft.com/en-us/windows/security/threat-protection/auditing/event-4625"
  ],
  "confidence": 0.92
}
```

**Field Reference:**

| Field | Type | Required | Description |
|---|---|---|---|
| `rule_name` | string | ✅ | Short, descriptive rule title |
| `severity` | enum | ✅ | `critical`, `high`, `medium`, `low`, `informational` |
| `description` | string | ✅ | 2–4 sentence human-readable explanation |
| `author` | string | ✅ | Always `"IR-Framework vX.X (Auto-Generated)"` |
| `status` | enum | ✅ | Always `"experimental"` for auto-generated rules |
| `tags` | List[string] | ✅ | Searchable labels for filtering and categorization |
| `false_positives` | List[string] | ✅ | Known benign scenarios that may trigger the rule |
| `references` | List[URL] | ❌ | Links to MITRE, vendor docs, threat reports |
| `confidence` | float [0–1] | ✅ | Agent confidence in this metadata block |

---

### 15.3 Section 2 — Detection Logic

The core of the IR. Captures what conditions must be true for the rule to fire.

```json
"detection_logic": {
  "event_type": "authentication_failure",
  "log_source": {
    "product": "windows",
    "service": "security",
    "category": "authentication"
  },
  "filters": [
    {
      "field": "event_id",
      "operator": "equals",
      "value": 4625,
      "confidence": 0.99
    },
    {
      "field": "logon_type",
      "operator": "in",
      "value": [3, 8, 10],
      "confidence": 0.85,
      "note": "Network, NetworkCleartext, RemoteInteractive logons only"
    }
  ],
  "exclusions": [
    {
      "field": "source_ip",
      "operator": "in_cidr",
      "value": "10.0.0.0/8",
      "reason": "Exclude internal network management tools"
    }
  ],
  "aggregation": {
    "function": "count",
    "group_by": ["source_ip"],
    "threshold": {
      "operator": "greater_than",
      "value": 5
    }
  },
  "correlation": {
    "type": "sequence",
    "events": [
      {
        "event_type": "authentication_failure",
        "min_count": 5,
        "role": "trigger"
      },
      {
        "event_type": "authentication_success",
        "min_count": 1,
        "role": "follow_up",
        "optional": true
      }
    ],
    "same_entity": "source_ip"
  }
}
```

**Filter Operators Supported:**

| Operator | Description | Example |
|---|---|---|
| `equals` | Exact match | `event_id equals 4625` |
| `not_equals` | Negation | `result_type not_equals 0` |
| `contains` | Substring match | `process_name contains "powershell"` |
| `starts_with` | Prefix match | `command_line starts_with "cmd /c"` |
| `in` | Value in list | `logon_type in [3, 8, 10]` |
| `not_in` | Value not in list | `account_name not_in ["SYSTEM", "LOCAL SERVICE"]` |
| `in_cidr` | IP in CIDR range | `source_ip in_cidr "192.168.0.0/16"` |
| `regex` | Regular expression | `process_name regex ".*\.exe$"` |
| `greater_than` | Numeric comparison | `failed_count greater_than 5` |
| `less_than` | Numeric comparison | `bytes_sent less_than 1000000` |
| `exists` | Field presence check | `parent_process_id exists` |

---

### 15.4 Section 3 — Entity Mapping

Defines the security entities (actors and objects) involved in the detection scenario.

```json
"entity_mapping": {
  "primary_entity": "source_ip",
  "entities": [
    {
      "type": "ip_address",
      "role": "attacker",
      "ir_field": "source_ip",
      "description": "The IP address making repeated failed login attempts"
    },
    {
      "type": "user_account",
      "role": "target",
      "ir_field": "target_username",
      "description": "The account being targeted by brute force attempts"
    },
    {
      "type": "host",
      "role": "victim",
      "ir_field": "target_hostname",
      "description": "The Windows host receiving the authentication attempts"
    }
  ],
  "siem_entity_mapping": {
    "sentinel": {
      "source_ip":        "IpAddress",
      "target_username":  "TargetUserName",
      "target_hostname":  "Computer"
    },
    "splunk": {
      "source_ip":        "src_ip",
      "target_username":  "user",
      "target_hostname":  "dest"
    },
    "sigma": {
      "source_ip":        "SourceAddress",
      "target_username":  "TargetUserName",
      "target_hostname":  "Computer"
    }
  }
}
```

**Entity Types:**

| Type | Description | Common Fields |
|---|---|---|
| `ip_address` | IPv4/IPv6 address or CIDR range | source_ip, dest_ip |
| `user_account` | Domain or local user account | username, upn, sam_account |
| `host` | Endpoint or server hostname | hostname, fqdn, device_id |
| `process` | Running process | process_name, process_id, cmdline |
| `file` | File system object | file_path, file_hash, file_name |
| `domain` | DNS domain name | domain, fqdn |
| `url` | Web resource | url, uri, request_url |
| `registry_key` | Windows registry path | registry_key, registry_value |

---

### 15.5 Section 4 — Temporal Logic

Defines time-based constraints that are critical for accurate detection.

```json
"temporal_logic": {
  "timeframe": {
    "duration": 10,
    "unit": "minutes",
    "type": "sliding_window"
  },
  "sequence": {
    "enabled": true,
    "ordered": true,
    "max_span": {
      "duration": 30,
      "unit": "minutes"
    },
    "events": [
      {
        "step": 1,
        "event_type": "authentication_failure",
        "min_occurrences": 5
      },
      {
        "step": 2,
        "event_type": "authentication_success",
        "min_occurrences": 1,
        "within": {
          "duration": 5,
          "unit": "minutes",
          "relative_to": "step_1_last_event"
        }
      }
    ]
  },
  "scheduling": {
    "run_every": "5m",
    "lookback": "15m"
  }
}
```

**Temporal Window Types:**

| Type | Description | Use Case |
|---|---|---|
| `sliding_window` | Rolling time window, evaluated continuously | Count-based threshold detections |
| `fixed_window` | Aligned to clock boundaries (hourly, daily) | Anomaly baseline comparisons |
| `session_window` | Group events by inactivity gap | User session analysis |
| `sequence_window` | Order-sensitive event chain within max span | Multi-step attack detection |

---

### 15.6 Section 5 — MITRE Mapping

Links the detection to the MITRE ATT&CK framework for coverage tracking.

```json
"mitre_mapping": [
  {
    "tactic": "Credential Access",
    "tactic_id": "TA0006",
    "technique": "Brute Force",
    "technique_id": "T1110",
    "sub_technique": "Password Spraying",
    "sub_technique_id": "T1110.003",
    "confidence": 0.90,
    "rationale": "Multiple failed authentications from single IP targeting multiple accounts matches password spraying pattern"
  }
]
```

---

### 15.7 Section 6 — Output Configuration

Controls which platforms the rule should be generated for and any platform-specific overrides.

```json
"output_config": {
  "target_platforms": ["sigma", "kql", "spl"],
  "primary_platform": "sigma",
  "platform_overrides": {
    "kql": {
      "table": "SecurityEvent",
      "time_column": "TimeGenerated",
      "additional_filters": "| where Computer !startswith 'DC'"
    },
    "spl": {
      "index": "wineventlog",
      "sourcetype": "WinEventLog:Security"
    }
  },
  "output_format": "files",
  "output_directory": "generated_rules/"
}
```

---

### 15.8 Section 7 — Provenance

Traces every IR field back to the source text, enabling explainability and debugging.

```json
"provenance": {
  "source_document": "brute_force_sop_v2.txt",
  "extraction_timestamp": "2026-05-19T14:23:01Z",
  "agent_versions": {
    "threat_intel": "1.2.0",
    "metadata": "1.1.0",
    "entity_extraction": "1.2.1",
    "mitre_mapping": "1.3.0",
    "ir_builder": "1.4.0"
  },
  "field_sources": {
    "detection_logic.filters[0].value": {
      "source_text": "Event ID 4625 indicates a failed logon attempt",
      "char_offset": [142, 195],
      "agent": "entity_extraction",
      "confidence": 0.99
    },
    "temporal_logic.timeframe.duration": {
      "source_text": "more than 5 failed attempts within 10 minutes",
      "char_offset": [67, 112],
      "agent": "threat_intel",
      "confidence": 0.93
    },
    "mitre_mapping[0].technique_id": {
      "source_text": "credential stuffing or password spraying attack",
      "char_offset": [23, 66],
      "agent": "mitre_mapping",
      "confidence": 0.88
    }
  }
}
```

---

## 16. IR Design Rationale

### 16.1 Why JSON (not YAML or XML)?

| Format | Pros | Cons | Decision |
|---|---|---|---|
| **JSON** | Universal tooling, strict typing, Pydantic-native, easy to validate | Verbose, no comments | ✅ **Chosen** |
| YAML | Human-readable, concise, supports comments | Parsing ambiguities, indentation errors, less strict | ❌ |
| XML | Schema validation (XSD), well-established | Extremely verbose, poor Python ergonomics | ❌ |

JSON was chosen because it integrates natively with Pydantic (schema validation), Python dicts (agent I/O), FastAPI (REST responses), and LangChain's structured output parsers.

### 16.2 Why Separate Filters from Aggregations?

Filters and aggregations are conceptually distinct operations:
- **Filters** narrow the event stream: `WHERE EventID = 4625`
- **Aggregations** compute statistics: `COUNT(*) GROUP BY source_ip`
- **Threshold** applies to the aggregation result: `HAVING count > 5`

Keeping them separate in the IR means:
- Filters compile into `where` clauses in KQL, `search` in SPL, `selection` in Sigma
- Aggregations compile into `summarize` in KQL, `stats` in SPL, `count` modifier in Sigma
- Each has its own validation logic

### 16.3 Why Mandatory Temporal Logic?

One of the most common detection engineering errors is omitting time constraints. A rule that counts events across all time is meaningless for real-time detection. The IR makes `temporal_logic.timeframe` a **required field** — the validation engine rejects any rule generated from an IR without it.

### 16.4 Why Per-Platform Entity Mapping in the IR?

Rather than storing abstract field names and resolving them only at generation time, the IR pre-computes the mapping for each target platform. This:
- Makes the Schema Mapper's work explicit and auditable
- Allows the Repair Agent to fix field names at the IR level
- Enables the Validation Agent to check field existence per platform before generating code

### 16.5 Why Confidence Scores on IR Fields?

Every extracted field carries a confidence score (0.0–1.0) from the extracting agent. This enables:
- **Repair prioritization**: The Repair Agent focuses first on low-confidence fields
- **Human review flagging**: Fields below a threshold (e.g., < 0.7) are highlighted for human review
- **Quality metrics**: Aggregate confidence scores predict overall rule reliability

---

## 17. Worked Examples — NL to IR Transformation

### 17.1 Example 1 — Brute Force Login Detection

**Input Text (from SOP):**
```
Section 3.2: Brute Force Detection Policy
If more than 5 failed Windows login attempts (Event ID 4625) are observed
from a single source IP address within a 10-minute window, an alert should
be raised. The alert should be classified as HIGH severity. Accounts locked
by automated systems (source IP in 10.0.0.0/8) should be excluded.
This behavior maps to MITRE ATT&CK T1110 (Brute Force).
```

**Extracted by Agents:**
- **Threat Intel**: event=auth_failure, threshold=5, window=10min, group_by=source_ip
- **Entity**: event_id=4625, source_ip, exclusion=10.0.0.0/8
- **Metadata**: severity=high, tags=[brute_force, windows]
- **MITRE**: T1110 (Brute Force), TA0006 (Credential Access)

**Resulting Security IR (abbreviated):**
```json
{
  "metadata": { "severity": "high", "rule_name": "Brute Force Login - Windows" },
  "detection_logic": {
    "event_type": "authentication_failure",
    "filters": [{"field": "event_id", "operator": "equals", "value": 4625}],
    "exclusions": [{"field": "source_ip", "operator": "in_cidr", "value": "10.0.0.0/8"}],
    "aggregation": { "function": "count", "group_by": ["source_ip"],
                     "threshold": {"operator": "greater_than", "value": 5} }
  },
  "temporal_logic": { "timeframe": {"duration": 10, "unit": "minutes"} },
  "mitre_mapping": [{"technique_id": "T1110", "tactic_id": "TA0006"}]
}
```

**Generated Sigma Rule:**
```yaml
title: Brute Force Login - Windows
id: a3f9c1d2-8b4e-4f2a-9c7d-1e5f3a2b8d4c
status: experimental
description: >
  Detects brute force login attempts by monitoring for more than 5 failed
  Windows authentication events from a single source IP within 10 minutes.
author: IR-Framework v1.0 (Auto-Generated)
date: 2026/05/19
tags:
  - attack.credential_access
  - attack.t1110
logsource:
  product: windows
  service: security
detection:
  selection:
    EventID: 4625
  filter_internal:
    SourceAddress|cidr: '10.0.0.0/8'
  condition: selection and not filter_internal | count(SourceAddress) > 5
timeframe: 10m
level: high
falsepositives:
  - Legitimate users who mistype passwords repeatedly
  - IT helpdesk bulk account resets
```

**Generated KQL Rule:**
```kql
SecurityEvent
| where TimeGenerated > ago(10m)
| where EventID == 4625
| where IpAddress !startswith "10."
| summarize FailedAttempts = count() by IpAddress, bin(TimeGenerated, 10m)
| where FailedAttempts > 5
| extend AlertSeverity = "High"
| extend MitreTechnique = "T1110 - Brute Force"
| project TimeGenerated, IpAddress, FailedAttempts, AlertSeverity, MitreTechnique
```

**Generated SPL Rule:**
```spl
index=wineventlog sourcetype="WinEventLog:Security" EventCode=4625 earliest=-10m
| where NOT match(src_ip, "^10\.")
| stats count as FailedAttempts by src_ip
| where FailedAttempts > 5
| eval Severity="High", MitreTechnique="T1110"
| table src_ip, FailedAttempts, Severity, MitreTechnique
```

---

### 17.2 Example 2 — Lateral Movement via Remote Service Creation

**Input Text:**
```
Threat Report: PsExec-Style Lateral Movement
Adversaries are observed using remote service creation to move laterally.
Specifically, Windows Service Control Manager (SCM) is used to install
services on remote hosts. This manifests as Event ID 7045 (service installed)
on the target host, combined with Event ID 4624 (successful logon) of type 3
(network logon) within 5 minutes on the same host. Severity: Critical.
MITRE: T1021.002 (Remote Services: SMB/Windows Admin Shares).
```

**Resulting Security IR (abbreviated):**
```json
{
  "metadata": {"severity": "critical", "rule_name": "Lateral Movement - Remote Service Creation"},
  "detection_logic": {
    "event_type": "lateral_movement_indicator",
    "filters": [{"field": "event_id", "operator": "in", "value": [7045]}],
    "correlation": {
      "type": "sequence",
      "events": [
        {"event_type": "service_installation", "filter": {"event_id": 7045}, "role": "trigger"},
        {"event_type": "network_logon", "filter": {"event_id": 4624, "logon_type": 3}, "role": "precursor"}
      ],
      "same_entity": "target_hostname",
      "ordering": "precursor_before_trigger"
    }
  },
  "temporal_logic": {
    "timeframe": {"duration": 5, "unit": "minutes"},
    "sequence": {"enabled": true, "ordered": true}
  },
  "mitre_mapping": [{"technique_id": "T1021.002", "tactic_id": "TA0008"}]
}
```

**Generated KQL Rule:**
```kql
let NetworkLogons = SecurityEvent
| where TimeGenerated > ago(30m)
| where EventID == 4624 and LogonType == 3
| project LogonTime=TimeGenerated, Computer, Account, IpAddress;

let ServiceInstalls = SecurityEvent
| where TimeGenerated > ago(30m)
| where EventID == 7045
| project InstallTime=TimeGenerated, Computer, ServiceName, ServiceFileName;

NetworkLogons
| join kind=inner ServiceInstalls on Computer
| where InstallTime between (LogonTime .. LogonTime + 5m)
| extend AlertSeverity = "Critical"
| extend MitreTechnique = "T1021.002 - Remote Services: SMB/Windows Admin Shares"
| project LogonTime, InstallTime, Computer, Account, IpAddress,
          ServiceName, ServiceFileName, AlertSeverity, MitreTechnique
```

---

### 17.3 Example 3 — Data Exfiltration via Large Outbound Transfer

**Input Text:**
```
Data Loss Prevention SOP — Section 7:
Alert when any single endpoint transfers more than 500MB of data to an
external IP address (non-RFC1918) over any protocol within a 1-hour window.
This applies to servers in the 172.16.0.0/12 range. Exclude known backup
destinations: 203.0.113.0/24. Severity: Critical. MITRE: T1041.
```

**Resulting Security IR (abbreviated):**
```json
{
  "metadata": {"severity": "critical", "rule_name": "Potential Data Exfiltration - Large Outbound Transfer"},
  "detection_logic": {
    "event_type": "network_connection",
    "filters": [
      {"field": "source_ip", "operator": "in_cidr", "value": "172.16.0.0/12"},
      {"field": "dest_ip", "operator": "not_in_cidr", "value": ["10.0.0.0/8","172.16.0.0/12","192.168.0.0/16"]},
      {"field": "direction", "operator": "equals", "value": "outbound"}
    ],
    "exclusions": [
      {"field": "dest_ip", "operator": "in_cidr", "value": "203.0.113.0/24", "reason": "Known backup destination"}
    ],
    "aggregation": {
      "function": "sum",
      "target_field": "bytes_sent",
      "group_by": ["source_ip", "dest_ip"],
      "threshold": {"operator": "greater_than", "value": 524288000}
    }
  },
  "temporal_logic": {"timeframe": {"duration": 60, "unit": "minutes"}},
  "mitre_mapping": [{"technique_id": "T1041", "tactic_id": "TA0010"}]
}
```

**Generated Sigma Rule:**
```yaml
title: Potential Data Exfiltration - Large Outbound Transfer
status: experimental
description: >
  Detects potential data exfiltration when a single source IP in the
  172.16.0.0/12 range transfers more than 500MB to an external IP in 1 hour.
tags:
  - attack.exfiltration
  - attack.t1041
logsource:
  category: network_connection
detection:
  selection:
    src_ip|cidr: '172.16.0.0/12'
    direction: 'outbound'
  filter_rfc1918_dest:
    dst_ip|cidr:
      - '10.0.0.0/8'
      - '172.16.0.0/12'
      - '192.168.0.0/16'
  filter_backup:
    dst_ip|cidr: '203.0.113.0/24'
  condition: >
    selection and not filter_rfc1918_dest and not filter_backup
    | sum(bytes_sent) by src_ip, dst_ip > 524288000
timeframe: 60m
level: critical
```

---

*End of Part IV. Part V continues below.*

---
---

# PART V — SCHEMA NORMALIZATION

---

## 18. Schema Normalization Theory

### 18.1 The Root Cause of Field Incompatibility

Every SIEM platform ingests logs from the same underlying sources — Windows Event Logs, Linux syslogs, cloud API logs — but each platform independently decided how to name fields when storing that data. The result is a fragmented ecosystem where the same concept has a different name on every platform:

| Concept | Windows Raw Log | Microsoft Sentinel | Splunk CIM | AWS CloudTrail | Elastic ECS |
|---|---|---|---|---|---|
| Source IP address | IpAddress | IpAddress | src_ip | sourceIPAddress | source.ip |
| Username | TargetUserName | TargetUserName | user | userIdentity.userName | user.name |
| Hostname | Computer | Computer | dest | requestParameters.instanceId | host.hostname |
| Process name | Image | Process | process_name | — | process.name |
| Event timestamp | TimeCreated | TimeGenerated | _time | eventTime | @timestamp |
| Domain name | SubjectDomainName | SubjectDomainName | src_nt_domain | — | user.domain |
| Bytes transferred | — | SentBytes | bytes_out | — | destination.bytes |
| Parent process | ParentProcessId | ParentProcessName | parent_process | — | process.parent.name |

Without normalization, every detection rule is brittle — it works on one platform and breaks on all others. The Schema Mapper's job is to resolve these differences using two industry standards: **OCSF** and **ASIM**.

### 18.2 The Two-Layer Normalization Approach

This framework uses a **two-layer normalization strategy**:

```
Security IR Fields (abstract, vendor-neutral)
         │
         ▼
Layer 1: OCSF Normalization
  Maps IR abstract fields → OCSF event class fields
  Provides: vendor-neutral semantic standardization
         │
         ▼
Layer 2: ASIM / Platform-Specific Normalization
  Maps OCSF fields → Sentinel ASIM fields / Splunk CIM fields / Sigma fields
  Provides: platform-ready field names for code generation
         │
         ▼
Platform-Specific Rule Generator receives fully resolved field names
```

This two-layer approach means:
- OCSF provides **semantic correctness** (what the field means)
- ASIM/CIM/ECS provides **syntactic correctness** (what the field is called on each platform)

---

## 19. OCSF Deep Dive

### 19.1 What Is OCSF?

The **Open Cybersecurity Schema Framework (OCSF)** is a vendor-neutral, open-source schema standard designed to normalize security telemetry across any source or destination. It was created by a consortium including AWS, Splunk, IBM, and CrowdStrike, and transitioned to **Linux Foundation governance in late 2024**.

OCSF's mission: eliminate the "data normalization tax" that security teams pay when integrating heterogeneous log sources.

**Current version:** OCSF 1.8.0 (March 2026)

### 19.2 OCSF Architecture

OCSF organizes all security events into a hierarchical taxonomy:

```
OCSF Taxonomy
│
├── Categories (top-level groupings)
│   ├── System Activity (1000)
│   ├── Findings (2000)
│   ├── Identity & Access Management (3000)
│   ├── Network Activity (4000)
│   ├── Discovery (5000)
│   ├── Application Activity (6000)
│   └── AI Security (7000)  ← New in v1.8.0
│
├── Event Classes (specific event types within categories)
│   ├── Authentication (3002)
│   ├── Network Connection (4001)
│   ├── Process Activity (1007)
│   ├── File System Activity (1001)
│   └── ... (40+ event classes total)
│
├── Objects (reusable data structures)
│   ├── Actor (who performed the action)
│   ├── Device (the machine involved)
│   ├── Network Interface
│   ├── File
│   ├── Process
│   └── ... (80+ objects)
│
└── Profiles (cross-cutting attribute sets)
    ├── Host Profile (adds host attributes to any event)
    ├── Network Profile (adds network attributes)
    ├── Security Control Profile
    └── AI Operation Profile  ← New in v1.8.0
```

### 19.3 OCSF Event Classes Used by This Project

| OCSF Event Class | Class ID | Used For | Key Fields |
|---|---|---|---|
| **Authentication** | 3002 | Login/logout events, brute force | `actor.user.name`, `src_endpoint.ip`, `status`, `logon_type` |
| **Process Activity** | 1007 | Process creation, execution | `actor.process.name`, `process.cmd_line`, `process.pid` |
| **Network Activity** | 4001 | Connections, flows, traffic | `src_endpoint.ip`, `dst_endpoint.ip`, `traffic.bytes_out` |
| **File System Activity** | 1001 | File create/modify/delete/copy | `file.path`, `file.name`, `file.hash.sha256` |
| **DNS Activity** | 4003 | DNS queries and responses | `query.hostname`, `answers`, `src_endpoint.ip` |
| **Scheduled Job Activity** | 1006 | Scheduled task creation/modification | `job.name`, `job.cmd`, `actor.user.name` |
| **Module Activity** | 1005 | DLL/driver loading | `module.path`, `module.hash`, `actor.process.name` |
| **Registry Key Activity** | 1010 | Registry modifications | `reg_key.path`, `reg_value.data`, `actor.process.name` |

### 19.4 OCSF Base Event Fields

Every OCSF event class includes these base fields:

| OCSF Field | Type | Description |
|---|---|---|
| `class_uid` | int | Event class identifier (e.g., 3002 for Authentication) |
| `class_name` | string | Human-readable class name |
| `category_uid` | int | Category identifier |
| `severity_id` | int | 0=Unknown, 1=Informational, 2=Low, 3=Medium, 4=High, 5=Critical |
| `status` | string | `Success`, `Failure`, `Unknown` |
| `time` | timestamp | Event occurrence time (Unix epoch ms) |
| `metadata.version` | string | OCSF schema version |
| `metadata.product` | object | Generating product info |
| `actor` | object | Who performed the action |
| `device` | object | The device where the event occurred |
| `observables` | array | List of observable entities (IPs, users, files) |

### 19.5 How the IR Maps to OCSF

The Security IR's abstract field names are defined to align with OCSF semantics:

| IR Abstract Field | OCSF Field | Notes |
|---|---|---|
| `source_ip` | `src_endpoint.ip` | Authentication and network events |
| `dest_ip` | `dst_endpoint.ip` | Network connection events |
| `target_username` | `actor.user.name` | Actor performing authentication |
| `target_hostname` | `device.hostname` | Target device |
| `process_name` | `actor.process.name` | Process performing action |
| `cmd_line` | `actor.process.cmd_line` | Command line arguments |
| `file_path` | `file.path` | File system events |
| `file_hash` | `file.hash.sha256` | File integrity |
| `bytes_sent` | `traffic.bytes_out` | Network volume |
| `event_type` | `class_uid` | Mapped via event class table |
| `severity` | `severity_id` | Mapped via severity enum |

---

## 20. ASIM Deep Dive

### 20.1 What Is ASIM?

The **Advanced Security Information Model (ASIM)** is Microsoft's normalization layer for Microsoft Sentinel. It is an abstraction built on top of KQL that allows detection rules and hunting queries to work across any data source that has an ASIM parser — regardless of the underlying table name or field naming convention.

ASIM operates as a **KQL function layer**: instead of querying raw tables like `SecurityEvent` or `SigninLogs`, analysts query normalized ASIM parsers like `_Im_Authentication()` or `_Im_NetworkSession()`.

**Current status (2026):** ASIM received a comprehensive schema refresh in early 2026 for consistent field coverage across all activity types.

### 20.2 ASIM Schema Categories

| ASIM Schema | Parser Function | Covers |
|---|---|---|
| **Authentication** | `_Im_Authentication()` | Sign-ins, logons, MFA events |
| **Network Session** | `_Im_NetworkSession()` | TCP/UDP connections, firewall logs |
| **DNS Activity** | `_Im_Dns()` | DNS queries from any resolver |
| **Process Events** | `_Im_ProcessCreate()` | Process creation from any EDR |
| **File Events** | `_Im_FileEvent()` | File create/delete/modify |
| **Registry Events** | `_Im_RegistryEvent()` | Registry key operations |
| **User Management** | `_Im_UserManagement()` | Account create/delete/modify |
| **Alert Events** | `_Im_AlertEvent()` | Security alerts from any source |
| **Web Session** | `_Im_WebSession()` | HTTP/HTTPS proxy and WAF logs |

### 20.3 ASIM Authentication Schema Fields

The Authentication schema is the most commonly used for detection rules:

| ASIM Field | Type | Description | Maps From |
|---|---|---|---|
| `TimeGenerated` | datetime | Event time | Windows: TimeGenerated |
| `EventType` | string | `Logon`, `Logoff`, `Elevate` | Derived from EventID |
| `EventResult` | string | `Success`, `Failure` | Windows: EventID (4624=Success, 4625=Failure) |
| `EventResultDetails` | string | Failure reason | Windows: Status/SubStatus |
| `SrcIpAddr` | string | Source IP address | Windows: IpAddress |
| `SrcHostname` | string | Source hostname | Windows: WorkstationName |
| `TargetUsername` | string | Target account name | Windows: TargetUserName |
| `TargetUsernameType` | string | `UPN`, `Windows`, `Simple` | Derived from account format |
| `TargetDomain` | string | Target account domain | Windows: TargetDomainName |
| `LogonMethod` | string | `Interactive`, `Network`, `RemoteInteractive` | Windows: LogonType |
| `DvcHostname` | string | Device where event occurred | Windows: Computer |
| `DvcId` | string | Device ID | Platform-specific |

### 20.4 ASIM-Based KQL Rule Pattern

Using ASIM, a detection rule becomes **source-agnostic**:

```kql
// ASIM-based brute force detection — works for ANY log source with Authentication parser
_Im_Authentication(starttime=ago(10m), eventresult='Failure')
| summarize FailedAttempts = count(),
            TargetAccounts = distinct_count(TargetUsername)
  by SrcIpAddr, bin(TimeGenerated, 5m)
| where FailedAttempts > 5
| extend AlertSeverity = "High"
| extend MitreTechnique = "T1110 - Brute Force"
```

vs. the raw table approach which only works for Windows:

```kql
// Raw table approach — only works for Windows Event Logs
SecurityEvent
| where TimeGenerated > ago(10m)
| where EventID == 4625
| summarize count() by IpAddress
| where count_ > 5
```

### 20.5 ASIM Parser Architecture

```
Raw Data Sources               ASIM Parsers              Unified Queries
─────────────────              ────────────              ───────────────
Windows Security Events ──→ M_AAD_Authentication ──→          │
Azure AD Sign-In Logs   ──→ M_WindowsSecurity_Auth ──→ _Im_Authentication()
Okta Auth Logs          ──→ M_Okta_Authentication ──→         │
AWS Cognito Logs        ──→ M_AWS_Authentication ──→          │
                                                        Detection Rules
                                                        Hunting Queries
                                                        Workbooks
```

---

## 21. Cross-Platform Field Mapping Tables

### 21.1 Authentication Event Fields

| IR Abstract Field | OCSF Field | Sentinel (Raw) | Sentinel (ASIM) | Splunk CIM | Sigma |
|---|---|---|---|---|---|
| `source_ip` | `src_endpoint.ip` | `IpAddress` | `SrcIpAddr` | `src_ip` | `SourceAddress` |
| `target_username` | `actor.user.name` | `TargetUserName` | `TargetUsername` | `user` | `TargetUserName` |
| `target_domain` | `actor.user.domain` | `TargetDomainName` | `TargetDomain` | `src_nt_domain` | `TargetDomainName` |
| `target_hostname` | `device.hostname` | `Computer` | `DvcHostname` | `dest` | `Computer` |
| `source_hostname` | `src_endpoint.hostname` | `WorkstationName` | `SrcHostname` | `src_host` | `WorkstationName` |
| `event_result` | `status` | `EventID` (4624/4625) | `EventResult` | `action` | `EventID` |
| `logon_type` | `logon_type` | `LogonType` | `LogonMethod` | `LogonType` | `LogonType` |
| `logon_process` | `actor.process.name` | `LogonProcessName` | `LogonProtocol` | `LogonProcess` | `LogonProcessName` |
| `failure_reason` | `status_detail` | `Status` | `EventResultDetails` | `SubStatus` | `Status` |
| `event_time` | `time` | `TimeGenerated` | `TimeGenerated` | `_time` | — |

### 21.2 Process Creation Event Fields

| IR Abstract Field | OCSF Field | Sentinel (SecurityEvent) | Sentinel (ASIM) | Splunk CIM | Sigma |
|---|---|---|---|---|---|
| `process_name` | `process.name` | `Process` | `TargetProcessName` | `process_name` | `Image` |
| `process_id` | `process.pid` | `NewProcessId` | `TargetProcessId` | `process_id` | `ProcessId` |
| `cmd_line` | `process.cmd_line` | `CommandLine` | `TargetProcessCommandLine` | `process` | `CommandLine` |
| `parent_process` | `parent_process.name` | `ParentProcessName` | `ActingProcessName` | `parent_process_name` | `ParentImage` |
| `parent_pid` | `parent_process.pid` | `ProcessId` | `ActingProcessId` | `parent_process_id` | `ParentProcessId` |
| `user` | `actor.user.name` | `SubjectUserName` | `ActorUsername` | `user` | `User` |
| `hostname` | `device.hostname` | `Computer` | `DvcHostname` | `dest` | `ComputerName` |
| `file_hash` | `process.file.hash.sha256` | `FileHash` | `TargetProcessMD5` | `process_hash` | `Hashes` |
| `event_id` | `class_uid` | `EventID` | — | — | `EventID` |

### 21.3 Network Connection Event Fields

| IR Abstract Field | OCSF Field | Sentinel (AzureNetworkAnalytics) | Sentinel (ASIM) | Splunk CIM | Sigma |
|---|---|---|---|---|---|
| `source_ip` | `src_endpoint.ip` | `SrcIp` | `SrcIpAddr` | `src_ip` | `src_ip` |
| `dest_ip` | `dst_endpoint.ip` | `DestIp` | `DstIpAddr` | `dest_ip` | `dst_ip` |
| `source_port` | `src_endpoint.port` | `SrcPort` | `SrcPortNumber` | `src_port` | `src_port` |
| `dest_port` | `dst_endpoint.port` | `DestPort` | `DstPortNumber` | `dest_port` | `dst_port` |
| `protocol` | `protocol_name` | `L4Protocol` | `NetworkProtocol` | `transport` | `Protocol` |
| `bytes_sent` | `traffic.bytes_out` | `OutboundBytes` | `DstBytes` | `bytes_out` | — |
| `bytes_received` | `traffic.bytes_in` | `InboundBytes` | `SrcBytes` | `bytes_in` | — |
| `action` | `disposition` | `FlowDirection` | `DvcAction` | `action` | `Initiated` |
| `direction` | `direction` | `FlowType` | `NetworkDirection` | `direction` | — |

### 21.4 DNS Activity Event Fields

| IR Abstract Field | OCSF Field | Sentinel (DnsEvents) | Sentinel (ASIM) | Splunk Stream | Sigma |
|---|---|---|---|---|---|
| `query_name` | `query.hostname` | `Name` | `DnsQuery` | `query` | `QueryName` |
| `query_type` | `query.type` | `QueryType` | `DnsQueryType` | `record_type` | `QueryType` |
| `response_code` | `rcode` | `ResponseCode` | `DnsResponseCode` | `reply_code` | `QueryStatus` |
| `source_ip` | `src_endpoint.ip` | `ClientIP` | `SrcIpAddr` | `src_ip` | `src_ip` |
| `answers` | `answers` | `IPAddresses` | `DnsResponseName` | `answer` | `QueryResults` |
| `hostname` | `device.hostname` | `Computer` | `DvcHostname` | `src_host` | `Computer` |

### 21.5 File Activity Event Fields

| IR Abstract Field | OCSF Field | Sentinel (ASIM) | Splunk CIM | Sigma |
|---|---|---|---|---|
| `file_path` | `file.path` | `TargetFilePath` | `file_path` | `TargetFilename` |
| `file_name` | `file.name` | `TargetFileName` | `file_name` | `TargetFilename` |
| `file_hash_md5` | `file.hash.md5` | `TargetFileMD5` | `file_hash` | `Hashes` |
| `file_hash_sha256` | `file.hash.sha256` | `TargetFileSHA256` | `file_hash` | `Hashes` |
| `file_size` | `file.size` | `TargetFileSize` | `file_size` | — |
| `action_type` | `activity_name` | `EventType` | `action` | `EventType` |
| `actor_user` | `actor.user.name` | `ActorUsername` | `user` | `User` |
| `actor_process` | `actor.process.name` | `ActingProcessName` | `process_name` | `Image` |

---

## 22. Custom Vendor Mapper Design

### 22.1 Architecture of the Schema Mapper Module

The Schema Mapper is a pure Python module that takes the Security IR and produces a **normalized IR** with platform-specific field names pre-resolved for each target generator.

```python
class SchemaMapper:
    """
    Maps Security IR abstract fields to platform-specific field names
    using OCSF as the semantic layer and ASIM/CIM/Sigma as the syntactic layer.
    """

    def __init__(self, schema_dir: str = "config/schemas/"):
        self.ocsf_schema = self._load_schema(f"{schema_dir}/ocsf_1.8.yaml")
        self.asim_schema = self._load_schema(f"{schema_dir}/asim_2026.yaml")
        self.splunk_cim = self._load_schema(f"{schema_dir}/splunk_cim_5.yaml")
        self.sigma_fields = self._load_schema(f"{schema_dir}/sigma_fields.yaml")
        self.custom_mappings = self._load_schema(f"{schema_dir}/custom_vendor.yaml")

    def map_ir(self, ir: SecurityIR, platforms: List[str]) -> NormalizedIR:
        normalized = ir.copy()
        for platform in platforms:
            normalized.entity_mapping.siem_entity_mapping[platform] = \
                self._resolve_fields(ir, platform)
        return normalized

    def _resolve_fields(self, ir: SecurityIR, platform: str) -> Dict[str, str]:
        """Resolve each IR abstract field to platform-specific field name."""
        event_class = self._get_ocsf_class(ir.detection_logic.event_type)
        mappings = {}
        for abstract_field in ir.get_all_fields():
            ocsf_field = self.ocsf_schema.resolve(event_class, abstract_field)
            platform_field = self._to_platform(ocsf_field, platform)
            mappings[abstract_field] = platform_field
        return mappings

    def _to_platform(self, ocsf_field: str, platform: str) -> str:
        lookup = {
            "sentinel_asim": self.asim_schema,
            "sentinel_raw":  self.asim_schema,  # with raw table fallback
            "splunk":        self.splunk_cim,
            "sigma":         self.sigma_fields,
        }
        schema = lookup.get(platform)
        return schema.get(ocsf_field, ocsf_field)  # fallback: use OCSF name
```

### 22.2 Schema Configuration Files

All mapping tables are stored as YAML configuration files — not hardcoded in Python. This makes the mapper fully extensible without code changes:

**`config/schemas/ocsf_to_asim.yaml`** (excerpt):
```yaml
# Maps OCSF field paths → ASIM field names
authentication:
  src_endpoint.ip:         SrcIpAddr
  actor.user.name:         TargetUsername
  actor.user.domain:       TargetDomain
  device.hostname:         DvcHostname
  status:                  EventResult
  logon_type:              LogonMethod

network_session:
  src_endpoint.ip:         SrcIpAddr
  dst_endpoint.ip:         DstIpAddr
  src_endpoint.port:       SrcPortNumber
  dst_endpoint.port:       DstPortNumber
  traffic.bytes_out:       DstBytes
  traffic.bytes_in:        SrcBytes
  protocol_name:           NetworkProtocol
```

**`config/schemas/ocsf_to_splunk_cim.yaml`** (excerpt):
```yaml
authentication:
  src_endpoint.ip:         src_ip
  actor.user.name:         user
  device.hostname:         dest
  status:                  action
  logon_type:              LogonType

network_session:
  src_endpoint.ip:         src_ip
  dst_endpoint.ip:         dest_ip
  src_endpoint.port:       src_port
  dst_endpoint.port:       dest_port
  traffic.bytes_out:       bytes_out
  protocol_name:           transport
```

### 22.3 Adding a New SIEM Platform

To add support for a new platform (e.g., Elastic ECS, Google Chronicle YARA-L), only two steps are needed:

**Step 1:** Add a YAML schema file `config/schemas/ocsf_to_elastic_ecs.yaml`:
```yaml
authentication:
  src_endpoint.ip:         source.ip
  actor.user.name:         user.name
  device.hostname:         host.hostname
  status:                  event.outcome
  logon_type:              process.name   # ECS uses different model

process_activity:
  process.name:            process.name
  process.cmd_line:        process.command_line
  actor.process.name:      process.parent.name
```

**Step 2:** Register the platform in `config/platforms.yaml`:
```yaml
platforms:
  elastic_ecs:
    schema_file: ocsf_to_elastic_ecs.yaml
    generator_class: ElasticESQLGenerator
    output_format: esql
    validation_parser: elastic_validator
```

No other code changes are required. The pipeline automatically picks up the new platform configuration.

### 22.4 Field Validation at Mapping Time

The Schema Mapper validates every resolved field against a **field existence registry** — a database of fields that actually exist in each platform's data model:

```python
class FieldValidator:
    def __init__(self, platform_field_registry: dict):
        self.registry = platform_field_registry

    def validate_field(self, platform: str, field_name: str) -> ValidationResult:
        known_fields = self.registry.get(platform, {})
        if field_name not in known_fields:
            return ValidationResult(
                valid=False,
                error=f"Field '{field_name}' does not exist in {platform} schema",
                suggestions=self._fuzzy_match(field_name, known_fields)
            )
        return ValidationResult(valid=True, field_type=known_fields[field_name])

    def _fuzzy_match(self, field: str, known: dict) -> List[str]:
        """Return closest matching field names for repair suggestions."""
        from difflib import get_close_matches
        return get_close_matches(field, known.keys(), n=3, cutoff=0.6)
```

If a field fails validation, the Repair Agent receives the error with fuzzy-matched suggestions, enabling targeted fixes.

### 22.5 OCSF Event Class to Log Source Mapping

| Attack Behavior | OCSF Event Class | Windows Log Source | Azure Log Source | AWS Log Source |
|---|---|---|---|---|
| Failed authentication | Authentication (3002) | SecurityEvent (4625) | SigninLogs | CloudTrail: ConsoleLogin |
| Process execution | Process Activity (1007) | SecurityEvent (4688) | — | CloudTrail: RunInstances |
| Network connection | Network Activity (4001) | — | AzureNetworkAnalytics | VPC Flow Logs |
| File creation | File System Activity (1001) | Sysmon (Event 11) | — | S3 Access Logs |
| DNS query | DNS Activity (4003) | DNS Server Logs | DnsEvents | Route53 Logs |
| Registry modification | Registry Key Activity (1010) | Sysmon (Event 12/13) | — | — |
| Scheduled task creation | Scheduled Job Activity (1006) | SecurityEvent (4698) | — | CloudTrail: PutRule |
| Service installation | Module Activity (1005) | System (Event 7045) | — | — |

---

*End of Part V. Part VI continues below.*

---
---

# PART VI — RULE GENERATION PIPELINE

---

## 23. Rule Generation Architecture

### 23.1 IR to Rule — The Compilation Step

Once the Security IR is built and schema-normalized, the Rule Generator layer performs a **deterministic, template-driven compilation** from IR JSON into platform-specific query code. This is the most important architectural decision in the entire system: **rule generation uses templates, not LLMs**.

Why templates instead of LLMs for generation?

| Criterion | Template-Based | LLM-Based |
|---|---|---|
| Syntax correctness | 100% (if template is correct) | 70–85% (hallucinations occur) |
| Determinism | Identical input → identical output | Non-deterministic |
| Debuggability | Clear mapping from IR field → output line | Opaque reasoning |
| Speed | Milliseconds | Seconds (API call overhead) |
| Cost | Zero per generation | API token cost per call |
| Maintainability | Edit template once, all rules update | Requires re-prompting |

The LLMs are used **exclusively for extraction and reasoning** (agents 1–6). Generation is handled by deterministic Jinja2 templates.

### 23.2 Generator Architecture

```
NormalizedIR
    │
    ├──▶ SigmaGenerator  ──▶  sigma_rule.yaml
    ├──▶ KQLGenerator    ──▶  kql_rule.kql
    └──▶ SPLGenerator    ──▶  spl_rule.spl

Each Generator:
  1. Validates IR has required fields for this platform
  2. Selects appropriate template based on detection_logic.event_type
  3. Renders template with IR field values
  4. Applies platform-specific post-processing
  5. Returns rendered rule string
```

### 23.3 Template Selection Logic

Each generator maintains a **template registry** — a mapping from IR `event_type` to the appropriate Jinja2 template file:

```python
SIGMA_TEMPLATES = {
    "authentication_failure":   "sigma/auth_failure.j2",
    "process_creation":         "sigma/process_creation.j2",
    "network_connection":       "sigma/network_connection.j2",
    "file_activity":            "sigma/file_activity.j2",
    "dns_query":                "sigma/dns_query.j2",
    "registry_modification":    "sigma/registry_mod.j2",
    "scheduled_task":           "sigma/scheduled_task.j2",
    "service_installation":     "sigma/service_install.j2",
    "lateral_movement":         "sigma/lateral_movement.j2",
    "generic":                  "sigma/generic.j2",    # fallback
}
```

If no specific template matches, the `generic` fallback template handles the IR using its full filter list without event-type-specific optimizations.

---

## 24. Sigma Rules Deep Dive

### 24.1 What Is Sigma?

Sigma is an open, vendor-neutral, YAML-based detection rule format. It serves as the **universal language for detection logic** — a Sigma rule can be converted into KQL, SPL, YARA-L, Lucene, or any other platform format using the `pySigma` conversion toolchain.

- **Maintained by:** SigmaHQ community
- **Current spec:** Sigma Specification v2.1.0
- **Repository:** github.com/SigmaHQ/sigma-specification
- **Converter:** pySigma library (Python)

### 24.2 Full Sigma Rule Structure

```yaml
# ── METADATA BLOCK ──────────────────────────────────────────
title: Brute Force Login - Windows Authentication
id: a3f9c1d2-8b4e-4f2a-9c7d-1e5f3a2b8d4c   # UUID v4 — unique per rule
status: experimental    # experimental | test | stable | deprecated
description: >
  Detects brute force login attempts by identifying more than 5 failed
  Windows authentication events from a single source IP within 10 minutes.
author: IR-Framework v1.0 (Auto-Generated)
date: 2026/05/19
modified: 2026/05/19
references:
  - https://attack.mitre.org/techniques/T1110/
  - https://docs.microsoft.com/en-us/windows/security/threat-protection/auditing/event-4625

# ── CLASSIFICATION BLOCK ────────────────────────────────────
tags:
  - attack.credential_access    # MITRE tactic
  - attack.t1110                # MITRE technique
  - attack.t1110.003            # MITRE sub-technique
level: high                     # informational | low | medium | high | critical
falsepositives:
  - Legitimate users who mistype passwords repeatedly
  - Password synchronization tools
  - IT helpdesk bulk account resets

# ── LOG SOURCE BLOCK ─────────────────────────────────────────
logsource:
  product: windows               # windows | linux | aws | azure | gcp
  service: security              # security | system | application | sysmon
  # category: authentication    # alternative to product+service

# ── DETECTION BLOCK ──────────────────────────────────────────
detection:
  # Named selection — events matching this are candidates
  selection:
    EventID: 4625               # Failed logon
    LogonType|in:               # Network, NetworkCleartext, RemoteInteractive
      - 3
      - 8
      - 10

  # Named filter — events matching this are excluded
  filter_internal:
    SourceAddress|cidr: '10.0.0.0/8'   # Exclude internal IPs

  # Condition — logical expression combining selections and filters
  condition: selection and not filter_internal | count(SourceAddress) > 5

# ── TEMPORAL CONSTRAINT ──────────────────────────────────────
timeframe: 10m
```

### 24.3 Sigma Detection Condition Grammar

The `condition` field is Sigma's most powerful feature. It supports:

| Syntax | Meaning | Example |
|---|---|---|
| `selection` | All events matching selection | `condition: selection` |
| `selection and filter` | Selection AND filter | `condition: sel and filter_legit` |
| `sel and not filter` | Selection excluding filter | `condition: sel and not filter_fp` |
| `sel1 or sel2` | Either selection | `condition: sel_proc or sel_network` |
| `count() > N` | Aggregate threshold | `condition: sel \| count() > 10` |
| `count(field) > N` | Distinct value count | `condition: sel \| count(SrcIP) > 5` |
| `min(field) < N` | Minimum value | `condition: sel \| min(bytes) < 100` |
| `near sel` | Proximity detection | `condition: sel1 near sel2` |

### 24.4 Sigma Correlation Rules (v2.1.0+)

The Sigma v2.1.0 specification adds **Correlation Rules** — multi-event detections that combine individual Sigma rules:

```yaml
# Base rule (saved as auth_failure.yaml)
title: Windows Auth Failure Base
name: auth_failure_base
status: experimental
logsource:
  product: windows
  service: security
detection:
  selection:
    EventID: 4625
  condition: selection

---

# Correlation rule — references the base rule
title: Brute Force - Auth Failure Correlation
type: event_count          # event_count | value_count | temporal | temporal_ordered
rules:
  auth_failure: auth_failure_base   # references base rule by name
group-by:
  - SourceAddress
timespan: 10m
condition:
  gte: 5                   # triggers when count >= 5
level: high
```

### 24.5 Sigma Generator Implementation

```python
class SigmaGenerator:
    def __init__(self, template_dir: str = "templates/sigma/"):
        self.env = Environment(loader=FileSystemLoader(template_dir))
        self.templates = SIGMA_TEMPLATES

    def generate(self, ir: NormalizedIR) -> str:
        template_path = self.templates.get(
            ir.detection_logic.event_type,
            "generic.j2"
        )
        template = self.env.get_template(template_path)

        context = {
            "metadata":   ir.metadata,
            "logsource":  self._build_logsource(ir),
            "selections": self._build_selections(ir),
            "filters":    self._build_filters(ir),
            "condition":  self._build_condition(ir),
            "timeframe":  ir.temporal_logic.timeframe,
            "mitre":      ir.mitre_mapping,
        }
        return template.render(**context)

    def _build_condition(self, ir: NormalizedIR) -> str:
        parts = ["selection"]
        if ir.detection_logic.exclusions:
            parts.append("and not filter_exclusions")
        if ir.detection_logic.aggregation:
            agg = ir.detection_logic.aggregation
            op_map = {"greater_than": ">", "less_than": "<", "equals": "=="}
            op = op_map[agg.threshold.operator]
            parts.append(
                f"| {agg.function}({agg.group_by[0] if agg.group_by else ''}) "
                f"{op} {agg.threshold.value}"
            )
        return " ".join(parts)
```

**Jinja2 Template (`sigma/auth_failure.j2`):**
```jinja2
title: {{ metadata.rule_name }}
id: {{ rule_id }}
status: {{ metadata.status }}
description: >
  {{ metadata.description }}
author: {{ metadata.author }}
date: {{ generated_date }}
tags:
{% for m in mitre %}
  - attack.{{ m.tactic_id | lower }}
  - attack.{{ m.technique_id | lower }}
{% if m.sub_technique_id %}
  - attack.{{ m.sub_technique_id | lower }}
{% endif %}
{% endfor %}
{% for tag in metadata.tags %}
  - {{ tag }}
{% endfor %}
logsource:
  product: {{ logsource.product }}
  service: {{ logsource.service }}
detection:
  selection:
{% for f in selections %}
    {{ f.sigma_field }}{% if f.operator == 'in' %}|in:{% else %}: {{ f.value }}{% endif %}
{% if f.operator == 'in' %}
{% for v in f.value %}
      - {{ v }}
{% endfor %}
{% endif %}
{% endfor %}
{% if filters %}
  filter_exclusions:
{% for f in filters %}
    {{ f.sigma_field }}|cidr: '{{ f.value }}'
{% endfor %}
{% endif %}
  condition: {{ condition }}
{% if timeframe %}
timeframe: {{ timeframe.duration }}{{ timeframe.unit[0] }}
{% endif %}
level: {{ metadata.severity }}
falsepositives:
{% for fp in metadata.false_positives %}
  - {{ fp }}
{% endfor %}
```

---

## 25. KQL Deep Dive

### 25.1 What Is KQL?

**Kusto Query Language (KQL)** is Microsoft's query language used in Microsoft Sentinel, Azure Monitor, Azure Data Explorer, and Microsoft Defender. It is a **pipe-based, columnar query language** similar in spirit to Unix pipes but purpose-built for time-series log analytics.

### 25.2 KQL Fundamental Operators

| Operator | Purpose | Detection Use Case |
|---|---|---|
| `where` | Filter rows | Narrow to relevant events |
| `summarize` | Aggregate | Count events, group by entity |
| `extend` | Add computed columns | Calculate derived fields, add labels |
| `project` | Select columns | Clean up output for alert display |
| `join` | Combine tables | Correlate events across log sources |
| `union` | Merge tables | Combine multiple log sources |
| `let` | Define variable/subquery | Named intermediate datasets |
| `bin()` | Time bucketing | Align events to time windows |
| `ago()` | Relative time | `ago(10m)` = 10 minutes ago |
| `distinct_count()` | Distinct count | Count unique values |
| `make_set()` | Collect distinct values | Aggregate related entities |
| `arg_max()` | Latest record per group | Most recent event per user |

### 25.3 KQL Detection Rule Patterns

#### Pattern 1: Simple Threshold Detection
```kql
// Detect > 5 failed logins from same IP in 10 minutes
SecurityEvent
| where TimeGenerated > ago(10m)
| where EventID == 4625
| where IpAddress !startswith "10."       // Exclude internal
| summarize FailedAttempts = count(),
            TargetAccounts = make_set(TargetUserName)
  by IpAddress, bin(TimeGenerated, 10m)
| where FailedAttempts > 5
| extend Severity = "High"
| extend MitreTechnique = "T1110 - Brute Force"
| project TimeGenerated, IpAddress, FailedAttempts, TargetAccounts, Severity
```

#### Pattern 2: Sequence / Join Correlation
```kql
// Detect network logon followed by service installation (PsExec-style)
let NetworkLogons = SecurityEvent
    | where TimeGenerated > ago(1h)
    | where EventID == 4624 and LogonType == 3
    | project LogonTime = TimeGenerated, Computer, Account, IpAddress;

let ServiceInstalls = SecurityEvent
    | where TimeGenerated > ago(1h)
    | where EventID == 7045
    | project InstallTime = TimeGenerated, Computer, ServiceName;

NetworkLogons
| join kind=inner ServiceInstalls on Computer
| where InstallTime between (LogonTime .. LogonTime + 5m)
| extend Severity = "Critical"
| extend MitreTechnique = "T1021.002 - Remote Services"
| project LogonTime, InstallTime, Computer, Account, IpAddress, ServiceName, Severity
```

#### Pattern 3: Anomaly / Baseline Deviation
```kql
// Detect process executed from unusual parent (e.g., Word spawning PowerShell)
SecurityEvent
| where TimeGenerated > ago(1h)
| where EventID == 4688
| where ParentProcessName has_any ("winword.exe", "excel.exe", "outlook.exe")
| where Process has_any ("powershell.exe", "cmd.exe", "wscript.exe", "mshta.exe")
| extend Severity = "High"
| extend MitreTechnique = "T1566.001 - Spearphishing Attachment"
| project TimeGenerated, Computer, Account, Process, ParentProcessName,
          CommandLine, Severity, MitreTechnique
```

#### Pattern 4: ASIM-Based Source-Agnostic Rule
```kql
// Same brute force rule — works for Windows, Azure AD, Okta, AWS Cognito
_Im_Authentication(starttime=ago(10m), eventresult='Failure')
| summarize FailedAttempts = count(),
            TargetAccounts = distinct_count(TargetUsername)
  by SrcIpAddr, bin(TimeGenerated, 5m)
| where FailedAttempts > 5
| extend Severity = "High", MitreTechnique = "T1110"
| project TimeGenerated, SrcIpAddr, FailedAttempts, TargetAccounts, Severity
```

### 25.4 KQL Generator Implementation

```python
class KQLGenerator:
    def __init__(self, template_dir: str = "templates/kql/"):
        self.env = Environment(loader=FileSystemLoader(template_dir))

    def generate(self, ir: NormalizedIR) -> str:
        fields = ir.entity_mapping.siem_entity_mapping["sentinel_asim"]
        agg = ir.detection_logic.aggregation
        temporal = ir.temporal_logic

        use_asim = ir.output_config.platform_overrides.get("kql", {}).get("use_asim", True)
        table = self._resolve_table(ir, use_asim)
        time_filter = f"ago({temporal.timeframe.duration}{temporal.timeframe.unit[0]})"

        lines = [table]
        lines.append(f"| where TimeGenerated > {time_filter}")

        for f in ir.detection_logic.filters:
            field = fields.get(f.field, f.field)
            lines.append(self._render_filter(field, f.operator, f.value))

        for excl in ir.detection_logic.exclusions:
            field = fields.get(excl.field, excl.field)
            lines.append(f"| where {field} !has \"{excl.value}\"")

        if agg:
            group_field = fields.get(agg.group_by[0], agg.group_by[0]) if agg.group_by else ""
            op_map = {"greater_than": ">", "less_than": "<", "equals": "=="}
            op = op_map[agg.threshold.operator]
            lines.append(f"| summarize Count = {agg.function}() by {group_field}")
            lines.append(f"| where Count {op} {agg.threshold.value}")

        mitre = ir.mitre_mapping[0] if ir.mitre_mapping else None
        lines.append(f"| extend Severity = \"{ir.metadata.severity.title()}\"")
        if mitre:
            lines.append(f"| extend MitreTechnique = \"{mitre.technique_id} - {mitre.technique}\"")

        return "\n".join(lines)
```

---

## 26. Splunk SPL Deep Dive

### 26.1 What Is SPL?

**Search Processing Language (SPL)** is Splunk's query language. Like KQL, it is pipe-based, but uses a Unix-inspired search syntax derived from grep and awk patterns. SPL is evaluated left-to-right through a pipeline of commands.

### 26.2 Key SPL Commands for Detection

| Command | Purpose | Detection Use |
|---|---|---|
| `search` / `index=` | Filter from index | Select relevant log source |
| `where` | Post-processing filter | Numeric and computed conditions |
| `stats` | Aggregate statistics | `count by src_ip`, `sum(bytes) by user` |
| `eval` | Compute new fields | `eval Severity="High"` |
| `table` | Select output columns | Clean alert output |
| `join` | Correlate datasets | Multi-event detections |
| `transaction` | Group by session | Session-based correlations |
| `timechart` | Time-bucketed stats | Time series aggregations |
| `rex` | Extract with regex | Parse unstructured fields |
| `lookup` | Enrich with CSV/KV | Threat intelligence lookup |

### 26.3 SPL Detection Rule Patterns

#### Pattern 1: Threshold Detection
```spl
index=wineventlog sourcetype="WinEventLog:Security"
    EventCode=4625 earliest=-10m
| where NOT match(src_ip, "^10\.")
| stats count as FailedAttempts,
        values(user) as TargetAccounts
  by src_ip
| where FailedAttempts > 5
| eval Severity="High", MitreTechnique="T1110"
| table src_ip, FailedAttempts, TargetAccounts, Severity, MitreTechnique
```

#### Pattern 2: Sequence Detection with Transaction
```spl
index=wineventlog sourcetype="WinEventLog:Security"
    (EventCode=4624 LogonType=3) OR EventCode=7045 earliest=-1h
| transaction host maxspan=5m
| where eventcount >= 2
| where match(EventCode, "4624") AND match(EventCode, "7045")
| eval Severity="Critical", MitreTechnique="T1021.002"
| table _time, host, user, src_ip, Severity, MitreTechnique
```

#### Pattern 3: Large Outbound Data Transfer
```spl
index=network sourcetype="cisco:asa" action=allowed earliest=-1h
| where NOT match(dest_ip, "^(10\.|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\.)")
| where NOT cidrmatch("203.0.113.0/24", dest_ip)
| stats sum(bytes_out) as TotalBytes by src_ip, dest_ip
| where TotalBytes > 524288000
| eval Severity="Critical", MitreTechnique="T1041"
| table src_ip, dest_ip, TotalBytes, Severity, MitreTechnique
```

### 26.4 SPL Generator Implementation

```python
class SPLGenerator:
    def __init__(self, template_dir: str = "templates/spl/"):
        self.env = Environment(loader=FileSystemLoader(template_dir))

    def generate(self, ir: NormalizedIR) -> str:
        overrides = ir.output_config.platform_overrides.get("spl", {})
        index = overrides.get("index", "main")
        sourcetype = overrides.get("sourcetype", "*")
        fields = ir.entity_mapping.siem_entity_mapping["splunk"]
        temporal = ir.temporal_logic
        agg = ir.detection_logic.aggregation

        lines = [f"index={index} sourcetype=\"{sourcetype}\""]

        # Add filter conditions inline in the search head
        for f in ir.detection_logic.filters:
            field = fields.get(f.field, f.field)
            lines[0] += f" {field}={f.value}"

        time_map = {"minutes": "m", "hours": "h", "days": "d"}
        unit = time_map.get(temporal.timeframe.unit, "m")
        lines[0] += f" earliest=-{temporal.timeframe.duration}{unit}"

        # Exclusions
        for excl in ir.detection_logic.exclusions:
            field = fields.get(excl.field, excl.field)
            lines.append(f"| where NOT cidrmatch(\"{excl.value}\", {field})")

        # Aggregation
        if agg:
            group_field = fields.get(agg.group_by[0], agg.group_by[0]) if agg.group_by else ""
            fn_map = {"count": "count", "sum": "sum", "distinct_count": "dc"}
            fn = fn_map.get(agg.function, "count")
            target = agg.target_field if hasattr(agg, "target_field") and agg.target_field else ""
            stat_expr = f"{fn}({target}) as Result" if target else f"{fn} as Result"
            lines.append(f"| stats {stat_expr} by {group_field}")

            op_map = {"greater_than": ">", "less_than": "<"}
            op = op_map.get(agg.threshold.operator, ">")
            lines.append(f"| where Result {op} {agg.threshold.value}")

        mitre = ir.mitre_mapping[0] if ir.mitre_mapping else None
        lines.append(f"| eval Severity=\"{ir.metadata.severity.title()}\"")
        if mitre:
            lines.append(f", MitreTechnique=\"{mitre.technique_id}\"")
        lines.append(f"| table {', '.join(fields.values())}, Severity, MitreTechnique")

        return "\n".join(lines)
```

---

## 27. Generator Implementation Strategy

### 27.1 Template Directory Structure

```
templates/
├── sigma/
│   ├── auth_failure.j2
│   ├── process_creation.j2
│   ├── network_connection.j2
│   ├── file_activity.j2
│   ├── dns_query.j2
│   ├── registry_mod.j2
│   ├── lateral_movement.j2
│   ├── scheduled_task.j2
│   └── generic.j2
├── kql/
│   ├── auth_failure.j2
│   ├── process_creation.j2
│   ├── network_connection.j2
│   ├── join_correlation.j2    # For sequence/multi-event patterns
│   └── generic.j2
└── spl/
    ├── auth_failure.j2
    ├── network_connection.j2
    ├── transaction_correlation.j2
    └── generic.j2
```

### 27.2 Template Rendering Pipeline

```
NormalizedIR
    │
    ▼
[Template Selector]
  ir.detection_logic.event_type → template_path
    │
    ▼
[Context Builder]
  Extracts IR fields into flat context dict
  Resolves platform field names from entity_mapping
  Formats operators, values, timeframes for target syntax
    │
    ▼
[Jinja2 Engine]
  template.render(**context)
    │
    ▼
[Post-Processor]
  Sigma: YAML lint, field ordering enforcement
  KQL:   Remove trailing pipes, validate operator syntax
  SPL:   Ensure proper quoting of string values
    │
    ▼
Generated Rule String (ready for validation)
```

### 27.3 Handling Complex IR Patterns

| IR Pattern | Sigma Output | KQL Output | SPL Output |
|---|---|---|---|
| Simple filter + threshold | `selection \| count() > N` | `summarize count() \| where count_ > N` | `stats count \| where count > N` |
| Sequence correlation | Correlation rule with `near` or two rules + `near` | `let A = ...; let B = ...; A \| join B` | `transaction` or `join` |
| Multiple filters (AND) | Multiple `selection` keys under same block | Chained `\| where` statements | Space-separated terms in search head |
| Multiple filters (OR) | Two named selections with `sel1 or sel2` condition | `\| where cond1 or cond2` | `(term1 OR term2)` in search |
| CIDR exclusion | `field\|cidr: 'x.x.x.x/y'` with `not filter` | `\| where field !startswith "prefix"` | `\| where NOT cidrmatch("cidr", field)` |
| Regex filter | `field\|re: 'pattern'` | `\| where field matches regex "pattern"` | `\| where match(field, "pattern")` |
| Distinct count threshold | `count(field) > N` in condition | `summarize distinct_count(field) \| where ...` | `dc(field) as Result \| where Result > N` |

### 27.4 Post-Processing and Quality Checks

After template rendering, each generator applies platform-specific post-processing:

**Sigma post-processor:**
```python
def sigma_post_process(raw_yaml: str) -> str:
    import yaml, uuid
    doc = yaml.safe_load(raw_yaml)
    # Ensure required fields present
    if "id" not in doc:
        doc["id"] = str(uuid.uuid4())
    if "date" not in doc:
        doc["date"] = datetime.now().strftime("%Y/%m/%d")
    # Enforce field ordering: title, id, status, description, ...
    ordered = reorder_sigma_keys(doc)
    return yaml.dump(ordered, allow_unicode=True, sort_keys=False)
```

**KQL post-processor:**
```python
def kql_post_process(raw_kql: str) -> str:
    lines = raw_kql.strip().split("\n")
    # Remove empty pipe stages
    lines = [l for l in lines if l.strip() not in ("|", "| ")]
    # Ensure TimeGenerated filter is first where clause
    lines = ensure_time_filter_first(lines)
    return "\n".join(lines)
```

---

*End of Part VI. Part VII continues below.*

---
---

# PART VII — VALIDATION & REPAIR PIPELINE

---

## 28. Validation Pipeline Architecture

### 28.1 Why Validation is Non-Negotiable

A generated rule that is not validated before deployment is more dangerous than no rule at all. An overly broad rule can produce thousands of false positive alerts per day, causing alert fatigue that causes analysts to miss real attacks. A rule with syntax errors simply fails silently — it never fires, leaving a blind spot.

This framework treats validation as a **first-class citizen** — not an optional final step, but a mandatory gate before any rule is considered complete.

### 28.2 Three-Stage Validation Architecture

```
Generated Rule (Sigma / KQL / SPL)
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│  STAGE 1: SYNTAX VALIDATION                                 │
│  • Parse rule for grammatical validity                      │
│  • Check required fields are present                        │
│  • Verify operator and value types                          │
│  Result: PASS → Stage 2 | FAIL → Repair Agent              │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  STAGE 2: SEMANTIC VALIDATION                               │
│  • Verify all field names exist in platform schema          │
│  • Check value ranges are valid (EventID ranges, etc.)      │
│  • Verify MITRE technique IDs are real                      │
│  • Check log source exists and is commonly available        │
│  Result: PASS → Stage 3 | FAIL → Repair Agent              │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  STAGE 3: TELEMETRY EXECUTION VALIDATION                    │
│  • Execute rule against representative log dataset          │
│  • Measure Precision, Recall, False Positive Rate           │
│  • Check execution time (performance)                       │
│  • Verify rule fires on known-malicious events              │
│  • Verify rule does NOT fire on known-benign events         │
│  Result: PASS → Output | FAIL → Repair Agent               │
└─────────────────────────────────────────────────────────────┘
```

### 28.3 Validation Result Schema

```python
class ValidationResult(BaseModel):
    rule_id: str
    platform: str                    # sigma | kql | spl
    overall_passed: bool

    stage_results: StageResults

    metrics: DetectionMetrics        # populated after telemetry validation
    errors: List[ValidationError]    # structured errors with repair hints
    warnings: List[str]              # non-blocking issues
    repair_recommendations: List[str]

class StageResults(BaseModel):
    syntax: StageResult
    semantic: StageResult
    telemetry: StageResult

class StageResult(BaseModel):
    passed: bool
    duration_ms: float
    errors: List[str]

class DetectionMetrics(BaseModel):
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    precision: float           # TP / (TP + FP)
    recall: float              # TP / (TP + FN)
    false_positive_rate: float # FP / (FP + TN)
    f1_score: float
    execution_time_ms: float

class ValidationError(BaseModel):
    stage: str                 # syntax | semantic | telemetry
    error_type: str            # field_not_found | syntax_error | etc.
    message: str
    field_path: Optional[str]  # IR field path that caused this error
    suggestions: List[str]     # Repair suggestions
    severity: str              # critical | high | warning
```

---

## 29. Stage 1 — Syntax Validation

### 29.1 Sigma Syntax Validation

Sigma validation uses the **pySigma** library to parse and validate rules:

```python
from sigma.rule import SigmaRule
from sigma.exceptions import SigmaParseError, SigmaConditionError

class SigmaSyntaxValidator:
    def validate(self, rule_yaml: str) -> StageResult:
        errors = []
        try:
            rule = SigmaRule.from_yaml(rule_yaml)

            # Required field checks
            required = ["title", "status", "logsource", "detection"]
            for field in required:
                if not hasattr(rule, field) or getattr(rule, field) is None:
                    errors.append(f"Missing required field: {field}")

            # Detection block validation
            if rule.detection:
                if not rule.detection.condition:
                    errors.append("Detection block missing 'condition' field")

            # Level validation
            valid_levels = {"informational", "low", "medium", "high", "critical"}
            if rule.level and str(rule.level) not in valid_levels:
                errors.append(f"Invalid level: {rule.level}")

        except SigmaParseError as e:
            errors.append(f"YAML parse error: {e}")
        except SigmaConditionError as e:
            errors.append(f"Condition error: {e}")

        return StageResult(
            passed=len(errors) == 0,
            errors=errors,
            duration_ms=0
        )
```

### 29.2 KQL Syntax Validation

KQL syntax is validated using a **lightweight KQL AST parser**:

```python
class KQLSyntaxValidator:
    # KQL operators that must appear in correct positions
    PIPE_OPERATORS = {
        "where", "summarize", "extend", "project", "join",
        "union", "let", "count", "top", "sort", "order"
    }
    INVALID_SQL_KEYWORDS = {"SELECT", "FROM", "GROUP BY", "HAVING", "JOIN ON"}

    def validate(self, kql_query: str) -> StageResult:
        errors = []
        lines = [l.strip() for l in kql_query.strip().split("\n") if l.strip()]

        # Check for SQL contamination (common LLM error)
        for kw in self.INVALID_SQL_KEYWORDS:
            if kw in kql_query.upper():
                errors.append(f"SQL keyword detected: '{kw}'. KQL uses different syntax.")

        # Check pipe structure
        for i, line in enumerate(lines[1:], 1):
            if line and not line.startswith("|") and not line.startswith("//"):
                errors.append(f"Line {i+1} must start with '|': {line[:50]}")

        # Check TimeGenerated filter present
        if "TimeGenerated" not in kql_query and "starttime" not in kql_query:
            errors.append("No time filter detected. Add '| where TimeGenerated > ago(Xm)'")

        # Check for balanced brackets
        if kql_query.count("(") != kql_query.count(")"):
            errors.append("Unbalanced parentheses detected")

        return StageResult(passed=len(errors) == 0, errors=errors, duration_ms=0)
```

### 29.3 SPL Syntax Validation

```python
class SPLSyntaxValidator:
    REQUIRED_SEARCH_TERMS = ["index=", "sourcetype=", "source="]
    VALID_COMMANDS = {
        "stats", "eval", "where", "table", "sort", "head", "tail",
        "rex", "regex", "lookup", "join", "transaction", "timechart"
    }

    def validate(self, spl_query: str) -> StageResult:
        errors = []
        lines = [l.strip() for l in spl_query.strip().split("\n") if l.strip()]

        # First line must be search head
        first = lines[0] if lines else ""
        has_search_term = any(t in first for t in self.REQUIRED_SEARCH_TERMS)
        if not has_search_term:
            errors.append("SPL query must start with index=, sourcetype=, or source=")

        # Check earliest/latest time filter
        if "earliest=" not in spl_query and "latest=" not in spl_query:
            errors.append("No time filter detected. Add 'earliest=-Xm' to search head")

        # Check pipe commands are valid
        for line in lines[1:]:
            if line.startswith("|"):
                cmd = line.lstrip("| ").split()[0].lower() if line.lstrip("| ").split() else ""
                if cmd and cmd not in self.VALID_COMMANDS:
                    errors.append(f"Unknown SPL command: '{cmd}'")

        return StageResult(passed=len(errors) == 0, errors=errors, duration_ms=0)
```

---

## 30. Stage 2 — Semantic Validation

### 30.1 Field Existence Validation

Verifies every field referenced in the rule actually exists in the target platform's schema:

```python
class SemanticValidator:
    def __init__(self, platform_schemas: dict):
        self.schemas = platform_schemas  # {platform: {field_name: field_type}}

    def validate_fields(self, rule: str, platform: str, ir: SecurityIR) -> List[ValidationError]:
        errors = []
        schema = self.schemas.get(platform, {})

        # Extract all field references from generated rule
        referenced_fields = self._extract_fields(rule, platform)

        for field in referenced_fields:
            if field not in schema:
                suggestions = self._fuzzy_match(field, schema)
                errors.append(ValidationError(
                    stage="semantic",
                    error_type="field_not_found",
                    message=f"Field '{field}' not found in {platform} schema",
                    suggestions=suggestions,
                    severity="critical"
                ))
        return errors

    def validate_event_ids(self, ir: SecurityIR) -> List[ValidationError]:
        """Validate Windows Event IDs are in valid range."""
        errors = []
        valid_security_events = {
            4624, 4625, 4626, 4627, 4634, 4647, 4648, 4657, 4688, 4697,
            4698, 4699, 4700, 4701, 4702, 4719, 4720, 4726, 4732, 4740,
            4768, 4769, 4776, 4777, 7045
        }
        for f in ir.detection_logic.filters:
            if f.field == "event_id":
                val = f.value if isinstance(f.value, list) else [f.value]
                for eid in val:
                    if int(eid) not in valid_security_events:
                        errors.append(ValidationError(
                            stage="semantic",
                            error_type="invalid_event_id",
                            message=f"EventID {eid} is not a recognized Windows Security Event",
                            suggestions=[str(e) for e in valid_security_events if abs(e - int(eid)) < 100],
                            severity="high"
                        ))
        return errors

    def validate_mitre_ids(self, ir: SecurityIR) -> List[ValidationError]:
        """Validate MITRE technique IDs against known technique list."""
        errors = []
        for mapping in ir.mitre_mapping:
            tid = mapping.technique_id
            if not re.match(r"^T\d{4}(\.\d{3})?$", tid):
                errors.append(ValidationError(
                    stage="semantic",
                    error_type="invalid_mitre_id",
                    message=f"'{tid}' is not a valid MITRE technique ID format (expected T####.###)",
                    suggestions=["Check https://attack.mitre.org for valid technique IDs"],
                    severity="medium"
                ))
        return errors
```

### 30.2 Logic Coherence Checks

Beyond field names, semantic validation checks that the detection logic is internally coherent:

| Check | Condition | Error Message |
|---|---|---|
| **Threshold without aggregation** | `threshold > 0` but no `aggregation` | "Threshold defined but no aggregation function specified" |
| **Aggregation without timeframe** | `aggregation` present but no `temporal_logic.timeframe` | "Aggregation requires a timeframe definition" |
| **Sequence without ordering** | `correlation.type = sequence` but `ordered = false` | "Sequence correlation should have ordered = true" |
| **Exclusion matches selection** | Exclusion filter overlaps selection filter | "Exclusion filter may exclude all selected events" |
| **Empty group_by** | `aggregation.group_by` is empty list | "Aggregation must group by at least one field" |
| **Success event in failure rule** | Event result filter mismatch | "Brute force detection should filter on failure events, not success" |

---

## 31. Stage 3 — Telemetry Execution Validation (Expanded)

The final and most critical validation stage executes the generated rule against synthetic or captured telemetry in a local sandbox. This empirical validation proves that the rule fires correctly (True Positive) without triggering on normal baseline activity (False Positive).

### 31.1 Synthetic Telemetry Generator Engine

Generating realistic logs is a significant engineering challenge. The Telemetry Generator Engine uses a constraint-based approach to simulate logs that conform to the OCSF schema.

**Architecture of the Generator:**
1. **IR parsing:** The engine reads the `DetectionLogic` and `EntityMapping` from the IR.
2. **Constraint Extraction:** It extracts filters (e.g., `user == 'admin'`), timeframes, and event types (e.g., `authentication_failure`).
3. **Faker Integration:** Using Python's `Faker` library augmented with cybersecurity-specific dictionaries, it generates mock IPs, process names, and user accounts.
4. **Targeted Generation:** 
   - *True Positive Generation:* Generates logs that explicitly satisfy all constraints within the required timeframe to ensure the rule fires.
   - *False Positive Generation:* Generates baseline "benign" logs (e.g., successful logins, normal background processes) mixed with near-miss conditions (e.g., 4 failed logins when the threshold is 5) to ensure the rule is not overly noisy.

### 31.2 Execution Sandbox

To avoid the massive cost and latency of running rules against cloud SIEMs (Sentinel/Splunk) during every repair loop, the framework uses a local execution sandbox:

- **Local EQL Engine:** For rules that can be mapped to Event Query Language (EQL), a local Elastic node executes the query.
- **Dataframe Evaluator:** For custom query logic, the pipeline translates the IR into Pandas/Polars dataframe operations and evaluates the generated logs locally.
- **Dockerized Splunk Lite:** For explicit SPL validation, a lightweight, ephemeral Splunk container is spun up via the `subprocess` module, ingests the JSON logs, runs the query via API, and returns the result.

### 31.3 The Execution Feedback Loop

When the sandbox runs a query, it produces structured feedback for the Repair Agent:
```json
{
  "execution_status": "success",
  "true_positive_fired": false,
  "false_positives_detected": 12,
  "error_message": null,
  "recommendation": "The rule syntax is valid, but the aggregation threshold was not met because the sliding window is too narrow. Consider widening the timeframe."
}
```
This structured feedback allows the Repair Agent to explicitly understand *why* a rule failed, far beyond simple syntax errors.


## 32. Closed-Loop Repair System

### 32.1 Repair Agent Architecture

The Repair Agent receives a structured `ValidationResult` containing:
- Which stage failed (syntax / semantic / telemetry)
- Specific error messages per failure
- Suggestions from fuzzy matching or threshold analysis
- Current IR state

The Repair Agent modifies the **Security IR** — not the generated rule — and triggers regeneration through all downstream stages.

```python
class RepairAgent:
    def __init__(self, llm, schema_mapper: SchemaMapper):
        self.llm = llm
        self.schema_mapper = schema_mapper

    def repair(self, ir: SecurityIR, validation_result: ValidationResult) -> SecurityIR:
        """Produce a repaired IR based on validation errors."""
        repair_plan = self._plan_repairs(validation_result)
        repaired_ir = ir.copy(deep=True)

        for repair_action in repair_plan:
            repaired_ir = self._apply_repair(repaired_ir, repair_action)

        repaired_ir.repair_count = (ir.repair_count or 0) + 1
        return repaired_ir

    def _plan_repairs(self, result: ValidationResult) -> List[RepairAction]:
        """Determine repair actions based on validation errors."""
        actions = []
        for error in result.errors:
            if error.error_type == "field_not_found":
                actions.append(RepairAction(
                    type="replace_field",
                    target_path=error.field_path,
                    new_value=error.suggestions[0] if error.suggestions else None
                ))
            elif error.error_type == "missing_timeframe":
                actions.append(RepairAction(
                    type="add_timeframe",
                    new_value={"duration": 10, "unit": "minutes"}
                ))
            elif error.error_type == "high_fpr":
                actions.append(RepairAction(
                    type="increase_threshold",
                    target_path="detection_logic.aggregation.threshold.value",
                    delta=5  # increase threshold by 5
                ))
            elif error.error_type == "low_recall":
                actions.append(RepairAction(
                    type="broaden_filters",
                    target_path="detection_logic.filters"
                ))
        return actions
```

### 32.2 Repair Strategies by Failure Type

| Failure | Stage | IR Repair Action |
|---|---|---|
| Invalid field name | Semantic | Replace with schema-validated alternative from fuzzy match |
| Missing timeframe | Syntax/Semantic | Insert `temporal_logic.timeframe: {duration: 10, unit: minutes}` |
| Syntax error in YAML | Syntax | Fix template rendering (IR structure unchanged; template hint updated) |
| FPR > 15% | Telemetry | Increase aggregation threshold by 5–10; add additional filter conditions |
| Recall < 80% | Telemetry | Broaden event type filters; reduce threshold; add OR conditions |
| Invalid EventID | Semantic | Replace with validated EventID from known-good table |
| Invalid MITRE ID | Semantic | Re-invoke MITRE Mapping Agent with additional context |
| Rule never fires | Telemetry | Check filter conditions against actual log field values; relax conditions |
| Rule always fires | Telemetry | Add more specific conditions; increase aggregation threshold significantly |

### 32.3 Repair Loop Control

```python
MAX_REPAIR_ITERATIONS = 3  # configurable

def repair_loop(ir: SecurityIR, validator: ValidationEngine,
                repair_agent: RepairAgent) -> PipelineOutput:
    current_ir = ir
    for iteration in range(MAX_REPAIR_ITERATIONS):
        # Generate rules from current IR
        rules = generate_all_rules(current_ir)

        # Validate
        results = validator.validate_all(rules, current_ir)

        if all(r.overall_passed for r in results.values()):
            return PipelineOutput(
                status="SUCCESS",
                rules=rules,
                ir=current_ir,
                iterations=iteration + 1,
                metrics={p: r.metrics for p, r in results.items()}
            )

        # Aggregate errors across all platforms
        all_errors = [e for r in results.values() for e in r.errors]

        # Repair IR
        current_ir = repair_agent.repair(current_ir, all_errors)

    # Max iterations reached
    return PipelineOutput(
        status="FAILED_MAX_RETRIES",
        rules=rules,  # return best attempt
        ir=current_ir,
        iterations=MAX_REPAIR_ITERATIONS,
        requires_human_review=True
    )
```

### 32.4 Human Review Queue

When a rule exceeds max repair iterations, it enters a **human review queue**:

```python
class HumanReviewQueue:
    def __init__(self, db_connection):
        self.db = db_connection

    def enqueue(self, pipeline_output: PipelineOutput, original_input: str):
        """Add failed rule to human review queue."""
        self.db.execute("""
            INSERT INTO review_queue
            (rule_id, original_input, best_ir, best_rules, validation_errors,
             repair_history, created_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending_review')
        """, (
            pipeline_output.ir.rule_id,
            original_input,
            pipeline_output.ir.json(),
            json.dumps(pipeline_output.rules),
            json.dumps([e.dict() for e in pipeline_output.all_errors]),
            json.dumps(pipeline_output.repair_history),
            datetime.utcnow().isoformat()
        ))
```

---

## 33. False Positive Reduction Strategies

### 33.1 Threshold Calibration

The most effective FP reduction strategy is proper threshold calibration. The framework uses the telemetry baseline to suggest optimal thresholds:

```python
def calibrate_threshold(benign_df: pd.DataFrame, attack_df: pd.DataFrame,
                        group_by_field: str, time_window_minutes: int) -> int:
    """
    Find the threshold that minimizes FPR while maintaining recall >= 0.8.
    """
    benign_counts = (
        benign_df
        .groupby([group_by_field, pd.Grouper(key="timestamp", freq=f"{time_window_minutes}min")])
        .size()
        .reset_index(name="count")["count"]
    )
    attack_counts = (
        attack_df
        .groupby([group_by_field, pd.Grouper(key="timestamp", freq=f"{time_window_minutes}min")])
        .size()
        .reset_index(name="count")["count"]
    )

    best_threshold = 1
    best_f1 = 0.0

    for threshold in range(1, int(benign_counts.max()) + 10):
        tp = (attack_counts >= threshold).sum()
        fp = (benign_counts >= threshold).sum()
        fn = (attack_counts < threshold).sum()
        tn = (benign_counts < threshold).sum()

        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

        if recall >= 0.8 and f1 > best_f1:
            best_f1 = f1
            best_threshold = threshold

    return best_threshold
```

### 33.2 Allowlisting and Exclusion Refinement

Common FP sources and their exclusion patterns:

| FP Source | Exclusion Strategy | IR Exclusion Pattern |
|---|---|---|
| IT management tools (SCCM, Ansible) | CIDR exclusion for management IP range | `source_ip in_cidr 10.0.0.0/8` |
| Service accounts | Account name pattern exclusion | `username in ["svc_*", "SYSTEM", "LOCAL SERVICE"]` |
| Backup agents | Process name exclusion | `process_name in ["backup_agent.exe", "veeam*"]` |
| Password sync tools | Logon type + source combination | `logon_type == 4 AND source_hostname contains "ADSync"` |
| Security scanners | Known scanner IP exclusion | `source_ip in_cidr "scanner_subnet"` |

### 33.3 Entity Allowlisting (Dynamic)

Beyond static exclusions, the framework supports **dynamic allowlisting** based on historical behavior:

```python
class DynamicAllowlist:
    """
    Learns which (entity, behavior) combinations are reliably benign
    based on historical alert dispositions.
    """
    def should_exclude(self, entity: str, behavior_type: str) -> bool:
        # Check if this entity has been marked benign for this behavior
        # >= 10 times with no true positive in the last 30 days
        dispositions = self.db.get_dispositions(entity, behavior_type, days=30)
        if len(dispositions) >= 10 and all(d == "benign" for d in dispositions):
            return True
        return False
```

---

*End of Part VII. Parts VIII and IX continue below.*

---
---

# PART VIII — PROMPT ENGINEERING & HALLUCINATION CONTROL

---

## 34. Prompt Engineering Strategy

### 34.1 Prompting Philosophy

Each agent in this system uses a **role-constrained, output-typed system prompt** that:
1. Assigns a specific expert persona
2. Restricts output to exactly one task
3. Specifies the exact output format (Pydantic schema)
4. Explicitly forbids out-of-scope reasoning

This approach reduces hallucination because an agent that is told "you are ONLY an entity extractor" cannot simultaneously hallucinate detection rules or query syntax.

### 34.2 System Prompt Components

Every agent system prompt follows this structure:

```
[PERSONA]
You are a [specialist role] with deep expertise in [narrow domain].

[TASK CONSTRAINT]
Your ONLY job is to [single specific task].
Do NOT [list of forbidden outputs].

[INPUT DESCRIPTION]
You will receive: [exact input format]

[OUTPUT SPECIFICATION]
You MUST output ONLY valid JSON matching this exact schema:
[Pydantic model JSON schema]

[FEW-SHOT EXAMPLES]
Example Input: [...]
Example Output: [...]

[GUARDRAILS]
- If uncertain about a field, use confidence: 0.5 and note uncertainty
- Do not invent values — only extract what is explicitly stated
- Do not include fields not in the schema
```

### 34.3 Per-Agent Prompt Strategy

| Agent | Persona | Core Constraint | Output Schema |
|---|---|---|---|
| **Threat Intel** | CTI analyst | Extract behaviors/IOCs only | `List[Behavior]`, `List[IOC]` |
| **Metadata** | Rule author | Generate metadata from behaviors | `Metadata` |
| **Entity Extraction** | NER specialist | Extract named entities only | `EntityMap` |
| **MITRE Mapping** | ATT&CK expert | Map behaviors to techniques | `List[MITREMapping]` |
| **IR Builder** | Detection architect | Assemble IR from agent outputs | `SecurityIR` |
| **Repair Agent** | QA engineer | Fix specific IR fields from error list | `RepairPlan` |

### 34.4 Few-Shot Example Strategy

Each agent's prompt includes 2–3 hand-crafted few-shot examples demonstrating:
- A clear input text
- The expected structured output
- Edge cases (ambiguous language, multiple behaviors, no IOCs present)

Example for the MITRE Mapping Agent:
```
Input: "The attacker creates a new Windows scheduled task to maintain
        persistence after reboots."

Output:
{
  "mitre_mappings": [{
    "tactic": "Persistence",
    "tactic_id": "TA0003",
    "technique": "Scheduled Task/Job",
    "technique_id": "T1053",
    "sub_technique": "Scheduled Task",
    "sub_technique_id": "T1053.005",
    "confidence": 0.97,
    "rationale": "Creating a scheduled task is the canonical T1053.005 indicator"
  }]
}
```

### 34.5 Chain-of-Thought for IR Builder

The IR Builder Agent is the most cognitively demanding agent — it must reconcile outputs from four other agents. It uses **structured chain-of-thought** prompting:

```
Step 1: Enumerate all behaviors received from Threat Intel Agent.
Step 2: For each behavior, identify which IR detection_logic fields it maps to.
Step 3: Check EntityMap for all relevant entities (IPs, users, hosts, processes).
Step 4: Verify MITRE mappings are present for each behavior.
Step 5: Identify required temporal constraints (look for time window mentions).
Step 6: Assemble the IR JSON, setting confidence scores based on source clarity.
Step 7: Flag any fields where the source text was ambiguous (confidence < 0.7).
```

This structured reasoning dramatically reduces IR construction errors.

---

## 35. Hallucination Reduction Techniques

### 35.1 Schema-Grounded Generation

The primary hallucination defense is **constraining agent outputs to Pydantic schemas** using LangChain's structured output parser:

```python
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate

parser = PydanticOutputParser(pydantic_object=EntityMap)

prompt = ChatPromptTemplate.from_messages([
    ("system", ENTITY_AGENT_SYSTEM_PROMPT),
    ("human", "{text}\n\n{format_instructions}")
]).partial(format_instructions=parser.get_format_instructions())

chain = prompt | llm | parser
# If LLM outputs invalid JSON, parser raises OutputParserException
# → retry with explicit error message to the LLM
```

When the LLM tries to output anything outside the schema, the parser raises an exception. The agent retries with an explicit error message: `"Your previous output was invalid JSON. The required schema is: [schema]. Try again."`

### 35.2 Field Grounding via OCSF Schema Injection

For field name hallucination, the OCSF schema is injected directly into the IR Builder prompt:

```python
def build_ir_builder_prompt(ir_builder_system: str, ocsf_fields: dict) -> str:
    field_list = "\n".join([
        f"  - {k}: maps to OCSF field '{v}'"
        for k, v in ocsf_fields.items()
    ])
    return f"""{ir_builder_system}

VALID FIELD NAMES (use ONLY these):
{field_list}

Do not invent field names outside this list.
"""
```

This eliminates field hallucination at the source — the model cannot invent a field name if it has been given the exhaustive list.

### 35.3 Constrained Decoding (Future Enhancement)

For production deployment, **constrained decoding** can be applied using tools like `outlines` (Python) or `llama.cpp` grammar-based sampling:

```python
import outlines
from outlines import models, generate

model = models.transformers("mistral-7b-instruct")
schema = SecurityIR.schema_json()

# Only tokens that keep the output valid JSON matching SecurityIR schema
# can be selected at each generation step
generator = generate.json(model, schema)
ir_output = generator(prompt)
```

Constrained decoding makes it **physically impossible** for the model to output JSON that violates the schema — hallucinated fields simply cannot be generated.

### 35.4 Temperature and Sampling Strategy

| Agent | Temperature | Top-P | Rationale |
|---|---|---|---|
| Threat Intel | 0.2 | 0.9 | Factual extraction — low creativity needed |
| Entity Extraction | 0.1 | 0.85 | Precision-critical — minimal variation |
| MITRE Mapping | 0.15 | 0.9 | Reference lookup — should be deterministic |
| Metadata Agent | 0.4 | 0.95 | Some creativity in description writing |
| IR Builder | 0.1 | 0.85 | Structural assembly — must be precise |
| Repair Agent | 0.2 | 0.9 | Targeted fixes — should be deliberate |

Lower temperature reduces creative hallucination at the cost of some diversity — the right trade-off for extraction and assembly tasks.

---

## 36. Security NLP Concepts

### 36.1 Cybersecurity-Specific NER

Standard NLP NER models (trained on news/Wikipedia) are poor at recognizing cybersecurity entities. The Entity Extraction Agent uses **domain-specific patterns** to supplement LLM extraction:

| Entity Pattern | Regex / Rule | Examples |
|---|---|---|
| Windows Event ID | `\bEvent(?:\s+ID)?\s+(\d{4,5})\b` | "Event 4625", "EventID 4688" |
| MITRE Technique | `T\d{4}(?:\.\d{3})?` | "T1110", "T1021.002" |
| CIDR Range | `\d{1,3}(?:\.\d{1,3}){3}/\d{1,2}` | "192.168.0.0/16" |
| Process Name | `[\w\-]+\.(?:exe\|dll\|ps1\|bat\|cmd)` | "powershell.exe", "svchost.dll" |
| Registry Key | `HK(?:LM\|CU\|CR\|U)\\\\.+` | "HKLM\Software\Microsoft\Windows" |
| File Path | `[A-Za-z]:\\\\(?:[\w\s\-]+\\\\)*[\w\s\-\.]+` | "C:\Windows\Temp\evil.exe" |
| IP Address | Standard IPv4/IPv6 regex | "192.0.2.100", "2001:db8::1" |

These patterns run as a **pre-processing step** before the LLM, providing structured entity candidates that the LLM then confirms or rejects.

### 36.2 Threat-Specific Vocabulary

The agents are primed with cybersecurity vocabulary mappings to reduce ambiguity:

| Natural Language | Technical Meaning | IR Implication |
|---|---|---|
| "logs in", "authenticates" | Authentication event | event_type: authentication |
| "runs", "executes", "launches" | Process creation | event_type: process_creation |
| "downloads", "fetches" | Network connection + file write | event_type: network_connection |
| "moves laterally", "pivots" | Lateral movement | mitre: T1021.* |
| "beacons", "calls home" | C2 communication | mitre: T1071.* |
| "exfiltrates", "steals data" | Data exfiltration | mitre: T1041 |
| "persistence", "stays resident" | Persistence mechanism | mitre: TA0003 |
| "hides", "evades", "bypasses" | Defense evasion | mitre: TA0005 |
| "dumps credentials", "harvests passwords" | Credential access | mitre: TA0006 |

---

---

# PART IX — DATASETS & EVALUATION

---

## 37. Datasets

### 37.1 Primary Dataset — SigmaHQ

**SigmaHQ** (Cyber Threat Intelligence Real-world Evaluation and Assessment for LLMs in MITRE) is a Microsoft Research benchmark released in 2025 specifically designed to evaluate LLMs on end-to-end detection engineering tasks.

| Property | SigmaHQ-25 | SigmaHQ-50 |
|---|---|---|
| Number of threat reports | 25 | 50 |
| Report format | Markdown, PDF | Markdown, PDF |
| Ground truth | Human-authored Sigma rules | Human-authored Sigma rules |
| MITRE coverage | 18 tactics, 60+ techniques | 18 tactics, 100+ techniques |
| Difficulty | Mixed | Mixed (includes complex multi-step) |
| Source | Microsoft Security Research | Microsoft Security Research |

**How this project uses SigmaHQ:**
- Feed each threat report through the full pipeline (NL → IR → Rules)
- Compare generated Sigma rules against human-authored ground truth
- Measure CodeBLEU, Logic Slot Consistency, and Execution Success Rate
- Measure MITRE mapping accuracy against ground truth labels

### 37.2 Secondary Dataset — SigmaHQ Community Rules

The **SigmaHQ rule repository** contains 3,000+ human-authored, production-quality detection rules covering a wide range of MITRE ATT&CK techniques.

**Usage in this project:**
- **Reverse engineering test**: Feed the rule's description/title through the pipeline and compare generated rule against the original human rule
- **CodeBLEU benchmark**: Score generated rules against SigmaHQ rules as reference
- **Field validation**: Extract all field names used across the 3,000+ rules to build the sigma field existence registry

### 37.3 Telemetry Dataset — HDFS Log Dataset

The **HDFS (Hadoop Distributed File System) Anomaly Detection Dataset** from the Loghub collection (UIUC / Wei Xu Lab) provides labeled system logs.

| Property | HDFS v1 | HDFS v2 |
|---|---|---|
| Total log lines | 11,175,629 | ~15M |
| Normal instances | 558,223 | ~700K |
| Anomaly instances | 16,838 | ~25K |
| Label source | Manual annotation | Automated + manual |
| Log format | HDFS block/operation logs | Extended with metadata |

**Usage in this project:**
- Validate that generated "process/file activity" detection rules execute correctly against the HDFS logs
- Measure rule execution performance (time to execute, memory usage)
- Demonstrate telemetry grounding of the validation pipeline on a publicly available dataset

### 37.4 Synthetic Telemetry

For scenario-specific testing (brute force, lateral movement, exfiltration), synthetic logs are generated using the `SyntheticLogGenerator` (§31.1) to create labeled datasets with known ground truth.

| Scenario | Benign Events | Attack Events | Ground Truth |
|---|---|---|---|
| Brute Force | 50,000 normal auth events | 500 failed logins from 5 attacker IPs | `is_attack = True` for attacker IPs |
| Lateral Movement | 10,000 normal service events | 50 PsExec-style service installs | `is_attack = True` for install events |
| Data Exfiltration | 100,000 normal network flows | 20 large outbound transfers | `is_attack = True` for >500MB flows |
| Process Injection | 200,000 normal process events | 100 abnormal parent-child chains | `is_attack = True` for abnormal chains |

---

## 38. Evaluation Metrics (Revised)

Evaluating the quality of AI-generated detection rules requires specialized metrics that prioritize semantic logic and execution over strict string similarity.

### 38.1 Deprecation of Standard CodeBLEU
Historically, CodeBLEU has been used to evaluate generated code. However, it is fundamentally flawed for domain-specific query languages like KQL and SPL because:
- **String Ordering Bias:** `user == 'admin' and action == 'login'` is functionally identical to `action == 'login' and user == 'admin'`, but CodeBLEU penalizes the difference heavily.
- **Syntax Brittleness:** Minor whitespace or aliasing differences in SQL-like languages drop BLEU scores significantly without affecting execution.
Therefore, while CodeBLEU is reported as a secondary structural baseline for legacy comparisons, it is **not** the primary success metric.

### 38.2 Custom Metric: Semantic Rule Equivalence (SRE)
To address the shortcomings of CodeBLEU, we introduce the Semantic Rule Equivalence (SRE) metric:
1. **AST Parsing:** Both the generated query and the human-written ground-truth query are parsed into an Abstract Syntax Tree (AST).
2. **Logical Normalization:** The ASTs are normalized (e.g., standardizing operator precedence, sorting commutative filters alphabetically).
3. **Equivalence Check:** If the normalized ASTs match, the SRE score is 1.0. This metric perfectly captures logical equivalence regardless of syntactical style.

### 38.3 Primary Empirical Metric: Execution Match Rate (EMR)
The ultimate measure of a rule's correctness is whether it fires exactly when the human-authored ground-truth rule fires. 

The Execution Match Rate (EMR) is calculated by:
1. Running both the generated rule and the ground-truth rule against the SigmaHQ and HDFS benchmark datasets.
2. Comparing the resulting alert sets.
3. Scoring based on Alert Jaccard Similarity (the intersection of alerts divided by the union of alerts).

An EMR of 1.0 means the generated rule has achieved perfect functional parity with the human expert, proving the operational readiness of the framework.


## 39. Experiment Design

### 39.1 Baseline vs. Proposed Framework

The core experimental comparison is between:

| System | Description |
|---|---|
| **Baseline A** | Direct GPT-4o single-prompt generation (no IR, no agents) |
| **Baseline B** | Chain-of-thought single-prompt (no IR, with CoT reasoning) |
| **Proposed** | Full multi-agent + IR framework (this project) |

All three systems receive identical inputs (SigmaHQ threat reports) and are evaluated on identical metrics.

### 39.2 Ablation Study Design

To isolate the contribution of each component:

| Ablation | What Is Removed | Measures Impact Of |
|---|---|---|
| **Ablation 1** | Remove IR layer (direct LLM generation) | IR's hallucination reduction |
| **Ablation 2** | Use single agent instead of multi-agent | Multi-agent decomposition |
| **Ablation 3** | Remove schema normalization (OCSF/ASIM) | Field mapping accuracy |
| **Ablation 4** | Remove validation + repair loop | Closed-loop refinement |
| **Ablation 5** | Remove MITRE mapping agent | Specialized MITRE reasoning |

Each ablation removes one component while keeping all others constant, enabling clean attribution of each component's contribution.

### 39.3 Experimental Protocol

```
For each threat report in SigmaHQ:
    1. Run through Baseline A → collect metrics
    2. Run through Baseline B → collect metrics
    3. Run through Proposed Framework → collect metrics
    4. For each ablation, run through modified framework → collect metrics

Report:
    - Mean and standard deviation of each metric across all reports
    - Paired t-test for statistical significance (Baseline A vs. Proposed)
    - Effect size (Cohen's d) for each significant improvement
    - Per-technique breakdown (which MITRE techniques are hardest)
```

### 39.4 Expected Results

| Metric | Baseline A | Baseline B | Proposed | Expected Improvement |
|---|---|---|---|---|
| SVR | ~60% | ~70% | ≥95% | +35 percentage points |
| Field Hallucination | ~45% | ~30% | ≤5% | -40 percentage points |
| CodeBLEU | ~0.35 | ~0.45 | ≥0.70 | +0.25–0.35 points |
| LSC | ~0.55 | ~0.65 | ≥0.85 | +0.20–0.30 points |
| Precision | ~0.50 | ~0.60 | ≥0.85 | +0.25–0.35 points |
| Recall | ~0.65 | ~0.70 | ≥0.80 | +0.10–0.15 points |

---

## 40. Benchmarking Methodology

### 40.1 Evaluation Pipeline Implementation

```python
class BenchmarkRunner:
    def __init__(self, systems: dict, datasets: dict, metrics: List[str]):
        self.systems = systems   # {"baseline_a": ..., "proposed": ...}
        self.datasets = datasets
        self.metrics = metrics

    def run_full_benchmark(self) -> BenchmarkReport:
        results = {}
        for system_name, system in self.systems.items():
            system_results = []
            for report in self.datasets["cti_realm"]:
                # Generate rules
                output = system.generate(report.text)
                # Evaluate against ground truth
                scores = self._evaluate(output, report.ground_truth_rule)
                system_results.append(scores)
            results[system_name] = self._aggregate(system_results)
        return BenchmarkReport(results=results)

    def _evaluate(self, output: PipelineOutput, reference: str) -> MetricScores:
        return MetricScores(
            code_bleu=compute_code_bleu(output.sigma_rule, reference),
            lsc=compute_lsc(output.ir, reference),
            syntax_valid=output.validation.syntax.passed,
            hallucination_rate=compute_hallucination_rate(output.sigma_rule),
            precision=output.validation.metrics.precision,
            recall=output.validation.metrics.recall
        )
```

### 40.2 Statistical Significance Testing

```python
from scipy import stats

def test_significance(baseline_scores: List[float],
                      proposed_scores: List[float]) -> SignificanceResult:
    t_stat, p_value = stats.ttest_rel(proposed_scores, baseline_scores)
    cohens_d = (
        (sum(proposed_scores)/len(proposed_scores) - sum(baseline_scores)/len(baseline_scores))
        / ((stats.tstd(proposed_scores + baseline_scores)))
    )
    return SignificanceResult(
        t_statistic=t_stat,
        p_value=p_value,
        significant=(p_value < 0.05),
        effect_size=cohens_d,
        interpretation="large" if abs(cohens_d) > 0.8 else "medium" if abs(cohens_d) > 0.5 else "small"
    )
```

---

*End of Parts VIII and IX. Parts X and XI continue below.*

---
---

# PART X — IMPLEMENTATION

---

## 41. Technology Stack

| Layer | Technology | Version | Purpose |
|---|---|---|---|
| **Language** | Python | 3.11+ | Primary implementation language |
| **Agent Orchestration** | LangGraph | 0.2.x | Multi-agent workflow, state graph, cycles |
| **LLM Integration** | LangChain | 0.3.x | Agent chains, output parsers, prompts |
| **LLM Backend** | OpenAI GPT-4o / Claude 3.5 Sonnet | API | Agent reasoning |
| **Schema Validation** | Pydantic | v2 | IR schema enforcement, agent output typing |
| **Sigma Parsing** | pySigma | 0.11.x | Sigma rule parsing and conversion |
| **API Server** | FastAPI | 0.111+ | REST API for pipeline access |
| **Data Processing** | pandas, numpy | Latest | Telemetry execution, metric computation |
| **Template Engine** | Jinja2 | 3.x | Rule generation templates |
| **Database** | SQLite (dev) / PostgreSQL (prod) | — | IR storage, rule versioning, audit logs |
| **Config Management** | PyYAML, python-dotenv | — | Schema files, environment variables |
| **Testing** | pytest, pytest-asyncio | — | Unit and integration tests |
| **Observability** | LangSmith | — | Agent trace logging |
| **Containerization** | Docker, Docker Compose | — | Reproducible environment |
| **Version Control** | Git + GitHub | — | Source control |

### 41.1 LLM Selection Rationale

| Model | Strengths | Use Case in This Project |
|---|---|---|
| **GPT-4o** | Best general reasoning, strong JSON output | IR Builder, Repair Agent |
| **Claude 3.5 Sonnet** | Excellent at following structured instructions | Entity Extraction, MITRE Mapping |
| **GPT-4o-mini** | Fast, cheap, good for simple extraction | Metadata Agent |
| **Local (Ollama/Mistral)** | No API cost, air-gapped environments | Threat Intel Agent (optional) |

The framework is model-agnostic — swapping models requires only changing the `llm` parameter in each agent's factory function.

---

## 42. Folder Structure & Software Architecture

```
Intermediate-Representation-IR-Framework-for-SIEM-Rule-Generation/
│
├── src/                              # All source code
│   ├── agents/                       # Agent implementations
│   │   ├── __init__.py
│   │   ├── base_agent.py             # Abstract base class for all agents
│   │   ├── coordinator.py            # Coordinator/orchestrator agent
│   │   ├── threat_intel_agent.py     # Threat intelligence extraction
│   │   ├── metadata_agent.py         # Rule metadata generation
│   │   ├── entity_extraction_agent.py # NER and entity extraction
│   │   ├── mitre_mapping_agent.py    # MITRE ATT&CK mapping
│   │   ├── ir_builder_agent.py       # Security IR construction
│   │   ├── validation_agent.py       # Multi-stage validation
│   │   └── repair_agent.py           # Autonomous repair
│   │
│   ├── ir_engine/                    # IR definition and processing
│   │   ├── __init__.py
│   │   ├── ir_schema.py              # Pydantic models for SecurityIR
│   │   ├── ir_builder.py             # IR construction utilities
│   │   └── ir_validator.py           # IR structural validation
│   │
│   ├── schema_mapping/               # OCSF/ASIM normalization
│   │   ├── __init__.py
│   │   ├── schema_mapper.py          # Main mapping engine
│   │   ├── field_validator.py        # Field existence checking
│   │   └── ocsf_resolver.py          # OCSF event class resolver
│   │
│   ├── generators/                   # Rule generation
│   │   ├── __init__.py
│   │   ├── base_generator.py         # Abstract generator interface
│   │   ├── sigma_generator.py        # Sigma YAML generator
│   │   ├── kql_generator.py          # KQL generator
│   │   └── spl_generator.py          # SPL generator
│   │
│   ├── validation/                   # Validation engines
│   │   ├── __init__.py
│   │   ├── syntax_validators.py      # Sigma/KQL/SPL syntax checkers
│   │   ├── semantic_validator.py     # Field and logic coherence checks
│   │   ├── telemetry_validator.py    # Log execution and metrics
│   │   └── validation_engine.py     # Orchestrates all three stages
│   │
│   ├── pipeline/                     # LangGraph pipeline
│   │   ├── __init__.py
│   │   ├── state.py                  # PipelineState TypedDict
│   │   ├── graph.py                  # LangGraph StateGraph definition
│   │   ├── nodes.py                  # Node function implementations
│   │   └── router.py                 # Conditional edge routing logic
│   │
│   ├── api/                          # FastAPI REST endpoints
│   │   ├── __init__.py
│   │   ├── main.py                   # FastAPI app entry point
│   │   ├── routers/
│   │   │   ├── generate.py           # POST /generate endpoint
│   │   │   ├── rules.py              # GET/PUT /rules endpoints
│   │   │   └── health.py             # GET /health endpoint
│   │   └── schemas.py                # Request/response Pydantic models
│   │
│   ├── storage/                      # Persistence layer
│   │   ├── __init__.py
│   │   ├── database.py               # SQLAlchemy models + session
│   │   ├── rule_store.py             # Rule CRUD operations
│   │   └── ir_cache.py               # IR caching
│   │
│   └── utils/                        # Shared utilities
│       ├── __init__.py
│       ├── logger.py                 # Structured logging setup
│       ├── preprocessor.py           # Text chunking, cleaning
│       └── metrics.py                # CodeBLEU, LSC computation
│
├── templates/                        # Jinja2 rule templates
│   ├── sigma/
│   ├── kql/
│   └── spl/
│
├── config/                           # Configuration files
│   ├── schemas/                      # OCSF/ASIM/CIM YAML mappings
│   │   ├── ocsf_to_asim.yaml
│   │   ├── ocsf_to_splunk_cim.yaml
│   │   ├── ocsf_to_sigma.yaml
│   │   └── platform_field_registry.yaml
│   ├── platforms.yaml                # Platform configuration registry
│   ├── agents.yaml                   # Agent model and temperature config
│   └── thresholds.yaml               # Validation acceptance thresholds
│
├── datasets/                         # Evaluation datasets
│   ├── cti_realm/                    # SigmaHQ threat reports
│   ├── sigmahq_sample/               # SigmaHQ reference rules
│   ├── hdfs_logs/                    # HDFS log dataset
│   └── synthetic/                    # Generated synthetic telemetry
│
├── tests/                            # Test suite
│   ├── unit/
│   │   ├── test_ir_schema.py
│   │   ├── test_schema_mapper.py
│   │   ├── test_generators.py
│   │   └── test_validators.py
│   └── integration/
│       ├── test_full_pipeline.py
│       └── test_benchmark_runner.py
│
├── notebooks/                        # Jupyter notebooks for research
│   ├── 01_ir_design_exploration.ipynb
│   ├── 02_schema_mapping_analysis.ipynb
│   ├── 03_benchmark_results.ipynb
│   └── 04_ablation_study.ipynb
│
├── scripts/                          # Utility scripts
│   ├── run_benchmark.py
│   ├── generate_synthetic_logs.py
│   └── export_rules.py
│
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── pyproject.toml
├── .env.example
└── README.md
```

---

## 43. Detailed Module Breakdown

### 43.1 `src/ir_engine/ir_schema.py`

The central data contract of the entire system. All Pydantic models defining the Security IR.

```python
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Literal, Union
from uuid import uuid4
from datetime import datetime

class FilterCondition(BaseModel):
    field: str
    operator: Literal["equals","not_equals","contains","starts_with","in",
                       "not_in","in_cidr","not_in_cidr","regex","greater_than",
                       "less_than","exists"]
    value: Union[str, int, float, List[Union[str, int, float]]]
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    note: Optional[str] = None

class AggregationConfig(BaseModel):
    function: Literal["count", "sum", "distinct_count", "min", "max", "avg"]
    target_field: Optional[str] = None   # for sum/min/max/avg
    group_by: List[str] = Field(default_factory=list)
    threshold: "ThresholdConfig"

class ThresholdConfig(BaseModel):
    operator: Literal["greater_than", "less_than", "equals", "gte", "lte"]
    value: Union[int, float]

class TimeframeConfig(BaseModel):
    duration: int
    unit: Literal["seconds", "minutes", "hours", "days"]
    type: Literal["sliding_window", "fixed_window", "session_window"] = "sliding_window"

class MITREMapping(BaseModel):
    tactic: str
    tactic_id: str          # TA####
    technique: str
    technique_id: str       # T####
    sub_technique: Optional[str] = None
    sub_technique_id: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str

class SecurityIR(BaseModel):
    ir_version: str = "1.0"
    rule_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    source_document: Optional[str] = None
    confidence_overall: float = Field(default=0.8, ge=0.0, le=1.0)
    repair_count: int = 0

    metadata: "IRMetadata"
    detection_logic: "DetectionLogic"
    entity_mapping: "EntityMapping"
    temporal_logic: "TemporalLogic"
    mitre_mapping: List[MITREMapping] = Field(default_factory=list)
    output_config: "OutputConfig"
    provenance: dict = Field(default_factory=dict)
```

### 43.2 `src/pipeline/state.py`

```python
from typing import TypedDict, Annotated, List, Optional
from operator import add

class PipelineState(TypedDict):
    # Input
    raw_input: str
    chunks: List[str]
    source_document: Optional[str]

    # Agent extractions
    behaviors: List[dict]
    iocs: List[dict]
    severity: str
    description: str
    tags: List[str]
    entities: dict
    mitre_mappings: List[dict]

    # IR stages
    security_ir: Optional[dict]
    normalized_ir: Optional[dict]

    # Generated rules
    sigma_rule: Optional[str]
    kql_rule: Optional[str]
    spl_rule: Optional[str]

    # Validation
    validation_results: dict
    repair_count: int
    errors: Annotated[List[str], add]

    # Output
    validated_rules: Optional[dict]
    pipeline_status: str      # "running" | "success" | "failed" | "pending_review"
    provenance: dict
```

### 43.3 `src/pipeline/graph.py`

Entry point for the LangGraph pipeline. Defines all nodes, edges, and compilation.

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from .state import PipelineState
from .nodes import (preprocess, threat_intel, metadata, entity_extraction,
                     mitre_mapping, ir_builder, schema_mapper,
                     sigma_gen, kql_gen, spl_gen, validator, repair, output)
from .router import route_after_validation

def build_pipeline(checkpoint_db: str = "pipeline.db") -> "CompiledGraph":
    workflow = StateGraph(PipelineState)

    # Register all nodes
    for name, fn in [("preprocess", preprocess), ("threat_intel", threat_intel),
                     ("metadata", metadata), ("entity_extraction", entity_extraction),
                     ("mitre_mapping", mitre_mapping), ("ir_builder", ir_builder),
                     ("schema_mapper", schema_mapper), ("sigma_gen", sigma_gen),
                     ("kql_gen", kql_gen), ("spl_gen", spl_gen),
                     ("validator", validator), ("repair", repair), ("output", output)]:
        workflow.add_node(name, fn)

    # Define edges
    workflow.set_entry_point("preprocess")
    workflow.add_edge("preprocess", "threat_intel")
    for node in ["metadata", "entity_extraction", "mitre_mapping"]:
        workflow.add_edge("threat_intel", node)
        workflow.add_edge(node, "ir_builder")
    workflow.add_edge("ir_builder", "schema_mapper")
    for gen in ["sigma_gen", "kql_gen", "spl_gen"]:
        workflow.add_edge("schema_mapper", gen)
        workflow.add_edge(gen, "validator")
    workflow.add_conditional_edges("validator", route_after_validation,
                                   {"pass": "output", "repair": "repair", "max_retries": "output"})
    workflow.add_edge("repair", "ir_builder")
    workflow.add_edge("output", END)

    with SqliteSaver.from_conn_string(checkpoint_db) as checkpointer:
        return workflow.compile(checkpointer=checkpointer)
```

---

## 44. API Design

### 44.1 REST Endpoints

| Method | Endpoint | Description | Request | Response |
|---|---|---|---|---|
| `POST` | `/generate` | Run full pipeline on input text | `GenerateRequest` | `GenerateResponse` |
| `GET` | `/rules/{rule_id}` | Get rule by ID | — | `RuleDetail` |
| `GET` | `/rules` | List all rules with filters | Query params | `RuleList` |
| `GET` | `/rules/{rule_id}/ir` | Get the underlying IR | — | `SecurityIR` |
| `PUT` | `/rules/{rule_id}/approve` | Human approval of a rule | — | `RuleDetail` |
| `GET` | `/review-queue` | List rules pending human review | — | `ReviewQueue` |
| `GET` | `/health` | Health check | — | `HealthStatus` |
| `GET` | `/metrics` | Pipeline performance metrics | — | `PipelineMetrics` |

### 44.2 Request/Response Schemas

```python
class GenerateRequest(BaseModel):
    text: str                              # Input NL document
    target_platforms: List[str] = ["sigma", "kql", "spl"]
    source_document: Optional[str] = None  # Filename for provenance
    options: dict = {}                     # Pipeline options

class GenerateResponse(BaseModel):
    rule_id: str
    status: str                  # "success" | "failed" | "pending_review"
    rules: dict                  # {"sigma": "...", "kql": "...", "spl": "..."}
    ir: dict                     # Full Security IR
    validation: dict             # Validation results
    metrics: dict                # Precision, recall, etc.
    iterations: int              # Repair iterations used
    processing_time_ms: float
```

### 44.3 FastAPI App Entry Point

```python
# src/api/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import generate, rules, health

app = FastAPI(
    title="IR-Based SIEM Rule Generation Framework",
    description="Converts natural language threat descriptions to validated SIEM detection rules",
    version="1.0.0"
)

app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

app.include_router(generate.router, prefix="/api/v1")
app.include_router(rules.router, prefix="/api/v1")
app.include_router(health.router)
```

---

## 45. Database & Storage Design

### 45.1 Database Schema

```sql
-- Core rules table
CREATE TABLE rules (
    id          TEXT PRIMARY KEY,          -- UUID
    rule_name   TEXT NOT NULL,
    severity    TEXT NOT NULL,
    status      TEXT NOT NULL,             -- experimental|pending_review|approved|rejected
    sigma_rule  TEXT,
    kql_rule    TEXT,
    spl_rule    TEXT,
    ir_json     TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT,
    source_doc  TEXT
);

-- Validation results
CREATE TABLE validation_results (
    id              TEXT PRIMARY KEY,
    rule_id         TEXT REFERENCES rules(id),
    platform        TEXT NOT NULL,         -- sigma|kql|spl
    passed          INTEGER NOT NULL,
    precision_score REAL,
    recall_score    REAL,
    fpr_score       REAL,
    f1_score        REAL,
    errors_json     TEXT,
    validated_at    TEXT NOT NULL
);

-- Repair history
CREATE TABLE repair_history (
    id              TEXT PRIMARY KEY,
    rule_id         TEXT REFERENCES rules(id),
    iteration       INTEGER NOT NULL,
    error_json      TEXT NOT NULL,
    repair_action   TEXT NOT NULL,
    repaired_at     TEXT NOT NULL
);

-- Human review queue
CREATE TABLE review_queue (
    id              TEXT PRIMARY KEY,
    rule_id         TEXT REFERENCES rules(id),
    status          TEXT DEFAULT 'pending', -- pending|approved|rejected|modified
    reviewer        TEXT,
    reviewed_at     TEXT,
    reviewer_notes  TEXT
);
```

---

## 46. Configuration Management

### 46.1 Environment Variables (`.env`)

```bash
# LLM Configuration
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=...
DEFAULT_LLM_MODEL=gpt-4o
IR_BUILDER_MODEL=gpt-4o
METADATA_MODEL=gpt-4o-mini

# Pipeline Configuration
MAX_REPAIR_ITERATIONS=3
VALIDATION_PRECISION_THRESHOLD=0.85
VALIDATION_RECALL_THRESHOLD=0.80
VALIDATION_FPR_THRESHOLD=0.15

# Database
DATABASE_URL=sqlite:///./pipeline.db
# DATABASE_URL=postgresql://user:pass@localhost:5432/siem_rules

# LangSmith Observability
LANGCHAIN_API_KEY=ls__...
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=siem-rule-generation

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
```

### 46.2 Agent Configuration (`config/agents.yaml`)

```yaml
agents:
  threat_intel:
    model: gpt-4o-mini
    temperature: 0.2
    max_tokens: 2000
    timeout_seconds: 30

  entity_extraction:
    model: gpt-4o-mini
    temperature: 0.1
    max_tokens: 1500
    timeout_seconds: 20

  mitre_mapping:
    model: gpt-4o
    temperature: 0.15
    max_tokens: 1500
    timeout_seconds: 30

  ir_builder:
    model: gpt-4o
    temperature: 0.1
    max_tokens: 4000
    timeout_seconds: 60

  repair:
    model: gpt-4o
    temperature: 0.2
    max_tokens: 2000
    timeout_seconds: 45
```

---

---

# PART XI — THREAT INTELLIGENCE & MITRE INTEGRATION

---

## 47. Threat Intelligence Integration

### 47.1 Supported CTI Input Formats

| Format | Description | Parser |
|---|---|---|
| **Plain text** | SOPs, incident reports, analyst notes | Direct chunking |
| **Markdown** | CTI reports, threat blogs | python-markdown → text |
| **PDF** | Vendor security advisories | pdfminer.six |
| **STIX 2.1 JSON** | Structured threat intelligence feeds | python-stix2 |
| **MISP JSON** | Malware Information Sharing Platform exports | Custom parser |
| **CSV** | IOC lists (IPs, hashes, domains) | pandas |

### 47.2 IOC Extraction and Usage

IOCs extracted by the Threat Intel Agent are embedded into the IR as filter conditions:

| IOC Type | IR Filter Field | IR Operator | Generated Rule Pattern |
|---|---|---|---|
| IP Address | `source_ip` or `dest_ip` | `equals` or `in` | Direct IP match filter |
| IP Range (CIDR) | `source_ip` | `in_cidr` | CIDR range filter |
| Domain Name | `query_name` (DNS) | `equals` | DNS query name filter |
| File Hash (MD5) | `file_hash_md5` | `equals` | Hash equality check |
| File Hash (SHA256) | `file_hash_sha256` | `equals` | Hash equality check |
| Process Name | `process_name` | `contains` or `equals` | Process name filter |
| URL Pattern | `url` | `contains` or `regex` | URL substring/regex match |

---

## 48. MITRE ATT&CK Mapping Pipeline

### 48.1 ATT&CK Navigator Integration

Generated rules automatically produce **ATT&CK Navigator layer files** for visualizing detection coverage:

```python
def generate_navigator_layer(rules: List[SecurityIR]) -> dict:
    """Generate ATT&CK Navigator v4.8 layer JSON from a set of IRs."""
    techniques = {}
    for ir in rules:
        for mapping in ir.mitre_mapping:
            tid = mapping.technique_id
            if tid not in techniques:
                techniques[tid] = {"techniqueID": tid, "score": 0, "color": "", "comment": ""}
            techniques[tid]["score"] += 1
            techniques[tid]["color"] = _score_to_color(techniques[tid]["score"])
            techniques[tid]["comment"] += f"Rule: {ir.metadata.rule_name}\n"

    return {
        "name": "IR Framework Coverage",
        "versions": {"attack": "15", "navigator": "4.8", "layer": "4.5"},
        "domain": "enterprise-attack",
        "techniques": list(techniques.values()),
        "gradient": {"colors": ["#ffffff", "#ff6666"], "minValue": 0, "maxValue": 10}
    }
```

### 48.2 MITRE ATT&CK Coverage Tracking

The system maintains a coverage matrix updated after each rule generation:

```python
class MITRECoverageTracker:
    def update_coverage(self, ir: SecurityIR):
        for mapping in ir.mitre_mapping:
            self.db.execute("""
                INSERT OR REPLACE INTO mitre_coverage
                (technique_id, tactic_id, rule_count, last_updated)
                VALUES (?, ?, COALESCE(
                    (SELECT rule_count FROM mitre_coverage WHERE technique_id=?) + 1, 1
                ), ?)
            """, (mapping.technique_id, mapping.tactic_id,
                  mapping.technique_id, datetime.utcnow().isoformat()))

    def get_coverage_summary(self) -> dict:
        covered = self.db.execute(
            "SELECT COUNT(DISTINCT technique_id) FROM mitre_coverage"
        ).fetchone()[0]
        return {
            "techniques_covered": covered,
            "total_techniques": 201,   # ATT&CK v15 Enterprise
            "coverage_percentage": round(covered / 201 * 100, 1)
        }
```

---

## 49. Temporal Correlation Logic

### 49.1 Event Sequencing Patterns

| Pattern | Description | Temporal Constraint | Example |
|---|---|---|---|
| **Single event threshold** | N occurrences within window | `count > N within T` | Brute force: 5 failures in 10 min |
| **Ordered sequence** | Event A before Event B | `A then B within T` | Login then service install |
| **Co-occurrence** | Events A and B in same window | `A and B within T` | Scanner activity + successful auth |
| **Absence detection** | Event A NOT followed by B | `A and not B within T` | Auth without MFA within 1 min |
| **Spike detection** | Rate exceeds baseline | `rate > baseline * k` | DNS requests 10x normal |

### 49.2 Sequence IR Representation

```json
"correlation": {
  "type": "temporal_ordered",
  "events": [
    {
      "step": 1,
      "event_type": "authentication_success",
      "filters": [{"field": "logon_type", "operator": "equals", "value": 3}],
      "role": "anchor"
    },
    {
      "step": 2,
      "event_type": "service_installation",
      "filters": [{"field": "event_id", "operator": "equals", "value": 7045}],
      "role": "follow_up",
      "within": {"duration": 5, "unit": "minutes", "relative_to": "step_1"}
    }
  ],
  "same_entity": "target_hostname",
  "max_span": {"duration": 30, "unit": "minutes"}
}
```

---

## 50. Aggregation & Threshold Logic

### 50.1 Aggregation Function Reference

| Function | IR Keyword | KQL | SPL | Sigma Condition |
|---|---|---|---|---|
| Event count | `count` | `count()` | `count` | `\| count() > N` |
| Distinct values | `distinct_count` | `distinct_count(field)` | `dc(field)` | `\| count(field) > N` |
| Sum of field | `sum` | `sum(field)` | `sum(field)` | `\| sum(field) > N` |
| Maximum value | `max` | `max(field)` | `max(field)` | — |
| Minimum value | `min` | `min(field)` | `min(field)` | — |

### 50.2 Threshold Defaults by Attack Type

When the source text does not specify a threshold, the framework applies empirically-derived defaults:

| Attack Type | Default Threshold | Default Window | Rationale |
|---|---|---|---|
| Brute Force (password) | count > 5 | 10 minutes | Industry standard SOC threshold |
| Credential Stuffing | distinct_count(user) > 20 | 5 minutes | Multiple accounts = stuffing pattern |
| Port Scan | distinct_count(dest_port) > 100 | 1 minute | 100 ports/min = clear scan |
| Data Exfiltration | sum(bytes_out) > 500MB | 1 hour | Well above normal user upload |
| DNS Beaconing | count > 60 | 1 hour | >1 req/min to same domain |
| Lateral Movement | event_count >= 2 | 5 minutes | Requires at least 2 correlated events |

---

*End of Parts X and XI. Final sections XII–XIV below.*

---
---

# PART XII — DEPLOYMENT & OPERATIONS

---

## 51. Containerization

### 51.1 Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY src/ ./src/
COPY templates/ ./templates/
COPY config/ ./config/

# Entry point
EXPOSE 8000
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 51.2 Docker Compose

```yaml
version: "3.9"

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/siem_rules
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - LANGCHAIN_API_KEY=${LANGCHAIN_API_KEY}
      - LANGCHAIN_TRACING_V2=true
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - ./config:/app/config
      - ./templates:/app/templates
      - ./datasets:/app/datasets

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: siem_rules
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    volumes:
      - pg_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  adminer:
    image: adminer
    ports:
      - "8080:8080"
    depends_on:
      - db

volumes:
  pg_data:
```

---

## 52. Testing Strategy

### 52.1 Unit Test Coverage

```python
# tests/unit/test_ir_schema.py
import pytest
from src.ir_engine.ir_schema import SecurityIR, FilterCondition

def test_filter_confidence_bounds():
    """Confidence must be between 0 and 1."""
    with pytest.raises(ValueError):
        FilterCondition(field="src_ip", operator="equals", value="1.2.3.4", confidence=1.5)

def test_ir_generates_uuid():
    """Each IR gets a unique rule_id."""
    ir1 = SecurityIR(metadata=..., detection_logic=..., ...)
    ir2 = SecurityIR(metadata=..., detection_logic=..., ...)
    assert ir1.rule_id != ir2.rule_id

def test_mitre_id_format():
    """Invalid MITRE ID format should be caught."""
    from src.validation.semantic_validator import SemanticValidator
    v = SemanticValidator({})
    errors = v.validate_mitre_ids_from_list(["T9999.999", "INVALID"])
    assert len(errors) > 0  # INVALID should fail
    # T9999.999 passes format check (format validator, not existence)
```

```python
# tests/unit/test_generators.py
from src.generators.sigma_generator import SigmaGenerator
import yaml

def test_sigma_output_is_valid_yaml(sample_ir):
    gen = SigmaGenerator()
    output = gen.generate(sample_ir)
    doc = yaml.safe_load(output)
    assert "title" in doc
    assert "detection" in doc
    assert "condition" in doc["detection"]

def test_kql_has_time_filter(sample_ir):
    from src.generators.kql_generator import KQLGenerator
    gen = KQLGenerator()
    output = gen.generate(sample_ir)
    assert "TimeGenerated" in output or "ago(" in output

def test_spl_has_index(sample_ir):
    from src.generators.spl_generator import SPLGenerator
    gen = SPLGenerator()
    output = gen.generate(sample_ir)
    assert output.strip().startswith("index=")
```

### 52.2 Integration Test — Full Pipeline

```python
# tests/integration/test_full_pipeline.py
import pytest
from src.pipeline.graph import build_pipeline

SAMPLE_INPUT = """
An attacker attempts to brute force a Windows domain account by making
repeated failed login attempts (Event 4625). More than 10 failures from
the same source IP within 5 minutes should be flagged. Exclude internal
management systems in the 10.0.0.0/8 range.
"""

@pytest.mark.asyncio
async def test_full_pipeline_produces_valid_sigma():
    pipeline = build_pipeline()
    state = {"raw_input": SAMPLE_INPUT, "repair_count": 0, "errors": []}
    result = await pipeline.ainvoke(state)

    assert result["pipeline_status"] in ("success", "pending_review")
    assert result.get("sigma_rule") is not None

    import yaml
    doc = yaml.safe_load(result["sigma_rule"])
    assert "detection" in doc
    assert "4625" in str(doc)  # EventID should appear

@pytest.mark.asyncio
async def test_repair_loop_activates_on_bad_field():
    """Inject a corrupted IR and verify repair loop triggers."""
    pipeline = build_pipeline()
    corrupted_ir = create_ir_with_invalid_field("NonExistentField12345")
    state = {"security_ir": corrupted_ir.dict(), "repair_count": 0, "errors": []}
    result = await pipeline.ainvoke(state, entry_point="schema_mapper")

    assert result["repair_count"] > 0
    assert "NonExistentField12345" not in result.get("sigma_rule", "")
```

### 52.3 Test Pyramid

```
                ▲
               / \
              /   \     E2E Tests (2-3 full pipeline runs)
             /─────\
            /       \   Integration Tests (20-30)
           /─────────\  Tests across 2+ modules
          /           \
         /─────────────\ Unit Tests (100+)
        /               \ Individual classes, functions
       ─────────────────────
```

---

## 53. Observability & Monitoring

### 53.1 Structured Logging

```python
# src/utils/logger.py
import logging, json
from datetime import datetime

class StructuredLogger:
    def __init__(self, service: str):
        self.service = service

    def log_agent_call(self, agent: str, input_tokens: int,
                       output_tokens: int, duration_ms: float, success: bool):
        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "service": self.service,
            "event": "agent_call",
            "agent": agent,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "duration_ms": duration_ms,
            "success": success
        }
        print(json.dumps(record))  # Ship to log aggregator

    def log_pipeline_complete(self, rule_id: str, status: str,
                               iterations: int, total_ms: float):
        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "service": self.service,
            "event": "pipeline_complete",
            "rule_id": rule_id,
            "status": status,
            "repair_iterations": iterations,
            "total_duration_ms": total_ms
        }
        print(json.dumps(record))
```

### 53.2 LangSmith Tracing

LangSmith automatically traces every agent invocation when `LANGCHAIN_TRACING_V2=true`:

- **Full trace view**: Input/output for every agent call
- **Token usage**: Per-agent and per-pipeline token consumption
- **Latency breakdown**: Time spent in each node
- **Error capture**: Full stack traces on agent failures
- **Human feedback**: Analysts can rate rule quality in LangSmith UI, feeding back into fine-tuning

### 53.3 Key Operational Metrics

| Metric | Collection Method | Alert Threshold |
|---|---|---|
| Pipeline success rate | Count status="success" / total | < 70% over 1 hour |
| Average repair iterations | Mean of repair_count | > 2.0 average |
| Agent API error rate | Count LLM exceptions / calls | > 5% over 30 minutes |
| Rule generation latency | Pipeline end-to-end time | > 120 seconds |
| Validation pass rate | Stage 1+2 pass / total | < 80% |
| Human review queue depth | Count pending_review | > 20 rules |

---

## 54. Security & Compliance

### 54.1 Input Validation

All API inputs are validated before entering the pipeline:

```python
class GenerateRequest(BaseModel):
    text: str = Field(min_length=10, max_length=50000)
    target_platforms: List[str] = Field(default=["sigma", "kql", "spl"])

    @validator("target_platforms")
    def validate_platforms(cls, v):
        allowed = {"sigma", "kql", "spl", "esql", "yara_l"}
        invalid = set(v) - allowed
        if invalid:
            raise ValueError(f"Unknown platforms: {invalid}")
        return v

    @validator("text")
    def sanitize_text(cls, v):
        # Strip prompt injection attempts
        dangerous = ["ignore previous", "forget your instructions", "jailbreak"]
        for pattern in dangerous:
            if pattern.lower() in v.lower():
                raise ValueError("Input contains potentially malicious content")
        return v.strip()
```

### 54.2 API Authentication

```python
from fastapi.security import APIKeyHeader
from fastapi import Security, HTTPException

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(api_key: str = Security(api_key_header)):
    if not api_key or api_key not in VALID_API_KEYS:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key
```

---

---

# PART XIII — RESEARCH ROADMAP

---

## 55. Research Contributions

### 55.1 Novel Research Claims

This project makes the following original research contributions:

1. **IR-as-Contract for Detection Engineering**: The first formal definition and implementation of an Intermediate Representation specifically designed as a typed, vendor-neutral contract between semantic extraction and syntactic rule generation for cybersecurity detection.

2. **Multi-Agent Decomposition for Rule Synthesis**: Empirical demonstration that decomposing rule generation into specialized agents (threat intel, entity, MITRE, IR builder, repair) outperforms monolithic LLM prompting on syntax validity, field accuracy, and MITRE alignment.

3. **Closed-Loop Telemetry Validation**: A novel closed-loop architecture where detection rules are evaluated against labeled telemetry data before delivery, with automated repair driven by structured error feedback at the IR level.

4. **Schema-Normalized Detection Generation**: First systematic application of OCSF as the semantic normalization layer and ASIM/CIM as the syntactic target layer for cross-platform SIEM rule generation.

5. **Detection Coverage Quantification**: A method for automatically computing and visualizing ATT&CK technique coverage from the IR layer, enabling gap analysis across an organization's entire rule library.

### 55.2 Research Questions Being Answered

| RQ# | Research Question | Measurement |
|---|---|---|
| **RQ1** | Does IR intermediation reduce syntax errors compared to direct LLM generation? | SVR: Proposed vs. Baseline A/B |
| **RQ2** | Does multi-agent decomposition improve MITRE mapping accuracy? | MITRE mapping F1: Proposed vs. Ablation 2 |
| **RQ3** | Does closed-loop repair improve Pass@1 beyond a single generation attempt? | Pass@1 vs. Pass@3 comparison |
| **RQ4** | Does schema normalization reduce field hallucination vs. direct generation? | Field hallucination rate: Proposed vs. Ablation 3 |
| **RQ5** | Do IR-generated rules achieve operational precision/recall suitable for SOC deployment? | P/R/F1 on labeled telemetry |

### 55.3 Hypothesis Framework

| Hypothesis | Expected Result | If Rejected |
|---|---|---|
| H1: IR reduces field hallucination | Proposed ≤ 5% vs. Baseline A ~45% | IR design may need augmentation with field constraints |
| H2: Multi-agent > single-agent | LSC improvement ≥ 15 percentage points | Role decomposition benefits may be model-dependent |
| H3: Repair loop increases Pass@1 | Repair version Pass@1 > no-repair by ≥ 15pp | Repair strategy needs redesign |
| H4: Generated rules are SOC-deployable | Precision ≥ 0.85, Recall ≥ 0.80 | Additional FP reduction needed for production |

---

## 56. Related Work

### 56.1 Prior Art in Automated Detection Rule Generation

| Work | Approach | Limitation vs. This Project |
|---|---|---|
| **SigmaFlow (2023)** | Template matching on STIX objects | Only works with structured STIX input; no NL handling |
| **GPT-Sigma (2024)** | Direct GPT-4 prompting for Sigma | No IR layer; 45%+ field hallucination rate |
| **MITRE TRAM** | ML-based tactic/technique classification | Classification only; does not generate detection rules |
| **SigmaHQ baseline** | Vanilla GPT-4 evaluation | No agent decomposition; no validation |
| **DetGen (2024)** | Fine-tuned LLM for Sigma generation | Requires expensive fine-tuning; single-platform output |
| **LLMSecDetect (2025)** | RAG-enhanced detection generation | No IR; no cross-platform; no repair loop |

**Differentiators of this project:**
- Only system using a typed IR as an intermediate contract
- Only system with cross-platform Sigma + KQL + SPL from a single input
- Only system with closed-loop telemetry-grounded repair
- Only system quantifying ATT&CK coverage from generated rules

### 56.2 Foundational Works Referenced

| Paper / Resource | Relevance |
|---|---|
| Minaee et al., "Large Language Models: A Survey" (2024) | LLM capability baseline |
| Anderson et al., "MITRE ATT&CK: Design and Philosophy" | ATT&CK framework foundations |
| Bayer et al., "SigmaHQ Dataset" (2025) | Primary evaluation benchmark |
| pySigma Documentation (2024) | Sigma rule format specification |
| Microsoft ASIM Documentation (2026) | ASIM schema reference |
| OCSF Specification v1.8 (2026) | OCSF schema reference |
| Chen et al., "CodeBLEU: A Method for Automatic Evaluation of Code Synthesis" | CodeBLEU metric definition |
| Wei et al., "Chain-of-Thought Prompting Elicits Reasoning in LLMs" | CoT prompting rationale |
| Park et al., "Generative Agents" | Multi-agent architecture inspiration |

---

## 57. Research Timeline

### 57.1 Project Phases

| Phase | Duration | Key Deliverables |
|---|---|---|
| **Phase 1: Foundation** | Weeks 1–4 | IR schema design, LangGraph setup, basic agent prompts |
| **Phase 2: Core Pipeline** | Weeks 5–8 | All agents, generators, basic validation, pySigma integration |
| **Phase 3: Validation** | Weeks 9–11 | Full 3-stage validation, repair loop, telemetry integration |
| **Phase 4: Evaluation** | Weeks 12–14 | SigmaHQ benchmarking, ablation studies, metric collection |
| **Phase 5: Write-Up** | Weeks 15–18 | Research paper, technical report, presentation slides |

### 57.2 Immediate Next Steps (Development Priority)

1. **Week 1:** Scaffold the `src/` directory structure; implement `ir_schema.py` with full Pydantic models
2. **Week 1:** Implement `PipelineState` and basic LangGraph graph with dummy nodes
3. **Week 2:** Implement Threat Intel and Entity Extraction agents with few-shot prompts
4. **Week 2:** Implement IR Builder Agent and verify output matches `SecurityIR` schema
5. **Week 3:** Implement Sigma generator and pySigma syntax validator
6. **Week 3:** Implement OCSF→ASIM schema mapper with YAML config files
7. **Week 4:** Implement KQL and SPL generators
8. **Week 4:** Implement semantic validator (field existence, EventID checks)
9. **Week 5:** Integrate HDFS dataset; implement telemetry validator
10. **Week 5:** Implement repair agent with structured repair actions
11. **Week 6:** End-to-end pipeline test on 5 sample inputs
12. **Week 7+:** SigmaHQ evaluation, ablation studies, benchmarking

---

---

# PART XIV — FUTURE WORK & EXTENSIBILITY

---

## 58. Short-Term Extensions (3–6 Months)

### 58.1 Additional SIEM Platforms

| Platform | Format | Priority | Technical Path |
|---|---|---|---|
| **Elastic ESQL** | ES|QL queries | High | Add `ocsf_to_ecs.yaml` + `ESQLGenerator` |
| **Google Chronicle YARA-L** | YARA-L 2.0 | High | Add `ocsf_to_chronicle.yaml` + `YARALGenerator` |
| **Microsoft Defender KQL** | Same as Sentinel KQL | Medium | Extend `KQLGenerator` with Defender table names |
| **IBM QRadar AQL** | AQL (SQL-like) | Medium | Add `AQLGenerator` with JOIN patterns |
| **AWS Security Lake OCSF** | Native OCSF queries | Low | Direct OCSF query generation |

### 58.2 Enhanced Input Processing

- **PDF/DOCX ingestion**: Use `pdfminer.six` and `python-docx` to extract text from vendor security advisories directly
- **STIX 2.1 native parsing**: Use `python-stix2` to parse structured CTI feeds without NL extraction agents
- **Web scraping pipeline**: Scrape and process threat intel blogs (Mandiant, CrowdStrike, MITRE) automatically
- **CVE integration**: Link CVE IDs in input text to NVD data for enrichment (affected products, CVSS scores)

### 58.3 Rule Library Management

- **Rule versioning**: Git-based rule versioning with diff tracking between IR versions
- **Rule deduplication**: Detect when two different inputs produce semantically equivalent rules
- **Coverage gap analysis**: Identify which ATT&CK techniques have no generated rules and surface them for prioritization
- **Rule deprecation**: Automatically flag rules when the underlying technique is deprecated in ATT&CK updates

---

## 59. Medium-Term Research Directions (6–18 Months)

### 59.1 Fine-Tuning Specialist Models

Instead of prompting large general models, fine-tune smaller specialist models:

| Specialist Model | Training Data | Target Task |
|---|---|---|
| **IR-Builder-7B** | 10K IR-input pairs from CTI reports | Security IR construction from CTI text |
| **MITRE-Mapper-3B** | 5K technique classification examples | MITRE technique identification |
| **SigmaGen-7B** | 50K SigmaHQ rules + IR pairs | Sigma rule generation from IR |
| **Repair-Agent-7B** | Validation error + repair pairs | Targeted IR repair from error messages |

Fine-tuned 7B models can match GPT-4o performance at 10% of the API cost with no data leaving the environment.

### 59.2 Adaptive Threshold Learning

Move from static thresholds to **organization-specific adaptive thresholds** learned from the organization's own telemetry:

```python
class AdaptiveThresholdLearner:
    """
    Learns organization-specific thresholds from baseline telemetry.
    Replaces generic defaults (5 failures/10 min) with
    organization-specific baselines (e.g., 3 failures/5 min for banking).
    """
    def fit(self, benign_telemetry: pd.DataFrame,
            attack_type: str, time_window_minutes: int) -> int:
        # Compute 99th percentile of normal activity as baseline
        baseline_counts = self._compute_event_counts(benign_telemetry, time_window_minutes)
        return int(baseline_counts.quantile(0.99)) + 1
```

### 59.3 Behavioral Fingerprinting

Instead of detecting individual IOCs (brittle — attackers change IPs, hashes), detect **behavioral patterns** (durable — techniques persist across campaigns):

- Move from `source_ip == "1.2.3.4"` (IOC-based) to `count(failed_auth) > threshold` (behavior-based)
- Move from `file_hash == "abc123"` to `process_parent == "word.exe" AND process_child in (known_living_off_the_land_binaries)`
- This shift is already partially implemented via the IR's `aggregation` layer but can be deepened with ML-based behavioral models

### 59.4 LLM-as-Judge Validation

Use a second LLM as a **judge** to evaluate generated rules on dimensions that automated checkers miss:

```python
class LLMJudge:
    """
    Uses a separate LLM to score rule quality on subjective dimensions.
    """
    JUDGE_PROMPT = """
    You are an expert detection engineer with 10 years of SOC experience.
    Rate the following detection rule on a scale of 1-10 for each dimension:

    1. Behavioral Fidelity: Does the rule accurately capture the described attack?
    2. False Positive Risk: How likely is this rule to generate false positives?
    3. Operational Clarity: Is the rule understandable to a junior analyst?
    4. Completeness: Are there any obvious attack variations the rule misses?

    Rule: {rule}
    Source Description: {description}

    Output JSON: {{"behavioral_fidelity": N, "fp_risk": N, "clarity": N, "completeness": N, "reasoning": "..."}}
    """
    def judge(self, rule: str, description: str) -> JudgeScore:
        response = self.llm.invoke(self.JUDGE_PROMPT.format(rule=rule, description=description))
        return JudgeScore(**json.loads(response.content))
```

---

## 60. Long-Term Vision (18+ Months)

### 60.1 Autonomous SOC Integration

The ultimate goal is integrating this framework into a **continuous detection engineering pipeline** where:

1. New threat intel arrives (STIX feed, blog post, incident report)
2. Framework automatically generates and validates detection rules
3. Rules with high confidence are automatically pushed to SIEM via API
4. Rules with lower confidence enter human review queue
5. SOC analyst dispositions (true positive / false positive) feed back into threshold calibration
6. Coverage gaps are surfaced weekly for prioritized manual authoring

```
Threat Intel Feed ──▶ IR Framework ──▶ SIEM API (auto-deploy, confidence ≥ 0.9)
                                   ──▶ Review Queue (confidence 0.7–0.9)
                                   ──▶ Discard (confidence < 0.7)
                         ▲
                         │
                    SOC Feedback (alert dispositions → threshold learning)
```

### 60.2 Cross-Organizational Rule Sharing

A federated model where participating organizations:
- Submit anonymized rule performance data (precision, recall, FPR) to a central registry
- Download community-calibrated thresholds tuned on real-world SOC data
- Share IR templates (not rules) for new threat categories

This creates a **network effect**: each organization's telemetry improves thresholds for all others, while raw log data never leaves the organization.

### 60.3 Detection as Code (DaC) Integration

Integrate the framework into the **Detection as Code** paradigm:
- Rules stored as version-controlled IR JSON files in Git
- CI/CD pipeline that re-validates rules when telemetry or schema changes
- Automated regression testing: any schema update re-runs all existing IR rules through the validation pipeline
- GitHub Actions workflow for rule promotion (experimental → test → stable)

```yaml
# .github/workflows/validate_rules.yaml
name: Validate Detection Rules
on: [push, pull_request]
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run rule validation
        run: python scripts/validate_all_rules.py --dataset datasets/synthetic/
      - name: Upload metrics
        uses: actions/upload-artifact@v4
        with:
          name: validation-report
          path: reports/validation_*.json
```

### 60.4 Multimodal Threat Intelligence

Extend the pipeline to process **multimodal threat intelligence**:
- **Diagram analysis**: Extract attack flows from threat report diagrams using vision models
- **PCAP analysis**: Extract behavioral patterns from packet captures for network-based rules
- **Memory dump analysis**: Extract process injection patterns from Windows memory dumps
- **Email phishing analysis**: Extract indicators from phishing email headers and bodies

---

## 61. Known Limitations & Mitigation Plans

| Limitation | Severity | Mitigation |
|---|---|---|
| **LLM API dependency** | High | Add local model fallback (Ollama + Mistral-7B) for air-gapped environments |
| **Context window limits** | Medium | Implement long-document chunking with overlap; summarize per-chunk then merge |
| **Telemetry dataset quality** | High | Expand synthetic generation; partner with organizations for anonymized real telemetry |
| **Repair loop convergence** | Medium | Implement gradient-based threshold search; add LLM judge to guide repair direction |
| **Schema staleness** | Low | Monthly automated pull of OCSF, ASIM, and SigmaHQ schemas |
| **Single IR per document** | Medium | Implement multi-rule extraction for documents describing compound attack chains |
| **LLM cost at scale** | Medium | Fine-tune smaller models; implement output caching for similar inputs |
| **No real-time telemetry** | Medium | Plan Phase 2 integration with streaming log platforms (Kafka, Splunk HEC) |

---

## 62. Summary of Key Design Decisions

| Decision | Chosen Approach | Alternative Considered | Reason for Choice |
|---|---|---|---|
| LLM role | Extraction + reasoning only | LLM for full rule generation | Template generation eliminates syntax errors |
| Intermediate Representation | JSON Schema (Pydantic) | Direct AST manipulation | Easier LLM output, human-readable, serializable |
| Agent framework | LangGraph | AutoGen, CrewAI | Native cycle support, built-in persistence |
| Schema standard | OCSF + ASIM | Custom schema | Industry adoption, future-proof |
| Validation order | Syntax → Semantic → Telemetry | Parallel validation | Earlier-stage failures are cheaper to fix |
| Repair target | Modify IR, regenerate rule | Modify rule directly | IR is source of truth; rule is a derived artifact |
| State persistence | SQLiteSaver checkpoints | In-memory only | Resume-ability on crash, audit trail |
| Platform support | Sigma + KQL + SPL | Single platform | Maximum research value; demonstrates IR generality |

---

---

---

# PART XV — SUPPLEMENTARY SECTIONS

---

## 63. Research Paper Structure

For academic publication or a formal whitepaper, the project should be structured as follows to highlight its novel contributions:

1. **Abstract**: Summary of the semantic gap problem, the IR-based solution, and empirical results.
2. **Introduction**: Motivation, the failure of direct LLM generation, and core contributions.
3. **Background & Related Work**: Current SOC workflows, SIEM capabilities, and limitations of existing NLP-to-Query systems (e.g., GPT-Sigma).
4. **Methodology: The Security IR**: Definition of the Intermediate Representation as a vendor-neutral contract.
5. **System Architecture**: Detailed breakdown of the LangGraph multi-agent pipeline (Threat Intel, Metadata, Entity, MITRE, IR Builder, Repair).
6. **Schema Normalization**: How OCSF and ASIM are leveraged to solve the cross-platform field mapping problem.
7. **Telemetry-Grounded Validation**: Description of the closed-loop repair mechanism and sandbox execution.
8. **Experimental Evaluation**: Benchmarking against SigmaHQ and SigmaHQ datasets. Metrics (CodeBLEU, LSC, SVR) comparing the proposed framework to baselines.
9. **Discussion**: Analysis of ablation studies, limitations, and the impact of the repair loop.
10. **Conclusion & Future Work**: Summary of findings and pathways to autonomous SOC integration.

---

## 64. Minimum Viable Prototype (MVP)

To ensure rapid development and iterative testing, the project will first deliver an MVP with constrained scope before expanding to the full architecture.

### MVP Scope Constraints
- **Supported Inputs**: Structured markdown threat reports (no PDF/DOCX parsing).
- **Target Platform**: Sigma rules only (simplifies generator logic).
- **Schema Mapping**: Direct translation to standard Sigma fields (bypassing full OCSF/ASIM translation initially).
- **Validation**: Syntax validation (pySigma) only; telemetry validation deferred.
- **Agents**: Core IR Builder and Sigma Generator only (monolithic prompt initially, refactored to multi-agent later).

### MVP Success Criteria
- The system can accept a 500-word threat description and output a syntactically valid Sigma YAML file.
- The generated rule correctly extracts at least one EventID and one IOC from the text.
- The pipeline executes end-to-end via a single FastAPI endpoint.

---

## 65. Advanced Features (Post-MVP)

Once the core pipeline is stable, the following advanced capabilities will be integrated:

- **Graph-Based Attack Correlation**: Correlating multiple generated IRs into a graph structure to detect multi-stage attack campaigns (e.g., Phishing → Lateral Movement → Exfiltration).
- **Explainable AI (XAI) Output**: Every generated rule will include a natural language "traceability report" explaining exactly which sentence in the source text justified each field in the detection logic.
- **Automated Threat Hunting Queries**: Beyond continuous detection rules, the framework will generate point-in-time threat hunting queries (e.g., retroactive KQL queries spanning 90 days).
- **RBAC & Approval Workflows**: Enterprise-grade role-based access control where junior analysts can generate rules, but Senior SOC engineers must approve them before deployment.

---

## 66. Risks and Challenges

| Risk | Probability | Impact | Mitigation Strategy |
|---|---|---|---|
| **LLM Hallucination of Fields** | High | High | Strict adherence to the IR schema; Pydantic validation; injected OCSF dictionaries in prompts. |
| **Telemetry Validation Overhead** | Medium | Medium | Use small, representative synthetic datasets for rapid validation; cache validation results. |
| **API Rate Limits / Latency** | High | Low | Implement exponential backoff in LangChain; use smaller models (GPT-4o-mini) for extraction tasks. |
| **Complex Temporal Logic Failure** | Medium | High | Rely on explicit Jinja2 templates for time windows rather than LLM query generation. |
| **Drift in SIEM Schemas** | Low | High | Externalize all mappings to YAML files; implement automated tests against daily schema definitions. |

---

## 67. Scalability Considerations

As the system processes higher volumes of threat intelligence, the architecture must scale:

1. **Horizontal Scaling of Agents**: Deploy LangGraph workers as Celery/Redis tasks, allowing multiple threat reports to be processed concurrently.
2. **IR Caching Layer**: Implement a Redis cache. If a new threat report yields an IR that is semantically identical to an existing rule, skip generation and map to the existing rule.
3. **Database Sharding**: Partition the `validation_results` and `repair_history` tables by month, as telemetry execution logs will grow rapidly.
4. **Vector Database Integration**: Store threat report embeddings in Qdrant/Pinecone to detect duplicate reports before they enter the expensive generation pipeline.

---

## 68. Learning Resources

For engineers onboarding to this project, the following resources are required reading:

### Core Frameworks
- **LangGraph Documentation**: State graphs, cycles, and persistence.
- **Pydantic V2**: Advanced schema validation and JSON serialization.
- **FastAPI**: Asynchronous REST API design.

### Cybersecurity Concepts
- **MITRE ATT&CK Framework**: Understanding tactics, techniques, and procedures (TTPs).
- **Sigma Rule Specification**: Syntax, modifiers, and conditions.
- **OCSF (Open Cybersecurity Schema Framework)**: Event classes and attributes.
- **Microsoft ASIM**: Advanced Security Information Model normalization.

---

## 69. Final Recommendations

1. **Protect the IR**: The Intermediate Representation is the most valuable IP in this system. Resist the urge to add platform-specific fields (e.g., KQL-specific keywords) to the IR. The IR must remain 100% vendor-agnostic.
2. **Prioritize Validation**: The repair loop is what elevates this from a "toy LLM project" to a production tool. Spend disproportionate development time ensuring the synthetic telemetry execution is accurate.
3. **Embrace Modularity**: Keep the schema mappers (`ocsf_to_sigma.yaml`) completely separate from the Python code. Adding a new SIEM platform should require zero Python changes, only new Jinja2 templates and YAML mappings.
4. **Monitor Token Costs**: Multi-agent systems consume massive token counts. Heavily cache prompt templates and use smaller models for straightforward tasks like Entity Extraction.

---

# CONCLUSION

This document is the authoritative technical reference for the **Natural Language to Executable Detection Logic** project. It provides complete specifications for:

- **Problem definition**: The semantic gap between threat intelligence and deployable SIEM rules
- **Architecture**: Multi-agent LangGraph pipeline with 8 specialized agents
- **Intermediate Representation**: Typed, validated Security IR as the cross-platform contract
- **Schema normalization**: OCSF + ASIM two-layer field mapping
- **Rule generation**: Deterministic Jinja2-based Sigma, KQL, and SPL generation
- **Validation**: Three-stage syntax → semantic → telemetry validation with structured error types
- **Repair**: Closed-loop autonomous IR repair with human review fallback
- **Prompt engineering**: Schema-grounded, role-constrained agent prompts with hallucination reduction
- **Evaluation**: SigmaHQ benchmark with CodeBLEU, LSC, Pass@k, and 6 other metrics
- **Implementation**: Complete folder structure, module implementations, API, and database design
- **Research**: Novel claims, related work, research questions, and 5 ablation designs
- **Supplementary**: MVP scoping, advanced features, scalability, and risks

Any new feature, agent, or platform extension should follow the patterns established in this document and maintain the **IR-as-contract** architectural principle as the single source of truth for all rule generation.

---

*Document Version: 1.0 | Last Updated: 2026-05-19 | Total Sections: 69 | Total Parts: XV*

*End of PROJECT_MASTER_DOCUMENT.md*
