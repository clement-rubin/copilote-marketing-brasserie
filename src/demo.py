"""Réponses du mode démo (LLM_PROVIDER=fake) : faire tourner toute la chaîne sans clé API.

Ce n'est PAS un LLM : on assemble des phrases tirées des passages RAG reçus dans le prompt.
Avantage : le mode démo respecte la règle « aucun fait sans source » par construction, et les
sorties passent par exactement le même code (parsing JSON, pydantic, garde-fou) qu'un vrai LLM.
"""

import json
import re

DEMO_WARNING = "Texte produit en mode démo (FakeLLMClient), sans LLM réel."

# Documents à privilégier par persona (mots-clés présents dans les noms de fichiers).
PREFERRED_SOURCES = {
    "expertise_bio": ["labels_bio", "histoire", "fiche"],
    "coulisses_brassage": ["interview", "histoire"],
    "mise_en_avant_distributeur": ["faq_distributeurs", "histoire"],
    "instagram_craft": ["fiche", "histoire"],
}

HOOKS = {
    "expertise_bio": "Le logo bio, tout le monde le connaît. Ce qu'il garantit, beaucoup moins.",
    "coulisses_brassage": "Brasser, ce n'est pas que verser du malt dans une cuve.",
    "mise_en_avant_distributeur": "Une bière ne se vend pas toute seule. Merci à ceux qui la racontent.",
    "instagram_craft": "Petite pause dégustation 🍻",
}

CALLS_TO_ACTION = {
    "expertise_bio": "Vous êtes caviste ou restaurateur ? Quelle question vos clients vous posent-ils le plus sur le bio ?",
    "coulisses_brassage": "Et chez vous, quelle est la tâche invisible qui prend la moitié de la journée ?",
    "mise_en_avant_distributeur": "Passez lui dire bonjour de notre part, et dites-nous ce que vous avez goûté.",
    "instagram_craft": "À consommer avec modération.",
}

# Mots-clés qui font remonter les phrases les plus utiles pour chaque persona.
KEYWORDS = {
    "expertise_bio": ["bio", "certifi", "orge"],
    "coulisses_brassage": ["brassage", "concassage", "empâtage", "nettoyage", "capsules"],
    "mise_en_avant_distributeur": ["partenaire", "caviste", "estaminet"],
    "instagram_craft": ["bouche :", "nez :"],
}

INSTAGRAM_TARGET = 90  # longueur des faits pour une légende de 150 à 500 caractères
LINKEDIN_TARGET = 700  # on ajoute des faits jusqu'à environ cette longueur (charte : 600 à 1 300)

INSTAGRAM_TAGS = ["#BrasserieDemoDuHainaut", "#BiereBio", "#BiereArtisanale", "#CraftBeer", "#Hainaut"]


def _field(pattern: str, text: str) -> str:
    match = re.search(pattern, text, flags=re.MULTILINE)
    return match.group(1).strip() if match else ""


def _passages(user: str) -> list[tuple[str, str]]:
    """Extrait les couples (source, texte) des blocs [source: ...] du prompt."""
    blocks = re.findall(r"\[source: ([^\]]+)\]\n(.*?)(?=\n\n\[source: |\n\n## |\Z)", user, re.DOTALL)
    return [(source, text) for source, text in blocks]


def _sentences(passage: str) -> list[str]:
    """Phrases exploitables d'un passage (on saute la ligne de titre « Doc > Section »)."""
    body = passage.split("\n", 1)[1] if "\n" in passage else passage
    body = body.replace("**", "")
    candidates = re.split(r"(?<=[.!?])\s+", body)
    return [s.lstrip("- ").strip() for s in candidates if 40 <= len(s) <= 220 and s.endswith(".")]


def summarize_article(user: str) -> str:
    """Résumé démo : reprend l'extrait RSS, sans rien ajouter."""
    title = _field(r"^Titre : (.*)$", user)
    extract = user.split('"""')[1].replace("Article fictif.", "").strip() if '"""' in user else ""
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", extract) if s][:2]
    while len(sentences) < 2:
        sentences.append("L'extrait du flux ne donne pas plus de détails.")
    resume = f"L'article s'intitule « {title} ». " + " ".join(sentences)
    pertinence = (
        "Sujet utile pour parler aux cavistes et aux CHR de l'origine et de la certification "
        "de nos bières, sans inventer de chiffres."
    )
    return json.dumps({"resume": resume, "pertinence": pertinence}, ensure_ascii=False)


def generate_post(user: str) -> str:
    """Post démo : accroche + lien avec l'article + faits tirés des passages + appel à l'action."""
    persona = _field(r"^Persona : (\w+)", user)
    title = _field(r"^Titre : (.*)$", user)
    preferred = PREFERRED_SOURCES.get(persona, [])
    keywords = KEYWORDS.get(persona, [])

    # Toutes les phrases candidates, classées : mot-clé de la persona d'abord, puis source préférée.
    candidates = []
    for order, (source, text) in enumerate(_passages(user)):
        source_rank = next((i for i, k in enumerate(preferred) if k in source), 99)
        for sentence in _sentences(text):
            has_keyword = any(k in sentence.lower() for k in keywords)
            candidates.append((not has_keyword, source_rank, order, sentence, source))
    candidates.sort(key=lambda c: c[:3])

    is_instagram = persona == "instagram_craft"
    facts: list[str] = []
    sources: list[str] = []
    for *_, sentence, source in candidates:
        if sentence in facts:
            continue
        if is_instagram and len(" ".join(facts)) > INSTAGRAM_TARGET:
            break
        if not is_instagram and len(" ".join(facts)) > LINKEDIN_TARGET - 300:
            break
        facts.append(sentence)
        if source not in sources:
            sources.append(source)

    if is_instagram:
        text = " ".join([HOOKS[persona], *facts, CALLS_TO_ACTION[persona]])
        hashtags = INSTAGRAM_TAGS
    else:
        bridge = f"Dans l'actualité cette semaine : « {title} ». Ça nous parle."
        text = "\n\n".join([HOOKS[persona], bridge, " ".join(facts), CALLS_TO_ACTION[persona]])[:1300]
        hashtags = ["#BiereBio", "#BiereArtisanale", "#CavisteIndependant"]

    warnings = [DEMO_WARNING]
    if persona == "mise_en_avant_distributeur":
        warnings.append("Vérifier l'accord écrit du partenaire avant publication")
    return json.dumps(
        {
            "texte": text,
            "hashtags": hashtags,
            "sources_utilisees": sources,
            "score_confiance": 0.6,
            "avertissements": warnings,
        },
        ensure_ascii=False,
    )


def demo_responder(system: str, user: str) -> str:
    """Point d'entrée branché sur FakeLLMClient : choisit la réponse selon la tâche du prompt."""
    task = _field(r"^# Tâche : (\w+)", user)
    if task == "resume_article":
        return summarize_article(user)
    if task == "generation_post":
        return generate_post(user)
    raise ValueError(f"Tâche inconnue pour le mode démo : {task!r}")
