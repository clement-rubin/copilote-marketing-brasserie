"""Tests de la couche LLM, sans réseau ni clé API (FakeLLMClient)."""

import pytest

from src.llm import FakeLLMClient, LLMError, complete_json, extract_json, get_llm_client
from src.models import ArticleSummary

VALID = '{"resume": "Un résumé assez long pour passer.", "pertinence": "Utile pour les cavistes."}'


def test_extract_json_strips_markdown_fences():
    assert extract_json(f"```json\n{VALID}\n```") == VALID


def test_extract_json_ignores_surrounding_text():
    assert extract_json(f"Voici le JSON : {VALID} Bonne journée") == VALID


def test_complete_json_returns_validated_model():
    result = complete_json(FakeLLMClient([VALID]), "sys", "user", ArticleSummary)
    assert result.pertinence == "Utile pour les cavistes."


def test_complete_json_retries_and_sends_error_back():
    fake = FakeLLMClient(["pas du json", VALID])
    complete_json(fake, "sys", "user", ArticleSummary, retries=1)
    assert len(fake.calls) == 2
    assert "invalide" in fake.calls[1][1]  # le 2e prompt contient l'erreur


def test_complete_json_gives_up_after_retries():
    with pytest.raises(LLMError, match="2 essai"):
        complete_json(FakeLLMClient(["{}", "{}"]), "sys", "user", ArticleSummary, retries=1)


def test_factory_default_is_fake(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert get_llm_client().name == "fake"


def test_factory_rejects_unknown_provider():
    with pytest.raises(LLMError, match="inconnu"):
        get_llm_client("mistral")


def test_real_providers_require_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    with pytest.raises(LLMError, match="GEMINI_API_KEY"):
        get_llm_client("gemini")


def test_openai_is_a_stub():
    with pytest.raises(LLMError, match="stub"):
        get_llm_client("openai")
