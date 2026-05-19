Natural Language to Executable Detection Logic
Complete System Design and Implementation Master Document

Project Proposal
Natural Language to Executable Detection Logic: A Multi-Agent Intermediate Representation Framework for Autonomous SIEM Rule Generation and Validation
1. Introduction and Objective

Modern Security Operations Centers (SOCs) rely heavily on Security Information and Event Management (SIEM) systems such as Microsoft Sentinel and Splunk to detect malicious activities from large-scale enterprise logs. However, developing analytical detection rules for these platforms requires extensive cybersecurity expertise, manual schema mapping, and platform-specific query engineering. Current AI-assisted approaches attempt to generate SIEM rules directly from natural language descriptions, but they frequently produce hallucinated syntax, incorrect MITRE ATT&CK mappings, and structurally invalid rules that are unsuitable for operational deployment.

This project proposes a multi-agent artificial intelligence framework capable of converting unstructured Standard Operating Procedures (SOPs) and Cyber Threat Reports (CTRs) into executable SIEM detection logic. The system introduces an Intermediate Representation (IR) layer to bridge the semantic gap between natural language threat descriptions and vendor-specific detection languages such as Kusto Query Language (KQL), Sigma, and Splunk SPL. Additionally, the framework incorporates a telemetry-grounded validation pipeline capable of automatically testing and repairing generated rules before deployment.

2. Problem Statement

The primary challenge in AI-driven detection engineering is the semantic disconnect between high-level threat narratives and the strict syntactic requirements of SIEM query languages. Large Language Models (LLMs) often fail when directly prompted to generate complex detection logic because they must simultaneously reason about cybersecurity semantics, vendor-specific schemas, and query syntax. This results in brittle rules with high false-positive rates, incorrect field mappings, and poor interoperability across cloud platforms such as AWS and Azure.

The project aims to address this challenge through a structured, schema-aware generation pipeline that separates semantic reasoning from platform-specific implementation.

3. Proposed Methodology

The proposed framework consists of four major stages:

Phase 1 – Multi-Agent NLP Extraction Layer:
Specialized AI agents process SOPs and threat reports to extract attack behaviors, indicators, constraints, severity levels, and MITRE ATT&CK mappings. Separate agents handle threat intelligence extraction and metadata generation to improve contextual understanding.

Phase 2 – Intermediate Representation (IR) Layer:
Instead of directly generating SIEM queries, the extracted logic is transformed into a standardized Intermediate Representation (IR). The IR captures filtering conditions, aggregation logic, thresholds, event relationships, and temporal constraints independent of vendor-specific syntax. This abstraction reduces hallucinations and improves portability across SIEM platforms.

Phase 3 – Dynamic Schema Mapping and Validation:
The IR is mapped to standardized cybersecurity schemas such as OCSF and ASIM. The system normalizes field names, validates entity mappings, and converts the IR into executable KQL, Sigma, or Splunk SPL queries suitable for AWS, Azure, and enterprise SOC environments.

Phase 4 – Closed-Loop Validation and Autonomous Repair:
Generated rules are executed against synthetic and benchmark telemetry datasets within a sandbox environment. If syntax failures or excessive false positives occur, a validation agent analyzes the execution logs and autonomously repairs the detection logic before finalization.

4. Expected Contributions

The proposed research is expected to contribute:

A schema-aware Intermediate Representation framework for AI-driven SIEM rule generation.
A multi-agent cybersecurity reasoning pipeline for converting natural language SOPs into executable detection logic.
An automated validation and repair mechanism that reduces hallucinations and false positives in generated SIEM rules.
Cross-platform interoperability through OCSF and ASIM-based schema normalization.
5. Datasets and Evaluation

The system will be evaluated using the SigmaHQ Repository for baseline rule comparisons, the CTI-REALM telemetry benchmark for realistic attack simulations, and the HDFS log dataset for anomaly-heavy operational validation. Performance will be measured using:

Precision, Recall, and False Positive Rate
Rule execution success rate
CodeBLEU and Logic Slot Consistency metrics
Cross-platform schema compatibility and detection accuracy

The final outcome of this project will be a research-oriented prototype demonstrating reliable and explainable AI-assisted SIEM rule engineering for modern SOC environments.

