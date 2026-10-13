"""File de validation humaine : approuver, rejeter ou éditer un post.

Tout post naît « brouillon ». Seul un humain peut l'approuver, et seuls les posts approuvés
peuvent être programmés (règle appliquée par Post.change_status).
"""

from src import guard
from src.models import Post, Status
from src.store import list_posts, load_post, save_post


def pending() -> list[Post]:
    """Posts en attente de validation (brouillons), du plus ancien au plus récent."""
    return list_posts(Status.DRAFT)


def approve(post_id: str, note: str = "") -> Post:
    """Approuve un brouillon."""
    post = load_post(post_id)
    post.change_status(Status.APPROVED)
    post.note_revue = note
    save_post(post)
    return post


def reject(post_id: str, note: str = "") -> Post:
    """Rejette un post (brouillon ou approuvé). La note explique pourquoi."""
    post = load_post(post_id)
    post.change_status(Status.REJECTED)
    post.note_revue = note
    save_post(post)
    return post


def edit(post_id: str, texte: str, hashtags: list[str] | None = None) -> Post:
    """Remplace le texte (et éventuellement les hashtags), puis relance le garde-fou.

    Un post édité repasse en brouillon : le nouveau texte doit être validé à son tour.
    """
    post = load_post(post_id)
    if post.statut is Status.SCHEDULED:
        raise ValueError("Un post déjà programmé ne peut plus être édité.")
    post.texte = texte
    if hashtags is not None:
        post.hashtags = [t if t.startswith("#") else f"#{t}" for t in hashtags]
    if post.statut is not Status.DRAFT:
        post.change_status(Status.DRAFT)
    post = guard.check(post, post.contexte)
    # Revalide le modèle complet (ex. 5 hashtags sur Instagram) avant d'écrire.
    post = Post.model_validate(post.model_dump())
    save_post(post)
    return post
