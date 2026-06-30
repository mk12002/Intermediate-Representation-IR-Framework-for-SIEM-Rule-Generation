import json

from src.execution.ir_interpreter import pipeline_fires
from src.generator.compiler import generate_kql
from src.ir_engine.ir_validator import validate_ir
from src.synthesis.fixture_generator import should_fire_rows, should_not_fire_rows
from src.synthesis.ir_generator import (
    _COMBINATION_TEMPLATES, _TEMPLATES, generate_batch, generate_combination_batch,
    generate_mixed_batch,
)
from src.validation.syntax_validators import validate_kql_syntax

ASIM_SCHEMA = json.loads(open("data/schema/asim_field_reference.json", encoding="utf-8").read())


def test_every_generated_pipeline_is_schema_and_syntax_valid():
    batch = generate_batch(150, seed=1) + generate_combination_batch(60, seed=1)
    for ir, meta in batch:
        v = validate_ir(ir, ASIM_SCHEMA)
        assert v.passed, f"{meta.template} failed schema validation: {v.error_type} {v.message}"
        kql = generate_kql(ir)
        sv = validate_kql_syntax(kql)
        assert sv.passed, f"{meta.template} failed syntax validation: {sv.message}"


def test_every_template_is_exercised_in_a_large_enough_batch():
    batch = generate_batch(200, seed=2)
    seen_templates = {meta.template for _, meta in batch}
    all_templates = {t.__name__.replace("gen_", "") for t in _TEMPLATES}
    assert seen_templates == all_templates


def test_every_combination_template_is_exercised_in_a_large_enough_batch():
    batch = generate_combination_batch(60, seed=4)
    seen_templates = {meta.template for _, meta in batch}
    all_templates = {t.__name__.replace("gen_", "") for t in _COMBINATION_TEMPLATES}
    assert seen_templates == all_templates


def test_mixed_batch_draws_from_both_pools():
    batch = generate_mixed_batch(60, seed=5, combination_fraction=0.5)
    seen_templates = {meta.template for _, meta in batch}
    single_names = {t.__name__.replace("gen_", "") for t in _TEMPLATES}
    combo_names = {t.__name__.replace("gen_", "") for t in _COMBINATION_TEMPLATES}
    assert seen_templates & single_names, "mixed batch produced no single-construct templates"
    assert seen_templates & combo_names, "mixed batch produced no combination templates"


def test_auto_generated_fixtures_match_the_generated_irs_own_intended_logic():
    """The actual closed-loop check this module exists for: a fixture
    derived from the SAME generation metadata that produced the IR must
    make that IR fire (should_fire) or not fire (should_not_fire) when
    run through the interpreter — confirming the generator and fixture
    generator agree with each other before either is ever used to
    evaluate a live system. Covers combination templates too — the
    same closed-loop guarantee must hold for chains, not just isolated
    constructs."""
    batch = generate_batch(80, seed=3) + generate_combination_batch(60, seed=6)
    for ir, meta in batch:
        # system_ir=ir: checking the generator against its OWN output,
        # so the "system" choosing field names IS the generator here —
        # the decoupling (see fixture_generator.py) matters once a real
        # system's independently-chosen IR is being evaluated instead.
        fire_rows = should_fire_rows(meta, system_ir=ir)
        if fire_rows:
            assert pipeline_fires(ir, fire_rows) is True, f"{meta.template}: should_fire rows did not fire"
        no_fire_rows = should_not_fire_rows(meta, system_ir=ir)
        if no_fire_rows:
            assert pipeline_fires(ir, no_fire_rows) is False, f"{meta.template}: should_not_fire rows fired anyway"


def test_generation_is_reproducible_with_a_fixed_seed():
    batch_a = generate_batch(10, seed=123)
    batch_b = generate_batch(10, seed=123)
    kql_a = [generate_kql(ir) for ir, _ in batch_a]
    kql_b = [generate_kql(ir) for ir, _ in batch_b]
    assert kql_a == kql_b
