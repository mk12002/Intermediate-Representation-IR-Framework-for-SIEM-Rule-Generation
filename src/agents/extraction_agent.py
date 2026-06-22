import os

from langchain_core.prompts import ChatPromptTemplate

from src.ir_engine.ir_schema import ExtractionOutput

from .base_agent import BaseAgent

_SYSTEM_PROMPT = """You are a security analyst extracting structured signal from a
natural language detection description. Do NOT guess at exact ASIM field
names or KQL syntax — that happens in a later step. Your job is only to
identify: the type of event being described, the actors involved, the
core action/behavior, any threshold language (e.g. "many", "more than
10"), any time-window language (e.g. "within five minutes",
"repeatedly"), and field names you believe are relevant.

{format_instructions}"""


class ExtractionAgent(BaseAgent):
    """First of System B's two generative steps — see docs/NL-KQL/architecture.md §11.1."""

    def __init__(self):
        model_name = os.getenv("EXTRACTION_LLM_MODEL", os.getenv("DEFAULT_LLM_MODEL", "qwen2.5:3b-instruct"))
        super().__init__(model_name=model_name)
        self.prompt = ChatPromptTemplate.from_messages(
            [("system", _SYSTEM_PROMPT), ("user", "{nl_description}")]
        )

    def extract(self, nl_description: str) -> ExtractionOutput:
        return self._invoke(
            prompt=self.prompt,
            pydantic_schema=ExtractionOutput,
            input_data={"nl_description": nl_description},
        )
