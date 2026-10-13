"""Tests du découpage (rapides, sans modèle) et du RAG (avec le vrai modèle d'embedding)."""

import pytest

from src.config import BRAND_DIR
from src.ingest import chunk_document, chunk_section, count_tokens, ingest, split_sections
from src.rag import retrieve, sources_of


def word_count(text: str) -> int:
    """Compteur de tokens simplifié pour les tests unitaires (1 mot = 1 token)."""
    return len(text.split())


def test_split_sections_ignores_disclaimer_before_title():
    body = "> Document FICTIF\n\n# Titre\n\nIntro.\n\n## Partie\n\nContenu."
    assert split_sections(body) == [("Titre", "Intro."), ("Partie", "Contenu.")]


def test_chunks_respect_max_tokens_and_overlap():
    text = " ".join(f"Phrase numéro {i} assez courte." for i in range(40))
    chunks = chunk_section("Doc > Section", text, word_count, max_tokens=30, overlap=10)
    assert len(chunks) > 1
    assert all(word_count(c) <= 30 for c in chunks)
    # chevauchement : la fin d'un chunk réapparaît au début du suivant
    last_sentence = chunks[0].split("\n")[1].split(". ")[-1]
    assert last_sentence.rstrip(".") in chunks[1]


def test_every_chunk_has_metadata():
    chunks = chunk_document(BRAND_DIR / "03_fiche_blonde_demo.md", word_count)
    assert chunks
    assert {c.doc_type for c in chunks} == {"fiche_biere"}
    assert all(c.text.startswith("Fiche technique - Blonde Démo") for c in chunks)


# --- Tests d'intégration : chargent le modèle (téléchargé au premier lancement) -------


@pytest.fixture(scope="module")
def chroma_dir(tmp_path_factory):
    path = tmp_path_factory.mktemp("chroma")
    ingest(chroma_dir=path)
    return path


def test_real_chunks_fit_in_embedding_window():
    chunks = [c for p in BRAND_DIR.glob("*.md") for c in chunk_document(p)]
    assert max(count_tokens(c.text) for c in chunks) <= 120


def test_retrieve_finds_the_right_beer(chroma_dir):
    passages = retrieve("degré d'alcool de la Saison", k=3, chroma_dir=chroma_dir)
    assert "05_fiche_saison_demo.md" in sources_of(passages)


def test_retrieve_can_filter_by_type(chroma_dir):
    passages = retrieve("label bio", k=3, doc_types=["labels_bio"], chroma_dir=chroma_dir)
    assert {p.doc_type for p in passages} == {"labels_bio"}
