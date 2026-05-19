from pydantic import BaseModel, Field
from typing import List
from .base_agent import BaseAgent
from langchain_core.prompts import ChatPromptTemplate

class MITREMapping(BaseModel):
    tactic: str = Field(description="e.g., 'Credential Access'")
    tactic_id: str = Field(description="e.g., 'TA0006'")
    technique: str = Field(description="e.g., 'Brute Force'")
    technique_id: str = Field(description="e.g., 'T1110'")
    rationale: str = Field(description="Why does this mapping apply?")

class ExtractedMITRE(BaseModel):
    mappings: List[MITREMapping]

class MITREMappingAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """Map the behaviors described in the text to the MITRE ATT&CK framework.
Provide the tactic name, tactic ID, technique name, technique ID, and rationale.

{format_instructions}"""),
            ("user", "Threat Report:\n{report_text}")
        ])

    def extract(self, report_text: str) -> dict:
        result = self._execute_with_retry(
            prompt=self.prompt,
            pydantic_schema=ExtractedMITRE,
            input_data={"report_text": report_text}
        )
        return {"mitre_mappings": [m.model_dump() for m in result.mappings]}
