import os
from typing import Type, TypeVar, Any
from pydantic import BaseModel, ValidationError
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.exceptions import OutputParserException
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)

class BaseAgent:
    def __init__(self, model_name: str = None, temperature: float = 0.0):
        # Default to phi3 for fast extraction, override via env or param
        self.model_name = model_name or os.getenv("FAST_LLM_MODEL", "phi3")
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        
        self.llm = ChatOllama(
            model=self.model_name,
            temperature=temperature,
            base_url=base_url,
            format="json"  # Crucial for local SLMs to enforce JSON format
        )
        self.max_retries = 3

    def _execute_with_retry(self, prompt: ChatPromptTemplate, pydantic_schema: Type[T], input_data: dict) -> T:
        parser = PydanticOutputParser(pydantic_object=pydantic_schema)
        
        # Inject format instructions into the prompt dynamically
        format_instructions = parser.get_format_instructions()
        if "format_instructions" not in input_data:
            input_data["format_instructions"] = format_instructions

        chain = prompt | self.llm | parser

        for attempt in range(self.max_retries):
            try:
                result = chain.invoke(input_data)
                return result
            except (OutputParserException, ValidationError) as e:
                logger.warning(f"Parse attempt {attempt + 1} failed for {self.__class__.__name__}: {str(e)}")
                if attempt == self.max_retries - 1:
                    logger.error("Max retries reached for JSON parsing.")
                    raise e
