"""Publishers réels pour les API natives : LinkedIn (Posts API) et Meta (Instagram, Facebook).

Ils ne sont utilisés qu'avec PUBLISH_MODE=live et des tokens valides dans .env. Ils n'ont pas
pu être testés contre les vraies API (il faut une application validée par LinkedIn et Meta) :
les tests vérifient les requêtes envoyées grâce à un faux transport HTTP.
Les formats suivent la documentation officielle au moment de l'écriture ; à revalider avant
la mise en production (les deux plateformes versionnent leurs API).
"""

import re

import httpx

from src.config import env
from src.models import Platform, Post
from src.publish import Publisher


class PublishError(RuntimeError):
    """Erreur de configuration ou réponse refusée par une API sociale."""


def _require(*names: str) -> list[str]:
    values = [env(n) for n in names]
    missing = [n for n, v in zip(names, values) if not v]
    if missing:
        raise PublishError(f"Variables manquantes dans .env : {', '.join(missing)}")
    return values


def _check(response: httpx.Response, api: str) -> httpx.Response:
    if response.status_code >= 400:
        raise PublishError(f"{api} a refusé la requête ({response.status_code}) : {response.text[:300]}")
    return response


# --------------------------------------------------------------------------- LinkedIn

# Caractères réservés du « little text format » utilisé par le champ commentary.
LINKEDIN_RESERVED = re.compile(r"([|{}@\[\]()<>\\*_~])")
HASHTAG = re.compile(r"#(\w+)")


def linkedin_commentary(text: str, hashtags: list[str]) -> str:
    """Échappe les caractères réservés et transforme les #hashtags au format attendu par LinkedIn."""
    escaped = LINKEDIN_RESERVED.sub(r"\\\1", f"{text}\n\n{' '.join(hashtags)}".strip())
    return HASHTAG.sub(lambda m: "{hashtag|\\#|" + m.group(1) + "}", escaped)


class LinkedInPublisher(Publisher):
    """Publie un post texte sur une page entreprise via POST /rest/posts.

    Prérequis : produit « Community Management API » approuvé, scope w_organization_social,
    token d'un administrateur de la page.
    """

    URL = "https://api.linkedin.com/rest/posts"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self.token, self.organization, self.version = _require(
            "LINKEDIN_ACCESS_TOKEN", "LINKEDIN_ORGANIZATION_ID", "LINKEDIN_API_VERSION"
        )
        self.client = client or httpx.Client(timeout=30)

    def publish(self, post: Post, when) -> str:
        body = {
            "author": f"urn:li:organization:{self.organization}",
            "commentary": linkedin_commentary(post.texte, post.hashtags),
            "visibility": "PUBLIC",
            "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }
        headers = {
            "Authorization": f"Bearer {self.token}",
            "LinkedIn-Version": self.version,  # format AAAAMM
            "X-Restli-Protocol-Version": "2.0.0",
        }
        response = _check(self.client.post(self.URL, json=body, headers=headers), "LinkedIn")
        return response.headers.get("x-restli-id", "")  # URN du post créé


# --------------------------------------------------------------------------- Meta


class _MetaPublisher(Publisher):
    def __init__(self, client: httpx.Client | None = None) -> None:
        self.token, self.version = _require("META_ACCESS_TOKEN", "META_GRAPH_VERSION")
        self.base = f"https://{env('META_GRAPH_HOST', 'graph.facebook.com')}/{self.version}"
        self.client = client or httpx.Client(timeout=30)

    def _post(self, path: str, **params: str) -> dict:
        response = self.client.post(f"{self.base}/{path}", data=params | {"access_token": self.token})
        return _check(response, "Meta Graph API").json()


class InstagramPublisher(_MetaPublisher):
    """Publication Instagram en deux temps : conteneur média, puis media_publish.

    L'API exige une image accessible publiquement (post.image_url).
    """

    def __init__(self, client: httpx.Client | None = None) -> None:
        super().__init__(client)
        (self.user_id,) = _require("INSTAGRAM_USER_ID")

    def publish(self, post: Post, when) -> str:
        if not post.image_url:
            raise PublishError(f"Post {post.id} : Instagram exige une image à une URL publique (image_url).")
        caption = f"{post.texte}\n\n{' '.join(post.hashtags)}"
        container = self._post(f"{self.user_id}/media", image_url=post.image_url, caption=caption)
        published = self._post(f"{self.user_id}/media_publish", creation_id=container["id"])
        return published["id"]


class FacebookPublisher(_MetaPublisher):
    """Publication sur la page Facebook (relais B2C des posts Instagram)."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        super().__init__(client)
        (self.page_id,) = _require("FACEBOOK_PAGE_ID")

    def publish(self, post: Post, when) -> str:
        message = f"{post.texte}\n\n{' '.join(post.hashtags)}"
        if post.image_url:
            return self._post(f"{self.page_id}/photos", url=post.image_url, caption=message)["id"]
        return self._post(f"{self.page_id}/feed", message=message)["id"]


def live_publishers(platform: Platform) -> dict[str, Publisher]:
    """Canaux réels pour une plateforme. Instagram est relayé sur Facebook si FACEBOOK_PAGE_ID est défini."""
    if platform is Platform.LINKEDIN:
        return {"linkedin": LinkedInPublisher()}
    channels: dict[str, Publisher] = {"instagram": InstagramPublisher()}
    if env("FACEBOOK_PAGE_ID"):
        channels["facebook"] = FacebookPublisher()
    return channels
