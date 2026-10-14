"""Tests du social listening (tendances et mentions)."""

from src.models import Article
from src.trends import analyze


def article(titre: str, resume: str = "") -> Article:
    return Article(url=f"https://example.org/{hash(titre)}", titre=titre, flux="t", theme="t", resume=resume)


ARTICLES = [
    article("Les terrasses adoptent la bière bio", "Les cafés veulent des bières bio légères."),
    article("Brasserie Exemple : nouvelle bière au sureau", "Une bière bio pour les terrasses."),
    article("Prix de l'orge en hausse", "Les brasseurs surveillent leurs coûts."),
]


def test_counts_articles_not_repetitions():
    report = analyze(ARTICLES, {})
    assert dict(report.top_terms)["terrasses"] == 2


def test_frequent_phrases():
    report = analyze(ARTICLES, {})
    assert ("biere bio", 2) not in report.top_phrases  # les phrases gardent les accents
    assert dict(report.top_phrases)["bière bio"] == 2


def test_competitor_and_keyword_mentions_ignore_case_and_accents():
    report = analyze(ARTICLES, {"keywords": ["BIERE BIO"], "competitors": ["brasserie exemple"]})
    by_term = {m.term: m for m in report.mentions}
    assert len(by_term["BIERE BIO"].articles) == 2
    assert by_term["brasserie exemple"].kind == "concurrent"
    assert by_term["brasserie exemple"].articles == ["Brasserie Exemple : nouvelle bière au sureau"]


def test_trends_use_rss_source_not_llm_summary():
    item = Article(url="https://example.org/x", titre="Houblon", flux="t", theme="t",
                   extrait="Le houblon local progresse.", resume="Résumé reformulé par le modèle.")
    terms = dict(analyze([item], {}).top_terms)
    assert "local" in terms
    assert "reformulé" not in terms
