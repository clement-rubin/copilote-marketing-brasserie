"""Base de connaissances interrogeable : une question -> une réponse sourcée (commande `ask`).

Même chaîne que la génération : RAG -> prompt -> JSON validé -> garde-fou sur les chiffres.
"""

from pathlib import Path

from src import guard, prompts
from src.llm import LLMClient, complete_json
from src.models import Answer
from src.rag import format_context, retrieve, sources_of

NOT_FOUND = "Je ne trouve pas cette information dans la documentation."


def ask(llm: LLMClient, question: str, k: int = 6, chroma_dir: Path | None = None) -> Answer:
    """Répond à une question en s'appuyant uniquement sur les documents de marque."""
    passages = retrieve(question, k=k, chroma_dir=chroma_dir)
    context = format_context(passages)
    user = prompts.render("question", question=question, contexte=context)
    answer = complete_json(llm, prompts.load("system"), user, Answer)

    allowed = sources_of(passages)
    answer.avertissements += [f"Source citée mais non fournie : {s}" for s in answer.sources_utilisees if s not in allowed]
    answer.sources_utilisees = [s for s in answer.sources_utilisees if s in allowed]
    answer.avertissements += [f"Chiffre non sourcé : {n}" for n in guard.unsourced_numbers(answer.reponse, context)]
    answer.avertissements += [f"Label non sourcé : {l}" for l in guard.unsourced_labels(answer.reponse, context)]
    return answer
