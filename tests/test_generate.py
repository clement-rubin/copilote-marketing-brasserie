"""Tests de la génération : vrai RAG, LLM simulé."""

import json

from src.generate import generate_post
from src.llm import FakeLLMClient, get_llm_client
from src.models import Article, Persona, Status
from src.store import list_posts

ARTICLE = Article(
    url="https://example.org/a",
    titre="Les cavistes misent sur les bières bio locales",
    flux="Démo",
    theme="bio",
    resume="Les clients demandent l'origine des ingrédients. Le bio local rassure. Les cavistes suivent.",
    pertinence="Argument direct pour nos revendeurs.",
)
FILLER = " Nos bières sont brassées dans une grange et nous aimons en parler avec les cavistes." * 8


def llm_answer(texte: str, **overrides) -> str:
    data = {
        "texte": texte,
        "hashtags": ["#BiereBio"],
        "sources_utilisees": ["06_labels_bio.md"],
        "score_confiance": 0.9,
        "avertissements": [],
    }
    return json.dumps(data | overrides, ensure_ascii=False)


def test_prompt_contains_article_and_sourced_passages(isolated):
    fake = FakeLLMClient([llm_answer("Texte sans chiffre." + FILLER)])
    generate_post(fake, ARTICLE, Persona.EXPERTISE_BIO)
    system, user = fake.calls[0]
    assert "N'invente AUCUN chiffre" in system
    assert ARTICLE.titre in user
    assert "[source: " in user
    assert "02_charte_editoriale.md" not in user  # la charte n'est pas une source de faits


def test_generated_post_is_a_saved_draft_with_image_prompt(isolated):
    post = generate_post(FakeLLMClient([llm_answer("Texte sans chiffre." + FILLER)]), ARTICLE, Persona.EXPERTISE_BIO)
    assert post.statut is Status.DRAFT
    assert post.prompt_image and "À éviter" in post.prompt_image
    assert [p.id for p in list_posts()] == [post.id]


def test_hallucinated_degree_is_caught(isolated):
    answer = llm_answer("La Blonde Démo titre 9,9 % vol." + FILLER)
    post = generate_post(FakeLLMClient([answer]), ARTICLE, Persona.EXPERTISE_BIO)
    assert any("9,9" in w for w in post.avertissements)
    assert post.score_confiance < 0.9


def test_invented_source_is_removed(isolated):
    answer = llm_answer("Texte." + FILLER, sources_utilisees=["fichier_invente.md"])
    post = generate_post(FakeLLMClient([answer]), ARTICLE, Persona.EXPERTISE_BIO)
    assert post.sources_utilisees == []
    assert any("fichier_invente.md" in w for w in post.avertissements)


def test_instagram_hashtags_are_fixed_to_five(isolated):
    answer = llm_answer("Petite pause dégustation à la grange, à consommer avec modération." * 3, hashtags=["#BiereBio"])
    post = generate_post(FakeLLMClient([answer]), ARTICLE, Persona.INSTAGRAM)
    assert len(post.hashtags) == 5
    assert any("Hashtags corrigés" in w for w in post.avertissements)


def test_demo_mode_produces_valid_posts_for_every_persona(isolated):
    llm = get_llm_client("fake")
    for persona in Persona:
        post = generate_post(llm, ARTICLE, persona)
        assert post.sources_utilisees, persona
        assert not any("non sourcé" in w for w in post.avertissements), post.avertissements
