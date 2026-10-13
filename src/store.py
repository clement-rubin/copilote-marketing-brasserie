"""Stockage des posts : un fichier JSON par post dans out/posts/."""

import json
from pathlib import Path

from src import config
from src.models import Post, Status


def save_post(post: Post, directory: Path | None = None) -> Path:
    """Écrit (ou réécrit) le post dans <dossier>/<id>.json."""
    directory = directory or config.posts_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{post.id}.json"
    path.write_text(
        json.dumps(post.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return path


def load_post(post_id: str, directory: Path | None = None) -> Post:
    """Charge un post par son identifiant. Lève FileNotFoundError s'il n'existe pas."""
    path = (directory or config.posts_dir()) / f"{post_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Post introuvable : {post_id}")
    return Post.model_validate_json(path.read_text(encoding="utf-8"))


def list_posts(status: Status | None = None, directory: Path | None = None) -> list[Post]:
    """Liste les posts, du plus ancien au plus récent, éventuellement filtrés par statut."""
    directory = directory or config.posts_dir()
    if not directory.exists():
        return []
    posts = [Post.model_validate_json(p.read_text(encoding="utf-8")) for p in directory.glob("*.json")]
    if status is not None:
        posts = [p for p in posts if p.statut is status]
    return sorted(posts, key=lambda p: p.cree_le)
