"""Interface web : une API REST (FastAPI) au-dessus des modules existants + une page statique.

Aucune logique métier ici : chaque route appelle les mêmes fonctions que la CLI.
Lancement : python -m src.cli ui   (puis http://localhost:8765)
Usage local et mono-utilisateur (pas d'authentification).
"""

import threading
from collections.abc import Callable
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src import config, review
from src.config import env
from src.generate import generate_post
from src.ingest import get_collection, get_embedder, ingest
from src.llm import LLMError, get_llm_client
from src.models import Persona, Post, Status
from src.orchestrate import DEMO_FEED, weekly
from src.publish import WEEKLY_SLOTS, publish_due, schedule
from src.qa import ask
from src.store import list_posts, load_post, save_post
from src.trends import analyze
from src.visuals import create_visual
from src.watch import load_articles, load_feeds, load_watchlist, watch

STATIC = Path(__file__).parent / "static"

app = FastAPI(title="Copilote Marketing", version="0.2.0")
app.mount("/static", StaticFiles(directory=STATIC), name="static")

@app.exception_handler(LLMError)
async def llm_unavailable(request: Request, error: LLMError) -> JSONResponse:
    """LLM saturé, quota dépassé ou clé refusée : réponse 503 lisible plutôt qu'une erreur 500."""
    return JSONResponse(status_code=503, content={"detail": f"LLM indisponible pour l'instant, réessayez plus tard. ({error})"})


@app.middleware("http")
async def no_cache_for_pages(request: Request, call_next: Callable) -> Response:
    """Toujours revalider la page et ses fichiers : une mise à jour du code est vue immédiatement."""
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


# Le modèle d'embedding met plusieurs secondes à charger : on le charge en arrière-plan
# dès le démarrage, pour que la première action de l'utilisateur soit rapide.
threading.Thread(target=get_embedder, daemon=True).start()


# --------------------------------------------------------------------------- Corps des requêtes


class WatchRequest(BaseModel):
    offline: bool = True


class GenerateRequest(BaseModel):
    article_url: str
    personas: list[Persona]


class ReviewRequest(BaseModel):
    note: str = ""


class EditRequest(BaseModel):
    texte: str


class AskRequest(BaseModel):
    question: str


class PublishRequest(BaseModel):
    at: datetime | None = None


# --------------------------------------------------------------------------- Utilitaires


def _post_json(post: Post) -> dict:
    """Post sérialisé pour l'interface (sans le contexte complet, trop volumineux)."""
    data = post.model_dump(mode="json", exclude={"contexte"})
    data["image_web"] = f"/images/{Path(post.image_path).name}" if post.image_path else None
    return data


def _get(post_id: str) -> Post:
    try:
        return load_post(post_id)
    except FileNotFoundError:
        raise HTTPException(404, f"Post introuvable : {post_id}")


def _guard(action: Callable[[], Post]) -> Post:
    """Transforme les erreurs métier (transition interdite, etc.) en erreur HTTP 400 lisible."""
    try:
        return action()
    except ValueError as error:
        raise HTTPException(400, str(error))


def _models_of(provider: str) -> list[str]:
    """Modèles configurés pour le fournisseur actif (Gemini peut en lister plusieurs, en secours)."""
    variable = {"gemini": "GEMINI_MODEL", "openai": "OPENAI_MODEL", "anthropic": "ANTHROPIC_MODEL"}.get(provider)
    return [m.strip() for m in env(variable).split(",") if m.strip()] if variable else []


# --------------------------------------------------------------------------- Pages


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    """Page unique de l'interface."""
    return FileResponse(STATIC / "index.html")


@app.get("/images/{name}", include_in_schema=False)
def image(name: str) -> FileResponse:
    """Sert un visuel généré, sans permettre de sortir du dossier des images."""
    path = (config.images_dir() / name).resolve()
    if path.parent != config.images_dir().resolve() or not path.exists():
        raise HTTPException(404)
    return FileResponse(path)


