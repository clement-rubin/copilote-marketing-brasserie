"""Génération multimodale : du prompt d'image (src/images.py) à un visuel prototype.

Même principe que pour le texte : une petite interface, plusieurs implémentations.
- PlaceholderImageGenerator : maquette SVG hors ligne (palette, format, sujet), gratuite ;
- OpenAIImageGenerator : DALL-E 3 ou gpt-image via l'API officielle (modèle lu dans IMAGE_MODEL).
Midjourney n'a pas d'API publique officielle : on utilise le prompt « Midjourney : ... » à la main.
Les visuels sont des PROTOTYPES : ils passent par la validation humaine comme les textes.
"""

import base64
import html
import textwrap
from abc import ABC, abstractmethod
from pathlib import Path

import httpx

from src import config
from src.config import env
from src.models import Platform, Post

# Formats de publication recommandés (pixels)
CANVAS = {Platform.LINKEDIN: (1200, 627), Platform.INSTAGRAM: (1080, 1350)}
PALETTE_HEX = ["#B5651D", "#8A9A5B", "#6F4E37", "#F4EFE6"]  # ambre, sauge, bois, blanc cassé


class ImageError(RuntimeError):
    """Erreur de configuration ou d'appel du générateur d'images."""


class ImageGenerator(ABC):
    name = "abstract"

    @abstractmethod
    def generate(self, post: Post, directory: Path) -> Path:
        """Crée le visuel du post dans `directory` et renvoie son chemin."""


def _prompt_for_model(post: Post) -> str:
    """Partie descriptive du prompt (sans la ligne Midjourney, inutile pour DALL-E)."""
    if not post.prompt_image:
        raise ImageError(f"Le post {post.id} n'a pas de prompt d'image.")
    return "\n".join(l for l in post.prompt_image.splitlines() if not l.startswith("Midjourney"))


class PlaceholderImageGenerator(ImageGenerator):
    """Maquette SVG : montre le format, la palette et le sujet, sans appel d'API."""

    name = "placeholder"

    def generate(self, post: Post, directory: Path) -> Path:
        width, height = CANVAS[post.plateforme]
        subject = _prompt_for_model(post).splitlines()[0].removeprefix("Sujet : ")
        lines = textwrap.wrap(subject, width=48 if post.plateforme is Platform.LINKEDIN else 40)[:6]
        text = "".join(
            f'<tspan x="60" dy="{0 if i == 0 else 46}">{html.escape(l)}</tspan>' for i, l in enumerate(lines)
        )
        swatches = "".join(
            f'<rect x="{60 + i * 90}" y="{height - 130}" width="70" height="70" rx="8" fill="{c}" stroke="#fff"/>'
            for i, c in enumerate(PALETTE_HEX)
        )
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#6F4E37"/><stop offset="1" stop-color="#B5651D"/></linearGradient></defs>
  <rect width="100%" height="100%" fill="url(#g)"/>
  <text x="60" y="90" font-family="Georgia, serif" font-size="30" fill="#F4EFE6" opacity="0.8">PROTOTYPE · {post.plateforme.value} · {width}×{height}</text>
  <text x="60" y="190" font-family="Georgia, serif" font-size="36" fill="#F4EFE6">{text}</text>
  {swatches}
  <text x="{60 + 4 * 90 + 20}" y="{height - 85}" font-family="Georgia, serif" font-size="24" fill="#F4EFE6">post {post.id}</text>
</svg>"""
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{post.id}.svg"
        path.write_text(svg, encoding="utf-8")
        return path


class OpenAIImageGenerator(ImageGenerator):
    """DALL-E 3 ou gpt-image via le SDK `openai`. Clé : OPENAI_API_KEY, modèle : IMAGE_MODEL."""

    name = "openai"

    # Tailles acceptées par chaque famille de modèles (paysage pour LinkedIn, portrait pour Instagram)
    SIZES = {
        "dall-e-3": {Platform.LINKEDIN: "1792x1024", Platform.INSTAGRAM: "1024x1792"},
        "gpt-image": {Platform.LINKEDIN: "1536x1024", Platform.INSTAGRAM: "1024x1536"},
    }

    def __init__(self) -> None:
        import openai

        api_key, self.model = env("OPENAI_API_KEY"), env("IMAGE_MODEL")
        if not api_key or not self.model:
            raise ImageError("OPENAI_API_KEY et IMAGE_MODEL doivent être définis dans .env")
        self.client = openai.OpenAI(api_key=api_key)

    def generate(self, post: Post, directory: Path) -> Path:
        family = "dall-e-3" if self.model.startswith("dall-e") else "gpt-image"
        options = {"response_format": "b64_json"} if family == "dall-e-3" else {}
        result = self.client.images.generate(
            model=self.model,
            prompt=_prompt_for_model(post),
            size=self.SIZES[family][post.plateforme],
            n=1,
            **options,
        )
        image = result.data[0]
        data = base64.b64decode(image.b64_json) if image.b64_json else httpx.get(image.url, timeout=60).content
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{post.id}.png"
        path.write_bytes(data)
        return path


GENERATORS: dict[str, type[ImageGenerator]] = {
    "placeholder": PlaceholderImageGenerator,
    "openai": OpenAIImageGenerator,
}


def get_image_generator(provider: str | None = None) -> ImageGenerator:
    """Fabrique le générateur choisi par IMAGE_PROVIDER (par défaut : placeholder)."""
    provider = (provider or env("IMAGE_PROVIDER", "placeholder")).lower()
    if provider not in GENERATORS:
        raise ImageError(f"IMAGE_PROVIDER inconnu : {provider!r}. Choix : {', '.join(GENERATORS)}")
    return GENERATORS[provider]()


def create_visual(post: Post, generator: ImageGenerator | None = None) -> Path:
    """Génère le visuel d'un post et enregistre son chemin dans le post (sans le sauvegarder)."""
    path = (generator or get_image_generator()).generate(post, config.images_dir())
    post.image_path = str(path)
    return path
