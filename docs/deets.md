# Project Executive Summary & Index
**Natural Language to Executable Detection Logic**

This document serves as the high-level index and navigational hub for the AI-driven Detection Engineering project.

## 1. Project Abstract
The core challenge in AI-driven cybersecurity is that Large Language Models (LLMs) often hallucinate syntax when asked to write complex SIEM rules (like Splunk SPL or Kusto KQL) directly from natural language. 

This project solves that by introducing **SecurityIR** (a strict, vendor-neutral Intermediate Representation). Our multi-agent LangGraph pipeline uses SLMs (Small Language Models like Llama-3 and Phi-3) to extract intelligence and assemble it into this IR. Once validated, deterministic Python generators (using Jinja2) compile the IR into flawless, executable queries for any SIEM platform.

## 2. Documentation Directory
To prevent architectural confusion, the massive original plans have been formalized into strict, academic-grade specification documents. 

Please refer to the following authoritative documents:

### 📖 [Project Master Document](./PROJECT_MASTER_DOCUMENT.md)
The complete architectural blueprint. Details the 4-stage pipeline (Preprocessing, Agentic IR Builder, Generation, Validation), the LangGraph cyclic state logic, and the theoretical foundation of the system.

### 📜 [RFC-001: SecurityIR v1.0](./RFC-001-SecurityIR-v1.md)
The strict specification for the Intermediate Representation. Defines the core JSON schemas, required Pydantic fields, enums (e.g., `distinct_count`), and compatibility invariants.

### 🚀 [Implementation Playbook](./IMPLEMENTATION_PLAYBOOK.md)
The week-by-week engineering guide. Defines the exact LLMs (`llama3`, `phi3`), the exact LangChain APIs (`PydanticOutputParser`, `ChatOllama`), the exact prompts, and the development milestones.

### 📊 [Evaluation Handbook](./EVALUATION_HANDBOOK.md)
The research benchmarking methodology. Defines how we test the framework against the monolithic baseline using the `SigmaHQ` dataset, detailing the calculation of the Semantic Rule Equivalence (SRE) and Execution Match Rate (EMR) metrics.

### ✅ [Implementation Checklist](./IMPLEMENTATION_CHECKLIST.md)
The active, living tracker of our development progress.

---
**Current Status:** 🟢 *Phase 2 Implementation (Extraction Agents Completed).*