# --------------------------------------------------------------------------- Tableau de bord


@app.get("/api/dashboard")
def dashboard() -> dict:
    """Indicateurs du tableau de bord : statuts, veille, tendances, prochaines publications."""
    posts = list_posts()
    articles = list(load_articles().values())
    upcoming = sorted(
        (p for p in posts if p.statut is Status.SCHEDULED and p.programme_le),
        key=lambda p: p.programme_le,
    )[:3]
    report = analyze(articles, load_watchlist(), top=6) if articles else None
    return {
        "config": {
            "llm": env("LLM_PROVIDER", "fake"),
            "modeles": _models_of(env("LLM_PROVIDER", "fake")),
            "images": env("IMAGE_PROVIDER", "placeholder"),
            "publication": env("PUBLISH_MODE", "mock"),
        },
        "chunks": get_collection().count(),
        "articles": len(articles),
        "statuts": {s.value: sum(p.statut is s for p in posts) for s in Status},
        "prochains": [_post_json(p) for p in upcoming],
        "tendances": report.top_terms if report else [],
        "concurrents": [
            {"terme": m.term, "mentions": len(m.articles)} for m in (report.mentions if report else []) if m.kind == "concurrent"
        ],
    }


# --------------------------------------------------------------------------- Base de connaissances


@app.post("/api/ingest")
def run_ingest() -> dict:
    """Réindexe les documents de marque dans ChromaDB."""
    chunks = ingest()
    return {"chunks": len(chunks), "documents": len({c.source for c in chunks})}


SUGGESTIONS = [
    "Quel est le degré de la Saison Démo ?",
    "Quels houblons dans la Blonde Démo ?",
    "Avez-vous le label Biogarantie ?",
    "Quel est le minimum de commande ?",
    "Quel est le prix de la Blonde ?",
]


@app.get("/api/suggestions")
def suggestions() -> list[str]:
    """Questions proposées dans la vue Base de connaissances (pré-calculées dans le site statique)."""
    return SUGGESTIONS


@app.post("/api/ask")
def run_ask(body: AskRequest) -> dict:
    """Question à la base de connaissances : réponse sourcée ou « je ne trouve pas »."""
    if not body.question.strip():
        raise HTTPException(400, "Question vide")
    return ask(get_llm_client(), body.question).model_dump()


# --------------------------------------------------------------------------- Veille


@app.get("/api/articles")
def articles() -> list[dict]:
    """Articles de veille, avec un indicateur « déjà utilisé pour un post »."""
    used = {p.article_url for p in list_posts()}
    return [a.model_dump(mode="json") | {"utilise": a.url in used} for a in load_articles().values()]


@app.post("/api/watch")
def run_watch(body: WatchRequest) -> dict:
    """Lance la veille (flux fictif ou flux réels + social listening)."""
    llm = get_llm_client()
    if body.offline:
        added = watch(llm, feeds=[DEMO_FEED], max_items=10)
    else:
        feeds, max_items = load_feeds()
        added = watch(llm, feeds=feeds, max_items=max_items)
    return {"ajoutes": len(added)}


@app.get("/api/trends")
def trends() -> dict:
    """Tendances et mentions des mots-clés et concurrents suivis."""
    report = analyze(list(load_articles().values()), load_watchlist(), top=12)
    return {
        "n_articles": report.n_articles,
        "termes": report.top_terms,
        "expressions": report.top_phrases,
        "mentions": [{"terme": m.term, "type": m.kind, "articles": m.articles} for m in report.mentions],
    }


# --------------------------------------------------------------------------- Génération


@app.post("/api/generate")
def run_generate(body: GenerateRequest) -> list[dict]:
    """Rédige un brouillon (avec visuel) par persona demandée, à partir d'un article."""
    article = load_articles().get(body.article_url)
    if not article:
        raise HTTPException(404, "Article de veille introuvable")
    llm = get_llm_client()
    posts = []
    for persona in body.personas:
        post = generate_post(llm, article, persona)
        create_visual(post)
        save_post(post)
        posts.append(_post_json(post))
    return posts


