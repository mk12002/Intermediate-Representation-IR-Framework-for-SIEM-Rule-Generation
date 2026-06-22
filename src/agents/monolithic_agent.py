import json
import os

from langchain_core.prompts import ChatPromptTemplate

from src.ir_engine.ir_schema import SecurityIR

from .base_agent import BaseAgent

_SYSTEM_PROMPT = """You are converting a natural language detection description
directly into a Security IR object that conforms exactly to the schema below.
You may ONLY use field names that appear in the provided ASIM field reference
below — do not infer or guess field names from general knowledge of similar
platforms.

ASIM field reference:
{asim_field_list}

{format_instructions}"""


class MonolithicAgent(BaseAgent):
    """Ablation 2 — merges Extraction + IR Builder into one prompt, skipping
    the intermediate ExtractionOutput structure. Isolates whether agent
    decomposition itself helps (RQ2). See docs/NL-KQL/MASTER_PLAN.md §18.
    """

    def __init__(self):
        model_name = os.getenv("IR_BUILDER_LLM_MODEL", os.getenv("DEFAULT_LLM_MODEL", "qwen2.5:7b-instruct"))
        super().__init__(model_name=model_name)
        self.prompt = ChatPromptTemplate.from_messages(
            [("system", _SYSTEM_PROMPT), ("user", "{nl_description}")]
        )

    def build(self, nl_description: str, asim_field_list: list[str]) -> SecurityIR:
        return self._invoke(
            prompt=self.prompt,
            pydantic_schema=SecurityIR,
            input_data={
                "nl_description": nl_description,
                "asim_field_list": json.dumps(asim_field_list),
            },
        )
