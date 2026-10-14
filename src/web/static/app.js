/* Copilote Marketing : interface web (JavaScript sans framework).
   Chaque vue appelle l'API FastAPI (src/web/app.py) et construit le DOM avec h().
   Tout texte venant de l'API passe par textContent (jamais innerHTML) : pas d'injection HTML. */

const PERSONAS = {
  expertise_bio: { label: "Expertise Bio", platform: "linkedin", desc: "Rendre la certification bio concrète et vendable pour les pros." },
  coulisses_brassage: { label: "Coulisses du Brassage", platform: "linkedin", desc: "Montrer le savoir-faire réel, ratés compris." },
  mise_en_avant_distributeur: { label: "Mise en avant distributeur", platform: "linkedin", desc: "Mettre à l'honneur un caviste ou un café partenaire." },
  instagram_craft: { label: "Instagram craft beer", platform: "instagram", desc: "Légende courte B2C, 5 hashtags, émojis mesurés." },
};

const STATUS_LABEL = { brouillon: "Brouillon", approuve: "Approuvé", rejete: "Rejeté", programme: "Programmé", publie: "Publié" };
const JOURS = ["dim.", "lun.", "mar.", "mer.", "jeu.", "ven.", "sam."];

const state = {
  article: null, // URL de l'article choisi dans l'atelier
  personas: new Set(Object.keys(PERSONAS)),
  revueFilter: window.COPILOTE_STATIC === true ? "tous" : "brouillon", // démo en ligne : pas de brouillon à relire
  qa: [],
  lastGenerated: [],
};

// ------------------------------------------------------------------ Outils

/** Construit un élément DOM : h("div", {class: "x", onclick: f}, enfant1, "texte", ...) */
function h(tag, props = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(props || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key.startsWith("on")) el.addEventListener(key.slice(2), value);
    else if (key === "class") el.className = value;
    else if (key === "style") el.style.cssText = value;
    else el.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return el;
}

// Site statique (Netlify) : pas de serveur Python. Les lectures viennent de fichiers JSON
// pré-générés par `python -m src.cli export-site`, les actions sont désactivées.
const STATIC_SITE = window.COPILOTE_STATIC === true;
const REPO_URL = "https://github.com/clement-rubin/copilote-marketing-brasserie";

/** "/api/posts?statut=brouillon" -> "/data/api/posts__statut_brouillon.json" (même règle que l'export). */
function staticPath(path) {
  return "/data" + path.replace("?", "__").replace(/[=&]/g, "_") + ".json";
}

async function staticApi(method, path, body) {
  if (method === "GET") {
    const response = await fetch(staticPath(path));
    if (!response.ok) throw new Error("Donnée absente de la démo en ligne.");
    return response.json();
  }
  if (path === "/api/ask") {
    const answers = await (await fetch("/data/ask.json")).json();
    return answers[body.question.trim()] || {
      reponse: "Dans la démo en ligne, seules les questions suggérées ont une réponse (pré-calculée avec le vrai LLM). Pour poser vos propres questions, lancez le projet en local.",
      sources_utilisees: [],
      avertissements: ["Démo en lecture seule"],
    };
  }
  if (path === "/api/eval") return (await fetch("/data/eval.json")).json();
  throw new Error("Démo en ligne en lecture seule : cette action demande le serveur Python. Le dépôt GitHub explique comment le lancer en 5 commandes.");
}

