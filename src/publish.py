"""Programmation des posts approuvés, derrière une interface Publisher.

Seul MockPublisher est implémenté : il écrit le post programmé dans out/scheduled/.
Brancher LinkedIn ou Meta = écrire une nouvelle classe Publisher (voir le README).
"""

import json
from abc import ABC, abstractmethod
from datetime import date, datetime, time, timedelta
from pathlib import Path

from src import config
from src.models import Platform, Post, Status
from src.store import list_posts, save_post

# Calendrier hebdomadaire : (jour de la semaine, heure, plateforme). Lundi = 0.
WEEKLY_SLOTS: list[tuple[int, time, Platform]] = [
    (1, time(9, 0), Platform.LINKEDIN),  # mardi 9 h
    (3, time(9, 0), Platform.LINKEDIN),  # jeudi 9 h
    (5, time(11, 0), Platform.INSTAGRAM),  # samedi 11 h
]
MAX_WEEKS = 52  # garde-fou contre une boucle infinie


class Publisher(ABC):
    """Interface commune à tous les canaux de publication."""

    @abstractmethod
    def publish(self, post: Post, when: datetime) -> str:
        """Programme le post à la date donnée et renvoie un identifiant de publication."""


class MockPublisher(Publisher):
    """Simule la programmation en écrivant un fichier JSON par post."""

    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory or config.scheduled_dir()

    def publish(self, post: Post, when: datetime) -> str:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f"{when:%Y-%m-%d_%Hh%M}_{post.plateforme.value}_{post.id}.json"
        payload = {
            "plateforme": post.plateforme.value,
            "programme_le": when.isoformat(),
            "texte": post.texte + "\n\n" + " ".join(post.hashtags),
            "prompt_image": post.prompt_image,
            "post_id": post.id,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)


def next_monday(today: date) -> date:
    """Le lundi qui suit `today` (strictement après)."""
    return today + timedelta(days=7 - today.weekday())


def plan(posts: list[Post], taken: set[datetime], start: date) -> list[tuple[Post, datetime]]:
    """Attribue à chaque post approuvé le prochain créneau libre de sa plateforme.

    Fonction pure (sans fichier) pour être testée facilement. Les posts les plus anciens
    passent en premier.
    """
    queues = {
        platform: [p for p in posts if p.plateforme is platform] for platform in Platform
    }
    planning: list[tuple[Post, datetime]] = []
    for week in range(MAX_WEEKS):
        if not any(queues.values()):
            break
        monday = start + timedelta(weeks=week)
        for weekday, hour, platform in WEEKLY_SLOTS:
            slot = datetime.combine(monday + timedelta(days=weekday), hour)
            if slot in taken or not queues[platform]:
                continue
            planning.append((queues[platform].pop(0), slot))
    return planning


def schedule(publisher: Publisher | None = None, today: date | None = None) -> list[tuple[Post, datetime]]:
    """Programme tous les posts approuvés à partir du lundi suivant."""
    publisher = publisher or MockPublisher()
    approved = list_posts(Status.APPROVED)
    taken = {p.programme_le for p in list_posts(Status.SCHEDULED) if p.programme_le}
    planning = plan(approved, taken, next_monday(today or date.today()))
    for post, when in planning:
        post.change_status(Status.SCHEDULED)  # vérifie la transition AVANT de publier
        post.programme_le = when
        publisher.publish(post, when)
        save_post(post)
    return planning
