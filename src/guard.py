"""Garde-fou déterministe appliqué APRÈS la génération.

Le prompt demande au LLM de ne rien inventer, mais on ne lui fait pas confiance :
on vérifie que chaque chiffre et chaque label du post apparaît dans le contexte fourni.
On vérifie aussi la forme (longueur, hashtags, émojis) et les mots interdits par la charte.
Le garde-fou ne bloque pas : il ajoute des avertissements et baisse le score de confiance,
et c'est l'humain qui tranche dans `review`.
"""

import re

from src.models import Platform, Post

# Chiffres : "6,5", "1 200", "2017", "70". Les espaces fines et insécables sont acceptés.
NUMBER = re.compile(r"\d+(?:[   ]\d{3})*(?:[.,]\d+)?")
HASHTAG = re.compile(r"#\w+")
EMOJI = re.compile(
    "[\U0001f300-\U0001faff\U00002600-\U000027bf\U0001f1e6-\U0001f1ff]", flags=re.UNICODE
)

# Labels qu'on ne doit jamais citer sans source.
KNOWN_LABELS = [
    "Eurofeuille",
    "Biogarantie",
    "Demeter",
    "Nature & Progrès",
    "Nature et Progrès",
    "Bio Cohérence",
    "Ecocert",
    "label AB",
    "Agriculture Biologique",
]

# Mots ou formules interdits par la charte éditoriale (data/brand/02_charte_editoriale.md).
FORBIDDEN = [
    "meilleure bière",
    "meilleur",
    "exceptionnel",
    "unique au monde",
    "révolutionnaire",
    "incroyable",
    "premium",
    "disruptif",
    "100 % naturel",
    "100% naturel",
    "zéro pesticide",
    "bon pour la santé",
    "bonne pour la santé",
]

# Règles de forme par plateforme : (longueur min, longueur max, émojis max, hashtags min, max)
FORMAT_RULES = {
    Platform.LINKEDIN: (600, 1300, 2, 1, 3),
    Platform.INSTAGRAM: (150, 500, 3, 5, 5),
}

PENALTY = 0.2  # baisse du score de confiance par problème de fond


def _normalize_number(raw: str) -> str:
    """'1 200' -> '1200', '6.5' -> '6,5' : même écriture pour comparer texte et contexte."""
    return re.sub(r"[   ]", "", raw).replace(".", ",")


def numbers_in(text: str) -> set[str]:
    """Ensemble des nombres d'un texte, hashtags exclus (#Top10 n'est pas un fait)."""
    return {_normalize_number(n) for n in NUMBER.findall(HASHTAG.sub("", text))}


def unsourced_numbers(text: str, context: str) -> list[str]:
    """Nombres présents dans le texte mais absents du contexte."""
    return sorted(numbers_in(text) - numbers_in(context))


def unsourced_labels(text: str, context: str) -> list[str]:
    """Labels cités dans le texte mais absents du contexte (comparaison insensible à la casse)."""
    lower_text, lower_context = text.lower(), context.lower()
    return [l for l in KNOWN_LABELS if l.lower() in lower_text and l.lower() not in lower_context]


def forbidden_words(text: str) -> list[str]:
    """Formules interdites par la charte présentes dans le texte."""
    lower = text.lower()
    return [w for w in FORBIDDEN if w in lower]


def format_problems(post: Post) -> list[str]:
    """Problèmes de forme : longueur, nombre d'émojis, nombre de hashtags."""
    min_len, max_len, max_emojis, min_tags, max_tags = FORMAT_RULES[post.plateforme]
    problems = []
    length = len(post.texte)
    if not min_len <= length <= max_len:
        problems.append(f"Longueur {length} caractères hors de [{min_len}, {max_len}]")
    emojis = len(EMOJI.findall(post.texte))
    if emojis > max_emojis:
        problems.append(f"{emojis} émojis (maximum {max_emojis})")
    if not min_tags <= len(post.hashtags) <= max_tags:
        problems.append(f"{len(post.hashtags)} hashtags (attendu entre {min_tags} et {max_tags})")
    return problems


def check(post: Post, context: str) -> Post:
    """Applique toutes les vérifications, enrichit les avertissements et ajuste le score.

    `context` = passages RAG + article de veille : tout ce que le modèle avait le droit d'utiliser.
    Idempotent : on peut le relancer après une édition humaine sans cumuler les pénalités.
    """
    previous = [w for w in post.avertissements if not w.startswith("[garde-fou]")]
    base_score = post.score_llm if post.score_llm is not None else post.score_confiance
    warnings: list[str] = []
    for number in unsourced_numbers(post.texte, context):
        warnings.append(f"[garde-fou] Chiffre non sourcé : {number}")
    for label in unsourced_labels(post.texte, context):
        warnings.append(f"[garde-fou] Label non sourcé : {label}")
    for word in forbidden_words(post.texte):
        warnings.append(f"[garde-fou] Formule interdite par la charte : « {word} »")
    substantive = len(warnings)  # problèmes de fond : ils baissent la confiance
    warnings += [f"[garde-fou] {p}" for p in format_problems(post)]

    post.avertissements = list(dict.fromkeys(previous + warnings))
    post.score_confiance = round(max(0.0, base_score - PENALTY * substantive), 2)
    return post
