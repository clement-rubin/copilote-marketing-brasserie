/* Visite guidée de l'interface.
   Un projecteur met en lumière une zone, une bulle explique son rôle et la mission de l'offre
   qu'elle couvre. La visite change de vue toute seule. Démarre à la première visite,
   puis via le bouton « Visite guidée ». Clavier : flèches pour naviguer, Échap pour quitter.
   Les textes s'adaptent à la configuration réelle (mode démo ou vrai LLM, lue sur /api/dashboard) :
   un « title » ou un « text » peut être une fonction qui reçoit cette configuration. */

const TOUR_KEY = "copilote-visite-vue";

/** Nom lisible du moteur de texte actif, ex. « Gemini (gemini-3.1-flash-lite) ». */
function llmLabel(cfg, withModel = true) {
  const names = { gemini: "Gemini", openai: "OpenAI", anthropic: "Claude (Anthropic)" };
  const model = withModel && cfg.modeles && cfg.modeles[0] ? ` (${cfg.modeles[0]})` : "";
  return (names[cfg.llm] || cfg.llm) + model;
}

const isDemo = (cfg) => cfg.llm === "fake";

const TOUR_STEPS = [
  {
    view: "tableau", selector: null,
    title: "Bienvenue dans le Copilote Marketing",
    text: (cfg) => `En 2 minutes, voici comment l'outil transforme l'actualité du marché en 3 posts par semaine, fidèles au ton de la brasserie, validés par un humain puis publiés. ${isDemo(cfg)
      ? "Vous êtes en mode démo : tout tourne hors ligne, sans clé ni coût."
      : `Les textes sont rédigés en direct par ${llmLabel(cfg)}.`} La visite suit le plan sur 3 mois du cahier des charges.`,
  },
  {
    view: "tableau", selector: ".nav",
    title: "Les 7 étapes du flux",
    text: "Le menu suit l'ordre du travail : veille (mois 1), atelier et revue (mois 2), calendrier et publication (mois 3). La base de connaissances et le contrôle qualité servent à tout moment.",
  },
  {
    view: "tableau", selector: "#config-chips",
    title: (cfg) => (isDemo(cfg) ? "Mode démo" : "Branché sur un vrai LLM"),
    text: (cfg) => isDemo(cfg)
      ? "Ces étiquettes montrent les moteurs actifs. FAKE, PLACEHOLDER et MOCK : tout tourne hors ligne, sans clé ni coût. Dans le fichier .env, on passe à Gemini, OpenAI ou Anthropic pour le texte, à DALL-E pour les images, et aux API LinkedIn / Meta pour la publication, sans changer une ligne de code."
      : `Le texte est rédigé par ${llmLabel(cfg)}.${cfg.modeles && cfg.modeles.length > 1 ? ` Si ce modèle est saturé ou trop lent, ${cfg.modeles.slice(1).join(", ")} prend le relais automatiquement.` : ""} Chaque appel a un délai maximal de 60 s et des réessais. Les images restent en ${cfg.images === "placeholder" ? "maquette" : cfg.images} et la publication en ${cfg.publication === "mock" ? "simulation" : cfg.publication} : il suffit d'ajouter les clés OpenAI, LinkedIn et Meta dans .env pour les passer en réel.`,
  },
  {
    view: "tableau", selector: ".ledger",
    title: "Le registre",
    text: "Où en est la production : articles de veille collectés, puis chaque post selon son statut. Brouillon → approuvé → programmé → publié. Le passage de l'un à l'autre est contrôlé par le code : impossible de publier un brouillon.",
  },
  {
    view: "tableau", selector: ".hero-cta",
    title: "La semaine en un geste",
    text: (cfg) => `Le bouton qui fait tout : veille, choix de 3 articles inédits, rédaction de 2 posts LinkedIn (les personas tournent chaque semaine) et d'une légende Instagram, avec leurs visuels.${isDemo(cfg) ? "" : ` Avec ${llmLabel(cfg, false)}, comptez une à deux minutes : chaque article est résumé, puis chaque post rédigé et vérifié.`} En production, cette étape est lancée chaque lundi par un planificateur (cron).`,
  },
  {
    view: "veille", selector: ".head .actions",
    title: "Mois 1 · Veille automatisée",
    text: (cfg) => `Lecture des flux RSS de la filière et des recherches Google News (dont « bière bio CHR »). Pas de scraping de pages : uniquement des flux publiés volontairement, pour respecter les CGU et le RGPD. ${isDemo(cfg) ? "Chaque article est résumé en 3 phrases" : `${llmLabel(cfg, false)} résume chaque article en 3 phrases`}, avec son intérêt pour la brasserie, et signale quand l'extrait du flux est trop court pour en dire plus.`,
  },
  {
    view: "veille", selector: ".grid.two",
    title: "Social listening",
    text: "Les tendances sont calculées sur le texte source des articles, jamais sur un texte généré par l'IA. À droite, les mots-clés et les concurrents suivis (définis dans data/feeds.yaml) et le nombre d'articles qui les citent.",
  },
  {
    view: "atelier", selector: ".personas",
    title: "Mois 2 · Content Factory",
    text: "On choisit un article de départ, puis les personas : Expertise Bio, Coulisses du Brassage, Mise en avant d'un distributeur (LinkedIn B2B) et la légende Instagram (B2C). Chaque persona a son propre prompt, versionné dans le dossier prompts/.",
  },
  // --- Revue : une étape par section de la vue. Le filtre passe sur « Tous » pour avoir des posts.
  {
    view: "revue", selector: ".tabs", revueFilter: "tous",
    title: "Revue · les statuts",
    text: "Mois 2 · validation humaine. Les onglets trient les posts par statut, avec leur nombre : brouillon (à relire), approuvé, rejeté, programmé, publié. Le badge orange dans le menu compte les brouillons en attente.",
  },
  {
    view: "revue", selector: ".post .post-head, .tabs", revueFilter: "tous",
    title: "Revue · l'en-tête du post",
    text: "Plateforme (LinkedIn ou Instagram), persona utilisée, identifiant, et le tampon de statut en haut à droite. Un post programmé affiche aussi sa date de publication ; un post publié, les canaux sur lesquels il est parti.",
  },
  {
    view: "revue", selector: ".post .post-text, .tabs", revueFilter: "tous",
    title: "Revue · le texte et les hashtags",
    text: (cfg) => `Le texte ${isDemo(cfg) ? "produit" : `rédigé par ${llmLabel(cfg, false)}`}, à partir d'un article de veille et des documents de la marque, suivi de ses hashtags : 1 à 3 sur LinkedIn, exactement 5 sur Instagram (imposé par le code). La longueur suit la charte : 600 à 1 300 caractères sur LinkedIn, 150 à 500 sur Instagram.`,
  },
  {
    view: "revue", selector: ".post .warnings, .post .sources, .tabs", revueFilter: "tous",
    title: "Revue · les avertissements",
    text: "Deux origines. En orange, ceux du modèle lui-même, quand une information manquait dans les documents (il doit le dire au lieu d'inventer). En rouge, ceux du garde-fou : chiffre ou label absent des sources, superlatif interdit, registre (tutoiement sur Instagram, vouvoiement sur LinkedIn), émojis, longueur. Chaque alerte de fond fait baisser la confiance.",
  },
  {
    view: "revue", selector: ".post .sources, .tabs", revueFilter: "tous",
    title: "Revue · les sources",
    text: "Les documents de la marque réellement utilisés pour ce post. Le code retire toute source citée qui n'a pas été fournie au modèle. C'est par ici qu'on vérifie un fait avant d'approuver.",
  },
  {
    view: "revue", selector: ".post .visual, .post .visual-empty, .tabs", revueFilter: "tous",
    title: "Revue · le visuel",
    text: (cfg) => `Le visuel prototype du post, au bon format (paysage pour LinkedIn, 4:5 pour Instagram). ${cfg.images === "openai" ? "Il est généré par DALL-E via l'API OpenAI." : "Ici en maquette hors ligne (palette et sujet) ; avec une clé OpenAI, il est généré par DALL-E."} Un bouton permet de le (re)générer.`,
  },
  {
    view: "revue", selector: ".post .glass-wrap, .tabs", revueFilter: "tous",
    title: "Revue · la confiance",
    text: "Le verre se remplit selon le score de confiance : l'auto-évaluation du modèle, diminuée de 0,2 par problème de fond relevé par le garde-fou. Ce n'est pas une probabilité, c'est un signal pour prioriser la relecture.",
  },
  {
    view: "revue", selector: ".post details.prompt, .tabs", revueFilter: "tous",
    title: "Revue · le prompt d'image",
    text: "Le prompt d'image détaillé (sujet, style, palette, composition, ce qu'il faut éviter), avec une ligne prête pour Midjourney. Le bouton « Copier le prompt » l'envoie dans le presse-papiers.",
  },
  {
    view: "revue", selector: ".post .actions:not(:empty), .tabs", revueFilter: "tous",  // un post qui a encore des boutons
    title: "Revue · rien ne part sans vous",
    text: (cfg) => `Approuver, rejeter avec une note, ou éditer. La note de revue s'affiche ensuite sous le texte, pour garder la trace de la décision. Une édition relance le garde-fou et remet le post en brouillon : le nouveau texte doit être validé à son tour. ${isDemo(cfg)
      ? "Avec un vrai LLM, cette étape est indispensable"
      : `Cas réel vu avec ${llmLabel(cfg, false)}`} : un post affirmait « depuis 2017, c'est ici que nos journées commencent », alors que la brasserie date de 2016 (2017 est la date de la certification bio). Le chiffre existe dans les sources, donc seul un humain pouvait voir l'erreur.`,
  },
  {
    view: "calendrier", selector: ".week",
    title: "Mois 3 · Programmation",
    text: "2 posts LinkedIn (mardi et jeudi à 9 h) et 1 Instagram (samedi à 11 h) par semaine. « Programmer les approuvés » remplit les prochains créneaux libres ; « Publier les échéances » envoie ce qui est arrivé à l'heure (ici à une date simulée).",
  },
  {
    view: "savoir", selector: ".ask",
    title: "Le Brand Book interrogeable",
    text: (cfg) => `Posez une question sur la marque : ${isDemo(cfg) ? "la réponse vient" : `${llmLabel(cfg, false)} répond`} uniquement à partir de la documentation interne, avec ses sources. Si l'information n'y est pas, l'outil répond « je ne trouve pas » au lieu d'inventer. Essayez « Avez-vous le label Biogarantie ? » (piège : la brasserie ne l'a pas) ou « Quel est le prix de la Blonde ? ».`,
  },
  {
    view: "controle", selector: ".head .actions",
    title: "Contrôle qualité",
    text: (cfg) => `Une évaluation automatique sur 10 cas (longueur, hashtags, émojis, chiffres non sourcés, formules interdites), puis deux posts piégés pour prouver que les détecteurs réagissent. ${isDemo(cfg)
      ? "Avec Gemini, elle a guidé l'itération des prompts : 8/10 en v1, 10/10 en v2, zéro chiffre inventé."
      : `Avec ${llmLabel(cfg, false)}, comptez environ 5 minutes (15 appels). C'est elle qui a guidé l'itération des prompts : 8/10 en v1, 10/10 en v2, zéro chiffre inventé.`}`,
  },
  {
    view: "tableau", selector: null,
    title: "À vous de jouer",
    text: (cfg) => `Commencez par « Lancer la semaine »${isDemo(cfg) ? "" : ` (une à deux minutes avec ${llmLabel(cfg, false)})`}, puis passez par la revue et le calendrier. La documentation de l'API est sur /docs, et le README explique chaque choix technique. Cette visite reste disponible via le bouton « Visite guidée ».`,
  },
];

