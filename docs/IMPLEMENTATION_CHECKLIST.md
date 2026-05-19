# Implementation Checklist

## Phase 1: Foundation (Weeks 1-4)
- [x] Scaffold project directory structure
- [x] Create project boilerplate files (`requirements.txt`, `.env.example`, `docker-compose.yml`, `Dockerfile`)
- [x] Implement Security IR Schema (`src/ir_engine/ir_schema.py`)
- [x] Implement LangGraph Pipeline State (`src/pipeline/state.py`)
- [x] Implement LangGraph Graph Definition (`src/pipeline/graph.py`)
- [x] Implement `ir_builder.py` and `ir_validator.py` utilities

## Phase 2: Agents (Weeks 5-8)
- [ ] Implement Base Agent (`src/agents/base_agent.py`)
- [ ] Implement Threat Intel Agent (`src/agents/threat_intel_agent.py`)
- [ ] Implement Entity Extraction Agent (`src/agents/entity_extraction_agent.py`)
- [ ] Implement Metadata Agent (`src/agents/metadata_agent.py`)
- [ ] Implement MITRE Mapping Agent (`src/agents/mitre_mapping_agent.py`)
- [ ] Implement IR Builder Agent (`src/agents/ir_builder_agent.py`)
- [ ] Implement Repair Agent (`src/agents/repair_agent.py`)
- [ ] Implement Coordinator Agent (`src/agents/coordinator.py`)

## Phase 3: Schema Mapping & Generators
- [ ] Implement OCSF Resolver (`src/schema_mapping/ocsf_resolver.py`)
- [ ] Implement Schema Mapper (`src/schema_mapping/schema_mapper.py`)
- [ ] Implement Field Validator (`src/schema_mapping/field_validator.py`)
- [ ] Create YAML mappings (`config/schemas/`)
- [ ] Implement Base Generator (`src/generators/base_generator.py`)
- [ ] Implement Sigma Generator (`src/generators/sigma_generator.py`)
- [ ] Implement KQL Generator (`src/generators/kql_generator.py`)
- [ ] Implement SPL Generator (`src/generators/spl_generator.py`)

## Phase 4: Validation Engine
- [ ] Implement Syntax Validators (`src/validation/syntax_validators.py`)
- [ ] Implement Semantic Validator (`src/validation/semantic_validator.py`)
- [ ] Implement Telemetry Validator (`src/validation/telemetry_validator.py`)
- [ ] Implement Validation Engine Coordinator (`src/validation/validation_engine.py`)

## Phase 5: API, Storage & Utils
- [ ] Implement DB Models & Store (`src/storage/database.py`, `rule_store.py`)
- [ ] Implement FastAPI endpoints (`src/api/main.py`, `routers/`)
- [ ] Implement API Schemas (`src/api/schemas.py`)
- [ ] Implement Logger (`src/utils/logger.py`)
- [ ] Implement Metrics (`src/utils/metrics.py`)

## Phase 6: Testing & Benchmarking
- [ ] Write Unit Tests
- [ ] Write Integration Tests
- [ ] Implement Benchmark Runner (`scripts/run_benchmark.py`)
- [ ] Final end-to-end evaluation
