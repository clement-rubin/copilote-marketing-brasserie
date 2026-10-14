"""Export de l'interface en site statique (Netlify, GitHub Pages…).

Un hébergeur statique ne peut pas faire tourner le serveur Python (FastAPI, ChromaDB, modèle
d'embedding), et une clé LLM ne doit jamais être exposée sur un site public. On fige donc :
- chaque lecture de l'API en fichier JSON (même contenu que le vrai serveur, obtenu par TestClient) ;
- les réponses aux questions suggérées et l'évaluation, calculées une fois avec le vrai LLM.
Dans le navigateur, app.js lit ces fichiers et désactive les actions (mode « lecture seule »).
"""

import json
import shutil
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from src import config
from src.models import Status
from src.store import list_posts, save_post
from src.visuals import PlaceholderImageGenerator, create_visual
from src.web.app import STATIC, SUGGESTIONS, app

# Toutes les lectures faites par l'interface (doit couvrir chaque api("GET", …) de app.js).
GET_PATHS = [
    "/api/dashboard",
    "/api/articles",
    "/api/trends",
    "/api/posts",
    "/api/calendar?weeks=4",
    "/api/suggestions",
    *[f"/api/posts?statut={status.value}" for status in Status],
]


def static_name(path: str) -> str:
    """Même règle que staticPath() dans app.js : "/api/posts?statut=x" -> "api/posts__statut_x.json"."""
    name = path.lstrip("/").replace("?", "__", 1)
    return name.replace("=", "_").replace("&", "_") + ".json"


def _write_json(dest: Path, relative: str, data: object) -> None:
    path = dest / "data" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _llm_label(cfg: dict) -> str:
    names = {"gemini": "Gemini", "openai": "OpenAI", "anthropic": "Claude", "fake": "le mode démo (sans LLM)"}
    model = f" ({cfg['modeles'][0]})" if cfg.get("modeles") else ""
    return names.get(cfg["llm"], cfg["llm"]) + model


def export_site(dest: Path, with_llm: bool = True) -> dict:
    """Construit le site statique dans `dest` et renvoie un petit bilan."""
    client = TestClient(app, raise_server_exceptions=False)  # une erreur LLM ne doit pas tout arrêter

    # 1. Chaque post doit avoir un visuel (maquette hors ligne, sans coût).
    for post in list_posts():
        if not post.image_path or not Path(post.image_path).exists():
            create_visual(post, PlaceholderImageGenerator())
            save_post(post)

    # 2. Page et fichiers statiques. Le marqueur COPILOTE_STATIC active le mode lecture seule.
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(STATIC, dest / "static")
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    html = html.replace(
        '<script src="/static/app.js"></script>',
        '<script>window.COPILOTE_STATIC = true;</script>\n  <script src="/static/app.js"></script>',
    )
    (dest / "index.html").write_text(html, encoding="utf-8")
    (dest / "static" / "index.html").unlink()

    # 3. Instantané des lectures.
    for path in GET_PATHS:
        response = client.get(path)
        response.raise_for_status()
        data = response.json()
        if path == "/api/dashboard":
            data["config"]["statique"] = True  # la visite guidée adapte ses textes
            cfg = data["config"]
        _write_json(dest, static_name(path), data)

    # 4. Visuels référencés par les posts.
    images = dest / "images"
    images.mkdir()
    for image in config.images_dir().glob("*"):
        shutil.copy(image, images / image.name)

    # 5. Réponses et évaluation calculées avec le vrai LLM (une seule fois, à l'export).
    answers, evaluation, failures = {}, None, 0
    if with_llm:
        for question in SUGGESTIONS:
            response = client.post("/api/ask", json={"question": question})
            if response.status_code == 200:
                answers[question] = response.json()
            else:
                failures += 1
        response = client.post("/api/eval")
        if response.status_code == 200:
            evaluation = response.json()
            _write_json(dest, "eval.json", evaluation)
        else:
            failures += 1
    _write_json(dest, "ask.json", answers)
    _write_json(dest, "meta.json", {"llm": _llm_label(cfg), "date": date.today().strftime("%d/%m/%Y")})

    return {
        "lectures": len(GET_PATHS),
        "visuels": len(list(images.glob("*"))),
        "reponses": len(answers),
        "evaluation": f"{evaluation['conformes']}/{len(evaluation['cas'])}" if evaluation else "non calculée",
        "echecs_llm": failures,
    }
