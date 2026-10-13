"""Orchestration du flux hebdomadaire : veille -> 3 articles -> 3 brouillons (2 LinkedIn + 1 Instagram).

À lancer une fois par semaine (cron, planificateur de tâches Windows ou n8n), avant la revue
humaine. La publication est un second job, plus fréquent : `publish-due`.
"""

from datetime import date
from pathlib import Path

from src import config
from src.generate import generate_post
from src.llm import LLMClient
from src.models import Persona, Post
from src.store import list_posts
from src.watch import load_articles, load_feeds, watch

LINKEDIN_PERSONAS = [Persona.EXPERTISE_BIO, Persona.COULISSES, Persona.DISTRIBUTEUR]
DEMO_FEED = {"name": "Flux démo (fictif)", "url": str(config.DATA_DIR / "demo_feed.xml"), "theme": "demo"}


def personas_for_week(week: int) -> list[Persona]:
    """2 personas LinkedIn en rotation (chacune revient 2 semaines sur 3) + Instagram."""
    first = week % len(LINKEDIN_PERSONAS)
    return [
        LINKEDIN_PERSONAS[first],
        LINKEDIN_PERSONAS[(first + 1) % len(LINKEDIN_PERSONAS)],
        Persona.INSTAGRAM,
    ]


def weekly(
    llm: LLMClient,
    offline: bool = False,
    today: date | None = None,
    chroma_dir: Path | None = None,
) -> list[Post]:
    """Lance la veille puis génère les 3 brouillons de la semaine, sur des articles pas encore utilisés."""
    if offline:
        watch(llm, feeds=[DEMO_FEED], max_items=10)
    else:
        feeds, max_items = load_feeds()
        watch(llm, feeds=feeds, max_items=max_items)

    used = {p.article_url for p in list_posts()}
    fresh = [a for a in load_articles().values() if a.url not in used]  # du plus récent au plus ancien
    if not fresh:
        return []

    personas = personas_for_week((today or date.today()).isocalendar().week)
    return [
        generate_post(llm, fresh[i % len(fresh)], persona, chroma_dir)
        for i, persona in enumerate(personas)
    ]
