import os

os.environ.setdefault("LLM_PROVIDER", "ollama")

from src.synthesis.back_translate import BackTranslator


def test_both_style_prompts_construct_without_stray_brace_errors():
    """Same bug class found twice already this project (stray literal
    `{`/`}` in worked-example prose breaking ChatPromptTemplate's
    variable detection) — guard both the rich and terse system prompts
    the same way."""
    translator = BackTranslator()
    assert sorted(translator.rich_prompt.input_variables) == ["compiled_kql", "format_instructions"]
    assert sorted(translator.terse_prompt.input_variables) == ["compiled_kql", "format_instructions"]


def test_translate_style_argument_selects_the_right_prompt(monkeypatch):
    translator = BackTranslator()
    seen = {}

    def fake_invoke(prompt, pydantic_schema, input_data):
        seen["prompt"] = prompt
        return pydantic_schema(description="x")

    monkeypatch.setattr(translator, "_invoke", fake_invoke)
    translator.translate("source_table", object(), style="terse")
    assert seen["prompt"] is translator.terse_prompt
    translator.translate("source_table", object(), style="rich")
    assert seen["prompt"] is translator.rich_prompt
