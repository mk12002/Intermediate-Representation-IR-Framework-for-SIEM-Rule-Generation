import os
import json
from .base_agent import BaseAgent
from langchain_core.prompts import ChatPromptTemplate
from src.ir_engine.ir_schema import SecurityIR

class IRBuilderAgent(BaseAgent):
    def __init__(self):
        # Override with the heavy default model (llama3) for complex reasoning
        model_name = os.getenv("DEFAULT_LLM_MODEL", "llama3")
        super().__init__(model_name=model_name)
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are the central IR Compiler for a SIEM detection framework.
Your job is to take disparate extractions provided by other agents (behaviors, entities, metadata, MITRE mappings) 
and synthesize them into a single, strict SecurityIR JSON object.

CRITICAL INSTRUCTIONS:
- You MUST adhere EXACTLY to the provided JSON Schema.
- Do NOT invent fields.
- Do NOT use operators outside the allowed Literal lists.
- If an entity or behavior requires a time constraint, define it in the timeframe object.

{format_instructions}"""),
            ("user", """Extracted Behaviors: {behaviors}
Extracted Entities: {entities}
Metadata: {metadata}
MITRE Mappings: {mitre_mappings}

Synthesize these into the final SecurityIR JSON object.""")
        ])

    def build_ir(self, state_data: dict) -> dict:
        result = self._execute_with_retry(
            prompt=self.prompt,
            pydantic_schema=SecurityIR,
            input_data={
                "behaviors": json.dumps(state_data.get("behaviors", [])),
                "entities": json.dumps(state_data.get("entities", [])),
                "metadata": json.dumps(state_data.get("metadata", {})),
                "mitre_mappings": json.dumps(state_data.get("mitre_mappings", []))
            }
        )
        return result.model_dump()
