from pydantic import BaseModel, Field
from typing import List, Literal
from .base_agent import BaseAgent
from langchain_core.prompts import ChatPromptTemplate

class Entity(BaseModel):
    category: Literal["user", "process", "file", "network", "hostname", "ip_address", "hash"]
    value: str
    context: str = Field(description="Why is this entity relevant?")

class ExtractedEntities(BaseModel):
    entities: List[Entity]

class EntityExtractionAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """Extract all concrete entities mentioned in the text. Map them strictly to the allowed categories.
            
Example:
Input: The attacker used 192.168.1.1 to beacon out.
Output: {{"entities": [{{"category": "ip_address", "value": "192.168.1.1", "context": "C2 beacon destination"}}]}}

{format_instructions}"""),
            ("user", "Text:\n{report_text}")
        ])

    def extract(self, report_text: str) -> dict:
        result = self._execute_with_retry(
            prompt=self.prompt,
            pydantic_schema=ExtractedEntities,
            input_data={"report_text": report_text}
        )
        return {"entities": [e.model_dump() for e in result.entities]}
