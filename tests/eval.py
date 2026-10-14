"""Mini-évaluation : 10 cas (article de veille x persona), vérifiés automatiquement.

Lancement : python -m tests.eval
Le LLM utilisé est celui de LLM_PROVIDER (fake par défaut, gemini ou anthropic si configuré).
Les posts sont générés dans un dossier temporaire : out/ n'est pas modifié.

Critères par cas :
- longueur conforme à la plateforme ;
- hashtags (1 à 3 sur LinkedIn, exactement 5 sur Instagram) et émojis dans la limite ;
- zéro chiffre et zéro label absents du contexte RAG + article ;
- zéro formule interdite par la charte ;
- au moins une source de marque citée.
Une seconde table vérifie que les détecteurs attrapent bien deux posts volontairement fautifs.
"""

import tempfile
from dataclasses import dataclass
from itertools import islice, product
from pathlib import Path

from rich.console import Console
from rich.markup import escape
from rich.table import Table

from src import config, guard
from src.generate import generate_post
from src.ingest import get_collection, ingest
from src.llm import get_llm_client
from src.models import Persona, Platform, Post, PostDraft
from src.watch import watch

N_CASES = 10
DEMO_FEED = [{"name": "Flux démo (fictif)", "url": str(config.DATA_DIR / "demo_feed.xml"), "theme": "demo"}]


@dataclass
class CaseResult:
    case: int
    persona: str
    article: str
    length: int
    length_ok: bool
    hashtags_ok: bool
    emojis_ok: bool
    unsourced: list[str]
    forbidden: list[str]
    sources: int
    confidence: float
    texte: str = ""  # gardé pour afficher les cas en échec et comprendre pourquoi

    @property
    def passed(self) -> bool:
        return all([self.length_ok, self.hashtags_ok, self.emojis_ok, not self.unsourced, not self.forbidden, self.sources])


def evaluate(post: Post, case: int, article_title: str) -> CaseResult:
    """Applique les critères à un post généré."""
    problems = guard.format_problems(post)
    unsourced = guard.unsourced_numbers(post.texte, post.contexte) + guard.unsourced_labels(post.texte, post.contexte)
    return CaseResult(
        case=case,
        persona=post.persona.value,
        article=article_title,
        length=len(post.texte),
        length_ok=not any(p.startswith("Longueur") for p in problems),
        hashtags_ok=not any("hashtags" in p for p in problems),
        emojis_ok=not any("émojis" in p for p in problems),
        unsourced=unsourced,
        forbidden=guard.forbidden_words(post.texte),
        sources=len(post.sources_utilisees),
        confidence=post.score_confiance,
        texte=post.texte,
    )


def run_eval() -> list[CaseResult]:
    """Génère les 10 cas et les évalue. Les sorties vont dans un dossier temporaire."""
    if get_collection().count() == 0:
        ingest()
    llm = get_llm_client()
    original_out = config.OUT_DIR
    with tempfile.TemporaryDirectory() as tmp:
        config.OUT_DIR = Path(tmp)
        try:
            articles = watch(llm, feeds=DEMO_FEED, max_items=10)
            # 10 couples (article, persona) tous différents
            pairs = list(islice(product(articles, Persona), N_CASES))
            return [evaluate(generate_post(llm, a, p), i + 1, a.titre) for i, (a, p) in enumerate(pairs)]
        finally:
            config.OUT_DIR = original_out


def detector_controls() -> list[tuple[str, list[str]]]:
    """Deux posts volontairement fautifs : les détecteurs doivent les signaler."""
    context = "[source: 03_fiche_blonde_demo.md]\nDegré d'alcool : 6,5 % vol."
    bad_degree = Post.from_draft(
        PostDraft(texte="Notre Blonde Démo titre 8 % et elle est labellisée Demeter. " * 12, hashtags=["#BiereBio"], score_confiance=0.9),
        Persona.EXPERTISE_BIO,
        None,
    )
    hype = Post.from_draft(
        PostDraft(texte="La MEILLEURE bière, incroyable et bonne pour la santé ! 🔥🔥🔥🔥 " * 4, hashtags=["#A", "#B", "#C", "#D", "#E"], score_confiance=0.9),
        Persona.INSTAGRAM,
        None,
    )
    results = []
    for name, post in [("degré + label inventés", bad_degree), ("superlatifs + santé + émojis", hype)]:
        checked = guard.check(post, context)
        results.append((name, [w.replace("[garde-fou] ", "") for w in checked.avertissements]))
    return results


def print_report(results: list[CaseResult]) -> None:
    console = Console()
    ok, ko = "[green]✓[/green]", "[red]✗[/red]"
    table = Table(title=f"Mini-évaluation ({get_llm_client().name})")
    for column in ["#", "persona", "article", "long.", "long. OK", "hashtags", "émojis", "non sourcés", "interdits", "sources", "conf.", "verdict"]:
        table.add_column(column)
    for r in results:
        table.add_row(
            str(r.case),
            r.persona,
            r.article[:28] + "…",
            str(r.length),
            ok if r.length_ok else ko,
            ok if r.hashtags_ok else ko,
            ok if r.emojis_ok else ko,
            ", ".join(r.unsourced) or "0",
            ", ".join(r.forbidden) or "0",
            str(r.sources),
            f"{r.confidence:.2f}",
            "[green]OK[/green]" if r.passed else "[red]ÉCHEC[/red]",
        )
    console.print(table)
    for r in results:
        if not r.passed:
            console.print(f"[red]Cas {r.case} en échec ({r.persona}) :[/red] {escape(r.texte)}\n")
    passed = sum(r.passed for r in results)
    mean = sum(r.confidence for r in results) / len(results)
    console.print(f"[bold]{passed}/{len(results)} cas conformes[/bold], confiance moyenne {mean:.2f}")

    controls = Table(title="Contrôle des détecteurs (posts volontairement fautifs)")
    controls.add_column("cas")
    controls.add_column("problèmes détectés")
    for name, warnings in detector_controls():
        controls.add_row(name, "\n".join(warnings) or "[red]aucun : détecteur défaillant[/red]")
    console.print(controls)


if __name__ == "__main__":
    print_report(run_eval())
