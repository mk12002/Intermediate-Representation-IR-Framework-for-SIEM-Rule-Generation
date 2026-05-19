# Implementation Playbook
**Natural Language to Executable Detection Logic Framework**

This playbook dictates the exact coding order, APIs, models, schemas, prompts, and datasets required to build the framework. It translates the architectural theory from `PROJECT_MASTER_DOCUMENT.md` into concrete, step-by-step engineering tasks.

---

## Week 1: Core Schemas & Pipeline Skeleton
**Goal:** Establish the deterministic foundation of the pipeline before introducing any LLM variance.

### 1. Exact Schemas (`src/ir_engine/ir_schema.py`)
- **API:** `pydantic.BaseModel`, `pydantic.Field`
- **Logic:** Define the exact `SecurityIR` schema. Must include `FilterCondition` (with `operator: Literal["equals", "contains", "regex", ...]`), `AggregationConfig`, and `TimeframeConfig`.
- *Status:* **Completed**.

### 2. Exact State (`src/pipeline/state.py`)
- **API:** `typing.TypedDict`, `typing.Annotated`, `operator.add`
- **Logic:** Define `PipelineState` containing raw inputs, extracted dictionaries, the IR dictionaries, validation errors, and the repair count.
- *Status:* **Completed**.

### 3. Exact LangGraph Workflow (`src/pipeline/graph.py`)
- **API:** `langgraph.graph.StateGraph`, `langgraph.checkpoint.memory.MemorySaver`
- **Logic:** Compile the workflow with parallel branches for extraction and sequential execution for generation/validation. Use `add_conditional_edges` on the validator node.
- *Status:* **Completed**.

### 4. IR Utilities (`src/ir_engine/ir_builder.py` & `ir_validator.py`)
- **Logic:** Utility classes implementing strict Pydantic validation and object assembly. These foundation files are injected into the pipeline early to provide error feedback.
- *Status:* **Completed**.

### Week 1 Milestone:
- The pipeline executes completely end-to-end using dummy nodes (returning empty dicts) without crashing. State passes correctly through the graph.

---

## Week 2: Prompts & Base Agents
**Goal:** Implement the specialized extraction agents using LangChain to populate the pipeline state.

### 1. Exact Models
- **Extraction Agents** (Threat Intel, Entity, Metadata, MITRE): `phi3` (Extremely fast, uses ~2.5GB VRAM, highly capable of structured extraction).
- **API Setup:** `langchain_ollama.ChatOllama(model="phi3", format="json", temperature=0.0)`

### 2. Exact Prompts
- **System Prompt (Threat Intel Agent):**
  ```text
  You are an expert SOC Analyst. Extract the core behavioral constraints from the provided cyber threat intelligence report.
  Ignore standard benign behavior. Focus strictly on indicators of compromise, attacker techniques, and anomalies.
  Format your output as a JSON list of dictionaries containing 'event_type', 'description', and 'confidence'.
  ```
- **System Prompt (Entity Extraction Agent):**
  ```text
  Extract all concrete entities mentioned in the text. Map them strictly to these categories: user, process, file, network, hostname, ip_address, hash.
  Output JSON format: {"category": "network", "value": "192.168.1.1", "context": "C2 beacon destination"}
  ```

### 3. Exact APIs
- Use `PydanticOutputParser` combined with Ollama's `format="json"` argument. SLMs require strong parsing logic since `.with_structured_output()` is optimized for OpenAI.
- Provide explicit Few-Shot examples in the system prompt.
- Example: `chain = prompt | llm | PydanticOutputParser(pydantic_object=ExtractedEntities)`

### Week 2 Milestone:
- A raw Markdown threat report is passed into the pipeline. The state correctly populates `behaviors`, `iocs`, `severity`, and `entities` lists.

---

## Week 3: IR Builder & MITRE Integration
**Goal:** Synthesize the disjointed extractions into a single, cohesive, structurally valid Intermediate Representation.

### 1. Exact Models
- **IR Builder Agent:** `llama3` 8B (4-bit quantized, uses ~4.7GB VRAM). Requires deep semantic reasoning to synthesize disparate extraction lists into a strict nested JSON schema.
- **API Setup:** `langchain_ollama.ChatOllama(model="llama3", format="json", temperature=0.0)`

