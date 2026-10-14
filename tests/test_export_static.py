"""Tests de l'export en site statique (Netlify), sans LLM ni réseau."""

import json
import re

from src.config import ROOT
from src.generate import generate_post
from src.llm import get_llm_client
from src.models import Persona
from src.watch import load_articles, watch
from src.web.export_static import GET_PATHS, export_site, static_name

APP_JS = ROOT / "src" / "web" / "static"


def test_static_name_matches_the_javascript_rule():
    assert static_name("/api/posts?statut=brouillon") == "api/posts__statut_brouillon.json"
    assert static_name("/api/calendar?weeks=4") == "api/calendar__weeks_4.json"


def test_every_read_made_by_the_interface_is_exported():
    """Chaque api("GET", "…") du JavaScript doit avoir son fichier dans le site statique."""
    code = "".join((APP_JS / name).read_text(encoding="utf-8") for name in ("app.js", "tour.js"))
    reads = set(re.findall(r'api\("GET", "([^"]+)"\)', code))
    assert reads, "aucune lecture trouvée : l'expression régulière ne correspond plus au code"
    assert reads <= set(GET_PATHS), f"lectures non exportées : {reads - set(GET_PATHS)}"


def test_export_builds_a_read_only_site(isolated):
    llm = get_llm_client("fake")
    watch(llm, feeds=[{"name": "Démo", "url": str(ROOT / "data" / "demo_feed.xml"), "theme": "demo"}], max_items=10)
    article = next(iter(load_articles().values()))
    post = generate_post(llm, article, Persona.INSTAGRAM)

    site = isolated / "site"
    summary = export_site(site, with_llm=False)

    html = (site / "index.html").read_text(encoding="utf-8")
    assert "window.COPILOTE_STATIC = true" in html
    for path in GET_PATHS:
        assert (site / "data" / static_name(path)).exists(), path
    dashboard = json.loads((site / "data" / "api" / "dashboard.json").read_text(encoding="utf-8"))
    assert dashboard["config"]["statique"] is True
    assert (site / "images" / f"{post.id}.svg").exists()  # visuel créé puis copié
    assert summary["visuels"] == 1

    exported = "".join(p.read_text(encoding="utf-8") for p in (site / "data").rglob("*.json"))
    assert '"contexte"' not in exported  # le contexte RAG complet n'est jamais publié
    assert "API_KEY" not in exported
