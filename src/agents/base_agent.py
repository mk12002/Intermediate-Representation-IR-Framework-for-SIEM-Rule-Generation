import logging
import os
from typing import Type, TypeVar

from langchain_core.exceptions import OutputParserException
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def build_chat_model(model_name: str, temperature: float):
    """Provider is fixed once for the whole study (MASTER_PLAN §20) via LLM_PROVIDER.

    Supported: "anthropic", "openai", "ollama" (local).
    """
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=model_name, temperature=temperature)
    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=model_name, temperature=temperature)
    if provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=model_name,
            temperature=temperature,
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            format="json",
        )
    raise ValueError(f"unknown LLM_PROVIDER: {provider}")


class BaseAgent:
    def __init__(self, model_name: str, temperature: float = 0.0):
        self.model_name = model_name
        self.llm = build_chat_model(model_name, temperature)
        self.max_attempts = 3

    def _invoke(self, prompt: ChatPromptTemplate, pydantic_schema: Type[T], input_data: dict) -> T:
        parser = PydanticOutputParser(pydantic_object=pydantic_schema)
        input_data.setdefault("format_instructions", parser.get_format_instructions())
        chain = prompt | self.llm | parser

        for attempt in range(self.max_attempts):
            try:
                return chain.invoke(input_data)
            except (OutputParserException, ValidationError) as e:
                logger.warning(
                    "parse attempt %d/%d failed for %s: %s",
                    attempt + 1, self.max_attempts, self.__class__.__name__, e,
                )
                if attempt == self.max_attempts - 1:
                    raise