### 2. Exact Logic (`src/ir_engine/ir_builder_agent.py`)
- Pass the entire accumulated `PipelineState` (behaviors, entities, metadata, mitre_mappings) into the IR Builder prompt.
- **System Prompt (IR Builder):**
  ```text
  You are the central IR Compiler. Your job is to take the disparate extractions provided in the pipeline state and synthesize them into a single, strict SecurityIR JSON object.
  You MUST adhere exactly to the provided JSON Schema. Do not invent fields. Do not use operators outside the allowed Literal lists.
  ```

### 3. Agent Integration with Validators
- Integrate the already-built `IRValidator` (`src/ir_engine/ir_validator.py`). Catch `ValidationError` from the LLM output and push the exact `loc` and `msg` strings into the pipeline's `errors` state array to trigger immediate retry if generation fails.

### Week 3 Milestone:
- The system generates a valid `SecurityIR` Pydantic object from a natural language report, surviving strict schema validation.

---

## Week 4: Schema Normalization & Generation
**Goal:** Convert the vendor-agnostic IR into deployable Sigma and KQL rules using deterministic templates.

### 1. Exact Schemas (`config/schemas/`)
- Implement a YAML-based two-layer normalization mapping.
- **Example `ocsf_to_asim.yaml`:**
  ```yaml
  authentication_failure:
    table: SigninLogs
    fields:
      src_ip: IPAddress
      user: UserPrincipalName
      action: ResultType
  authentication_success:
    table: SigninLogs
    fields:
      src_ip: IPAddress
      user: UserPrincipalName
      action: ResultType
  ```

### 2. Exact Logic (`src/generators/sigma_generator.py`)
- Do **not** use LLMs for this step. Use `jinja2`.
- **API:** `jinja2.Environment(loader=FileSystemLoader("templates/sigma"))`
- **Template (`sigma_base.yml.j2`):**
  ```yaml
  title: {{ metadata.rule_name }}
  description: {{ metadata.description }}
  logsource:
    category: {{ detection_logic.event_type }}
  detection:
    selection:
      {% for filter in detection_logic.filters %}
      {{ filter.field }}: {{ filter.value }}
      {% endfor %}
    condition: selection
  ```

### Week 4 Milestone:
- The pipeline produces a valid `.yml` (Sigma) and `.kql` string based purely on the IR constraints, without hallucinating platform-specific syntax.

---

## Week 5: Validation & Telemetry Sandbox
**Goal:** Prove the generated rules actually work via the 3-stage validation pipeline.

### 1. Advanced Validation Engines (`src/validation/`)
- **Syntax Validation Engine:** Integrate `pysigma.val.SigmaValidator`.
- **Semantic Validation Engine:** Build the AST-based custom parser to check Semantic Rule Equivalence (SRE) if comparing against a baseline rule.
- **Telemetry Validation (The Sandbox):** Use Python's `subprocess` to execute a local mocked Pandas evaluator or `eql` engine against generated JSON logs.

### 2. Exact Datasets
- **Log Generator (`src/validation/log_simulator.py`):**
  - **API:** `faker.Faker()`
  - Generate 100 negative samples (benign noise) and 5 positive samples (explicitly violating the IR constraints).
- **Benchmark Dataset:** `SigmaHQ` sample dataset (100 rules for end-to-end evaluation).

### Week 5 Milestone:
- The validation engine successfully executes a generated rule against mock logs and returns a structured JSON feedback object (`true_positives`, `false_positives`, `error_msg`).

---

## Week 6: The Repair Loop & Evaluation
**Goal:** Close the loop. Allow the system to fix its own logic based on sandbox feedback and evaluate the final performance.

### 1. Exact Prompts
- **System Prompt (Repair Agent):**
  ```text
  You are the Repair Agent. The generated SIEM rule failed execution.
  Original IR: {ir_json}
  Sandbox Feedback: {feedback_json}
  Errors: {error_list}
  
  Identify why the rule failed (e.g., syntax error, threshold too low causing false positives). Return a patched SecurityIR JSON object.
  CRITICAL INSTRUCTION: Only modify the field(s) referenced in the loc path of each ValidationError. Leave all other fields identical to the original IR.
  ```

### 2. Exact Milestones & Evaluation
- Implement `scripts/run_benchmark.py`.
- Run the pipeline on 50 samples from the `SigmaHQ (Descriptions)` dataset.
- Calculate and log the final **Execution Match Rate (EMR)** (Target: >85% alignment with human-written ground truth).
- Calculate and log the **Pass@k** metric for the repair loop (Target: rule passes validation within 3 attempts).

---
*End of Playbook.*
