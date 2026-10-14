"""Veille : lecture des flux RSS, déduplication par URL, résumé par le LLM, stockage JSON.

Règle : uniquement des flux RSS (ou API officielles). On ne télécharge jamais la page HTML
de l'article : le LLM résume le titre et l'extrait fournis par le flux.
"""

import html
import json
import re
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from time import mktime
from urllib.parse import parse_qsl, quote_plus, urlencode, urlsplit, urlunsplit

import feedparser
import yaml

from src import config, prompts
from src.llm import LLMClient, LLMError, complete_json
from src.models import Article, ArticleSummary

USER_AGENT = "CopiloteMarketingDemo/0.1 (projet etudiant; lecture RSS uniquement)"
TRACKING_PARAMS = ("utm_", "fbclid", "gclid", "mc_")

Fetcher = Callable[[str], feedparser.FeedParserDict]


def fetch_feed(url: str) -> feedparser.FeedParserDict:
    """Lit un flux RSS (URL ou chemin de fichier local) avec un User-Agent explicite."""
    return feedparser.parse(url, agent=USER_AGENT)


GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=fr&gl=BE&ceid=BE:fr"


def _read_config(path: Path | None = None) -> dict:
    return yaml.safe_load((path or config.FEEDS_FILE).read_text(encoding="utf-8"))


def load_watchlist(path: Path | None = None) -> dict[str, list[str]]:
    """Termes du social listening : {"keywords": [...], "competitors": [...]}."""
    listening = _read_config(path).get("listening") or {}
    return {
        "keywords": list(listening.get("keywords") or []),
        "competitors": list(listening.get("competitors") or []),
    }


def listening_feeds(watchlist: dict[str, list[str]]) -> list[dict]:
    """Transforme chaque terme suivi en recherche Google News RSS (flux public, pas de scraping)."""
    feeds = []
    for kind, theme in (("keywords", "listening"), ("competitors", "concurrent")):
        for term in watchlist.get(kind, []):
            query = quote_plus(f'"{term}"' if kind == "competitors" else term)
            feeds.append({"name": f"Google News - {term}", "url": GOOGLE_NEWS_RSS.format(query=query), "theme": theme})
    return feeds


def load_feeds(path: Path | None = None) -> tuple[list[dict], int]:
    """Lit feeds.yaml : flux fixes + recherches du social listening, et le max d'articles par flux."""
    data = _read_config(path)
    feeds = list(data["feeds"]) + listening_feeds(load_watchlist(path))
    return feeds, int(data.get("max_items_per_feed", 5))


def normalize_url(url: str) -> str:
    """Clé de déduplication : minuscules pour l'hôte, sans paramètres de suivi, sans # ni / final."""
    parts = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(parts.query) if not k.lower().startswith(TRACKING_PARAMS)]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


def clean_html(text: str) -> str:
    """Retire les balises HTML et les espaces superflus d'un extrait RSS."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()


def load_articles(path: Path | None = None) -> dict[str, Article]:
    """Charge les articles déjà collectés, indexés par URL normalisée."""
    path = path or config.watch_file()
    if not path.exists():
        return {}
    return {a["url"]: Article.model_validate(a) for a in json.loads(path.read_text(encoding="utf-8"))}


def save_articles(articles: dict[str, Article], path: Path | None = None) -> None:
    """Sauvegarde les articles, du plus récent au plus ancien."""
    path = path or config.watch_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(articles.values(), key=lambda a: a.publie_le or a.collecte_le, reverse=True)
    path.write_text(
        json.dumps([a.model_dump(mode="json") for a in ordered], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def summarize(llm: LLMClient, article: Article, extrait: str) -> ArticleSummary:
    """Demande au LLM un résumé en 3 phrases et la pertinence pour la marque."""
    user = prompts.render(
        "resume_article",
        titre=article.titre,
        flux=article.flux,
        theme=article.theme,
        extrait=extrait or "(pas d'extrait dans le flux)",
    )
    return complete_json(llm, prompts.load("system"), user, ArticleSummary)


def watch(
    llm: LLMClient,
    feeds: list[dict] | None = None,
    max_items: int = 5,
    store: Path | None = None,
    fetch: Fetcher = fetch_feed,
) -> list[Article]:
    """Lit les flux, résume les nouveaux articles et les ajoute au stockage.

    Renvoie la liste des articles nouvellement ajoutés. Un flux en erreur n'arrête pas les autres.
    """
    if feeds is None:
        feeds, max_items = load_feeds()
    articles = load_articles(store)
    added: list[Article] = []

    for feed in feeds:
        parsed = fetch(feed["url"])
        if parsed.get("bozo") and not parsed.entries:
            print(f"[veille] flux illisible, ignoré : {feed['name']}")
            continue
        for entry in parsed.entries[:max_items]:
            url = normalize_url(entry.get("link", ""))
            if not url or url in articles:
                continue  # déduplication par URL
            published = entry.get("published_parsed")
            article = Article(
                url=url,
                titre=clean_html(entry.get("title", "")),
                flux=feed["name"],
                theme=feed.get("theme", ""),
                publie_le=datetime.fromtimestamp(mktime(published)) if published else None,
            )
            article.extrait = clean_html(entry.get("summary", ""))
            try:
                summary = summarize(llm, article, article.extrait)
            except LLMError as error:
                print(f"[veille] résumé impossible, article réessayé au prochain passage : {error}")
                continue
            article.resume, article.pertinence = summary.resume, summary.pertinence
            articles[url] = article
            added.append(article)

    save_articles(articles, store)
    return added
