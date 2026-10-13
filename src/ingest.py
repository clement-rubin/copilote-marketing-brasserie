"""Ingestion : documents de marque -> chunks -> embeddings -> ChromaDB.

Choix de découpage :
- le modèle d'embedding (MiniLM multilingue) tronque à 128 tokens. Au-delà, le texte
  n'est pas vectorisé du tout. On vise donc des chunks de 120 tokens au maximum ;
- on découpe d'abord par section markdown (un chunk ne mélange pas deux sujets), puis par
  phrase, avec un chevauchement d'environ 30 tokens entre chunks voisins ;
- chaque chunk commence par "Titre > Section" pour garder le contexte après découpage.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import chromadb
import yaml

from src import config

EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
COLLECTION = "brand"
MAX_TOKENS = 120
OVERLAP_TOKENS = 30

TokenCounter = Callable[[str], int]


@dataclass
class Chunk:
    """Un morceau de document prêt à être vectorisé."""

    id: str
    text: str
    source: str
    doc_type: str
    section: str


# --------------------------------------------------------------------------- Modèle


@lru_cache(maxsize=1)
def get_embedder():
    """Charge le modèle une seule fois (le premier appel le télécharge, environ 470 Mo)."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBEDDING_MODEL)


def count_tokens(text: str) -> int:
    """Compte les tokens avec le tokenizer du modèle d'embedding lui-même."""
    return len(get_embedder().tokenizer.encode(text, add_special_tokens=False))


def embed(texts: list[str]) -> list[list[float]]:
    """Vectorise des textes (vecteurs normalisés, donc comparables par cosinus)."""
    return get_embedder().encode(texts, normalize_embeddings=True).tolist()


# --------------------------------------------------------------------------- Lecture


def read_markdown(path: Path) -> tuple[dict, str]:
    """Sépare le front matter YAML (entre deux lignes ---) du corps du document."""
    raw = path.read_text(encoding="utf-8")
    match = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n(.*)$", raw, flags=re.DOTALL)
    if not match:
        return {}, raw
    return yaml.safe_load(match.group(1)) or {}, match.group(2)


def split_sections(body: str) -> list[tuple[str, str]]:
    """Découpe le corps en (titre de section, texte). Ignore ce qui précède le titre H1."""
    sections: list[tuple[str, str]] = []
    heading, lines = None, []
    for line in body.splitlines():
        if line.startswith("#"):
            if heading is not None and "".join(lines).strip():
                sections.append((heading, "\n".join(lines).strip()))
            heading, lines = line.lstrip("#").strip(), []
        elif heading is not None:  # le bandeau "document fictif" avant le H1 est ignoré
            lines.append(line)
    if heading is not None and "".join(lines).strip():
        sections.append((heading, "\n".join(lines).strip()))
    return sections


def split_units(text: str) -> list[str]:
    """Découpe un texte en petites unités : lignes, puis phrases."""
    units = []
    for line in text.splitlines():
        units.extend(s for s in re.split(r"(?<=[.!?»])\s+", line.strip()) if s)
    return units


# --------------------------------------------------------------------------- Découpage


def chunk_section(
    prefix: str,
    text: str,
    count: TokenCounter,
    max_tokens: int = MAX_TOKENS,
    overlap: int = OVERLAP_TOKENS,
) -> list[str]:
    """Regroupe les phrases d'une section en chunks de `max_tokens` au plus, avec chevauchement.

    `count` est injecté pour pouvoir tester sans charger le modèle.
    """
    budget = max_tokens - count(prefix) - 1
    units = []
    for unit in split_units(text):
        if count(unit) <= budget:
            units.append(unit)
        else:  # phrase trop longue : on la coupe par mots
            words, piece = unit.split(), []
            for word in words:
                if piece and count(" ".join(piece + [word])) > budget:
                    units.append(" ".join(piece))
                    piece = []
                piece.append(word)
            units.append(" ".join(piece))

    chunks: list[str] = []
    current: list[str] = []
    for unit in units:
        if current and count(" ".join(current + [unit])) > budget:
            chunks.append(" ".join(current))
            # Chevauchement : on garde les dernières phrases tant qu'elles tiennent dans `overlap`
            kept: list[str] = []
            for previous in reversed(current):
                if count(" ".join([previous] + kept)) > overlap:
                    break
                kept.insert(0, previous)
            current = kept
        current.append(unit)
    if current:
        chunks.append(" ".join(current))
    return [f"{prefix}\n{c}" for c in chunks]


def chunk_document(path: Path, count: TokenCounter = count_tokens) -> list[Chunk]:
    """Transforme un fichier markdown en liste de chunks avec métadonnées."""
    meta, body = read_markdown(path)
    title = meta.get("titre", path.stem)
    doc_type = meta.get("type", "inconnu")
    chunks = []
    for section, text in split_sections(body):
        prefix = title if section == title else f"{title} > {section}"
        for text_chunk in chunk_section(prefix, text, count):
            chunks.append(
                Chunk(
                    id=f"{path.name}::{len(chunks)}",
                    text=text_chunk,
                    source=path.name,
                    doc_type=doc_type,
                    section=section,
                )
            )
    return chunks


# --------------------------------------------------------------------------- Stockage


def get_collection(chroma_dir: Path | None = None, reset: bool = False):
    """Ouvre (ou recrée) la collection ChromaDB. Les embeddings sont calculés par nous."""
    client = chromadb.PersistentClient(path=str(chroma_dir or config.CHROMA_DIR))
    if reset and COLLECTION in [c.name for c in client.list_collections()]:
        client.delete_collection(COLLECTION)
    return client.get_or_create_collection(
        COLLECTION, embedding_function=None, metadata={"hnsw:space": "cosine"}
    )


def ingest(brand_dir: Path | None = None, chroma_dir: Path | None = None) -> list[Chunk]:
    """Réindexe tous les documents de marque. Idempotent : la collection est recréée."""
    brand_dir = brand_dir or config.BRAND_DIR
    chunks = [c for path in sorted(brand_dir.glob("*.md")) for c in chunk_document(path)]
    if not chunks:
        raise FileNotFoundError(f"Aucun document markdown dans {brand_dir}")
    collection = get_collection(chroma_dir, reset=True)
    collection.add(
        ids=[c.id for c in chunks],
        documents=[c.text for c in chunks],
        embeddings=embed([c.text for c in chunks]),
        metadatas=[{"source": c.source, "doc_type": c.doc_type, "section": c.section} for c in chunks],
    )
    return chunks
