"""Tests des modèles pydantic : validation des sorties et cycle de vie des posts."""

import pytest
from pydantic import ValidationError

from src.models import Persona, Platform, Post, PostDraft, Status

TAGS_5 = ["#BiereBio", "#BiereArtisanale", "#CraftBeer", "#Hainaut", "#BrasserieDemoDuHainaut"]


def make_draft(**overrides) -> PostDraft:
    data = {
        "texte": "Jeudi soir, la grange est ouverte. On sort la Saison Démo pour l'occasion.",
        "hashtags": TAGS_5,
        "sources_utilisees": ["05_fiche_saison_demo.md"],
        "score_confiance": 0.8,
    }
    return PostDraft(**(data | overrides))


def test_draft_rejects_confidence_out_of_range():
    with pytest.raises(ValidationError):
        make_draft(score_confiance=1.5)


def test_draft_adds_missing_hash():
    draft = make_draft(hashtags=["BiereBio", " #CraftBeer "])
    assert draft.hashtags == ["#BiereBio", "#CraftBeer"]


def test_post_from_draft_starts_as_draft_on_right_platform():
    post = Post.from_draft(make_draft(), Persona.INSTAGRAM, article_url="https://exemple.org/a")
    assert post.statut is Status.DRAFT
    assert post.plateforme is Platform.INSTAGRAM


def test_instagram_requires_exactly_five_hashtags():
    with pytest.raises(ValidationError, match="5 hashtags"):
        Post.from_draft(make_draft(hashtags=TAGS_5[:3]), Persona.INSTAGRAM, None)


def test_linkedin_persona_cannot_go_on_instagram():
    with pytest.raises(ValidationError):
        Post(**make_draft().model_dump(), persona=Persona.COULISSES, plateforme=Platform.INSTAGRAM)


def test_draft_cannot_be_scheduled_directly():
    post = Post.from_draft(make_draft(), Persona.INSTAGRAM, None)
    with pytest.raises(ValueError, match="Transition interdite"):
        post.change_status(Status.SCHEDULED)


def test_normal_lifecycle():
    post = Post.from_draft(make_draft(), Persona.INSTAGRAM, None)
    post.change_status(Status.APPROVED)
    post.change_status(Status.SCHEDULED)
    assert post.statut is Status.SCHEDULED
