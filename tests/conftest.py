"""Fixtures partagées : base vectorielle de test et dossiers de sortie isolés."""

import pytest

from src import config
from src.ingest import ingest


@pytest.fixture(scope="session")
def chroma_dir(tmp_path_factory):
    """Indexe les documents de marque une seule fois pour toute la session de tests."""
    path = tmp_path_factory.mktemp("chroma")
    ingest(chroma_dir=path)
    return path


@pytest.fixture
def isolated(tmp_path, monkeypatch, chroma_dir):
    """Redirige out/ et chroma_db/ vers des dossiers temporaires, et force le mode démo."""
    monkeypatch.setattr(config, "OUT_DIR", tmp_path / "out")
    monkeypatch.setattr(config, "CHROMA_DIR", chroma_dir)
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    return tmp_path
