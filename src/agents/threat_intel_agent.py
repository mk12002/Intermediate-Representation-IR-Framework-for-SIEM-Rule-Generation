from pydantic import BaseModel, Field
from typing import List, Literal
from .base_agent import BaseAgent
from langchain_core.prompts import ChatPromptTemplate

class Behavior(BaseModel):
    event_type: str = Field(description="Broad category of the event, e.g., 'authentication_failure', 'process_creation'")
    description: str = Field(description="Detailed description of what the attacker is doing")
    confidence: float = Field(default=1.0, description="Confidence in this extraction (0.0 - 1.0)")

class ExtractedBehaviors(BaseModel):
    behaviors: List[Behavior]

class ThreatIntelAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert SOC Analyst. Extract the core behavioral constraints from the provided cyber threat intelligence report.
Ignore standard benign behavior. Focus strictly on indicators of compromise, attacker techniques, and anomalies.

{format_instructions}"""),
            ("user", "Threat Report:\n{report_text}")
        ])

    def extract(self, report_text: str) -> dict:
        result = self._execute_with_retry(
            prompt=self.prompt,
            pydantic_schema=ExtractedBehaviors,
            input_data={"report_text": report_text}
        )
        return {"behaviors": [b.model_dump() for b in result.behaviors]}
