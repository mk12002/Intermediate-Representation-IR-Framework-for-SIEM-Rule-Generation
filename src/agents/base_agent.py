import logging
import os
from typing import Type, TypeVar

from langchain_core.exceptions import OutputParserException
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_cache_configured = False


def _maybe_configure_llm_cache() -> None:
    """Opt-in, disk-persisted cache keyed on the exact rendered prompt +
    model + params (LangChain's standard SQLiteCache) — set LLM_CACHE_PATH
    to make iterative re-runs of an unrelated fix cheap. Deliberately NOT
    used during a variance/replication study (PROJECT_STATUS.md §4T): at
    temperature=0 the model is still not fully deterministic, so caching
    the FIRST response would silently hide the exact variance an N-run
    replication exists to measure. Idempotent — set_llm_cache is global
    and only needs to run once per process."""
    global _cache_configured
    if _cache_configured:
        return
    cache_path = os.getenv("LLM_CACHE_PATH")
    if cache_path:
        from langchain_community.cache import SQLiteCache
        from langchain_core.globals import set_llm_cache

        set_llm_cache(SQLiteCache(database_path=cache_path))
    _cache_configured = True


def build_chat_model(model_name: str, temperature: float):
    """Provider is fixed once for the whole study (MASTER_PLAN §20) via LLM_PROVIDER.

    Supported: "anthropic", "openai", "azure_foundry", "ollama" (local).
    """
    _maybe_configure_llm_cache()
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    # OpenAI's `seed` param is "best effort" reproducibility, not a
    # cryptographic guarantee — found live (PROJECT_STATUS.md §4T) to
    # reduce but not eliminate run-to-run variance. None (the default)
    # preserves every prior round's behavior exactly; set LLM_SEED to opt
    # in for a specific replication run.
    _seed_env = os.getenv("LLM_SEED")
    seed = int(_seed_env) if _seed_env else None
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=model_name, temperature=temperature)
    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=model_name, temperature=temperature, seed=seed)
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
            seed=seed,
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
