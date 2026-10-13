"""Interface en ligne de commande : python -m src.cli <commande>.

Enchaînement type : ingest -> watch -> generate -> review -> schedule.
"""

import sys
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from src import config, review as review_queue
from src.generate import generate_batch
from src.ingest import ingest as run_ingest
from src.llm import get_llm_client
from src.models import Persona, Post, Status
from src.publish import schedule as run_schedule
from src.store import list_posts, load_post
from src.watch import load_articles, load_feeds, watch as run_watch

# Les émojis des posts doivent s'afficher même dans une console Windows.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

app = typer.Typer(help="Copilote Marketing : veille, génération et programmation de posts.")
console = Console()


@app.command()
def ingest() -> None:
    """Découpe les documents de marque et les vectorise dans ChromaDB."""
    chunks = run_ingest()
    sources = sorted({c.source for c in chunks})
    console.print(f"[green]{len(chunks)} chunks indexés depuis {len(sources)} documents.[/green]")


@app.command()
def watch(
    offline: bool = typer.Option(False, help="Utiliser le flux fictif data/demo_feed.xml (sans réseau)."),
) -> None:
    """Lit les flux RSS, résume les nouveaux articles et les stocke (dédupliqués par URL)."""
    llm = get_llm_client()
    if offline:
        feeds = [{"name": "Flux démo (fictif)", "url": str(config.DATA_DIR / "demo_feed.xml"), "theme": "demo"}]
        added = run_watch(llm, feeds=feeds, max_items=10)
    else:
        feeds, max_items = load_feeds()
        added = run_watch(llm, feeds=feeds, max_items=max_items)
    console.print(f"[green]{len(added)} nouvel(s) article(s)[/green] (LLM : {llm.name})")
    for article in added:
        console.print(f"• {article.titre}\n  [dim]{article.url}[/dim]")


@app.command()
def generate(
    articles: int = typer.Option(1, help="Nombre d'articles de veille récents à utiliser."),
    persona: list[Persona] = typer.Option(None, help="Persona(s) ; toutes par défaut."),
) -> None:
    """Génère des posts (statut brouillon) à partir des derniers articles de veille."""
    stored = list(load_articles().values())[:articles]
    if not stored:
        console.print("[red]Aucun article de veille. Lancez d'abord `watch`.[/red]")
        raise typer.Exit(1)
    llm = get_llm_client()
    posts = generate_batch(llm, stored, persona or list(Persona))
    for post in posts:
        show_post(post)
    console.print(f"[green]{len(posts)} brouillon(s) créé(s).[/green] Validez-les avec `review`.")


@app.command("list")
def list_command(statut: Status = typer.Option(None, help="Filtrer par statut.")) -> None:
    """Liste les posts et leur statut."""
    table = Table("id", "plateforme", "persona", "statut", "confiance", "avert.", "programmé le")
    for post in list_posts(statut):
        table.add_row(
            post.id,
            post.plateforme.value,
            post.persona.value,
            post.statut.value,
            f"{post.score_confiance:.2f}",
            str(len(post.avertissements)),
            french_date(post.programme_le) if post.programme_le else "",
        )
    console.print(table)


@app.command()
def show(post_id: str) -> None:
    """Affiche un post complet, avec ses sources, avertissements et prompt d'image."""
    show_post(load_post(post_id), with_image=True)


@app.command()
def review(
    approve: list[str] = typer.Option(None, "--approve", help="Approuver ce post (id)."),
    reject: list[str] = typer.Option(None, "--reject", help="Rejeter ce post (id)."),
    edit: str = typer.Option(None, "--edit", help="Éditer ce post (id), avec --text."),
    text: str = typer.Option(None, "--text", help="Nouveau texte pour --edit."),
    note: str = typer.Option("", "--note", help="Note de revue."),
) -> None:
    """Valide les brouillons. Sans option : mode interactif, un brouillon à la fois."""
    if approve or reject or edit:
        for post_id in approve or []:
            review_queue.approve(post_id, note)
            console.print(f"[green]Approuvé :[/green] {post_id}")
        for post_id in reject or []:
            review_queue.reject(post_id, note)
            console.print(f"[yellow]Rejeté :[/yellow] {post_id}")
        if edit:
            if not text:
                raise typer.BadParameter("--edit exige --text")
            show_post(review_queue.edit(edit, text))
        return

    drafts = review_queue.pending()
    if not drafts:
        console.print("Aucun brouillon à valider.")
        return
    for post in drafts:
        show_post(post)
        choice = typer.prompt("[a]pprouver, [r]ejeter, [e]diter, [p]asser, [q]uitter", default="p")
        if choice == "a":
            review_queue.approve(post.id, typer.prompt("Note", default=""))
        elif choice == "r":
            review_queue.reject(post.id, typer.prompt("Raison du rejet", default=""))
        elif choice == "e":
            new_text = typer.edit(post.texte)
            if new_text:
                show_post(review_queue.edit(post.id, new_text.strip()))
        elif choice == "q":
            break


