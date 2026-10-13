<!--
Question posée à la base de connaissances de la marque (commande `ask`).
v1 (2026-10-13).
Usage : l'équipe marketing vérifie un fait avant de l'écrire (« quel degré pour la Saison ? »).
Règle clé : répondre UNIQUEMENT avec les passages ; sinon dire qu'on ne sait pas.
Sortie : Answer (src/models.py). Les chiffres de la réponse sont ensuite contrôlés par src/guard.py.
-->
# Tâche : question

Question de l'équipe marketing : {{question}}

## Passages de la marque (SEULE source autorisée)
{{contexte}}

Consignes :
- Réponds en français, en 1 à 4 phrases, uniquement à partir des passages ci-dessus.
- Si les passages ne contiennent pas la réponse, écris exactement « Je ne trouve pas cette information dans la documentation. » et explique dans "avertissements" ce qui manque.
- "sources_utilisees" : les noms de fichiers dont tu as utilisé une information.

Format de sortie :
{"reponse": "...", "sources_utilisees": ["fichier.md"], "avertissements": []}
