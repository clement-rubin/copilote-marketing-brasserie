"""Social listening : tendances et mentions des concurrents dans les articles de veille.

Calculé sur le texte SOURCE (titre + extrait RSS), jamais sur le résumé produit par le LLM :
une tendance doit refléter ce que dit le marché, pas ce que le modèle a reformulé.
Volontairement simple et sans LLM (donc gratuit et reproductible) :
- termes et expressions les plus fréquents dans les titres et extraits ;
- nombre d'articles qui mentionnent chaque mot-clé suivi et chaque concurrent.
"""

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

from src.models import Article

STOPWORDS = set(
    """
    alors aussi autour avec avoir avant cette ces chaque comme dans depuis des donc elle elles
    encore entre être fait font leur leurs lors mais même moins nous ont par pas peu plus pour
    pourquoi quand que quel quelle qui sans selon son sont sous sur tous tout toute très une
    vers vous votre article fictif résumé extrait flux titre intitule intitulé sujet utile
    the and for with from that this into their about have more your will been were what
    les des une aux est son ses par pas qui que sur ont nos vos ils elle leur via
    are its has was not but you all can new
    """.split()
)


@dataclass
class Mention:
    term: str
    kind: str  # "mot-clé" ou "concurrent"
    articles: list[str] = field(default_factory=list)  # titres des articles qui le citent


@dataclass
class TrendReport:
    n_articles: int
    top_terms: list[tuple[str, int]]
    top_phrases: list[tuple[str, int]]
    mentions: list[Mention]


def _fold(text: str) -> str:
    """Minuscules sans accents : « Bière » et « biere » comptent pour le même terme."""
    normalized = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in normalized if not unicodedata.combining(c))


def _words(text: str) -> list[str]:
    words = re.findall(r"[a-zà-ÿœ]+", text.lower())
    return [w for w in words if len(w) >= 3 and w not in STOPWORDS]  # 3 lettres : « bio », « chr »


def source_text(article: Article) -> str:
    """Titre + extrait RSS ; le résumé ne sert que pour les articles collectés avant l'ajout de l'extrait."""
    return f"{article.titre} {article.extrait or article.resume}"


def analyze(articles: list[Article], watchlist: dict[str, list[str]], top: int = 10) -> TrendReport:
    """Calcule les termes fréquents et les mentions des termes suivis."""
    terms: Counter[str] = Counter()
    phrases: Counter[str] = Counter()
    for article in articles:
        words = _words(source_text(article))
        terms.update(set(words))  # on compte les articles, pas les répétitions
        phrases.update({f"{a} {b}" for a, b in zip(words, words[1:])})

    # Mot-clé : tous ses mots présents dans l'article. Concurrent : nom exact.
    def matches(term: str, kind: str, text: str) -> bool:
        if kind == "competitors":
            return _fold(term) in text
        return all(word in text for word in _fold(term).split())

    mentions = []
    for kind, label in (("keywords", "mot-clé"), ("competitors", "concurrent")):
        for term in watchlist.get(kind, []):
            hits = [a.titre for a in articles if matches(term, kind, _fold(source_text(a)))]
            mentions.append(Mention(term, label, hits))

    return TrendReport(
        n_articles=len(articles),
        top_terms=terms.most_common(top),
        top_phrases=[(p, n) for p, n in phrases.most_common(top) if n > 1],
        mentions=mentions,
    )