async function api(method, path, body) {
  if (STATIC_SITE) return staticApi(method, path, body);
  const response = await fetch(path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    let detail = response.statusText;
    try { detail = (await response.json()).detail || detail; } catch (_) {}
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return response.json();
}

function toast(message, kind = "info") {
  const el = h("div", { class: `toast ${kind}` }, message);
  document.getElementById("toasts").append(el);
  setTimeout(() => el.remove(), 4200);
}

/** Bouton qui affiche un indicateur pendant l'action et signale les erreurs. */
function actionButton(label, className, action, busyLabel = "Brassage…") {
  const button = h("button", { class: `btn ${className}`, type: "button" }, label);
  button.addEventListener("click", async () => {
    button.disabled = true;
    button.replaceChildren(h("span", { class: "spin" }), busyLabel);
    try {
      await action();
    } catch (error) {
      toast(error.message, "error");
    } finally {
      button.disabled = false;
      button.replaceChildren(label);
    }
  });
  return button;
}

function frDate(iso, withYear = false) {
  const d = new Date(iso);
  const date = d.toLocaleDateString("fr-BE", { day: "2-digit", month: "2-digit", ...(withYear ? { year: "numeric" } : {}) });
  const time = d.toLocaleTimeString("fr-BE", { hour: "2-digit", minute: "2-digit" }).replace(":", "h");
  return `${JOURS[d.getDay()]} ${date} · ${time}`;
}

function header(kicker, title, italic, lede, ...actions) {
  return h("header", { class: "head reveal" },
    h("div", {},
      h("div", { class: "kicker" }, kicker),
      h("h1", {}, title, " ", h("em", {}, italic)),
      lede ? h("p", { class: "lede" }, lede) : null,
    ),
    actions.length ? h("div", { class: "actions" }, actions) : null,
  );
}

function stagger(nodes) {
  nodes.forEach((node, i) => {
    node.classList.add("reveal");
    node.style.animationDelay = `${80 + i * 70}ms`;
  });
  return nodes;
}

function empty(title, text, ...actions) {
  return h("div", { class: "empty" }, h("b", {}, title), text, actions.length ? h("div", { class: "actions", style: "justify-content:center;margin-top:14px" }, actions) : null);
}

async function refreshBadge() {
  try {
    const drafts = await api("GET", "/api/posts?statut=brouillon");
    document.getElementById("badge-revue").textContent = drafts.length || "";
  } catch (_) {}
}

// ------------------------------------------------------------------ Composants

function bars(items) {
  const max = Math.max(1, ...items.map(([, n]) => n));
  return h("div", { class: "bars" }, items.map(([term, n], i) =>
    h("div", { class: "bar" },
      h("span", {}, term),
      h("div", { class: "track" }, h("div", { class: "fill", style: `width:${(n / max) * 100}%;animation-delay:${i * 60}ms` })),
      h("span", { class: "n" }, n),
    )));
}

function glass(score) {
  const pct = Math.round(score * 100);
  return h("div", { class: "glass-wrap", title: "Score de confiance après garde-fou" },
    h("div", { class: "glass" }, h("div", { class: "beer", style: `height:${pct}%` })),
    h("div", { class: "glass-label" }, "confiance", h("b", {}, `${pct} %`)),
  );
}

function clip(article, { selectable = false, onSelect, compact = false } = {}) {
  const el = h("article", { class: `clip ${selectable ? "selectable" : ""} ${compact ? "compact" : ""} ${state.article === article.url ? "selected" : ""}` },
    article.utilise ? h("span", { class: "used" }, "utilisé") : null,
    h("div", { class: "meta" },
      h("span", { class: `tag ${article.theme === "concurrent" ? "concurrent" : ""}` }, article.theme || "veille"),
      h("span", {}, article.flux),
      article.publie_le ? h("span", {}, "· " + new Date(article.publie_le).toLocaleDateString("fr-BE")) : null,
    ),
    h("h3", {}, article.titre),
    compact ? null : h("p", {}, article.resume),
    compact ? null : h("p", { class: "why" }, article.pertinence),
    compact ? null : h("div", { class: "meta" }, h("a", { href: article.url, target: "_blank", rel: "noopener" }, "Lire la source ↗")),
  );
  if (selectable) el.addEventListener("click", (event) => { if (event.target.tagName !== "A") onSelect(article); });
  return el;
}

function postCard(post, onChange) {
  const persona = PERSONAS[post.persona] || { label: post.persona };
  let editing = false;
  const card = h("article", { class: "card post" });

  const replaceWith = (updated, message) => {
    toast(message);
    refreshBadge();
    if (onChange) onChange(updated);
    else card.replaceWith(postCard(updated, onChange));
  };

  function render() {
    const textBlock = editing
      ? h("textarea", { "aria-label": "Texte du post" }, post.texte)
      : h("p", { class: `post-text ${post.plateforme}` }, post.texte);

    const actions = [];
    if (editing) {
      actions.push(
        actionButton("Enregistrer", "primary small", async () => {
          const updated = await api("POST", `/api/posts/${post.id}/edit`, { texte: textBlock.value });
          replaceWith(updated, "Texte modifié : le garde-fou a été relancé, le post repasse en brouillon.");
        }),
        h("button", { class: "btn ghost small", type: "button", onclick: () => { editing = false; render(); } }, "Annuler"),
      );
    } else {
      if (post.statut === "brouillon") {
        actions.push(actionButton("Approuver", "primary small", async () => {
          replaceWith(await api("POST", `/api/posts/${post.id}/approve`, { note: "" }), "Post approuvé : il peut être programmé.");
        }));
      }
      if (["brouillon", "approuve"].includes(post.statut)) {
        actions.push(actionButton("Rejeter", "danger small", async () => {
          const note = window.prompt("Raison du rejet (facultatif) :", "") ?? "";
          replaceWith(await api("POST", `/api/posts/${post.id}/reject`, { note }), "Post rejeté.");
        }));
      }
      if (["brouillon", "approuve", "rejete"].includes(post.statut)) {
        actions.push(h("button", { class: "btn ghost small", type: "button", onclick: () => { editing = true; render(); } }, "Éditer"));
      }
    }

    const warnings = (post.avertissements || []).map((w) =>
      h("li", { class: w.startsWith("[garde-fou]") ? "guard" : "" }, w.replace("[garde-fou] ", "Garde-fou · ")));

    const visual = post.image_web
      ? h("img", { class: "visual", src: `${post.image_web}?v=${Date.now()}`, alt: `Visuel prototype du post ${post.id}` })
      : h("div", { class: "visual-empty" }, "Pas encore de visuel",
          actionButton("Générer le visuel", "ghost small", async () => {
            replaceWith(await api("POST", `/api/posts/${post.id}/visual`), "Visuel généré.");
          }, "Rendu…"));

    const copy = h("button", { class: "btn ghost small", type: "button", onclick: async () => {
      await navigator.clipboard.writeText(post.prompt_image || "");
      toast("Prompt d'image copié (Midjourney / DALL-E).");
    } }, "Copier le prompt");

    const statusInfo = post.statut === "programme" && post.programme_le
      ? h("span", { class: "tag" }, "le " + frDate(post.programme_le))
      : post.statut === "publie"
        ? h("span", { class: "tag" }, "canaux : " + Object.keys(post.publications || {}).join(", "))
        : null;

    card.replaceChildren(
      h("div", { class: "post-main" },
        h("span", { class: `stamp ${post.statut}` }, STATUS_LABEL[post.statut] || post.statut),
        h("div", { class: "post-head" },
          h("span", { class: `tag ${post.plateforme}` }, post.plateforme),
          h("span", { class: "tag" }, persona.label),
          statusInfo,
          h("span", { class: "post-id" }, "#" + post.id),
        ),
        textBlock,
        h("div", { class: "hashtags" }, (post.hashtags || []).join(" ")),
        warnings.length ? h("ul", { class: "warnings" }, warnings) : null,
        h("div", { class: "sources" }, (post.sources_utilisees || []).length
          ? post.sources_utilisees.map((s) => h("span", { class: "tag source" }, "📄 " + s))
          : h("span", { class: "tag" }, "aucune source")),
        post.note_revue ? h("p", { class: "lede", style: "font-size:13px;margin-bottom:12px" }, "Note de revue : " + post.note_revue) : null,
        h("div", { class: "actions" }, actions),
      ),
      h("div", { class: "post-side" },
        visual,
        glass(post.score_confiance),
        h("details", { class: "prompt" }, h("summary", {}, "Prompt d'image"), h("pre", {}, post.prompt_image || ""), copy),
      ),
    );
  }

  render();
  return card;
}

// ------------------------------------------------------------------ Vues

const views = {
  async tableau(root) {
    const d = await api("GET", "/api/dashboard");
    renderConfig(d.config);
    const s = d.statuts;
    const ledger = h("section", { class: "ledger" },
      [["Articles de veille", d.articles], ["Brouillons", s.brouillon, true], ["Approuvés", s.approuve], ["Programmés", s.programme], ["Publiés", s.publie]]
        .map(([label, value, amber]) => h("div", {}, h("div", { class: "label" }, label), h("div", { class: `value ${amber ? "amber" : ""}` }, value))));

    const cta = h("section", { class: "card hero-cta" },
      h("h2", {}, "La semaine, en un geste"),
      h("p", {}, "Veille, choix de 3 articles, rédaction de 2 posts LinkedIn (personas en rotation) et d'une légende Instagram, visuels compris. Tout arrive en brouillon : rien ne part sans votre accord."),
      h("div", { class: "actions" },
        actionButton("Lancer la semaine (flux démo)", "amber", async () => {
          const posts = await api("POST", "/api/weekly", { offline: true });
          toast(posts.length ? `${posts.length} brouillons prêts pour la revue.` : "Aucun nouvel article à exploiter.");
          state.revueFilter = "brouillon";
          location.hash = "#/revue";
        }),
        d.chunks === 0 ? actionButton("Indexer la marque", "ghost", async () => {
          const r = await api("POST", "/api/ingest");
          toast(`${r.chunks} chunks indexés depuis ${r.documents} documents.`);
          render();
        }) : null,
      ));

    const upcoming = h("section", { class: "card" },
      h("h2", {}, "Prochaines publications", h("small", {}, "calendrier")),
      d.prochains.length
        ? h("div", { class: "upcoming" }, d.prochains.map((p) => h("div", { class: "slot-line" },
            h("div", { class: "slot-date" }, h("b", {}, frDate(p.programme_le).split(" · ")[0]), frDate(p.programme_le).split(" · ")[1]),
            h("div", {}, h("span", { class: `tag ${p.plateforme}` }, p.plateforme), " ", h("span", { style: "font-size:14px" }, p.texte.slice(0, 110) + "…")))))
        : h("p", { class: "lede" }, "Rien de programmé. Approuvez des posts puis passez par le calendrier."));

    const trends = h("section", { class: "card" },
      h("h2", {}, "Ce dont parle le marché", h("small", {}, `${d.articles} articles`)),
      d.tendances.length ? bars(d.tendances) : h("p", { class: "lede" }, "Lancez une veille pour voir les tendances."),
      d.concurrents.length ? h("div", { class: "actions", style: "margin-top:16px" },
        d.concurrents.map((c) => h("span", { class: "tag concurrent" }, `${c.terme} · ${c.mentions} mention(s)`))) : null);

    root.append(
      header("Brasserie Démo du Hainaut · Content Factory", "Le copilote", "marketing.",
        "Veille du marché, base de connaissances de la marque, rédaction LinkedIn et Instagram, validation humaine et publication programmée."),
      ...stagger([ledger, h("div", { class: "grid two" }, cta, upcoming), trends]),
    );
  },

  async veille(root) {
    const [articles, trends] = await Promise.all([api("GET", "/api/articles"), api("GET", "/api/trends")]);
    const runWatch = (offline) => async () => {
      const r = await api("POST", "/api/watch", { offline });
      toast(`${r.ajoutes} nouvel(s) article(s) résumé(s).`);
      render();
    };
    root.append(header("Mois 1 · Sourcing", "Veille &", "social listening",
      "Flux RSS de la filière, recherches Google News sur les mots-clés suivis et les concurrents. Chaque article est résumé en 3 phrases, avec sa pertinence pour la marque.",
      actionButton("Veille démo", "ghost", runWatch(true), "Lecture…"),
      actionButton("Veille réelle (RSS)", "primary", runWatch(false), "Lecture des flux…")));

    if (!articles.length) {
      root.append(empty("Aucun article pour l'instant", "Lancez une veille (démo hors ligne ou flux réels)."));
      return;
    }
    const mentions = h("section", { class: "card" },
      h("h2", {}, "Termes suivis", h("small", {}, "feeds.yaml")),
      h("div", { class: "bars" }, trends.mentions.map((m) => h("div", { class: "bar" },
        h("span", { class: m.type === "concurrent" ? "tag concurrent" : "" }, m.terme),
        h("div", { class: "track" }, h("div", { class: "fill", style: `width:${Math.min(100, m.articles.length * 25)}%` })),
        h("span", { class: "n" }, m.articles.length)))));
    const terms = h("section", { class: "card" }, h("h2", {}, "Tendances", h("small", {}, `${trends.n_articles} articles`)), bars(trends.termes.slice(0, 8)));
    root.append(...stagger([h("div", { class: "grid two" }, terms, mentions)]));
    root.append(h("h2", { style: "margin-top:34px" }, "Revue de presse", h("small", {}, "cliquer pour créer des posts")));
    root.append(h("div", { class: "clips" }, stagger(articles.map((a) => clip(a, {
      selectable: true,
      onSelect: (art) => { state.article = art.url; location.hash = "#/atelier"; },
    })))));
  },

  async atelier(root) {
    const articles = await api("GET", "/api/articles");
    root.append(header("Mois 2 · Content Factory", "Atelier de", "contenu",
      "Choisissez un article de départ et les personas. Les faits sur la marque viennent uniquement de la base de connaissances ; le garde-fou vérifie chaque chiffre et chaque label."));
    if (!articles.length) {
      root.append(empty("Pas encore de matière première", "Il faut d'abord une veille.", h("a", { class: "btn primary", href: "#/veille" }, "Aller à la veille")));
      return;
    }
    if (!articles.some((a) => a.url === state.article)) state.article = (articles.find((a) => !a.utilise) || articles[0]).url;

    const personaButtons = Object.entries(PERSONAS).map(([id, p]) => {
      const btn = h("button", { class: "persona", type: "button", "aria-pressed": state.personas.has(id) ? "true" : "false" },
        h("span", { class: `tag ${p.platform}` }, p.platform), h("b", {}, p.label), h("span", {}, p.desc));
      btn.addEventListener("click", () => {
        state.personas.has(id) ? state.personas.delete(id) : state.personas.add(id);
        btn.setAttribute("aria-pressed", state.personas.has(id) ? "true" : "false");
      });
      return btn;
    });

    const results = h("div", { class: "posts" }, state.lastGenerated.map((p) => postCard(p)));
    const generate = actionButton("Rédiger les posts", "amber", async () => {
      if (!state.personas.size) throw new Error("Choisissez au moins une persona.");
      const posts = await api("POST", "/api/generate", { article_url: state.article, personas: [...state.personas] });
      state.lastGenerated = posts;
      results.replaceChildren(...stagger(posts.map((p) => postCard(p))));
      refreshBadge();
      toast(`${posts.length} brouillon(s) rédigé(s) avec visuels.`);
      results.scrollIntoView({ behavior: "smooth", block: "start" });
    }, "Rédaction…");

    const clipsBox = h("div", { class: "clips compact-list" });
    const drawClips = () => clipsBox.replaceChildren(...articles.map((a) => clip(a, {
      selectable: true, compact: true, onSelect: (art) => { state.article = art.url; drawClips(); },
    })));
    drawClips();

    root.append(...stagger([
      h("section", {}, h("h2", {}, "1 · Article de départ", h("small", {}, "point de départ, pas source de faits")), clipsBox),
      h("section", {}, h("h2", {}, "2 · Personas"), h("div", { class: "personas" }, personaButtons),
        h("div", { class: "actions", style: "margin-top:18px" }, generate)),
    ]), h("h2", { style: "margin-top:34px" }, "3 · Brouillons"), results);
  },

  async revue(root) {
    const all = await api("GET", "/api/posts");
    const counts = Object.fromEntries(Object.keys(STATUS_LABEL).map((s) => [s, all.filter((p) => p.statut === s).length]));
    root.append(header("Validation humaine", "Rien ne part", "sans vous.",
      "Chaque post naît brouillon. Approuvez, rejetez ou éditez : une édition relance le garde-fou et remet le post en brouillon."));

    const list = h("div", { class: "posts" });
    const tabs = h("div", { class: "tabs", role: "tablist" });
    const draw = () => {
      tabs.replaceChildren(...[...Object.keys(STATUS_LABEL), "tous"].map((s) => h("button", {
        role: "tab", type: "button", "aria-selected": state.revueFilter === s ? "true" : "false",
        onclick: () => { state.revueFilter = s; draw(); },
      }, s === "tous" ? "Tous" : STATUS_LABEL[s], h("span", { class: "count" }, s === "tous" ? all.length : counts[s]))));
      const shown = all.filter((p) => state.revueFilter === "tous" || p.statut === state.revueFilter);
      list.replaceChildren(...(shown.length
        ? stagger(shown.map((p) => postCard(p, () => render())))
        : [empty("Rien ici", state.revueFilter === "brouillon" ? "Aucun brouillon en attente." : "Aucun post avec ce statut.",
            h("a", { class: "btn ghost", href: "#/atelier" }, "Aller à l'atelier"))]));
    };
    draw();
    root.append(tabs, list);
  },

  async calendrier(root) {
    const weeks = await api("GET", "/api/calendar?weeks=4");
    const dateInput = h("input", { type: "date", value: new Date(Date.now() + 30 * 864e5).toISOString().slice(0, 10), "aria-label": "Date simulée" });
    root.append(header("Mois 3 · Orchestration", "Le tableau de", "brassage",
      "2 posts LinkedIn (mardi et jeudi 9 h) et 1 Instagram (samedi 11 h) par semaine. La publication part à l’échéance : en simulation ici, via les API LinkedIn et Meta en mode live.",
      actionButton("Programmer les approuvés", "primary", async () => {
        const r = await api("POST", "/api/schedule");
        toast(r.programmes.length ? `${r.programmes.length} post(s) programmé(s).` : "Aucun post approuvé à programmer.");
        render();
      }),
      h("span", { class: "inline-field" }, "Simuler le", dateInput),
      actionButton("Publier les échéances", "amber", async () => {
        const r = await api("POST", "/api/publish-due", { at: dateInput.value + "T23:59:00" });
        toast(r.publies.length ? `${r.publies.length} post(s) publié(s) (simulation).` : "Aucun post arrivé à échéance à cette date.");
        render();
      }, "Publication…")));

    root.append(h("div", { class: "weeks" }, stagger(weeks.map((w) => h("section", { class: "week" },
      h("div", { class: "week-label" }, "semaine", h("b", {}, w.semaine), new Date(w.lundi).toLocaleDateString("fr-BE", { day: "2-digit", month: "short" })),
      w.creneaux.map((slot) => h("div", { class: "slot" },
        h("div", { class: "slot-when" }, h("span", {}, frDate(slot.date)), h("span", { class: `tag ${slot.plateforme}` }, slot.plateforme)),
        slot.post
          ? h("div", { class: `slot-body ${slot.post.statut}` },
              h("span", { class: "tag" }, STATUS_LABEL[slot.post.statut]), " ",
              h("span", { class: "post-id" }, "#" + slot.post.id),
              h("p", {}, slot.post.texte))
          : h("div", { class: "slot-body free" }, "créneau libre"))))))));
  },

  async savoir(root) {
    root.append(header("Mois 1 · Brand Book IA", "Demandez à la", "marque.",
      "Questions-réponses sur la documentation interne (histoire, fiches techniques, labels, interview). Réponse sourcée, ou « je ne trouve pas » : jamais d'invention."));
    const input = h("input", { type: "text", placeholder: "Quel est le degré de la Saison Démo ?", "aria-label": "Question" });
    const log = h("div", { class: "qa" });
    const drawLog = () => log.replaceChildren(...state.qa.map(({ q, a }) => h("article", { class: `card qa-item ${a.sources_utilisees.length ? "" : "not-found"}` },
      h("p", { class: "q" }, "« " + q + " »"),
      h("p", { class: "a" }, a.reponse),
      h("div", { class: "sources" }, a.sources_utilisees.map((s) => h("span", { class: "tag source" }, "📄 " + s))),
      a.avertissements.length ? h("ul", { class: "warnings" }, a.avertissements.map((w) => h("li", {}, w))) : null)));
    const askQuestion = async (question) => {
      if (!question.trim()) return;
      const answer = await api("POST", "/api/ask", { question });
      state.qa.unshift({ q: question, a: answer });
      input.value = "";
      drawLog();
    };
    const send = actionButton("Demander", "primary", () => askQuestion(input.value), "Recherche…");
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") send.click(); });
    const suggestions = await api("GET", "/api/suggestions");
    root.append(...stagger([
      h("div", { class: "ask" }, input, send),
      h("div", { class: "suggestions" }, suggestions.map((s) => h("button", { type: "button", onclick: () => { input.value = s; send.click(); } }, s))),
    ]), log);
    drawLog();
    input.focus();
  },

  async controle(root) {
    const out = h("div", {});
    root.append(header("Qualité", "Mini-", "évaluation",
      "10 couples (article × persona) générés puis vérifiés automatiquement : longueur, hashtags, émojis, chiffres et labels non sourcés, formules interdites, sources. Puis deux posts piégés pour vérifier que les détecteurs réagissent.",
      actionButton("Lancer l'évaluation", "amber", async () => {
        const r = await api("POST", "/api/eval");
        const mark = (ok) => h("span", { class: ok ? "ok" : "ko" }, ok ? "✓" : "✗");
        out.replaceChildren(...stagger([
          h("div", { class: "grid two" },
            h("section", { class: "card" }, h("div", { class: "kicker" }, "cas conformes"), h("div", { class: "score-big" }, r.conformes, h("small", {}, " / " + r.cas.length))),
            h("section", { class: "card" }, h("h2", {}, "Détecteurs face à des posts piégés"),
              r.controles.map((c) => h("div", { style: "margin-bottom:12px" }, h("b", {}, c.cas), h("ul", { class: "warnings", style: "margin-top:6px" }, c.detections.map((d) => h("li", { class: "guard" }, d))))))),
          h("section", { class: "card", style: "overflow-x:auto" }, h("table", { class: "eval" },
            h("thead", {}, h("tr", {}, ["#", "persona", "article", "long.", "long. OK", "hashtags", "émojis", "non sourcés", "interdits", "sources", "confiance", "verdict"].map((t) => h("th", {}, t)))),
            h("tbody", {}, r.cas.map((c) => h("tr", {},
              h("td", {}, c.case), h("td", {}, PERSONAS[c.persona]?.label || c.persona), h("td", {}, c.article.slice(0, 42) + "…"),
              h("td", {}, c.length), h("td", {}, mark(c.length_ok)), h("td", {}, mark(c.hashtags_ok)), h("td", {}, mark(c.emojis_ok)),
              h("td", {}, c.unsourced.join(", ") || "0"), h("td", {}, c.forbidden.join(", ") || "0"), h("td", {}, c.sources),
              h("td", {}, Math.round(c.confidence * 100) + " %"), h("td", {}, mark(c.passed))))))),
        ]));
      }, "Évaluation…")));
    root.append(out);
  },
};

// ------------------------------------------------------------------ Routeur

function renderConfig(config) {
  const box = document.getElementById("config-chips");
  const llm = config.modeles && config.modeles.length ? `${config.llm} · ${config.modeles[0]}` : config.llm;
  box.replaceChildren(...[["LLM", llm], ["Images", config.images], ["Publication", config.publication]]
    .map(([k, v]) => h("div", { class: "chip-config" }, k, h("b", {}, v))));
}

async function render() {
  const name = (location.hash.replace("#/", "") || "tableau").split("?")[0];
  const view = views[name] ? name : "tableau";
  document.querySelectorAll(".nav a").forEach((a) => a.classList.toggle("active", a.dataset.view === view));
  const root = document.getElementById("view");
  root.replaceChildren();
  try {
    await views[view](root);
  } catch (error) {
    root.append(empty("Oups", error.message));
    toast(error.message, "error");
  }
  refreshBadge();
}

function staticBanner(meta) {
  const banner = h("div", { class: "static-banner", role: "note" },
    h("b", {}, "Démo en ligne, en lecture seule. "),
    `Données réelles générées avec ${meta.llm} le ${meta.date}. Les actions demandent le serveur Python : `,
    h("a", { href: REPO_URL, target: "_blank", rel: "noopener" }, "code et installation sur GitHub ↗"));
  document.body.prepend(banner);
}

if (STATIC_SITE) fetch("/data/meta.json").then((r) => r.json()).then(staticBanner).catch(() => {});

window.addEventListener("hashchange", () => {
  if (window.tourNavigating) return; // la visite guidée déclenche elle-même le rendu et l'attend
  render();
  window.scrollTo({ top: 0 });
});
api("GET", "/api/dashboard").then((d) => renderConfig(d.config)).catch(() => {});
render();
