"""Génération de PROMPTS d'images (Midjourney / DALL-E). Aucune image n'est générée ici.

Choix : un gabarit déterministe plutôt qu'un appel LLM. La direction artistique d'une marque
doit être stable d'un post à l'autre ; un gabarit garantit la même palette et les mêmes
interdits à chaque fois, sans coût ni variabilité.
"""

from src.models import Persona, Platform, Post

BRAND_STYLE = (
    "photographie documentaire, argentique 35 mm, lumière naturelle chaude de fin d'après-midi, "
    "grain léger, profondeur de champ faible"
)
PALETTE = "ambre, cuivre, vert sauge, bois brut, briques rouges du Hainaut, blanc cassé"
AVOID = (
    "texte ou logo inventé sur les étiquettes, marques réelles, personnes en état d'ivresse, "
    "personnes ayant l'air mineures, verres qui débordent, rendu plastique ou trop saturé, "
    "décor de pub industrielle, mains déformées"
)

SCENES: dict[Persona, str] = {
    Persona.EXPERTISE_BIO: (
        "gros plan sur des grains d'orge et des cônes de houblon dans des mains de brasseur, "
        "champ d'orge flou en arrière-plan"
    ),
    Persona.COULISSES: (
        "intérieur d'une grange rénovée transformée en brasserie, cuve en inox avec vapeur, "
        "brasseur en tablier de dos, outils de nettoyage visibles"
    ),
    Persona.DISTRIBUTEUR: (
        "façade et vitrine d'une petite cave à bières de quartier, étagères en bois "
        "avec des bouteilles sans étiquette lisible, caviste souriant derrière le comptoir"
    ),
    Persona.INSTAGRAM: (
        "table en bois dans une grange le soir, guirlandes lumineuses, deux verres de bière "
        "à moitié pleins, mousse fine, ambiance conviviale et calme"
    ),
}

BEERS = {
    "Blonde Démo": "un verre de bière blonde dorée légèrement voilée",
    "Ambrée Démo": "un verre de bière ambrée cuivrée à mousse beige",
    "Saison Démo": "un verre de bière saison blond paille, trouble",
}

ASPECT = {Platform.LINKEDIN: "1.91:1", Platform.INSTAGRAM: "4:5"}


def image_prompt(post: Post) -> str:
    """Construit un prompt d'image détaillé à partir de la persona et des bières citées."""
    scene = SCENES[post.persona]
    beers = [desc for name, desc in BEERS.items() if name.lower() in post.texte.lower()]
    if beers:
        scene += ", au premier plan " + " et ".join(beers)
    ratio = ASPECT[post.plateforme]
    return (
        f"Sujet : {scene}.\n"
        f"Style : {BRAND_STYLE}.\n"
        f"Palette : {PALETTE}.\n"
        "Composition : sujet principal sur un tiers, espace négatif pour le texte du post, "
        "pas de texte dans l'image.\n"
        f"Format : {ratio}.\n"
        f"À éviter : {AVOID}.\n"
        f"Midjourney : {scene}, {BRAND_STYLE}, palette {PALETTE} --ar {ratio} --style raw "
        "--no text, logo, watermark"
    )
