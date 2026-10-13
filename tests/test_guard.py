"""Tests du garde-fou anti-hallucination."""

from src import guard
from src.models import Persona, Post, PostDraft

CONTEXT = "[source: 03_fiche_blonde_demo.md]\nDegré d'alcool : 6,5 % vol. Label : Eurofeuille. 1 200 hectolitres."
LONG = " Une phrase neutre pour atteindre la longueur minimale demandée par la charte." * 9


def linkedin(texte: str, score: float = 0.9) -> Post:
    draft = PostDraft(texte=texte, hashtags=["#BiereBio"], score_confiance=score)
    return Post.from_draft(draft, Persona.EXPERTISE_BIO, None)


def test_sourced_numbers_pass():
    assert guard.unsourced_numbers("Notre blonde fait 6.5 % et on brasse 1200 hl.", CONTEXT) == []


def test_invented_number_is_flagged():
    assert guard.unsourced_numbers("Notre blonde fait 7 % vol.", CONTEXT) == ["7"]


def test_hashtag_numbers_are_ignored():
    assert guard.unsourced_numbers("Santé #Top10", CONTEXT) == []


def test_invented_label_is_flagged():
    assert guard.unsourced_labels("Certifiée Demeter et Eurofeuille", CONTEXT) == ["Demeter"]


def test_forbidden_words():
    assert "incroyable" in guard.forbidden_words("Une bière INCROYABLE")


def test_check_lowers_confidence_and_warns():
    post = guard.check(linkedin("Notre blonde à 8 % est labellisée Demeter." + LONG), CONTEXT)
    assert post.score_confiance == 0.5  # 0.9 - 2 x 0.2
    assert any("Chiffre non sourcé : 8" in w for w in post.avertissements)
    assert any("Demeter" in w for w in post.avertissements)


def test_check_is_idempotent():
    post = linkedin("Notre blonde à 8 % vol." + LONG)
    once = guard.check(post, CONTEXT)
    twice = guard.check(once, CONTEXT)
    assert twice.score_confiance == 0.7
    assert len(twice.avertissements) == 1


def test_format_problems_for_short_linkedin_post():
    problems = guard.format_problems(linkedin("Trop court : ce post LinkedIn ne respecte pas la charte éditoriale."))
    assert any("Longueur" in p for p in problems)