const tour = { index: 0, active: false, layer: null, spot: null, bubble: null, config: { llm: "fake" } };

/** Un titre ou un texte d'étape peut être une chaîne ou une fonction de la configuration. */
const resolve = (value) => (typeof value === "function" ? value(tour.config) : value);

function tourSeen() {
  try { return localStorage.getItem(TOUR_KEY) === "1"; } catch (_) { return true; }
}

function markTourSeen() {
  try { localStorage.setItem(TOUR_KEY, "1"); } catch (_) {}
}

/** Change de vue et attend la fin de son rendu. */
async function tourGoTo(view, force = false) {
  const current = (location.hash.replace("#/", "") || "tableau").split("?")[0];
  if (current === view && !force) return;
  if (current === view) { await render(); return; } // même vue, mais l'état a changé (ex. filtre)
  window.tourNavigating = true;
  location.hash = "#/" + view;
  await render();
  window.tourNavigating = false;
}

function tourTarget(selector) {
  if (!selector) return null;
  for (const one of selector.split(",")) {
    const el = document.querySelector(one.trim());
    if (el && el.getClientRects().length) return el;
  }
  return null;
}

function placeTour(target) {
  const { spot, bubble } = tour;
  const margin = 12;
  if (!target) {
    spot.style.cssText = "top:50%;left:50%;width:0;height:0";
    bubble.classList.add("centered");
    bubble.style.cssText = "";
    return;
  }
  bubble.classList.remove("centered");
  const r = target.getBoundingClientRect();
  const pad = 8;
  spot.style.cssText = `top:${r.top - pad}px;left:${r.left - pad}px;width:${r.width + pad * 2}px;height:${r.height + pad * 2}px`;

  if (window.innerWidth < 700) { bubble.style.cssText = ""; return; } // feuille en bas d'écran (CSS)
  const bw = bubble.offsetWidth, bh = bubble.offsetHeight;
  let top, left;
  if (r.right + bw + margin * 2 < window.innerWidth && r.width < window.innerWidth * 0.45) {
    left = r.right + margin * 2; top = r.top; // à droite de la cible (ex. le menu)
  } else if (r.bottom + bh + margin * 2 < window.innerHeight) {
    top = r.bottom + margin * 2; left = r.left; // en dessous
  } else if (r.top - bh - margin * 2 > 0) {
    top = r.top - bh - margin * 2; left = r.left; // au-dessus
  } else if (r.left - bw - margin * 2 > 0) {
    left = r.left - bw - margin * 2; top = r.top; // à gauche (ex. le visuel, dans la colonne de droite)
  } else {
    // Aucune place libre autour : le coin de l'écran qui masque le moins la cible.
    const corners = [
      [margin, margin], [margin, window.innerWidth - bw - margin],
      [window.innerHeight - bh - margin, margin], [window.innerHeight - bh - margin, window.innerWidth - bw - margin],
    ];
    const hidden = ([t, l]) =>
      Math.max(0, Math.min(l + bw, r.right) - Math.max(l, r.left)) * Math.max(0, Math.min(t + bh, r.bottom) - Math.max(t, r.top));
    [top, left] = corners.reduce((best, c) => (hidden(c) < hidden(best) ? c : best));
  }
  left = Math.max(margin, Math.min(left, window.innerWidth - bw - margin));
  top = Math.max(margin, Math.min(top, window.innerHeight - bh - margin));
  bubble.style.cssText = `top:${top}px;left:${left}px`;
}

