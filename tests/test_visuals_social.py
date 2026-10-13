"""Tests des visuels, des publishers réels (faux transport HTTP) et de l'orchestration."""

import json
from datetime import date, datetime

import httpx
import pytest

from src.images import image_prompt
from src.models import Persona, Post, PostDraft, Status
from src.orchestrate import personas_for_week, weekly
from src.publish import publish_due
from src.social import FacebookPublisher, InstagramPublisher, LinkedInPublisher, PublishError, linkedin_commentary
from src.store import list_posts, load_post, save_post
from src.visuals import ImageError, PlaceholderImageGenerator, create_visual, get_image_generator
from src.llm import get_llm_client

TAGS_5 = ["#A", "#B", "#C", "#D", "#E"]


def make_post(persona: Persona = Persona.COULISSES, status: Status = Status.DRAFT) -> Post:
    tags = TAGS_5 if persona is Persona.INSTAGRAM else ["#BiereBio"]
    draft = PostDraft(texte="Un texte (avec parenthèses) assez long pour être valide ici.", hashtags=tags, score_confiance=0.8)
    post = Post.from_draft(draft, persona, None)
    post.prompt_image = image_prompt(post)
    post.statut = status
    return post


# --------------------------------------------------------------------------- visuels


def test_placeholder_visual_has_platform_format(isolated):
    post = make_post(Persona.INSTAGRAM)
    path = create_visual(post, PlaceholderImageGenerator())
    svg = path.read_text(encoding="utf-8")
    assert 'width="1080" height="1350"' in svg
    assert post.image_path == str(path)


def test_openai_image_generator_requires_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    with pytest.raises(ImageError, match="OPENAI_API_KEY"):
        get_image_generator("openai")


# --------------------------------------------------------------------------- API sociales


def recording_client(responses: list[httpx.Response]) -> tuple[httpx.Client, list[httpx.Request]]:
    """Faux client HTTP : renvoie les réponses données et garde les requêtes envoyées."""
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return responses.pop(0)

    return httpx.Client(transport=httpx.MockTransport(handler)), sent


@pytest.fixture
def social_env(monkeypatch):
    for name, value in {
        "LINKEDIN_ACCESS_TOKEN": "tok", "LINKEDIN_ORGANIZATION_ID": "42", "LINKEDIN_API_VERSION": "202601",
        "META_ACCESS_TOKEN": "mtok", "META_GRAPH_VERSION": "v21.0", "INSTAGRAM_USER_ID": "17",
        "FACEBOOK_PAGE_ID": "99",
    }.items():
        monkeypatch.setenv(name, value)


def test_linkedin_commentary_escapes_reserved_chars_and_formats_hashtags():
    text = linkedin_commentary("Bière (bio) !", ["#BiereBio"])
    assert "\\(bio\\)" in text
    assert "{hashtag|\\#|BiereBio}" in text


def test_linkedin_publisher_sends_posts_api_request(social_env):
    client, sent = recording_client([httpx.Response(201, headers={"x-restli-id": "urn:li:share:1"})])
    post_id = LinkedInPublisher(client).publish(make_post(), datetime.now())
    body = json.loads(sent[0].content)
    assert post_id == "urn:li:share:1"
    assert sent[0].url == "https://api.linkedin.com/rest/posts"
    assert sent[0].headers["LinkedIn-Version"] == "202601"
    assert body["author"] == "urn:li:organization:42"
    assert body["lifecycleState"] == "PUBLISHED"


def test_instagram_publisher_two_steps(social_env):
    client, sent = recording_client([httpx.Response(200, json={"id": "c1"}), httpx.Response(200, json={"id": "m1"})])
    post = make_post(Persona.INSTAGRAM)
    post.image_url = "https://exemple.org/visuel.jpg"
    assert InstagramPublisher(client).publish(post, datetime.now()) == "m1"
    assert sent[0].url.path == "/v21.0/17/media"
    assert sent[1].url.path == "/v21.0/17/media_publish"
    assert b"creation_id=c1" in sent[1].content


def test_instagram_requires_public_image(social_env):
    client, _ = recording_client([])
    with pytest.raises(PublishError, match="URL publique"):
        InstagramPublisher(client).publish(make_post(Persona.INSTAGRAM), datetime.now())


def test_facebook_publisher_posts_to_page_feed(social_env):
    client, sent = recording_client([httpx.Response(200, json={"id": "99_1"})])
    assert FacebookPublisher(client).publish(make_post(Persona.INSTAGRAM), datetime.now()) == "99_1"
    assert sent[0].url.path == "/v21.0/99/feed"


def test_missing_tokens_are_reported(monkeypatch):
    monkeypatch.setenv("LINKEDIN_ACCESS_TOKEN", "")
    with pytest.raises(PublishError, match="LINKEDIN_ACCESS_TOKEN"):
        LinkedInPublisher()


# --------------------------------------------------------------------------- orchestration


def test_publish_due_only_publishes_past_slots(isolated):
    past, future = make_post(status=Status.SCHEDULED), make_post(status=Status.SCHEDULED)
    past.programme_le, future.programme_le = datetime(2026, 1, 6, 9), datetime(2099, 1, 6, 9)
    save_post(past)
    save_post(future)
    done = publish_due(now=datetime(2026, 10, 13), mode="mock")
    assert [p.id for p, _ in done] == [past.id]
    assert load_post(past.id).statut is Status.PUBLISHED
    assert "mock" in load_post(past.id).publications
    assert load_post(future.id).statut is Status.SCHEDULED


def test_personas_rotate_each_week():
    weeks = [personas_for_week(w) for w in range(3)]
    assert all(len(w) == 3 and w[-1] is Persona.INSTAGRAM for w in weeks)
    assert len({tuple(w[:2]) for w in weeks}) == 3  # une combinaison différente chaque semaine


def test_weekly_creates_three_drafts_then_skips_used_articles(isolated):
    llm = get_llm_client("fake")
    first = weekly(llm, offline=True, today=date(2026, 10, 13))
    assert [p.plateforme.value for p in first] == ["linkedin", "linkedin", "instagram"]
    assert all(p.statut is Status.DRAFT for p in first)
    second = weekly(llm, offline=True, today=date(2026, 10, 20))
    used_first = {p.article_url for p in first}
    assert used_first.isdisjoint({p.article_url for p in second})
    assert len(list_posts()) == 6
