"""Tests de l'API de l'interface web (FastAPI TestClient, mode démo, dossiers isolés)."""

from fastapi.testclient import TestClient

from src.web.app import app

client = TestClient(app)


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def test_index_and_static_are_served(isolated):
    assert "Copilote" in client.get("/").text
    assert client.get("/static/app.js").status_code == 200


def test_full_flow_through_the_api(isolated):
    assert ok(client.post("/api/watch", json={"offline": True}))["ajoutes"] == 5
    articles = ok(client.get("/api/articles"))
    posts = ok(client.post("/api/generate", json={"article_url": articles[0]["url"], "personas": ["expertise_bio", "instagram_craft"]}))
    assert [p["statut"] for p in posts] == ["brouillon", "brouillon"]
    assert all(p["image_web"] for p in posts)  # visuel généré et servi
    assert client.get(posts[0]["image_web"]).status_code == 200

    for post in posts:
        ok(client.post(f"/api/posts/{post['id']}/approve", json={"note": ""}))
    assert len(ok(client.post("/api/schedule"))["programmes"]) == 2
    published = ok(client.post("/api/publish-due", json={"at": "2099-01-01T00:00:00"}))["publies"]
    assert len(published) == 2

    dashboard = ok(client.get("/api/dashboard"))
    assert dashboard["statuts"]["publie"] == 2
    assert any(slot["post"] for week in ok(client.get("/api/calendar?weeks=60")) for slot in week["creneaux"])


def test_forbidden_transition_returns_400(isolated):
    ok(client.post("/api/watch", json={"offline": True}))
    url = ok(client.get("/api/articles"))[0]["url"]
    post = ok(client.post("/api/generate", json={"article_url": url, "personas": ["coulisses_brassage"]}))[0]
    ok(client.post(f"/api/posts/{post['id']}/reject", json={"note": "non"}))
    response = client.post(f"/api/posts/{post['id']}/approve", json={"note": ""})
    assert response.status_code == 400
    assert "Transition interdite" in response.json()["detail"]


def test_ask_and_trends(isolated):
    answer = ok(client.post("/api/ask", json={"question": "Quel est le degré de la Saison Démo ?"}))
    assert "5,8" in answer["reponse"]
    ok(client.post("/api/watch", json={"offline": True}))
    trends = ok(client.get("/api/trends"))
    assert any(m["type"] == "concurrent" and m["articles"] for m in trends["mentions"])


def test_unknown_post_and_image_path_traversal(isolated):
    assert client.get("/api/posts/inexistant").status_code == 404
    assert client.get("/images/..%2F..%2F.env").status_code == 404
