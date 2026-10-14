"""Accès au LLM derrière une petite interface, pour ne pas dépendre d'un fournisseur.

Le reste du code n'appelle que `LLMClient.complete()` et `complete_json()`.
Changer de fournisseur = changer LLM_PROVIDER dans le .env, sans toucher au reste.
"""

import json
import re
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from src.config import env

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """Erreur de configuration ou de réponse du LLM."""


RETRYABLE_CODES = (429, 500, 503, 529)  # quota dépassé, erreur serveur, modèle surchargé
FATAL_CODES = (400, 401, 403)  # requête invalide, clé absente ou refusée
TIMEOUT_SECONDS = 60


def http_code(error: Exception) -> int | None:
    """Code HTTP d'une erreur d'API (chaque SDK a ses propres classes d'erreur)."""
    return getattr(error, "code", None) or getattr(error, "status_code", None)


def with_retry(call: Callable[[], T], attempts: int = 3, base_delay: float = 2.0) -> T:
    """Réessaie un appel d'API sur les erreurs temporaires, avec un délai qui double (2 s, 4 s…).

    Les erreurs définitives (clé invalide, modèle inconnu…) remontent tout de suite.
    """
    for attempt in range(attempts):
        try:
            return call()
        except Exception as error:
            if http_code(error) not in RETRYABLE_CODES or attempt == attempts - 1:
                raise
            time.sleep(base_delay * 2**attempt)
    raise AssertionError("inatteignable")


def api_call(provider: str, call: Callable[[], T]) -> T:
    """Appel d'API avec réessais ; toute erreur restante devient une LLMError.

    Ainsi, le reste du code n'a qu'un seul type d'erreur à gérer, quel que soit le fournisseur.
    """
    try:
        return with_retry(call)
    except Exception as error:
        raise LLMError(f"{provider} : {error}") from error


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
        response = api_call("Anthropic", lambda: self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        ))
        return "".join(block.text for block in response.content if block.type == "text")


class GeminiClient(LLMClient):
    """Gemini via le SDK officiel `google-genai`.

    GEMINI_MODEL peut lister plusieurs modèles séparés par des virgules : si le premier est
    saturé, retiré ou trop lent (plus de TIMEOUT_SECONDS), on passe au suivant. Utile car les
    modèles les plus récents sont souvent saturés sur l'offre gratuite.
    """

    name = "gemini"

    def __init__(self) -> None:
        from google import genai  # import local, comme pour Anthropic

        api_key = env("GEMINI_API_KEY")
        self.models = [m.strip() for m in env("GEMINI_MODEL").split(",") if m.strip()]
        if not api_key or not self.models:
            raise LLMError("GEMINI_API_KEY et GEMINI_MODEL doivent être définis dans .env")
        self.model = self.models[0]  # dernier modèle ayant répondu (affiché dans l'interface)
        # Sans délai maximal, une requête vers un modèle saturé peut attendre indéfiniment.
        # Réessais internes du SDK désactivés : notre with_retry() est le seul à décider.
        self.client = genai.Client(
            api_key=api_key,
            http_options={"timeout": TIMEOUT_SECONDS * 1000, "retry_options": {"attempts": 1}},
        )

    def complete(self, system: str, user: str, json_mode: bool = False) -> str:
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system,
            # Gemini sait forcer une sortie JSON valide : on en profite quand c'est demandé.
            response_mime_type="application/json" if json_mode else None,
        )
        last_error: LLMError | None = None
        for model in self.models:
            try:
                response = api_call(f"Gemini ({model})", lambda: self.client.models.generate_content(
                    model=model, contents=user, config=config
                ))
            except LLMError as error:
                if http_code(error.__cause__) in FATAL_CODES:
                    raise  # clé ou requête invalide : un autre modèle n'y changera rien
                last_error = error  # saturé, indisponible ou trop lent : on tente le suivant
                continue
            self.model = model
            return response.text or ""
        raise last_error or LLMError("Gemini : aucun modèle configuré")


class OpenAIClient(LLMClient):
    """GPT via le SDK officiel `openai`. Modèle lu dans OPENAI_MODEL."""

    name = "openai"

    def __init__(self) -> None:
        import openai  # import local, comme pour les autres fournisseurs

        api_key, self.model = env("OPENAI_API_KEY"), env("OPENAI_MODEL")
        if not api_key or not self.model:
            raise LLMError("OPENAI_API_KEY et OPENAI_MODEL doivent être définis dans .env")
        self.client = openai.OpenAI(api_key=api_key)

    def complete(self, system: str, user: str, json_mode: bool = False) -> str:
        # Le mode JSON d'OpenAI garantit un JSON syntaxiquement valide.
        options = {"response_format": {"type": "json_object"}} if json_mode else {}
        response = api_call("OpenAI", lambda: self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            **options,
        ))
        return response.choices[0].message.content or ""


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
        raw = client.complete(system, prompt, json_mode=True)  # une erreur d'API remonte telle quelle
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
