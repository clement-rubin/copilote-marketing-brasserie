<!--
Résumé d'un article de veille.
v1 (2026-10-13).
Entrées : titre, flux, thème, extrait RSS (souvent court : on ne scrape pas la page).
Sortie : ArticleSummary (src/models.py).
Choix : on demande la pertinence pour la marque dès la veille, pour pouvoir trier les articles
avant de dépenser des appels de génération.
-->
# Tâche : resume_article

Résume cet article de veille pour l'équipe marketing de la brasserie.

Titre : {{titre}}
Flux : {{flux}} (thème : {{theme}})
Extrait du flux RSS :
"""
{{extrait}}
"""

Consignes :
- "resume" : exactement 3 phrases en français, factuelles, fondées uniquement sur le titre et l'extrait. Si l'extrait est trop court, dis-le dans le résumé au lieu de compléter.
- "pertinence" : 1 ou 2 phrases sur pourquoi cette actualité peut intéresser une brasserie artisanale bio qui vend à des cavistes, distributeurs et cafés-restaurants (CHR).

Format de sortie :
{"resume": "...", "pertinence": "..."}
