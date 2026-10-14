# Audit de conformité (14 octobre 2026)

Référentiel : l'offre de stage « Ingénieur(e) IA Générative & Automatisation Social Media » (missions, profil, cahier des charges) et le brief technique initial du projet.
Méthode : chaque exigence est confrontée à une **preuve vérifiée** (commande exécutée, test automatisé ou fichier), jamais à une simple déclaration du README.

Légende : ✅ conforme · ⚠️ conforme avec réserve (expliquée) · ❌ non fait

## 1. Missions de l'offre

| Exigence | Statut | Preuve | Réserve |
|---|---|---|---|
| **Veille & social listening** : tendances du marché brassicole | ✅ | `trends` ; veille réelle exécutée : 9 flux, 42 articles, tous thèmes couverts (craft beer, brasserie, bio, CHR, concurrent) ; `tests/test_trends.py` | Tendances calculées sur le texte source RSS, pas sur le texte généré |
| … mots-clés des concurrents | ✅ | `listening.competitors` dans `data/feeds.yaml` → recherches Google News RSS ; mentions comptées | Liste de concurrents fictive, à remplir avec la direction |
| … actualités filière CHR / bio | ✅ | flux `horeca bière`, `brasserie bio`, mot-clé `bière bio CHR` | — |
| … « scripts (Scraping/API) » | ⚠️ | RSS + Google News RSS uniquement (`src/watch.py`) | Pas de scraping de pages : choix assumé (CGU, droit d'auteur, RGPD, robustesse). Le scraping de LinkedIn/Instagram est interdit par leurs CGU |
| **RAG** : base propriétaire (histoire, fiches techniques, charte) | ✅ | 8 documents dans `data/brand/`, 51 chunks ≤ 120 tokens (`test_real_chunks_fit_in_embedding_window`) | Documents fictifs : à remplacer par la vraie documentation |
| … interrogeable par un LLM, réponses uniquement fondées sur les documents | ✅ | `ask` : « degré de la Saison » → 5,8 % (source citée) ; « prix de la Blonde » → « je ne trouve pas » ; `tests/test_qa.py` | — |
| … LangChain + ChromaDB/Pinecone (cité « ex: ») | ⚠️ | ChromaDB ✅ ; appels directs plutôt que LangChain | Choix justifié dans le README (moins de couches, chaque ligne s'explique) |
| **Prompt engineering** LinkedIn B2B (distributeurs) | ✅ | `prompts/persona_*.md`, personas exactes de l'offre : Expertise Bio, Coulisses du Brassage, Mise en avant d'un distributeur | Qualité rédactionnelle non démontrée sans clé LLM (voir §4) |
| … légendes Instagram B2C (amateurs) | ✅ | `prompts/persona_instagram_craft.md` ; 5 hashtags imposés par pydantic ; 150 à 500 caractères contrôlés | Idem |
| **Multimodal** : DALL-E 3 | ⚠️ | `src/visuals.py` : `OpenAIImageGenerator` (dall-e-3 / gpt-image) ; maquette SVG hors ligne testée | Jamais appelé en réel (pas de clé OpenAI) |
| … Midjourney | ⚠️ | Prompt « Midjourney : … --ar … --no text » généré pour chaque post | Midjourney n'a pas d'API publique officielle : usage manuel du prompt |
| **Orchestration** : flux de publication automatisé | ✅ | `weekly` (3 brouillons) → revue → `schedule` → `publish-due` (cron / planificateur), testé de bout en bout en simulation (`tests/test_web.py`, `tests/test_cli.py`) | — |
| … via API natives (LinkedIn, Instagram/Facebook) | ⚠️ | `src/social.py` : Posts API LinkedIn, Instagram (conteneur + `media_publish`), page Facebook ; requêtes vérifiées par faux transport HTTP | Jamais appelées en réel : nécessite des applications validées par LinkedIn et Meta |

## 2. Profil et cahier des charges

| Exigence | Statut | Preuve | Réserve |
|---|---|---|---|
| API OpenAI, Anthropic | ⚠️ | `src/llm.py` : `OpenAIClient`, `AnthropicClient` (+ Gemini), modèle lu dans `.env` | Code conforme aux SDK, jamais appelé en réel (pas de clé) |
| Approche « Growth Marketing » | ⚠️ | Rotation des personas, calendrier, tendances | Pas de mesure de l'engagement : listé en piste n° 1 du README |
| Objectif MVP : sourcer l'actualité | ✅ | `watch` / `weekly` | — |
| … 3 posts hebdomadaires B2B + B2C | ✅ | `weekly` : 2 LinkedIn (personas en rotation) + 1 Instagram, sur des articles non encore utilisés (`test_weekly_creates_three_drafts_then_skips_used_articles`) | — |
| … programmer leur publication | ✅ | calendrier mardi / jeudi 9 h (LinkedIn), samedi 11 h (Instagram) ; `test_plan_two_linkedin_one_instagram_per_week` | — |
| … respecter parfaitement le ton de la marque | ⚠️ | charte dans le prompt système, mots interdits contrôlés par `src/guard.py`, éval 10/10 sur la forme | Marque fictive ; respect fin du ton non mesurable sans LLM réel ni relecture par l'équipe |
| Mois 1, S1-2 : Brand Book vectorisé, RAG | ✅ | `ingest`, `ask` | — |
| Mois 1, S3-4 : scripts RSS + Google News « bière bio CHR », résumés | ✅ | `watch`, mot-clé présent dans `feeds.yaml` | — |
| Mois 2 : personas LinkedIn, multimodalité | ✅ / ⚠️ | voir §1 | Images : pas d'appel réel |
| Mois 3 | — | Absent du texte de l'offre (la section Mois 2 y est répétée) ; couvert par l'orchestration | — |

## 3. Brief technique initial

| Exigence | Statut | Preuve |
|---|---|---|
| 6 à 8 documents fictifs (histoire, charte avec bons/mauvais posts, 3 fiches bières, labels bio, interview) | ✅ | `data/brand/` (8 documents, chacun marqué « fictif ») |
| Stack : Python 3.11+, ChromaDB, MiniLM multilingue, feedparser, SDK Anthropic, pydantic, typer, pytest | ✅ | `requirements.txt` |
| `LLMClient` + Anthropic (modèle en variable d'environnement) + stubs | ✅ | dépassé : OpenAI et Gemini réellement implémentés ; aucun nom de modèle dans `src/` (vérifié) |
| Chunks ~500 tokens | ✅ | 120 tokens, décision validée (le modèle tronque à 128) |
| Veille : résumé 3 phrases + pertinence, JSON, dédup URL | ✅ | second passage de veille réelle : 0 doublon |
| Sortie pydantic : texte, persona, sources, score, avertissements | ✅ | `src/models.py` |
| Anti-hallucination (chiffres, labels) | ✅ | `src/guard.py`, `tests/test_guard.py`, contrôle des détecteurs dans l'éval | 
| Validation humaine, seuls les approuvés programmables | ✅ | `test_draft_cannot_be_scheduled_directly`, `test_forbidden_transition_returns_400` |
| Calendrier 2 LinkedIn + 1 Instagram, MockPublisher, doc des vraies API | ✅ | `src/publish.py`, README |
| Prompts d'images (style, palette, composition, interdits) | ✅ | `src/images.py` |
| Mini-évaluation 10 cas + tableau | ✅ | `python -m tests.eval` : 10/10 |
| README français (objectif, schéma, installation en 5 commandes, sortie réelle, choix, limites, pistes) | ⚠️ | complet ; la « sortie réelle » vient du mode démo (signalé) |
| `out/examples/` (2 LinkedIn + 1 Instagram) | ✅ | 3 posts + 1 programmation |
| Aucun secret dans le code, `.env.example` fourni | ✅ | scan des fichiers suivis : aucune clé ; `.env` ignoré par Git |
| Aucun fait inventé sur une marque réelle | ✅ | aucune occurrence de la marque réelle ni de ses coordonnées dans le dépôt |
| Code lisible, type hints, docstrings | ✅ | vérification AST : routes et fonctions publiques documentées après correction |
| Fonctionne de bout en bout avec `python -m src.cli …` | ✅ | **clone neuf** du dépôt installé en suivant le README (venv Python 3.11, `pip install -r requirements.txt`, `.env` copié) : 77 tests verts, `ingest` puis `weekly --offline` produisent 3 brouillons |
| Tests qui passent | ✅ | 77 tests (dépôt et clone neuf), éval 10/10 |
| Publié sur GitHub | ❌ | action publique : à faire par le candidat |

## 4. Corrections apportées pendant l'audit

1. **Tendances faussées** : elles étaient calculées sur le résumé généré ; en mode démo, la phrase « l'extrait ne donne pas plus de détails » faisait remonter « détails » et « donne » en tête. Elles utilisent désormais le texte source RSS (nouveau champ `extrait`) et un test le garantit.
2. **Reproductibilité** : les dépendances n'avaient qu'une borne basse ; elles sont maintenant bornées à la version majeure testée, versions exactes en commentaire.
3. **Documentation du code** : docstrings ajoutées aux 19 routes de l'API (visibles sur `/docs`) et annotations de type complétées.

## 5. Risques restants et actions recommandées (par priorité)

1. **Aucune sortie d'un vrai LLM n'est montrée** (pas de clé). C'est le point le plus visible pour un recruteur. Action : clé Gemini gratuite (5 minutes), `LLM_PROVIDER=gemini`, régénérer `out/examples/` et relancer `python -m tests.eval`.
2. **Dépôt non publié.** Action : créer le dépôt GitHub et pousser.
3. **API sociales et images non testées en réel** : à présenter comme « prêtes à brancher », pas comme « en production ».
4. **Garde-fou** : il vérifie la présence d'un chiffre ou d'un label, pas le sens de la phrase (exemple documenté avec Biogarantie). La relecture humaine reste indispensable.
