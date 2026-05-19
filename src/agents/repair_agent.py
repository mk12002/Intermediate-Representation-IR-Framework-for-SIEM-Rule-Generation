import os
import json
from .base_agent import BaseAgent
from langchain_core.prompts import ChatPromptTemplate
from src.ir_engine.ir_schema import SecurityIR

class RepairAgent(BaseAgent):
    def __init__(self):
        # Use the heavy default model (llama3) for complex reasoning
        model_name = os.getenv("DEFAULT_LLM_MODEL", "llama3")
        super().__init__(model_name=model_name)
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are the Repair Agent for a SIEM detection framework.
The generated SIEM rule (SecurityIR) failed Pydantic validation or execution sandbox testing.

CRITICAL INSTRUCTION: Only modify the field(s) referenced in the loc path of each ValidationError. 
Leave all other fields identical to the original IR. Do NOT invent new logic.

{format_instructions}"""),
            ("user", """Original IR: {ir_json}
Validation Errors: {error_list}
Sandbox Feedback: {feedback_json}

Identify why the rule failed and return a patched, valid SecurityIR JSON object.""")
        ])

    def repair_ir(self, ir_dict: dict, error_list: list, feedback_json: dict = None) -> dict:
        result = self._execute_with_retry(
            prompt=self.prompt,
            pydantic_schema=SecurityIR,
            input_data={
                "ir_json": json.dumps(ir_dict),
                "error_list": json.dumps(error_list),
                "feedback_json": json.dumps(feedback_json or {})
            }
        )
        return result.model_dump()