async function showTourStep(index) {
  if (tour.busy) return; // une étape à la fois : on ignore les clics rapides pendant un changement de vue
  tour.busy = true;
  try {
    await renderTourStep(index);
  } finally {
    tour.busy = false;
  }
}

async function renderTourStep(index) {
  tour.index = index;
  const step = TOUR_STEPS[index];
  tour.bubble.classList.add("switching");
  // Certaines étapes imposent un filtre de la revue (ex. « Tous », pour qu'il y ait des posts à montrer).
  const refilter = step.revueFilter && state.revueFilter !== step.revueFilter;
  if (refilter) state.revueFilter = step.revueFilter;
  await tourGoTo(step.view, refilter);
  await new Promise((resolve) => setTimeout(resolve, 260)); // laisse finir les animations d'apparition
  const target = tourTarget(step.selector);
  if (target) target.scrollIntoView({ block: "center", behavior: "instant" });

  const last = index === TOUR_STEPS.length - 1;
  tour.bubble.replaceChildren(
    h("div", { class: "tour-count" }, `${index + 1} / ${TOUR_STEPS.length}`),
    h("h3", { id: "tour-title" }, resolve(step.title)),
    h("p", {}, resolve(step.text)),
    h("div", { class: "tour-progress" }, h("span", { style: `width:${((index + 1) / TOUR_STEPS.length) * 100}%` })),
    h("div", { class: "tour-nav" },
      h("button", { class: "btn ghost small", type: "button", onclick: endTour }, last ? "Fermer" : "Passer"),
      h("span", { class: "tour-spacer" }),
      index > 0 ? h("button", { class: "btn ghost small", type: "button", onclick: () => showTourStep(index - 1) }, "← Précédent") : null,
      h("button", { class: "btn primary small", type: "button", onclick: () => (last ? endTour() : showTourStep(index + 1)) }, last ? "Commencer" : "Suivant →"),
    ),
  );
  placeTour(target);
  tour.bubble.classList.remove("switching");
  tour.bubble.querySelector(".btn.primary").focus({ preventScroll: true });
}

