"""Test de bout en bout de la CLI en mode démo : watch -> generate -> review -> schedule."""

from typer.testing import CliRunner

from src.cli import app
from src.models import Status
from src.store import list_posts

runner = CliRunner()


def run(*args: str):
    result = runner.invoke(app, list(args))
    assert result.exit_code == 0, result.output
    return result


def test_full_pipeline(isolated):
    run("watch", "--offline")
    run("generate", "--articles", "1")
    drafts = list_posts(Status.DRAFT)
    assert len(drafts) == 4  # 3 personas LinkedIn + 1 Instagram

    run("review", *[arg for p in drafts for arg in ("--approve", p.id)])
    result = run("schedule")
    assert "4 post(s) programmé(s)" in result.output
    assert len(list_posts(Status.SCHEDULED)) == 4
    run("list")


def test_generate_without_articles_fails_cleanly(isolated):
    result = runner.invoke(app, ["generate"])
    assert result.exit_code == 1
    assert "watch" in result.output
