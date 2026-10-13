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
    "instagram_craft": "Petite pause dégustation à la grange 🍻 Aujourd'hui, on te parle d'une de nos bières.",
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

INSTAGRAM_TARGET = 60  # longueur des faits pour une légende de 150 à 500 caractères
LINKEDIN_TARGET = 700  # on ajoute des faits jusqu'à environ cette longueur (charte : 600 à 1 300)

INSTAGRAM_TAGS = ["#BrasserieDemoDuHainaut", "#BiereBio", "#BiereArtisanale", "#CraftBeer", "#Hainaut"]


def _field(pattern: str, text: str) -> str:
    match = re.search(pattern, text, flags=re.MULTILINE)
    return match.group(1).strip() if match else ""


def _passages(user: str) -> list[tuple[str, str]]:
    """Extrait les couples (source, texte) des blocs [source: ...] du prompt."""
    end = r"(?=\n\n\[source: |\n\n## |\n\nConsignes|\Z)"  # fin d'un bloc
    blocks = re.findall(r"\[source: ([^\]]+)\]\n(.*?)" + end, user, re.DOTALL)
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
    target = INSTAGRAM_TARGET if is_instagram else LINKEDIN_TARGET - 300
    # Instagram : 1er passage limité à une seule fiche (une légende parle d'une seule bière),
    # 2e passage sans contrainte si la légende reste trop courte.
    for single_source in ([True, False] if is_instagram else [False]):
        for *_, sentence, source in candidates:
            if len(" ".join(facts)) > target:
                break
            if sentence in facts or (single_source and sources and source != sources[0]):
                continue
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


def answer_question(user: str) -> str:
    """Réponse démo : phrases qui contiennent les mots rares de la question, dans le bon passage.

    - « sujet » = mots en majuscule de la question (Saison, Blonde…) : ils choisissent le passage ;
    - les autres mots (degré, prix, fût…) doivent apparaître dans la phrase retenue ;
    - chaque mot pèse 1 / (nombre de phrases qui le contiennent) : les mots rares départagent.
    """
    question = _field(r"^Question de l'équipe marketing : (.*)$", user)
    generic = {"démo", "bière", "bières", "brasserie", "quel", "quelle", "quels", "avec", "quoi", "notre", "nos"}
    raw_words = re.findall(r"\w+", question)
    subject = {w.lower() for w in raw_words[1:] if w[0].isupper()} - generic
    asked = {w.lower() for w in raw_words if len(w) > 3} - generic - subject

    def words(text: str) -> set[str]:
        return set(re.findall(r"\w+", text.lower()))

    sentences = []  # (phrase, source, mots de la phrase, mots du passage)
    for source, text in _passages(user):
        body = text.split("\n", 1)[-1].replace("**", "")
        for sentence in re.split(r"(?<=[.!?])\s+", body):
            sentence = sentence.lstrip("- ").strip()
            sentences.append((sentence, source, words(sentence), words(text)))
    frequency = {w: sum(w in s[2] for s in sentences) or 1 for w in asked | subject}

    scored = []
    for sentence, source, in_sentence, in_passage in sentences:
        hits = asked & in_sentence
        if not hits:
            continue  # la phrase doit répondre à la question, pas seulement citer le sujet
        score = sum(1 / frequency[w] for w in hits) + sum(1 / frequency[w] for w in subject & in_passage)
        scored.append((score, sentence, source))
    best = sorted(scored, key=lambda s: -s[0])[:2]
    if not best:
        answer = {
            "reponse": "Je ne trouve pas cette information dans la documentation.",
            "sources_utilisees": [],
            "avertissements": ["Aucun passage pertinent dans la documentation"],
        }
    else:
        answer = {
            "reponse": " ".join(sentence for _, sentence, _ in best),
            "sources_utilisees": list(dict.fromkeys(source for *_, source in best)),
            "avertissements": [DEMO_WARNING],
        }
    return json.dumps(answer, ensure_ascii=False)


def demo_responder(system: str, user: str) -> str:
    """Point d'entrée branché sur FakeLLMClient : choisit la réponse selon la tâche du prompt."""
    task = _field(r"^# Tâche : (\w+)", user)
    if task == "resume_article":
        return summarize_article(user)
    if task == "generation_post":
        return generate_post(user)
    if task == "question":
        return answer_question(user)
    raise ValueError(f"Tâche inconnue pour le mode démo : {task!r}")
