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

    Supported: "anthropic", "openai", "azure_foundry", "ollama" (local).
    """
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=model_name, temperature=temperature)
    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=model_name, temperature=temperature)
    if provider == "azure_foundry":
        from langchain_openai import ChatOpenAI

        # Azure AI Foundry's unified v1 endpoint is OpenAI-API-compatible —
        # plain ChatOpenAI works against it via base_url, no AzureChatOpenAI
        # (which targets the older *.openai.azure.com + api-version shape).
        # model_name here is the Azure *deployment name*, not a bare model ID.
        return ChatOpenAI(
            model=model_name,
            temperature=temperature,
            base_url=os.environ["AZURE_FOUNDRY_ENDPOINT"],
            api_key=os.environ["AZURE_FOUNDRY_API_KEY"],
        )
    if provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=model_name,
            temperature=temperature,
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            format="json",
            # Thinking-capable models (e.g. Qwen3.x) otherwise burn the
            # entire output budget on <think> content and never emit the
            # final answer (observed: done_reason="length", content="").
            # Structured extraction has no use for chain-of-thought here.
            reasoning=False,
        )
    raise ValueError(f"unknown LLM_PROVIDER: {provider}")


class BaseAgent:
    def __init__(self, model_name: str, temperature: float = 0.0):
        self.model_name = model_name
        self.temperature = temperature
        self.llm = build_chat_model(model_name, temperature)
        # At temperature=0 the call is deterministic — retrying an identical
        # parse failure just reproduces the same failure N times and wastes
        # the attempt budget that the *real* repair mechanism (the IR
        # Builder's structured-error repair loop, see repair_loop.py) needs.
        # Only retry here when there's actual stochasticity to benefit from.
        self.max_attempts = 3 if temperature > 0 else 1

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
