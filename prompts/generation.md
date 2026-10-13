<!--
Génération d'un post, commune à toutes les personas.
v1 (2026-10-13).
Assemblage : ce gabarit + les consignes de la persona (prompts/persona_*.md) + le contexte RAG.
Sortie : PostDraft (src/models.py), validé par pydantic puis contrôlé par src/guard.py.
Le score de confiance est une auto-évaluation du modèle : le code le baisse ensuite si le
garde-fou trouve des chiffres ou labels non sourcés.
-->
# Tâche : generation_post
Persona : {{persona_id}}

## Consignes de la persona
{{persona}}

## Article de veille (point de départ, pas une source de faits sur la marque)
Titre : {{article_titre}}
Résumé : {{article_resume}}
Pertinence : {{article_pertinence}}

## Passages de la marque (SEULE source de faits sur la marque)
{{contexte}}

## Format de sortie
Un objet JSON avec exactement ces clés :
{
  "texte": "le post complet, sans les hashtags",
  "hashtags": ["#Exemple", "..."],
  "sources_utilisees": ["nom_du_fichier.md", "..."],
  "score_confiance": 0.0,
  "avertissements": ["information manquante ou à vérifier", "..."]
}
- "sources_utilisees" : uniquement des noms de fichiers présents dans les balises [source: ...] ci-dessus, ceux dont tu as réellement utilisé un fait.
- "score_confiance" : entre 0 et 1. Baisse-le si le contexte est pauvre ou si le lien avec l'article est faible.
- "avertissements" : liste vide si tout est sourcé.
