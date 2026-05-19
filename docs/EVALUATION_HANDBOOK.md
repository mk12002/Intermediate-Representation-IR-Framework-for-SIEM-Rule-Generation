# Evaluation Handbook
**Natural Language to Executable Detection Logic Framework**

This handbook defines the exact methodology, baselines, ablation configurations, and metric computations required to scientifically evaluate the IR-based multi-agent framework against traditional Large Language Model approaches.

---

## 1. Exact Benchmark Methodology

To ensure academic rigor, we evaluate the framework against two standardized datasets, measuring both structural validity and execution correctness.

### 1.1 Datasets
- **SigmaHQ Benchmark Dataset (N=100):** A curated subset of official Sigma rules paired with their natural language descriptions. Because academic datasets like SigmaHQ are often gated or unavailable, we use the robust, open-source SigmaHQ repository as our single source of truth for evaluating extraction capabilities, Semantic Rule Equivalence (SRE), and the Execution Match Rate (EMR).

### 1.2 Evaluation Pipeline Flow
1. Load dataset (Description + Ground Truth Query).
2. Pass Description through the Multi-Agent Pipeline.
3. Compare Output Query vs. Ground Truth Query (SRE & Syntax checks).
4. Execute both queries against synthetic telemetry.
5. Compute EMR based on triggered alerts.

---

## 2. Telemetry Generation Protocol

Generating statistically significant telemetry is handled by `scripts/generate_telemetry.py`. 

### 2.1 The OCSF Simulator
We use `faker` combined with cyber-specific providers to generate JSON logs conforming to the Open Cybersecurity Schema Framework (OCSF).

**Generation Logic:**
- **Negative Samples (95%):** Pure background noise. Successful authentications, standard web traffic, benign process creations (e.g., `svchost.exe`, `explorer.exe`).
- **Positive Samples (5%):** Logs specifically designed to trigger the ground-truth rule by extracting constraints from the ground-truth Sigma rule and satisfying them in the mock data.

**Exact API Usage:**
```python
from faker import Faker
import json

fake = Faker()
# Custom providers for cyber entities
def generate_malicious_login():
    return {
        "class_name": "Authentication",
        "activity_id": 3, # Logon Failed
        "user": {"name": "admin"},
        "src_endpoint": {"ip": fake.ipv4_public()}
    }
```

---

## 3. Baseline Prompts

To prove the superiority of the Multi-Agent IR architecture, we evaluate against a standard **Single-Prompt Monolithic Baseline**.

### 3.1 The Monolithic Baseline Prompt
This baseline uses `gpt-4o` attempting to do the entire task in one shot.

```text
You are an expert Detection Engineer. 
Read the following cyber threat intelligence report.
Your task is to generate a valid Sigma YAML rule that detects the behavior described.
Do not output anything other than the YAML. Ensure all field names are correct.

Threat Report: {report_text}
```
*Hypothesis:* This baseline will suffer from high hallucination rates, invalid YAML syntax, and incorrect field mappings.

---

## 4. Exact Ablation Setups

Ablation studies systematically disable components of the framework to measure their individual impact. 

We configure the evaluation script (`scripts/run_benchmark.py`) with the following flags:

| Ablation Config | Flag | Expected Result on Metrics |
|-----------------|------|----------------------------|
| **Full Pipeline** | `--mode full` | Highest EMR, Highest Syntax Validity. |
| **No Repair Loop** | `--mode no_repair` | Pipeline fails instantly on syntax errors. Drop in Pass@k. |
| **No IR (Direct Gen)** | `--mode no_ir` | Agents output KQL directly. Massive drop in schema compliance. |
| **Single Agent** | `--mode single_agent` | Monolithic prompt. High hallucination, low SRE. |

---

## 5. Evaluation Scripts & CLI

The central evaluation engine is located at `scripts/run_benchmark.py`.

**Execution CLI Examples:**
```bash
# 1. Run the baseline evaluation on SigmaHQ
python scripts/run_benchmark.py --dataset sigmahq --mode single_agent --output results/baseline.json

# 2. Run the full pipeline evaluation
python scripts/run_benchmark.py --dataset sigmahq --mode full --output results/full_pipeline.json

# 3. Generate Evaluation Report (Computes deltas)
python scripts/compute_metrics.py --baseline results/baseline.json --experiment results/full_pipeline.json
```

---

## 6. Metrics Computation

The `scripts/compute_metrics.py` file mathematically calculates the final scores.

### 6.1 Syntax Validity Rate (SVR)
A binary check using `pySigma`.
- **Formula:** `Total Valid YAML / Total Generated`

### 6.2 Semantic Rule Equivalence (SRE)
Instead of CodeBLEU, we parse queries into ASTs.
- **Python Implementation:**
  ```python
  def compute_sre(ast_generated, ast_ground_truth):
      # Normalize commutative operators (e.g., A AND B == B AND A)
      nodes_gen = set(extract_nodes(normalize_ast(ast_generated)))
      nodes_gt = set(extract_nodes(normalize_ast(ast_ground_truth)))
      # Return partial match score (Jaccard similarity of AST nodes)
      if not nodes_gt: return 0.0
      return len(nodes_gen.intersection(nodes_gt)) / len(nodes_gen.union(nodes_gt))
  ```

### 6.3 Execution Match Rate (EMR)
The ultimate empirical metric. Both rules run against the synthetic telemetry.
- **Formula (Jaccard Similarity):** 
  ```python
  def compute_emr(alerts_generated: set, alerts_ground_truth: set):
      intersection = alerts_generated.intersection(alerts_ground_truth)
      union = alerts_generated.union(alerts_ground_truth)
      if len(union) == 0: return 1.0 # Both correctly fired 0 alerts
      return len(intersection) / len(union)
  ```

### 6.4 Repair Pass@k
Measures the effectiveness of the autonomous repair loop.
- **Formula:** What percentage of rules become syntactically and semantically valid within $k$ iterations of the Repair Agent (where $k=3$ is standard).
