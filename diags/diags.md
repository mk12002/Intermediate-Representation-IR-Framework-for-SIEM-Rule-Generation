1. High-Level End-to-End System Architecture

'''
flowchart TD

A[User Provides SOP / Threat Report] --> B[Input Preprocessing Layer]

B --> C1[Threat Intelligence Agent]
B --> C2[Metadata Agent]
B --> C3[Entity Extraction Agent]

C1 --> D[Intermediate Representation Builder]
C2 --> D
C3 --> D

D --> E[Security IR Object]

E --> F1[Schema Mapper]
E --> F2[Rule Generator]

F1 --> G[OCSF / ASIM Normalization]

G --> F2

F2 --> H1[Sigma Rule Generator]
F2 --> H2[KQL Generator]
F2 --> H3[Splunk SPL Generator]

H1 --> I[Validation Engine]
H2 --> I
H3 --> I

I --> J1[Syntax Validation]
I --> J2[Semantic Validation]
I --> J3[Telemetry Execution Validation]

J1 --> K[Repair Agent]
J2 --> K
J3 --> K

K --> D

I --> L[Final Validated Detection Rule]

L --> M[SIEM Deployment / SOC Usage]
'''

2. Detailed Multi-Agent Workflow
'''
flowchart LR

A[SOP / Threat Report] --> B[Coordinator Agent]

B --> C1[Threat Intel Agent]
B --> C2[Metadata Agent]
B --> C3[Entity Extraction Agent]
B --> C4[MITRE Mapping Agent]

C1 --> D1[Attack Behavior Extraction]
C1 --> D2[IOC Identification]

C2 --> D3[Severity Classification]
C2 --> D4[Rule Description Generation]

C3 --> D5[IP Extraction]
C3 --> D6[Username Extraction]
C3 --> D7[Process Extraction]

C4 --> D8[Tactic Mapping]
C4 --> D9[Technique Mapping]

D1 --> E[IR Builder Agent]
D2 --> E
D3 --> E
D4 --> E
D5 --> E
D6 --> E
D7 --> E
D8 --> E
D9 --> E

E --> F[Structured Security IR]
'''

3. Intermediate Representation (IR) Internal Structure
'''
flowchart TD

A[Security IR]

A --> B1[Metadata]
A --> B2[Detection Logic]
A --> B3[Entity Mapping]
A --> B4[Temporal Logic]
A --> B5[MITRE Mapping]
A --> B6[Output Configuration]

B1 --> C1[Rule Name]
B1 --> C2[Severity]
B1 --> C3[Tags]

B2 --> C4[Filters]
B2 --> C5[Aggregations]
B2 --> C6[Thresholds]

B3 --> C7[User]
B3 --> C8[IP Address]
B3 --> C9[Hostname]

B4 --> C10[Time Window]
B4 --> C11[Sequence Correlation]

B5 --> C12[Tactics]
B5 --> C13[Techniques]

B6 --> C14[Target SIEM]
B6 --> C15[Rule Format]
'''

4. SOP → IR → Rule Transformation Flow
'''
flowchart LR

A[Natural Language SOP]

A --> B[Semantic Parsing]

B --> C[Behavior Extraction]

C --> D[Structured Detection Logic]

D --> E[Intermediate Representation]

E --> F1[Sigma Translation]
E --> F2[KQL Translation]
E --> F3[SPL Translation]

F1 --> G[Executable Sigma Rule]
F2 --> H[Executable KQL Rule]
F3 --> I[Executable SPL Rule]
'''

5. Schema Mapping Architecture
'''
flowchart TD

A[Security IR Fields]

A --> B[Schema Normalization Layer]

B --> C1[OCSF Mapper]
B --> C2[ASIM Mapper]
B --> C3[Custom Vendor Mapper]

C1 --> D1[Normalized User Field]
C1 --> D2[Normalized IP Field]

C2 --> D3[Sentinel-Compatible Fields]

C3 --> D4[Vendor Specific Fields]

D1 --> E[Unified Detection Schema]
D2 --> E
D3 --> E
D4 --> E

E --> F[Platform-Specific Rule Generator]
'''

6. Validation and Repair Pipeline
'''
flowchart TD

A[Generated Detection Rule]

A --> B[Syntax Validator]

B --> C{Syntax Valid?}

C -- No --> D[Repair Agent]

D --> E[Modify Rule Logic]

E --> A

C -- Yes --> F[Telemetry Execution Engine]

F --> G[Run Rule Against Logs]

G --> H{False Positives High?}

H -- Yes --> I[Repair Agent]

I --> J[Adjust Thresholds / Filters]

J --> A

H -- No --> K[Validated Detection Rule]
'''

7. Telemetry Validation Workflow
'''
flowchart LR

A[Generated Rule]

A --> B1[HDFS Logs]
A --> B2[CTI-REALM Telemetry]
A --> B3[Synthetic Enterprise Logs]

B1 --> C[Detection Execution Engine]
B2 --> C
B3 --> C

C --> D1[True Positives]
C --> D2[False Positives]
C --> D3[False Negatives]

D1 --> E[Metric Calculator]
D2 --> E
D3 --> E

E --> F1[Precision]
E --> F2[Recall]
E --> F3[FPR]
E --> F4[Execution Success Rate]
'''

8. Direct LLM vs Proposed IR Pipeline
'''
flowchart TD

subgraph Traditional Approach
A1[SOP] --> B1[Single LLM Prompt]
B1 --> C1[Direct KQL/Sigma]
C1 --> D1[High Hallucination Risk]
end

subgraph Proposed IR-Based Framework
A2[SOP] --> B2[Multi-Agent Parsing]
B2 --> C2[Intermediate Representation]
C2 --> D2[Schema Mapping]
D2 --> E2[Rule Generation]
E2 --> F2[Validation + Repair]
F2 --> G2[Validated Rule]
end
'''

9. Full Research Evaluation Pipeline
'''
flowchart TD

A[Input SOP Dataset]

A --> B1[Baseline Direct LLM]
A --> B2[Proposed IR Framework]

B1 --> C1[Generated Rules]
B2 --> C2[Generated Rules]

C1 --> D[Benchmark Evaluation]
C2 --> D

D --> E1[Syntax Validity]
D --> E2[Execution Success]
D --> E3[Precision]
D --> E4[Recall]
D --> E5[False Positive Rate]
D --> E6[CodeBLEU]
D --> E7[Logic Consistency]

E1 --> F[Comparative Analysis]
E2 --> F
E3 --> F
E4 --> F
E5 --> F
E6 --> F
E7 --> F

F --> G[Research Results]
'''

10. Suggested Folder-Level System Architecture
'''
flowchart TD

A[Project Root]

A --> B1[input_processing]
A --> B2[agents]
A --> B3[ir_engine]
A --> B4[schema_mapper]
A --> B5[rule_generators]
A --> B6[validation]
A --> B7[repair_engine]
A --> B8[datasets]
A --> B9[evaluation]
A --> B10[api]

B2 --> C1[threat_agent.py]
B2 --> C2[metadata_agent.py]
B2 --> C3[entity_agent.py]

B3 --> C4[ir_schema.py]
B3 --> C5[ir_builder.py]

B5 --> C6[sigma_generator.py]
B5 --> C7[kql_generator.py]

B6 --> C8[syntax_validator.py]
B6 --> C9[telemetry_validator.py]

B7 --> C10[repair_agent.py]

B9 --> C11[metrics.py]
B9 --> C12[benchmark_runner.py]
'''