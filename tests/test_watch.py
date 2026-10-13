"""Tests de la veille RSS, sur le flux fictif local (aucun réseau)."""

from src import config
from src.llm import FakeLLMClient, get_llm_client
from src.watch import clean_html, load_articles, normalize_url, watch

DEMO_FEED = [{"name": "Démo", "url": str(config.DATA_DIR / "demo_feed.xml"), "theme": "demo"}]
SUMMARY = '{"resume": "Un. Deux. Trois phrases de résumé.", "pertinence": "Utile pour les cavistes."}'


def test_normalize_url_removes_tracking_and_trailing_slash():
    assert normalize_url("https://Example.org/a/?utm_source=rss&id=3#top") == "https://example.org/a?id=3"


def test_clean_html():
    assert clean_html("<p>Bière &amp; <b>bio</b></p>") == "Bière & bio"


def test_watch_deduplicates_by_url(isolated):
    added = watch(get_llm_client(), feeds=DEMO_FEED, max_items=10)
    # 5 items dans le flux, dont un doublon (même URL, sans utm_source)
    assert len(added) == 4
    assert all(a.resume and a.pertinence for a in added)


def test_watch_skips_already_known_articles(isolated):
    watch(get_llm_client(), feeds=DEMO_FEED, max_items=10)
    fake = FakeLLMClient([SUMMARY] * 10)
    assert watch(fake, feeds=DEMO_FEED, max_items=10) == []
    assert fake.calls == []  # aucun appel LLM pour des articles déjà vus
    assert len(load_articles()) == 4


def test_watch_survives_llm_failure(isolated):
    fake = FakeLLMClient(["pas du json"] * 20)
    assert watch(fake, feeds=DEMO_FEED, max_items=10) == []  # rien d'enregistré, pas de crash
