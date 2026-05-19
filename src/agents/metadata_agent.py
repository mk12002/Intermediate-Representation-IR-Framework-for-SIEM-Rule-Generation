from pydantic import BaseModel, Field
from typing import List, Literal
from .base_agent import BaseAgent
from langchain_core.prompts import ChatPromptTemplate

class Metadata(BaseModel):
    severity: Literal["informational", "low", "medium", "high", "critical"]
    description: str = Field(description="A 1-sentence summary of the rule's purpose")
    tags: List[str] = Field(description="Keywords for the rule, e.g., ['lateral_movement', 'windows']")

class MetadataAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a Detection Engineering manager. Given a threat report, provide the appropriate metadata (severity, brief description, and tags) for the resulting SIEM rule.

{format_instructions}"""),
            ("user", "Threat Report:\n{report_text}")
        ])

    def extract(self, report_text: str) -> dict:
        result = self._execute_with_retry(
            prompt=self.prompt,
            pydantic_schema=Metadata,
            input_data={"report_text": report_text}
        )
        return result.model_dump()