Table of Contents
Introduction
Real-World Cybersecurity Background
Understanding SIEM Systems
Detection Engineering Fundamentals
SOC Architecture and Workflows
Problem Statement and Research Gap
Why Current LLM Approaches Fail
Core Research Objectives
System Overview
High-Level System Architecture
Multi-Agent Architecture
Intermediate Representation (IR) Theory
Designing the Security IR
Schema Normalization and Mapping
OCSF and ASIM Deep Dive
Rule Generation Pipeline
Sigma Rules Deep Dive
KQL Deep Dive
Validation Pipeline
Closed-Loop Repair System
Telemetry and Log Analysis
Datasets and Benchmarking
Evaluation Metrics
Experiment Design
Folder Structure and Software Architecture
Detailed Module Breakdown
API Design
Database and Storage Design
LangGraph Workflow Design
Prompt Engineering Strategy
Hallucination Reduction Techniques
Rule Validation Strategies
False Positive Reduction Strategies
Threat Intelligence Integration
MITRE ATT&CK Mapping
Temporal Correlation Logic
Aggregation and Threshold Logic
Entity Extraction Pipeline
Security NLP Concepts
Research Contributions
Research Paper Structure
Phased Implementation Roadmap
Minimum Viable Prototype (MVP)
Advanced Features
Risks and Challenges
Scalability Considerations
Deployment Architecture
Future Work
Learning Resources
Final Recommendations
1. Introduction

This project focuses on building an AI-assisted detection engineering framework capable of converting unstructured natural language cybersecurity documents into executable SIEM detection rules.

The primary objective is to bridge the gap between:

Human-readable cybersecurity narratives
Machine-executable SIEM detection logic

The project introduces:

Multi-agent reasoning
Intermediate Representation (IR)
Schema-aware rule generation
Validation and repair loops
Telemetry-grounded evaluation

The system aims to improve:

Detection engineering speed
Rule validity
Schema interoperability
False positive reduction
SOC operational efficiency

This project is NOT:

a SIEM platform
a chatbot
an autonomous SOC
a threat intelligence platform

It IS:

an AI-assisted detection rule compiler
a research prototype
a cybersecurity AI systems framework
2. Real-World Cybersecurity Background
What Happens Inside a SOC?

A Security Operations Center (SOC) continuously monitors:

authentication logs
cloud logs
endpoint telemetry
network traffic
server events
process executions
DNS requests
API activity

The SOC attempts to detect:

malware
brute force attacks
phishing
lateral movement
persistence
data exfiltration
privilege escalation

SOC analysts create detection rules manually.

These rules are:

time-consuming to build
platform-specific
error-prone
difficult to maintain
3. Understanding SIEM Systems
What Is a SIEM?

SIEM = Security Information and Event Management.

Examples:

Microsoft Sentinel
Splunk
Elastic Security
IBM QRadar
Chronicle

A SIEM performs:

Log collection
Log normalization
Event correlation
Threat detection
Alerting
Investigation support
Example SIEM Workflow
Windows Event Logs
CloudTrail Logs
Azure Activity Logs
Linux Syslogs
Firewall Logs


        ↓


SIEM Ingestion


        ↓


Detection Rules Execute


        ↓


Alerts Generated


        ↓


SOC Investigation
4. Detection Engineering Fundamentals

Detection engineering is the process of creating rules that identify malicious activity.

Example:

Detect:
- more than 5 failed logins
- within 10 minutes
- followed by successful login

This becomes:

Sigma rule
KQL query
SPL query

Detection engineering requires:

understanding attacker behavior
understanding telemetry
understanding SIEM syntax
understanding schemas
5. SOC Architecture and Workflows
Typical SOC Workflow
Logs arrive
SIEM stores logs
Detection rules execute
Alerts are generated
Analysts investigate
Incident response begins
Problem in Current SOCs

Detection engineering bottlenecks:

rules are written manually
syntax differs across platforms
schema mappings are difficult
false positives are common
onboarding new detections is slow

This creates:

detection lag
analyst fatigue
operational inefficiency
6. Problem Statement and Research Gap
Core Research Problem

Current LLMs fail when directly generating SIEM rules because they must simultaneously:

understand cybersecurity semantics
understand SIEM syntax
understand schemas
understand temporal logic
understand aggregations
understand ATT&CK mappings

This causes:

hallucinated syntax
invalid YAML
incorrect field mappings
poor interoperability
high false positive rates
7. Why Current LLM Approaches Fail
Traditional Approach
Natural Language
       ↓
Single Prompt
       ↓
Direct KQL/Sigma

Problems:

too much reasoning burden
no intermediate abstraction
no schema normalization
no validation loop
Example Failure

Prompt:

Generate Sentinel rule for brute force login attempts.

Possible AI issues:

invalid KQL syntax
wrong field names
incorrect aggregation logic
missing time windows
invalid ATT&CK mapping
8. Core Research Objectives

The project aims to:

