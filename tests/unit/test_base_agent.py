import os
from unittest.mock import patch

from src.agents.base_agent import BaseAgent


def _make_agent(temperature: float) -> BaseAgent:
    with patch.dict(os.environ, {"LLM_PROVIDER": "ollama"}), patch(
        "src.agents.base_agent.build_chat_model"
    ) as mock_build:
        mock_build.return_value = object()
        return BaseAgent(model_name="qwen3.5:4b", temperature=temperature)


def test_max_attempts_is_one_at_zero_temperature():
    """At temperature=0 the call is deterministic — retrying an identical
    parse failure just reproduces the identical failure. Internal retry
    must not run here; the real repair mechanism lives in repair_loop.py."""
    agent = _make_agent(temperature=0.0)
    assert agent.max_attempts == 1


def test_max_attempts_allows_retry_at_nonzero_temperature():
    agent = _make_agent(temperature=0.7)
    assert agent.max_attempts == 3