@app.post("/api/weekly")
def run_weekly(body: WatchRequest) -> list[dict]:
    """Flux hebdomadaire : veille + 3 brouillons (2 LinkedIn + 1 Instagram) avec visuels."""
    posts = weekly(get_llm_client(), offline=body.offline)
    for post in posts:
        create_visual(post)
        save_post(post)
    return [_post_json(p) for p in posts]


# --------------------------------------------------------------------------- Posts et revue


@app.get("/api/posts")
def posts(statut: Status | None = None) -> list[dict]:
    """Liste des posts, du plus récent au plus ancien, filtrable par statut."""
    return [_post_json(p) for p in reversed(list_posts(statut))]


@app.get("/api/posts/{post_id}")
def post(post_id: str) -> dict:
    """Détail d'un post."""
    return _post_json(_get(post_id))


@app.post("/api/posts/{post_id}/approve")
def approve(post_id: str, body: ReviewRequest) -> dict:
    """Approuve un brouillon."""
    _get(post_id)
    return _post_json(_guard(lambda: review.approve(post_id, body.note)))


@app.post("/api/posts/{post_id}/reject")
def reject(post_id: str, body: ReviewRequest) -> dict:
    """Rejette un post, avec une note facultative."""
    _get(post_id)
    return _post_json(_guard(lambda: review.reject(post_id, body.note)))


@app.post("/api/posts/{post_id}/edit")
def edit(post_id: str, body: EditRequest) -> dict:
    """Remplace le texte, relance le garde-fou et repasse le post en brouillon."""
    _get(post_id)
    return _post_json(_guard(lambda: review.edit(post_id, body.texte)))


@app.post("/api/posts/{post_id}/visual")
def visual(post_id: str) -> dict:
    """(Re)génère le visuel d'un post."""
    post = _get(post_id)
    create_visual(post)
    save_post(post)
    return _post_json(post)


# --------------------------------------------------------------------------- Calendrier


@app.get("/api/calendar")
def calendar(weeks: int = 4) -> list[dict]:
    """Créneaux des prochaines semaines (à partir du lundi courant) et posts qui les occupent."""
    by_slot = {p.programme_le: p for p in list_posts() if p.programme_le}
    monday = date.today() - timedelta(days=date.today().weekday())
    result = []
    for week in range(weeks):
        start = monday + timedelta(weeks=week)
        slots = []
        for weekday, hour, platform in WEEKLY_SLOTS:
            when = datetime.combine(start + timedelta(days=weekday), hour)
            post = by_slot.get(when)
            slots.append({"date": when.isoformat(), "plateforme": platform.value, "post": _post_json(post) if post else None})
        result.append({"lundi": start.isoformat(), "semaine": start.isocalendar().week, "creneaux": slots})
    return result


@app.post("/api/schedule")
def run_schedule() -> dict:
    """Programme les posts approuvés dans les prochains créneaux libres."""
    planning = schedule()
    return {"programmes": [{"id": p.id, "date": when.isoformat()} for p, when in planning]}


@app.post("/api/publish-due")
def run_publish_due(body: PublishRequest) -> dict:
    """Publie les posts arrivés à échéance (date simulable)."""
    done = publish_due(now=body.at)
    return {"publies": [{"id": p.id, "canaux": channels} for p, channels in done]}


# --------------------------------------------------------------------------- Évaluation


@app.post("/api/eval")
def run_eval() -> dict:
    """Lance la mini-évaluation sur 10 cas et le contrôle des détecteurs."""
    from tests.eval import detector_controls, run_eval as evaluate

    results = evaluate()
    return {
        "cas": [r.__dict__ | {"passed": r.passed} for r in results],
        "conformes": sum(r.passed for r in results),
        "controles": [{"cas": name, "detections": warnings} for name, warnings in detector_controls()],
    }
