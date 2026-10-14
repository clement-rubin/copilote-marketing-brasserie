"""Génération des posts : article de veille + passages RAG -> LLM -> pydantic -> garde-fou."""

from pathlib import Path

from src import guard, prompts
from src.images import image_prompt
from src.llm import LLMClient, complete_json
from src.models import Article, Persona, Platform, Post, PostDraft
from src.rag import format_context, retrieve_many, sources_of
from src.store import save_post

# Requêtes RAG par persona, complétées par le titre de l'article de veille.
PERSONA_QUERIES: dict[Persona, list[str]] = {
    Persona.EXPERTISE_BIO: [
        "certification bio label européen",
        "ingrédients issus de l'agriculture biologique",
        "origine locale de l'orge",
    ],
    Persona.COULISSES: [
        "journée de brassage étapes",
        "histoire de la brasserie dans la grange",
        "refermentation en bouteille",
    ],
    Persona.DISTRIBUTEUR: [
        "partenaires cavistes et cafés mis en avant",
        "conditions pour devenir revendeur",
        "relation avec les cavistes",
    ],
    Persona.INSTAGRAM: [
        "dégustation du jeudi soir à la grange",
        "profil de dégustation et accords mets",
        "bière de saison désaltérante",
    ],
}

# Types de documents qui contiennent des FAITS. La charte éditoriale est exclue :
# ses exemples de « mauvais posts » ne doivent pas servir de source.
FACT_DOC_TYPES = ["histoire", "fiche_biere", "labels_bio", "interview", "faq_distributeurs"]

MAX_PASSAGES = 8
INSTAGRAM_DEFAULT_TAGS = ["#BrasserieDemoDuHainaut", "#BiereBio", "#BiereArtisanale", "#CraftBeer", "#Hainaut"]


def fix_instagram_hashtags(draft: PostDraft) -> PostDraft:
    """Ramène les hashtags Instagram à exactement 5 (complète ou coupe) et le signale."""
    tags = list(dict.fromkeys(draft.hashtags))
    if len(tags) != 5:
        draft.avertissements.append(f"Hashtags corrigés automatiquement ({len(tags)} reçus, 5 attendus)")
        for tag in INSTAGRAM_DEFAULT_TAGS:
            if len(tags) >= 5:
                break
            if tag not in tags:
                tags.append(tag)
        draft.hashtags = tags[:5]
    return draft


def generate_post(
    llm: LLMClient, article: Article, persona: Persona, chroma_dir: Path | None = None
) -> Post:
    """Génère un post au statut brouillon, vérifié par le garde-fou, avec son prompt d'image."""
    passages = retrieve_many(
        PERSONA_QUERIES[persona] + [article.titre], k=4, doc_types=FACT_DOC_TYPES, chroma_dir=chroma_dir
    )[:MAX_PASSAGES]
    context = format_context(passages)

    user = prompts.render(
        "generation",
        persona_id=persona.value,
        persona=prompts.load(f"persona_{persona.value}"),
        article_titre=article.titre,
        article_resume=article.resume,
        article_pertinence=article.pertinence,
        contexte=context,
    )
    draft = complete_json(llm, prompts.load("system"), user, PostDraft)

    # Le modèle ne peut citer que des sources qu'on lui a réellement fournies.
    allowed = sources_of(passages)
    invented = [s for s in draft.sources_utilisees if s not in allowed]
    draft.sources_utilisees = [s for s in draft.sources_utilisees if s in allowed]
    draft.avertissements += [f"Source citée mais non fournie : {s}" for s in invented]

    if persona.platform is Platform.INSTAGRAM:
        draft = fix_instagram_hashtags(draft)

    post = Post.from_draft(draft, persona, article_url=article.url)
    post.genere_par = f"{llm.name}:{getattr(llm, 'model', '')}".rstrip(":")
    post.contexte = f"{context}\n\n[article] {article.titre}\n{article.resume}"
    post = guard.check(post, post.contexte)
    post.prompt_image = image_prompt(post)
    save_post(post)
    return post


def generate_batch(
    llm: LLMClient,
    articles: list[Article],
    personas: list[Persona],
    chroma_dir: Path | None = None,
) -> list[Post]:
    """Un post par couple (article, persona)."""
    return [generate_post(llm, a, p, chroma_dir) for a in articles for p in personas]