@app.command()
def schedule() -> None:
    """Programme les posts approuvés : 2 LinkedIn + 1 Instagram par semaine (MockPublisher)."""
    planning = run_schedule()
    if not planning:
        console.print("Aucun post approuvé à programmer.")
        return
    table = Table("date", "plateforme", "id", "début du texte")
    for post, when in planning:
        table.add_row(french_date(when), post.plateforme.value, post.id, post.texte[:60] + "…")
    console.print(table)
    console.print(f"[green]{len(planning)} post(s) programmé(s)[/green] dans {config.scheduled_dir()}")


@app.command()
def export(
    post_ids: list[str],
    dest: Path = typer.Option(config.OUT_DIR / "examples", help="Dossier de destination."),
) -> None:
    """Exporte des posts en markdown lisible (texte, sources, avertissements, prompt d'image)."""
    dest.mkdir(parents=True, exist_ok=True)
    for post_id in post_ids:
        post = load_post(post_id)
        path = dest / f"{post.plateforme.value}_{post.persona.value}_{post.id}.md"
        path.write_text(post_to_markdown(post), encoding="utf-8")
        console.print(f"[green]Exporté :[/green] {path}")


JOURS = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]


def french_date(when: datetime) -> str:
    """'mar. 20/10/2026 09h00', indépendamment de la langue du système."""
    return f"{JOURS[when.weekday()]} {when:%d/%m/%Y %Hh%M}"


def post_to_markdown(post: Post) -> str:
    """Rendu markdown d'un post, avec toutes ses métadonnées de traçabilité."""
    warnings = "\n".join(f"- {w}" for w in post.avertissements) or "- aucun"
    sources = ", ".join(f"`{s}`" for s in post.sources_utilisees) or "aucune"
    return (
        f"# {post.plateforme.value.capitalize()} · {post.persona.value}\n\n"
        f"- Identifiant : `{post.id}`\n- Statut : {post.statut.value}\n"
        f"- Article de départ : {post.article_url}\n- Sources de marque : {sources}\n"
        f"- Score de confiance : {post.score_confiance:.2f}\n\n"
        f"## Texte\n\n{post.texte}\n\n{' '.join(post.hashtags)}\n\n"
        f"## Avertissements\n\n{warnings}\n\n"
        f"## Prompt d'image\n\n```text\n{post.prompt_image}\n```\n"
    )


def show_post(post: Post, with_image: bool = False) -> None:
    """Affiche un post dans un cadre, avec ses métadonnées."""
    color = "green" if not post.avertissements else "yellow"
    # escape() : le texte des posts ne doit pas être interprété comme du balisage rich
    body = f"{escape(post.texte)}\n\n[cyan]{' '.join(post.hashtags)}[/cyan]\n\n"
    body += f"[dim]Sources : {', '.join(post.sources_utilisees) or 'aucune'}[/dim]\n"
    body += f"[dim]Confiance : {post.score_confiance:.2f}[/dim]"
    for warning in post.avertissements:
        body += f"\n[yellow]⚠ {escape(warning)}[/yellow]"
    if with_image and post.prompt_image:
        body += f"\n\n[magenta]Prompt image :[/magenta]\n{escape(post.prompt_image)}"
    title = f"{post.id} · {post.plateforme.value} · {post.persona.value} · {post.statut.value}"
    console.print(Panel(body, title=title, border_style=color))


if __name__ == "__main__":
    app()
