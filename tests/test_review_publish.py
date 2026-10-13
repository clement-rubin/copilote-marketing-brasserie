"""Tests de la validation humaine et de la programmation."""

from datetime import date, datetime

import pytest

from src import review
from src.models import Persona, Platform, Post, PostDraft, Status
from src.publish import next_monday, plan, schedule
from src.store import list_posts, load_post, save_post

TAGS_5 = ["#A", "#B", "#C", "#D", "#E"]


def make_post(persona: Persona, status: Status = Status.DRAFT) -> Post:
    tags = TAGS_5 if persona is Persona.INSTAGRAM else ["#BiereBio"]
    draft = PostDraft(texte="Un texte de post suffisamment long pour être valide.", hashtags=tags, score_confiance=0.8)
    post = Post.from_draft(draft, persona, None)
    post.statut = status
    return post


def test_next_monday():
    assert next_monday(date(2026, 10, 13)) == date(2026, 10, 19)  # mardi -> lundi suivant
    assert next_monday(date(2026, 10, 19)) == date(2026, 10, 26)  # lundi -> lundi d'après


def test_plan_two_linkedin_one_instagram_per_week():
    posts = [make_post(Persona.COULISSES) for _ in range(3)] + [make_post(Persona.INSTAGRAM)]
    planning = plan(posts, taken=set(), start=date(2026, 10, 19))
    slots = [(p.plateforme, when) for p, when in planning]
    assert slots == [
        (Platform.LINKEDIN, datetime(2026, 10, 20, 9)),  # mardi
        (Platform.LINKEDIN, datetime(2026, 10, 22, 9)),  # jeudi
        (Platform.INSTAGRAM, datetime(2026, 10, 24, 11)),  # samedi
        (Platform.LINKEDIN, datetime(2026, 10, 27, 9)),  # semaine suivante
    ]


def test_plan_skips_taken_slots():
    planning = plan([make_post(Persona.COULISSES)], taken={datetime(2026, 10, 20, 9)}, start=date(2026, 10, 19))
    assert planning[0][1] == datetime(2026, 10, 22, 9)


def test_only_approved_posts_are_scheduled(isolated):
    draft = make_post(Persona.COULISSES)
    approved = make_post(Persona.EXPERTISE_BIO, Status.APPROVED)
    save_post(draft)
    save_post(approved)
    planning = schedule(today=date(2026, 10, 13))
    assert [p.id for p, _ in planning] == [approved.id]
    assert load_post(draft.id).statut is Status.DRAFT
    assert load_post(approved.id).statut is Status.SCHEDULED
    assert len(list((isolated / "out" / "scheduled").glob("*.json"))) == 1


def test_review_approve_and_reject(isolated):
    a, b = make_post(Persona.COULISSES), make_post(Persona.COULISSES)
    save_post(a)
    save_post(b)
    review.approve(a.id, "ok")
    review.reject(b.id, "trop vague")
    assert load_post(a.id).statut is Status.APPROVED
    assert load_post(b.id).note_revue == "trop vague"
    assert review.pending() == []


def test_edit_sends_approved_post_back_to_draft_and_rechecks(isolated):
    post = make_post(Persona.COULISSES, Status.APPROVED)
    save_post(post)
    edited = review.edit(post.id, "Nouveau texte avec un chiffre inventé : 42 brassins.")
    assert edited.statut is Status.DRAFT
    assert any("42" in w for w in edited.avertissements)


def test_scheduled_post_cannot_be_edited(isolated):
    post = make_post(Persona.COULISSES, Status.SCHEDULED)
    save_post(post)
    with pytest.raises(ValueError):
        review.edit(post.id, "Trop tard.")
    assert len(list_posts(Status.SCHEDULED)) == 1
