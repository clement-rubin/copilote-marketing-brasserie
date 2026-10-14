/* Visite guidée de l'interface.
   Un projecteur met en lumière une zone, une bulle explique son rôle et la mission de l'offre
   qu'elle couvre. La visite change de vue toute seule. Démarre à la première visite,
   puis via le bouton « Visite guidée ». Clavier : flèches pour naviguer, Échap pour quitter. */

const TOUR_KEY = "copilote-visite-vue";

const TOUR_STEPS = [
  {
    view: "tableau", selector: null,
    title: "Bienvenue dans le Copilote Marketing",
    text: "En 2 minutes, voici comment l'outil transforme l'actualité du marché en 3 posts par semaine, fidèles au ton de la brasserie, validés par un humain puis publiés. La visite suit le plan sur 3 mois du cahier des charges.",
  },
  {
    view: "tableau", selector: ".nav",
    title: "Les 7 étapes du flux",
    text: "Le menu suit l'ordre du travail : veille (mois 1), atelier et revue (mois 2), calendrier et publication (mois 3). La base de connaissances et le contrôle qualité servent à tout moment.",
  },
  {
    view: "tableau", selector: "#config-chips",
    title: "Mode démo ou mode réel",
    text: "Ces étiquettes montrent les moteurs actifs. FAKE, PLACEHOLDER et MOCK : tout tourne hors ligne, sans clé ni coût. Dans le fichier .env, on passe à Gemini, OpenAI ou Anthropic pour le texte, à DALL-E pour les images, et aux API LinkedIn / Meta pour la publication, sans changer une ligne de code.",
  },
  {
    view: "tableau", selector: ".ledger",
    title: "Le registre",
    text: "Où en est la production : articles de veille collectés, puis chaque post selon son statut. Brouillon → approuvé → programmé → publié. Le passage de l'un à l'autre est contrôlé par le code : impossible de publier un brouillon.",
  },
  {
    view: "tableau", selector: ".hero-cta",
    title: "La semaine en un geste",
    text: "Le bouton qui fait tout : veille, choix de 3 articles inédits, rédaction de 2 posts LinkedIn (les personas tournent chaque semaine) et d'une légende Instagram, avec leurs visuels. En production, cette étape est lancée chaque lundi par un planificateur (cron).",
  },
  {
    view: "veille", selector: ".head .actions",
    title: "Mois 1 · Veille automatisée",
    text: "Lecture des flux RSS de la filière et des recherches Google News (dont « bière bio CHR »). Pas de scraping de pages : uniquement des flux publiés volontairement, pour respecter les CGU et le RGPD. Chaque article est résumé en 3 phrases, avec son intérêt pour la brasserie.",
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
  {
    view: "revue", selector: ".post .sources, .tabs",
    title: "Zéro fait inventé",
    text: "Chaque post cite les documents de la marque qu'il a utilisés. Le garde-fou vérifie ensuite que chaque chiffre et chaque label du texte figure bien dans ces documents : sinon, avertissement rouge et confiance en baisse.",
  },
  {
    view: "revue", selector: ".post .glass-wrap, .tabs",
    title: "Visuel et confiance",
    text: "La jauge en forme de verre donne la confiance du post après le garde-fou. Juste au-dessus, le visuel prototype (DALL-E en mode réel) ; juste en dessous, le prompt d'image prêt à coller dans Midjourney, avec la palette et les interdits de la marque.",
  },
  {
    view: "revue", selector: ".post .actions, .tabs",
    title: "Rien ne part sans vous",
    text: "Approuver, rejeter avec une note, ou éditer. Une édition relance le garde-fou et remet le post en brouillon : le nouveau texte doit être validé à son tour.",
  },
  {
    view: "calendrier", selector: ".week",
    title: "Mois 3 · Programmation",
    text: "2 posts LinkedIn (mardi et jeudi à 9 h) et 1 Instagram (samedi à 11 h) par semaine. « Programmer les approuvés » remplit les prochains créneaux libres ; « Publier les échéances » envoie ce qui est arrivé à l'heure (ici à une date simulée).",
  },
  {
    view: "savoir", selector: ".ask",
    title: "Le Brand Book interrogeable",
    text: "Posez une question sur la marque : la réponse vient uniquement de la documentation interne, avec ses sources. Si l'information n'y est pas, l'outil répond « je ne trouve pas » au lieu d'inventer. Essayez « Quel est le prix de la Blonde ? ».",
  },
  {
    view: "controle", selector: ".head .actions",
    title: "Contrôle qualité",
    text: "Une évaluation automatique sur 10 cas (longueur, hashtags, émojis, chiffres non sourcés, formules interdites), puis deux posts piégés pour prouver que les détecteurs réagissent.",
  },
  {
    view: "tableau", selector: null,
    title: "À vous de jouer",
    text: "Commencez par « Lancer la semaine », puis passez par la revue et le calendrier. La documentation de l'API est sur /docs, et le README explique chaque choix technique. Cette visite reste disponible via le bouton « Visite guidée ».",
  },
];

const tour = { index: 0, active: false, layer: null, spot: null, bubble: null };

function tourSeen() {
  try { return localStorage.getItem(TOUR_KEY) === "1"; } catch (_) { return true; }
}

function markTourSeen() {
  try { localStorage.setItem(TOUR_KEY, "1"); } catch (_) {}
}

/** Change de vue et attend la fin de son rendu. */
async function tourGoTo(view) {
  const current = (location.hash.replace("#/", "") || "tableau").split("?")[0];
  if (current === view) return;
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
  } else {
    top = window.innerHeight - bh - margin; left = window.innerWidth - bw - margin; // coin
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
  await tourGoTo(step.view);
  await new Promise((resolve) => setTimeout(resolve, 260)); // laisse finir les animations d'apparition
  const target = tourTarget(step.selector);
  if (target) target.scrollIntoView({ block: "center", behavior: "instant" });

  const last = index === TOUR_STEPS.length - 1;
  tour.bubble.replaceChildren(
    h("div", { class: "tour-count" }, `${index + 1} / ${TOUR_STEPS.length}`),
    h("h3", { id: "tour-title" }, step.title),
    h("p", {}, step.text),
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

function startTour() {
  if (tour.active) return;
  tour.active = true;
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
