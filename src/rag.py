"""Récupération (retrieval) des passages de marque pertinents, avec leurs sources."""

from pathlib import Path

from src.ingest import embed, get_collection
from src.models import Passage


def retrieve(
    query: str,
    k: int = 5,
    doc_types: list[str] | None = None,
    chroma_dir: Path | None = None,
) -> list[Passage]:
    """Renvoie les `k` passages les plus proches de `query`, du plus au moins pertinent.

    `doc_types` filtre par type de document (ex. ["fiche_biere", "labels_bio"]).
    """
    collection = get_collection(chroma_dir)
    if collection.count() == 0:
        raise RuntimeError("Base vectorielle vide : lancez d'abord `python -m src.cli ingest`.")
    where = {"doc_type": {"$in": doc_types}} if doc_types else None
    result = collection.query(query_embeddings=embed([query]), n_results=k, where=where)
    return [
        Passage(text=text, source=meta["source"], doc_type=meta["doc_type"], score=1 - distance)
        for text, meta, distance in zip(
            result["documents"][0], result["metadatas"][0], result["distances"][0]
        )
    ]


def retrieve_many(
    queries: list[str],
    k: int = 4,
    doc_types: list[str] | None = None,
    chroma_dir: Path | None = None,
) -> list[Passage]:
    """Fusionne les résultats de plusieurs requêtes, sans doublon, triés par score."""
    best: dict[str, Passage] = {}
    for query in queries:
        for passage in retrieve(query, k=k, doc_types=doc_types, chroma_dir=chroma_dir):
            if passage.text not in best or passage.score > best[passage.text].score:
                best[passage.text] = passage
    return sorted(best.values(), key=lambda p: p.score, reverse=True)


def format_context(passages: list[Passage]) -> str:
    """Met en forme les passages pour le prompt, chacun étiqueté par sa source."""
    return "\n\n".join(f"[source: {p.source}]\n{p.text}" for p in passages)


def sources_of(passages: list[Passage]) -> list[str]:
    """Liste des fichiers sources, sans doublon, dans l'ordre d'apparition."""
    return list(dict.fromkeys(p.source for p in passages))
