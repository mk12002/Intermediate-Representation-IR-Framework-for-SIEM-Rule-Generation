# AI-Driven Detection Engineering Framework
**Bridging Natural Language and Executable SIEM Logic via Intermediate Representation (SecurityIR)**

![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-orange.svg)
![Ollama](https://img.shields.io/badge/Local_LLM-Ollama-black)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## 📖 Abstract
Translating cyber threat intelligence (CTI) into executable SIEM rules (like Splunk SPL, Microsoft Sentinel KQL, or Sigma) is a highly specialized task. While Large Language Models (LLMs) can parse threat reports, they historically fail at generating syntactically flawless query logic, suffering from extreme hallucination rates and invalid schemas.

This project solves the AI generation gap by introducing **SecurityIR**—a strict, vendor-neutral Intermediate Representation. Instead of asking AI to write a Kusto query, we use a multi-agent LangGraph pipeline powered by local Small Language Models (SLMs) to extract threat intelligence and populate a highly constrained, Pydantic-validated JSON schema (the IR). Once validated, deterministic Python generators compile the IR into flawless, executable rules for any SIEM platform.

---

## ⚡ Core Innovations

1. **SecurityIR Contract**: A formal, schema-validated Intermediate Representation (RFC-001) that isolates AI semantic reasoning from strict syntax generation.
2. **Local SLM Architecture**: Designed to run entirely locally without expensive API calls. Optimized for **RTX 4050 (6GB VRAM)**, utilizing `Phi-3-Mini` for rapid intelligence extraction and `Llama-3-8B` for deep IR synthesis via Ollama.
3. **Autonomous Repair Loop**: If an LLM hallucinates an invalid schema or invalid logic, the pipeline catches the Pydantic `ValidationError` and routes it to a dedicated Repair Agent to self-correct before compilation.
4. **Empirical Validation Sandbox**: Generated rules are executed against synthetic, OCSF-compliant mock telemetry locally to guarantee True Positive detection capabilities (Execution Match Rate).

---

## 🏗️ System Architecture

```mermaid
graph TD
    A[Raw Threat Report / CTI] --> B(LangGraph Pipeline)
    
    subgraph Multi-Agent Extraction Layer [Phi-3]
        B --> C[Threat Intel Agent]
        B --> D[Entity Extraction Agent]
        B --> E[Metadata Agent]
    end
    
    C --> F(IR Builder Agent [Llama-3])
    D --> F
    E --> F
    
    F --> G{Pydantic Validator}
    G -- "ValidationError (loc, msg)" --> H[Repair Agent]
    H --> G
    
    G -- "Valid SecurityIR JSON" --> I(Deterministic Generator Engine)
    
    subgraph Target Platforms
        I --> J[Sigma YAML]
        I --> K[Microsoft Sentinel KQL]
        I --> L[Splunk SPL]
    end
```

---

## 🚀 Getting Started

### Prerequisites
- **Python 3.10+**
- **Ollama**: Must be installed and running locally.
- **Hardware**: Minimum 6GB VRAM (e.g., RTX 4050) for local SLM execution.

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/IR-Framework-for-SIEM-Rule-Generation.git
   cd IR-Framework-for-SIEM-Rule-Generation
   ```

2. **Pull the Local Models via Ollama:**
   ```bash
   ollama pull phi3
   ollama pull llama3
   ```

3. **Install Python Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment:**
   Copy the example environment file and adjust if necessary.
   ```bash
   cp .env.example .env
   ```

---

## 📚 Documentation Hub

This project is built on a foundation of rigorous, academic-grade specification documents. To understand the underlying engineering and evaluation methodology, please refer to the `docs/` folder:

- 📖 **[Project Master Document](docs/PROJECT_MASTER_DOCUMENT.md)**: The complete architectural blueprint and theoretical foundation.
- 📜 **[RFC-001: SecurityIR v1.0](docs/RFC-001-SecurityIR-v1.md)**: The strict specification for the Intermediate Representation schemas and enums.
- 🚀 **[Implementation Playbook](docs/IMPLEMENTATION_PLAYBOOK.md)**: The step-by-step engineering guide detailing exact APIs, models, and prompts.
- 📊 **[Evaluation Handbook](docs/EVALUATION_HANDBOOK.md)**: The research benchmarking methodology (utilizing the SigmaHQ dataset).
- 📌 **[Project Index (deets.md)](docs/deets.md)**: The executive summary and high-level project map.

---

## 🔬 Evaluation & Metrics

Our framework evaluates generation quality using two custom, highly rigorous metrics:
- **Semantic Rule Equivalence (SRE):** An AST-based (Abstract Syntax Tree) comparison that measures logical equivalence rather than string similarity, overcoming the limitations of standard CodeBLEU.
- **Execution Match Rate (EMR):** The ultimate empirical metric. Generated rules are executed against synthetic telemetry alongside human-authored ground-truth rules to ensure a perfect alert match rate.

---

## 📜 License
This project is licensed under the MIT License - see the LICENSE file for details.