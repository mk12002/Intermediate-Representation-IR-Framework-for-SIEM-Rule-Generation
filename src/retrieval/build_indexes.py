"""Builds the two routed RAG indexes from their source corpora, once,
offline. The built indexes (data/rag_indexes/*.pkl) ARE committed to the
repo so normal users don't need to run this. Run this script only when:
  - You are setting up from scratch (no .rag_corpora/ and no pre-built
    .pkl files), OR
  - The train-split pairs or source corpora have changed and you want
    to pick up the new content.

**§4AD: down to two indexes, not three.** A third index (KQL construct
syntax/semantics, MicrosoftDocs/dataexplorer-docs) was built in §4AB,
then dropped here after the evidence came in: its own retrieval-quality
check was "honestly mixed" (TF-IDF has no real semantic understanding,
so exact-vocabulary queries retrieved the right page and vaguer natural-
language ones often didn't), and the full RAG A/B + independent second
rater (§4AC) found no measurable Logic Correctness benefit to credit
against that added complexity. `build_construct_index()` and its corpus-
clone instructions are removed; re-add both if testing semantic
embeddings instead of TF-IDF — the wash result is specific to lexical
retrieval (see PROJECT_STATUS.md §4AD), not a verdict on RAG in general.

=== One-time corpus setup (only needed if .rag_corpora/ is absent) ===

Clone the ASIM schema doc repo with sparse checkout — blob:none keeps
it lean by not materializing file content until git checkout needs it:

  # ASIM normalization schema field definitions (14 pages, one per schema):
  # NOTE: Sentinel docs moved from azure-docs -> defender-docs; the public
  # branch is correct — confirmed live 2026-06-30.
  git clone --filter=blob:none --no-checkout --depth=1 --branch public \\
      https://github.com/MicrosoftDocs/defender-docs.git \\
      .rag_corpora/defender-docs
  cd .rag_corpora/defender-docs
  git sparse-checkout init --cone
  git sparse-checkout set sentinel
  git checkout public
  cd ../..

This directory is gitignored (.rag_corpora/ in .gitignore). Corpus #2
(worked NL->KQL examples) comes from data/processed/pairs_verified.jsonl
(already in the repo) and needs no separate clone.

=== Run the index build ===

    PYTHONPATH=. python src/retrieval/build_indexes.py

No LLM calls — pure offline TF-IDF preprocessing. Writes two .pkl
files to data/rag_indexes/ (committed to the repo).

=== Sources ===

  1. ASIM field definitions — MicrosoftDocs/defender-docs, sentinel/
     normalization-schema-*.md. Field-level descriptions that
     data/schema/asim_field_reference.json deliberately doesn't carry
     (it's a bare field-name list for the schema validator, not docs).
     Measured 3/3 correct retrieval after the camelCase-query fix (§4AB).
  2. Worked NL->KQL examples — this project's OWN train-split verified
     pairs (data/processed/pairs_verified.jsonl, filtered to
     data/splits/train_ids.json) — never the test split or the
     held-out set, so a later held-out A/B test stays honest.
"""
import json
import re
from pathlib import Path

from src.retrieval.retriever import Chunk, TfidfRetriever

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RAG_CORPORA = _REPO_ROOT / ".rag_corpora"
_INDEX_DIR = _REPO_ROOT / "data" / "rag_indexes"

_MAX_CHUNK_CHARS = 4000  # keep prompt-injected chunks compact; doc pages
# run long (examples, "see also" sections) and only the first portion
# (title + syntax + summary) carries the actual high-value signal.


_BOILERPLATE_PATTERNS = [
    r"^---\n.*?\n---\n",                          # YAML frontmatter (author/ms.date/ms.topic)
    r"> \[!INCLUDE.*?\]\n?",                        # repeated "applies to version" admonitions
    r":::moniker.*?:::moniker-end\n?",              # per-version conditional blocks (often duplicate content per moniker)
    r"> \[!div[^\n]*\n> <a href=\"[^\n]*\n?",       # "Run the query" deep-link buttons (long encoded URLs, no content)
    r":::image[^\n]*\n?",                           # image embeds — alt text only, no retrievable content
]


def _clean_markdown_frontmatter(text: str) -> str:
    """Strips Microsoft Learn boilerplate shared across every doc page —
    YAML frontmatter, version-applicability admonitions, moniker-range
    blocks, and encoded deep-link buttons — none of which carry
    retrieval signal, and which otherwise both dilute TF-IDF's term
    weighting and waste prompt tokens on content with zero detection-
    logic value."""
    for pattern in _BOILERPLATE_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.DOTALL)
    return text.strip()


def _title_from_filename(path: Path) -> str:
    stem = path.stem
    stem = re.sub(r"-(operator|function|aggregation-function|plugin)$", "", stem)
    return stem.replace("-", " ")


def build_asim_schema_index() -> TfidfRetriever:
    src_dir = _RAG_CORPORA / "defender-docs" / "sentinel"
    chunks = []
    for path in sorted(src_dir.glob("normalization-schema-*.md")):
        text = _clean_markdown_frontmatter(path.read_text(encoding="utf-8"))[:_MAX_CHUNK_CHARS]
        if len(text.strip()) < 50:
            continue
        title = _title_from_filename(path)
        chunks.append(Chunk(id=path.stem, text=f"{title}\n\n{text}", metadata={"title": title}))
    print(f"asim_schema index: {len(chunks)} chunks from {src_dir}")
    return TfidfRetriever.build(chunks)


def build_worked_examples_index() -> TfidfRetriever:
    train_ids = set(json.loads((_REPO_ROOT / "data" / "splits" / "train_ids.json").read_text(encoding="utf-8")))
    pairs = [
        json.loads(line)
        for line in (_REPO_ROOT / "data" / "processed" / "pairs_verified.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    chunks = []
    for p in pairs:
        if p["rule_id"] not in train_ids:
            continue  # train split ONLY — never test split, never held-out
        desc = p["description_raw"].strip().strip("'\"")
        chunks.append(Chunk(
            id=p["rule_id"],
            text=desc,
            metadata={"description": desc, "kql": p["query"]},
        ))
    print(f"worked_examples index: {len(chunks)} chunks (train split only)")
    return TfidfRetriever.build(chunks)


def main():
    _INDEX_DIR.mkdir(parents=True, exist_ok=True)
    build_asim_schema_index().save(str(_INDEX_DIR / "asim_schema.pkl"))
    build_worked_examples_index().save(str(_INDEX_DIR / "worked_examples.pkl"))
    print("done.")


if __name__ == "__main__":
    main()
