"""Accès au LLM derrière une petite interface, pour ne pas dépendre d'un fournisseur.

Le reste du code n'appelle que `LLMClient.complete()` et `complete_json()`.
Changer de fournisseur = changer LLM_PROVIDER dans le .env, sans toucher au reste.
"""

import json
import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from src.config import env

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """Erreur de configuration ou de réponse du LLM."""


class LLMClient(ABC):
    """Interface minimale commune à tous les fournisseurs."""

    name: str = "abstract"

    @abstractmethod
    def complete(self, system: str, user: str, json_mode: bool = False) -> str:
        """Envoie un prompt système + un message utilisateur, renvoie le texte de la réponse."""


# --------------------------------------------------------------------------- Implémentations


class AnthropicClient(LLMClient):
    """Claude via le SDK officiel `anthropic`. Modèle lu dans ANTHROPIC_MODEL."""

    name = "anthropic"

    def __init__(self, max_tokens: int = 1500) -> None:
        import anthropic  # import local : le paquet n'est requis que si on l'utilise

        api_key, self.model = env("ANTHROPIC_API_KEY"), env("ANTHROPIC_MODEL")
        if not api_key or not self.model:
            raise LLMError("ANTHROPIC_API_KEY et ANTHROPIC_MODEL doivent être définis dans .env")
        self.client = anthropic.Anthropic(api_key=api_key)
        self.max_tokens = max_tokens

    def complete(self, system: str, user: str, json_mode: bool = False) -> str:
        # Claude n'a pas de "mode JSON" : la consigne est dans le prompt, et la sortie est
        # de toute façon validée par pydantic dans complete_json().
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(block.text for block in response.content if block.type == "text")


class GeminiClient(LLMClient):
    """Gemini via le SDK officiel `google-genai`. Modèle lu dans GEMINI_MODEL."""

    name = "gemini"

    def __init__(self) -> None:
        from google import genai  # import local, comme pour Anthropic

        api_key, self.model = env("GEMINI_API_KEY"), env("GEMINI_MODEL")
        if not api_key or not self.model:
            raise LLMError("GEMINI_API_KEY et GEMINI_MODEL doivent être définis dans .env")
        self.client = genai.Client(api_key=api_key)

    def complete(self, system: str, user: str, json_mode: bool = False) -> str:
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system,
            # Gemini sait forcer une sortie JSON valide : on en profite quand c'est demandé.
            response_mime_type="application/json" if json_mode else None,
        )
        response = self.client.models.generate_content(
            model=self.model, contents=user, config=config
        )
        return response.text or ""


class OpenAIClient(LLMClient):
    """Stub : montre où brancher OpenAI. Non implémenté dans ce MVP."""

    name = "openai"

    def __init__(self) -> None:
        # Implémentation attendue : openai.OpenAI(api_key=OPENAI_API_KEY), puis
        # client.chat.completions.create(model=OPENAI_MODEL, messages=[system, user],
        # response_format={"type": "json_object"} si json_mode).
        raise LLMError("OpenAIClient n'est pas implémenté (stub de démonstration).")

    def complete(self, system: str, user: str, json_mode: bool = False) -> str:
        raise NotImplementedError


class FakeLLMClient(LLMClient):
    """Faux LLM pour les tests et la démo hors ligne : aucune clé, aucun réseau.

    - `responses` : réponses renvoyées dans l'ordre (pratique en test) ;
    - `default` : fonction (system, user) -> texte, utilisée quand la file est vide.
    Chaque appel est enregistré dans `calls` pour pouvoir inspecter les prompts envoyés.
    """

    name = "fake"

    def __init__(
        self,
        responses: list[str] | None = None,
        default: Callable[[str, str], str] | None = None,
    ) -> None:
        self.responses = list(responses or [])
        self.default = default
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str, json_mode: bool = False) -> str:
        self.calls.append((system, user))
        if self.responses:
            return self.responses.pop(0)
        if self.default:
            return self.default(system, user)
        raise LLMError("FakeLLMClient : plus de réponse en file et pas de fonction par défaut.")


PROVIDERS: dict[str, type[LLMClient]] = {
    "anthropic": AnthropicClient,
    "gemini": GeminiClient,
    "openai": OpenAIClient,
    "fake": FakeLLMClient,
}


def get_llm_client(provider: str | None = None) -> LLMClient:
    """Fabrique le client choisi par LLM_PROVIDER (par défaut : fake)."""
    provider = (provider or env("LLM_PROVIDER", "fake")).lower()
    if provider not in PROVIDERS:
        raise LLMError(f"LLM_PROVIDER inconnu : {provider!r}. Choix : {', '.join(PROVIDERS)}")
    if provider == "fake":
        from src.demo import demo_responder  # mode démo : réponses construites depuis le RAG

        return FakeLLMClient(default=demo_responder)
    return PROVIDERS[provider]()


# --------------------------------------------------------------------------- Sortie JSON


def extract_json(raw: str) -> str:
    """Récupère l'objet JSON d'une réponse, même entouré de ```json ... ``` ou de texte."""
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end < start:
        raise LLMError(f"Aucun objet JSON dans la réponse : {raw[:200]!r}")
    return raw[start : end + 1]


def complete_json(
    client: LLMClient, system: str, user: str, schema: type[T], retries: int = 1
) -> T:
    """Appelle le LLM et valide la réponse avec `schema`.

    En cas de JSON invalide, on renvoie l'erreur au modèle et on réessaie `retries` fois.
    """
    prompt = user
    for attempt in range(retries + 1):
        raw = client.complete(system, prompt, json_mode=True)
        try:
            return schema.model_validate_json(extract_json(raw))
        except (LLMError, ValidationError, json.JSONDecodeError) as error:
            if attempt == retries:
                raise LLMError(f"Réponse invalide après {retries + 1} essai(s) : {error}") from error
            prompt = (
                f"{user}\n\nTa réponse précédente était invalide :\n{error}\n"
                "Réponds uniquement avec un objet JSON conforme au format demandé."
            )
    raise AssertionError("inatteignable")
