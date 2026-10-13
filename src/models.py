"""Modèles de données validés par pydantic.

Deux familles de modèles :
- ce que le LLM a le droit de produire (`ArticleSummary`, `PostDraft`) ;
- ce que l'application stocke (`Article`, `Post`), qui ajoute des champs que seul le
  code contrôle (identifiant, statut, dates). Le LLM ne choisit jamais le statut d'un post.
"""

from datetime import datetime
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


class Platform(str, Enum):
    LINKEDIN = "linkedin"
    INSTAGRAM = "instagram"


class Persona(str, Enum):
    """Angles éditoriaux. Les trois premiers sont LinkedIn (B2B), le dernier Instagram (B2C)."""

    EXPERTISE_BIO = "expertise_bio"
    COULISSES = "coulisses_brassage"
    DISTRIBUTEUR = "mise_en_avant_distributeur"
    INSTAGRAM = "instagram_craft"

    @property
    def platform(self) -> Platform:
        return Platform.INSTAGRAM if self is Persona.INSTAGRAM else Platform.LINKEDIN


class Status(str, Enum):
    """Cycle de vie : brouillon -> approuve | rejete, approuve -> programme -> publie."""

    DRAFT = "brouillon"
    APPROVED = "approuve"
    REJECTED = "rejete"
    SCHEDULED = "programme"
    PUBLISHED = "publie"


# Transitions autorisées. Tout le reste est refusé par `Post.change_status`.
ALLOWED_TRANSITIONS: dict[Status, set[Status]] = {
    Status.DRAFT: {Status.APPROVED, Status.REJECTED},
    Status.APPROVED: {Status.SCHEDULED, Status.REJECTED, Status.DRAFT},  # éditer = re-valider
    Status.REJECTED: {Status.DRAFT},  # on peut repasser un post rejeté en brouillon après édition
    Status.SCHEDULED: {Status.PUBLISHED},
    Status.PUBLISHED: set(),
}


# --------------------------------------------------------------------------- RAG


class Passage(BaseModel):
    """Un extrait des documents de marque renvoyé par le RAG."""

    text: str
    source: str  # nom du fichier, ex. "03_fiche_blonde_demo.md"
    doc_type: str  # type déclaré dans le front matter, ex. "fiche_biere"
    score: float = 0.0  # similarité (plus haut = plus proche)


# --------------------------------------------------------------------------- Veille


class ArticleSummary(BaseModel):
    """Sortie attendue du LLM pour résumer un article de veille."""

    resume: str = Field(min_length=20, description="Résumé en 3 phrases")
    pertinence: str = Field(min_length=10, description="Pourquoi c'est utile pour la marque")


class Article(BaseModel):
    """Un article de veille stocké en JSON."""

    url: str
    titre: str
    flux: str  # nom du flux RSS d'origine
    theme: str
    publie_le: datetime | None = None
    collecte_le: datetime = Field(default_factory=datetime.now)
    resume: str = ""
    pertinence: str = ""


# --------------------------------------------------------------------------- Posts


class Answer(BaseModel):
    """Réponse du LLM à une question posée à la base de connaissances (commande `ask`)."""

    reponse: str = Field(min_length=1)
    sources_utilisees: list[str] = Field(default_factory=list)
    avertissements: list[str] = Field(default_factory=list)


class PostDraft(BaseModel):
    """Sortie attendue du LLM pour un post. Validée avant toute sauvegarde."""

    texte: str = Field(min_length=50)
    hashtags: list[str] = Field(default_factory=list)
    sources_utilisees: list[str] = Field(
        default_factory=list, description="Fichiers de marque réellement utilisés"
    )
    score_confiance: float = Field(ge=0.0, le=1.0)
    avertissements: list[str] = Field(
        default_factory=list, description="Infos manquantes dans le contexte, à vérifier"
    )

    @field_validator("hashtags")
    @classmethod
    def hashtags_start_with_hash(cls, tags: list[str]) -> list[str]:
        """Normalise les hashtags : ajoute le # manquant, retire les espaces."""
        return [t if t.startswith("#") else f"#{t}" for t in (t.strip() for t in tags) if t]


class Post(BaseModel):
    """Un post stocké, avec ce que le code contrôle (id, statut, dates)."""

    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    persona: Persona
    plateforme: Platform
    texte: str
    hashtags: list[str] = Field(default_factory=list)
    sources_utilisees: list[str] = Field(default_factory=list)
    score_confiance: float = Field(ge=0.0, le=1.0)  # score final, après garde-fou
    score_llm: float | None = None  # auto-évaluation brute du modèle, avant garde-fou
    avertissements: list[str] = Field(default_factory=list)
    article_url: str | None = None  # article de veille qui a servi de point de départ
    contexte: str = ""  # passages RAG + article fournis au LLM : traçabilité et re-vérification
    prompt_image: str | None = None
    image_path: str | None = None  # visuel généré localement (prototype)
    image_url: str | None = None  # URL publique du visuel (exigée par l'API Instagram)
    publications: dict[str, str] = Field(default_factory=dict)  # canal -> id renvoyé par l'API
    statut: Status = Status.DRAFT
    cree_le: datetime = Field(default_factory=datetime.now)
    programme_le: datetime | None = None
    note_revue: str = ""

    @model_validator(mode="after")
    def check_platform(self) -> "Post":
        """La plateforme doit correspondre à la persona, et Instagram exige 5 hashtags."""
        if self.plateforme != self.persona.platform:
            raise ValueError(f"La persona {self.persona.value} ne va pas sur {self.plateforme.value}")
        if self.plateforme is Platform.INSTAGRAM and len(self.hashtags) != 5:
            raise ValueError(f"Instagram exige exactement 5 hashtags, reçu {len(self.hashtags)}")
        return self

    @classmethod
    def from_draft(cls, draft: PostDraft, persona: Persona, article_url: str | None) -> "Post":
        """Crée un post au statut brouillon à partir de la sortie du LLM."""
        return cls(
            persona=persona,
            plateforme=persona.platform,
            article_url=article_url,
            score_llm=draft.score_confiance,
            **draft.model_dump(),
        )

    def change_status(self, new: Status) -> None:
        """Change le statut en respectant ALLOWED_TRANSITIONS, sinon lève ValueError."""
        if new not in ALLOWED_TRANSITIONS[self.statut]:
            raise ValueError(f"Transition interdite : {self.statut.value} -> {new.value}")
        self.statut = new