Build a schema-aware IR system
Reduce hallucinations in rule generation
Improve syntax validity
Normalize cross-platform schemas
Add telemetry-grounded validation
Introduce repair-based iterative refinement
9. System Overview
Core Pipeline
Natural Language SOP
        ↓
Multi-Agent Parsing
        ↓
Intermediate Representation
        ↓
Schema Mapping
        ↓
Rule Generation
        ↓
Validation
        ↓
Repair Loop
        ↓
Validated Detection Rule
10. High-Level System Architecture
Major Components
Input Layer

Receives:

SOPs
Threat reports
Analyst notes
Agent Layer

Performs:

extraction
reasoning
classification
mapping
IR Layer

Stores:

structured detection semantics
Mapping Layer

Handles:

OCSF
ASIM
vendor normalization
Rule Generator

Generates:

Sigma
KQL
SPL
Validation Layer

Checks:

syntax
telemetry execution
false positives
Repair Layer

Fixes:

syntax failures
logic flaws
noisy rules
11. Multi-Agent Architecture
Why Multi-Agent?

One model doing everything causes:

confusion
inconsistent reasoning
hallucinations
poor modularity

Instead:

divide responsibilities
Coordinator Agent

Responsibilities:

workflow orchestration
routing
state management
agent communication
Threat Intelligence Agent

Extracts:

attack behaviors
attacker tactics
suspicious indicators
ATT&CK mappings

Example:

multiple failed SSH logins

Maps to:

Brute Force
MITRE T1110
Metadata Agent

Generates:

severity
tags
descriptions
YAML metadata
Entity Extraction Agent

Extracts:

usernames
IP addresses
hostnames
ports
process names
IR Builder Agent

MOST IMPORTANT AGENT.

Converts:

extracted semantics → structured IR
Validation Agent

Checks:

syntax
execution
false positives
Repair Agent

Refines:

thresholds
filters
mappings
syntax
12. Intermediate Representation (IR) Theory
What Is an IR?

IR = Intermediate Representation.

Used in:

compilers
query planners
databases
distributed systems
Compiler Analogy
Python Code
     ↓
Bytecode
     ↓
Machine Code

Your project:

Natural Language
      ↓
Security IR
      ↓
KQL / Sigma
Why IR Matters

The IR:

separates semantics from syntax
improves modularity
reduces hallucinations
enables portability
13. Designing the Security IR
IR Requirements

The IR must represent:

filters
thresholds
aggregations
entities
temporal windows
correlations
ATT&CK mappings
severity
Example IR
{
  "rule_name": "Brute Force Login",
  "event_type": "authentication_failure",
  "threshold": {
    "count": 5,
    "window": "10m"
  },
  "correlation": {
    "followed_by": "authentication_success"
  },
  "entity": "user",
  "severity": "high",
  "mitre": ["T1110"]
}
IR Sections
Metadata

Contains:

rule name
severity
tags
descriptions
Detection Logic

Contains:

filters
counts
thresholds
aggregations
Temporal Logic

Contains:

windows
sequences
ordering
Entity Mapping

Contains:

users
IPs
hosts
processes
14. Schema Normalization and Mapping
Why Schema Mapping Exists

Different SIEMs use different fields.

Example:

Concept	Sentinel	Splunk	AWS
User	AccountName	user	userIdentity
IP	SrcIpAddr	src_ip	sourceIPAddress
Goal of Mapping

Create:

Unified Semantic Layer

that later converts into:

Sentinel fields
Splunk fields
Sigma-compatible fields
15. OCSF and ASIM Deep Dive
OCSF

Open Cybersecurity Schema Framework.

Purpose:

vendor-neutral schema standardization
ASIM

Advanced Security Information Model.

Used by:

Microsoft Sentinel

Purpose:

normalized field abstraction
Why Important?

Without normalization:

generated rules fail across environments
interoperability becomes impossible
16. Rule Generation Pipeline
Transformation Flow
IR
 ↓
Rule Templates
 ↓
Executable SIEM Rule
Generators
Sigma Generator

Produces:

Sigma YAML rules
KQL Generator

Produces:

Microsoft Sentinel queries
SPL Generator

Produces:

Splunk rules
17. Sigma Rules Deep Dive
What Is Sigma?

Sigma is:

vendor-neutral
YAML-based
detection-rule standard
Example Sigma Rule
logsource:
  product: windows


detection:
  selection:
    EventID: 4625


condition: selection
Sigma Structure
Metadata
title
id
description
tags
Logsource
product
service
Detection
filters
conditions
logic
18. KQL Deep Dive
What Is KQL?

KQL = Kusto Query Language.

Used in:

Microsoft Sentinel
Azure Data Explore

