import json
import os
from typing import Optional

from langchain_core.prompts import ChatPromptTemplate

from src.ir_engine.ir_schema import ExtractionOutput, SecurityIR
from src.ir_engine.ir_validator import ValidationResult

from .base_agent import BaseAgent

_BUILD_SYSTEM_PROMPT = """You are converting a structured extraction into a Security IR
object that conforms exactly to the schema below. You may ONLY use field
names that appear in the provided ASIM field reference below — do not infer
or guess field names from general knowledge of similar platforms.

ASIM field reference for {likely_event_type}:
{asim_field_list}

{format_instructions}

Return ONLY one JSON object that is a valid INSTANCE of this schema —
actual field values describing this specific detection, never the schema
definition itself (no "$defs", "properties", or "required" keys in your
output)."""

_REPAIR_SYSTEM_PROMPT = """Your previous IR failed validation with the following error:
{structured_validator_error}

Correct ONLY the issue described above. Do not change other parts of the IR
unless necessary to fix this specific error.

Previous IR:
{previous_ir_json}

ASIM field reference for {likely_event_type}:
{asim_field_list}

{format_instructions}

Return ONLY one corrected JSON object that is a valid INSTANCE of this
schema — actual field values, never the schema definition itself (no
"$defs", "properties", or "required" keys in your output)."""


class IRBuilderAgent(BaseAgent):
    """Second of System B's two generative steps — see docs/NL-KQL/architecture.md §11.2."""

    def __init__(self):
        model_name = os.getenv("IR_BUILDER_LLM_MODEL", os.getenv("DEFAULT_LLM_MODEL", "qwen3.5:4b"))
        super().__init__(model_name=model_name)
        self.build_prompt = ChatPromptTemplate.from_messages(
            [("system", _BUILD_SYSTEM_PROMPT), ("user", "{extraction_output}")]
        )
        self.repair_prompt = ChatPromptTemplate.from_messages(
            [("system", _REPAIR_SYSTEM_PROMPT), ("user", "Correct the IR.")]
        )

    def build(
        self,
        extraction: ExtractionOutput,
        asim_field_list: list[str],
        repair_error: Optional[ValidationResult] = None,
        previous_ir: Optional[SecurityIR] = None,
    ) -> SecurityIR:
        if repair_error is None:
            return self._invoke(
                prompt=self.build_prompt,
                pydantic_schema=SecurityIR,
                input_data={
                    "likely_event_type": extraction.likely_event_type,
                    "asim_field_list": json.dumps(asim_field_list),
                    "extraction_output": extraction.model_dump_json(),
                },
            )

        return self._invoke(
            prompt=self.repair_prompt,
            pydantic_schema=SecurityIR,
            input_data={
                "structured_validator_error": repair_error.message,
                "previous_ir_json": previous_ir.model_dump_json() if previous_ir else "{}",
                "likely_event_type": extraction.likely_event_type,
                "asim_field_list": json.dumps(asim_field_list),
            },
        )