function onTourKey(event) {
  if (!tour.active) return;
  if (event.key === "Escape") endTour();
  else if (event.key === "ArrowRight" && tour.index < TOUR_STEPS.length - 1) showTourStep(tour.index + 1);
  else if (event.key === "ArrowLeft" && tour.index > 0) showTourStep(tour.index - 1);
}

function onTourResize() {
  if (tour.active) placeTour(tourTarget(TOUR_STEPS[tour.index].selector));
}

async function startTour() {
  if (tour.active) return;
  tour.active = true;
  try {
    tour.config = (await api("GET", "/api/dashboard")).config; // textes adaptés au moteur actif
  } catch (_) {
    tour.config = { llm: "fake" };
  }
  tour.spot = h("div", { class: "tour-spot" });
  tour.bubble = h("section", { class: "tour-bubble", role: "dialog", "aria-modal": "true", "aria-labelledby": "tour-title" });
  tour.layer = h("div", { class: "tour-layer" }, tour.spot, tour.bubble);
  document.body.append(tour.layer);
  document.addEventListener("keydown", onTourKey);
  window.addEventListener("resize", onTourResize);
  window.addEventListener("scroll", onTourResize, { passive: true });
  showTourStep(0);
}

function endTour() {
  if (!tour.active) return;
  tour.active = false;
  markTourSeen();
  document.removeEventListener("keydown", onTourKey);
  window.removeEventListener("resize", onTourResize);
  window.removeEventListener("scroll", onTourResize);
  tour.layer.remove();
  tourGoTo("tableau");
}

document.getElementById("tour-launch").addEventListener("click", startTour);
if (!tourSeen()) setTimeout(startTour, 900);
