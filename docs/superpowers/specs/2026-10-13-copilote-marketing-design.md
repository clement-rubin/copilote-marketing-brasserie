# Copilote Marketing : design (2026-10-13)

## Objectif

MVP de démonstration pour une candidature de stage : un copilote marketing pour une brasserie
artisanale bio **fictive** (« Brasserie Démo du Hainaut ») qui fait de la veille RSS, génère des
posts LinkedIn (B2B) et Instagram (B2C) fidèles au ton de la marque, avec un RAG comme seule
source de faits, une validation humaine et une programmation simulée.

## Contraintes et décisions déjà prises

| Sujet | Décision | Raison |
|---|---|---|
| Emplacement | `C:\dev\copilote-marketing` (hors OneDrive) | la synchro casse le venv et SQLite |
| Python | venv 3.11 | torch/chromadb instables en 3.14 |
| Chunks | 120 tokens max, chevauchement 30, mesurés avec le tokenizer du modèle | MiniLM tronque à 128 tokens |
| LLM | interface `LLMClient` ; Gemini et Anthropic réels, OpenAI en stub, `FakeLLMClient` | pas de clé Anthropic ; Gemini a un quota gratuit |
| Mode par défaut | `LLM_PROVIDER=fake` | tout tourne sans clé ni réseau (tests, démo) |
| LangChain | non | appels directs plus courts et explicables |
| Stockage | fichiers JSON dans `out/` | lisible, diffable, pas de base à installer |
| Publication | `MockPublisher` uniquement | les API LinkedIn/Meta exigent une app validée |

## Architecture (un module = une responsabilité)

```
feeds.yaml ─► watch.py ─► out/watch/articles.json
                 │ (LLM : résumé 3 phrases + pertinence, dédup par URL)
data/brand ─► ingest.py ─► chroma_db/ ─► rag.py (top-k + sources)
                                            │
articles + passages RAG ─► generate.py ─► guard (chiffres/labels sourcés) ─► images.py
                                            │
                                   out/posts/<id>.json (statut brouillon)
                                            │
                              review.py (approuver / rejeter / éditer)
                                            │
                     publish.py (calendrier 2 LinkedIn + 1 Instagram / semaine)
                                            │
                                   out/scheduled/<date>_<id>.json
```

- `config.py` : chemins et `.env`.
- `models.py` : pydantic. `PostDraft` (ce que le LLM produit) est séparé de `Post` (ce que le
  code stocke : id, statut, dates). Transitions de statut contrôlées par le code.
- `llm.py` : interface, implémentations, `complete_json` (extraction JSON + validation + 1 retry).
- `prompts/*.md` : un fichier par prompt, commenté, chargé par `prompts.py`.
- `guard.py` : garde-fou déterministe (voir plus bas).
- `demo.py` : réponses du `FakeLLMClient` en mode démo (construites à partir des passages RAG,
  pour rester cohérentes avec la règle « aucun fait sans source »).
- `cli.py` : typer. Commandes `ingest`, `watch`, `generate`, `review`, `schedule`, `list`.

## Anti-hallucination

1. Le prompt donne les passages RAG étiquetés `[source: fichier]` et impose : aucun fait de marque
   hors contexte, toute info manquante va dans `avertissements`.
2. Après génération, `guard.py` extrait du texte :
   - les nombres (degrés, %, cl, IBU, années, quantités) ;
   - les labels connus (Eurofeuille, Biogarantie, Demeter, Nature & Progrès, AB…).
   Chaque élément absent des passages RAG fournis (et de l'article de veille pour les chiffres
   de l'actualité) ajoute un avertissement et baisse le score de confiance de 0,2 (plancher 0).
3. Mots interdits de la charte (superlatifs creux, allégations santé) : avertissement aussi.

Le garde-fou n'empêche pas la sauvegarde : le post reste un brouillon et l'humain voit les
avertissements dans `review`.

## Personas

LinkedIn : `expertise_bio`, `coulisses_brassage`, `mise_en_avant_distributeur`.
Instagram : `instagram_craft` (150 à 500 caractères, 1 à 3 émojis, exactement 5 hashtags).

## Calendrier

`schedule` prend les posts approuvés, les plus anciens d'abord, et remplit des semaines de
3 créneaux : mardi 9 h LinkedIn, jeudi 9 h LinkedIn, samedi 11 h Instagram, à partir du lundi
suivant. Les créneaux déjà occupés (posts déjà programmés) sont sautés.

## Tests

- Unitaires sans réseau : modèles, LLM (fake), découpage, garde-fou, dédup RSS (flux en fixture),
  transitions, calendrier, CLI de bout en bout en mode fake.
- Intégration : RAG avec le vrai modèle d'embedding.
- `tests/eval.py` : 10 cas, tableau récapitulatif (longueur, hashtags, chiffres non sourcés).

## Hors périmètre

Génération d'images (prompts seulement), vraies API sociales, interface web, scraping HTML.
