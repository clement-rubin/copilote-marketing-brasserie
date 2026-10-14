"""Tests de la couche LLM, sans réseau ni clé API (FakeLLMClient)."""

import pytest

from src.llm import FakeLLMClient, LLMError, complete_json, extract_json, get_llm_client, with_retry
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


def test_openai_requires_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    with pytest.raises(LLMError, match="OPENAI_API_KEY"):
        get_llm_client("openai")


class FlakyError(Exception):
    def __init__(self, code: int) -> None:
        super().__init__(f"HTTP {code}")
        self.code = code


def test_with_retry_recovers_from_temporary_errors():
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise FlakyError(503)
        return "ok"

    assert with_retry(flaky, base_delay=0) == "ok"
    assert len(calls) == 3


def test_with_retry_does_not_retry_permanent_errors():
    calls = []

    def broken():
        calls.append(1)
        raise FlakyError(404)

    with pytest.raises(FlakyError):
        with_retry(broken, base_delay=0)
    assert len(calls) == 1


def test_gemini_falls_back_to_next_model_when_overloaded(monkeypatch):
    """Modèle saturé (503) -> modèle suivant ; erreur définitive -> LLMError immédiate."""
    import src.llm as llm_module
    from src.llm import GeminiClient

    monkeypatch.setattr(llm_module.time, "sleep", lambda _: None)  # pas d'attente réelle en test
    asked = []

    class FakeModels:
        def generate_content(self, model, contents, config):
            asked.append(model)
            if model == "sature":
                raise FlakyError(503)

            class Response:
                text = '{"ok": true}'

            return Response()

    client = object.__new__(GeminiClient)  # sans __init__ : pas de clé ni de réseau
    client.models, client.model = ["sature", "secours"], "sature"
    client.client = type("C", (), {"models": FakeModels()})()
    assert client.complete("sys", "user") == '{"ok": true}'
    assert client.model == "secours"
    assert asked.count("sature") == 3 and asked[-1] == "secours"  # 3 essais puis repli
