import os

from src.agents.base_agent import build_chat_model

from .prompt import BASELINE_PROMPT


class BaselineRunner:
    """System A — single-prompt direct generation. No validation, no repair.

    Must use the same underlying LLM and temperature as System B (the IR
    Builder Agent) for a fair comparison — see docs/NL-KQL/MASTER_PLAN.md §9.5.
    """

    def __init__(self, model_name: str | None = None, temperature: float = 0.0):
        model_name = model_name or os.getenv("IR_BUILDER_LLM_MODEL", os.getenv("DEFAULT_LLM_MODEL", "qwen3.5:4b"))
        self.llm = build_chat_model(model_name, temperature)
        self.chain = BASELINE_PROMPT | self.llm

    def run(
        self,
        nl_description: str,
        asim_field_reference: str,
        few_shot_example_1: str,
        few_shot_example_2: str,
    ) -> str:
        result = self.chain.invoke(
            {
                "nl_description": nl_description,
                "asim_field_reference": asim_field_reference,
                "few_shot_example_1": few_shot_example_1,
                "few_shot_example_2": few_shot_example_2,
            }
        )
        return result.content.strip()
