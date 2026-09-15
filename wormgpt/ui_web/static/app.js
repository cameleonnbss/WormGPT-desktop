/* ============================================================
   WormGPT web UI — logique (parle au Bridge Python)
   ============================================================ */
"use strict";

/* pywebview injecte window.pywebview APRÈS le chargement des scripts de la
   page — on ne capture donc jamais l'API au chargement : on la rafraîchit à
   chaque tentative et init() re-essaie jusqu'à ce qu'elle soit disponible. */
let API = (window.pywebview && window.pywebview.api) ? window.pywebview.api : null;
function refreshAPI() {
  if (window.pywebview && window.pywebview.api) API = window.pywebview.api;
}
const S = { strings: {}, msgs: [], catalog: [], settings: null, view: "home",
            generating: false, searchOn: false, reasonOn: true,
            attachB64: null, attachName: "", curMsg: null, curReason: "",
            streamText: "", progress: {}, sessId: "", lang: "en" };

const t = (k) => S.strings[k] || k;

/* ---------- utilitaires ---------- */
const $ = (id) => document.getElementById(id);

/* ---------- icônes SVG (aucun emoji dans l'interface) ---------- */
const ICO = {
  home: '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/>',
  chat: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
  models: '<path d="M12 2l10 6-10 6L2 8z"/><path d="M2 14l10 6 10-6"/>',
  // tableau de bord « Spécifications & performances »
  specs: '<path d="M12 20a8 8 0 1 1 8-8"/><path d="M12 12l4.5-4.5"/><circle cx="12" cy="12" r="1.6"/><path d="M4 20h16"/>',
  reason: '<path d="M9 18h6M10 21h4"/><path d="M12 3a6 6 0 0 1 4.2 10.3c-.8.8-1.2 1.6-1.2 2.7h-6c0-1.1-.4-1.9-1.2-2.7A6 6 0 0 1 12 3z"/>',
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3c3.2 3.6 3.2 14.4 0 18M12 3c-3.2 3.6-3.2 14.4 0 18"/>',
  spark: '<path d="M12 2v5M12 17v5M2 12h5M17 12h5M4.9 4.9l3.2 3.2M15.9 15.9l3.2 3.2M19.1 4.9l-3.2 3.2M8.1 15.9l-3.2 3.2"/>',
  settings: '<circle cx="12" cy="12" r="3.2"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5 5l2.1 2.1M16.9 16.9 19 19M19 5l-2.1 2.1M7.1 16.9 5 19"/>',
  lock: '<rect x="4.5" y="10.5" width="15" height="10" rx="2.5"/><path d="M8 10.5V7.5a4 4 0 0 1 8 0v3"/>',
  sliders: '<path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1.5 14h5M9.5 8h5M17.5 16h5"/>',
  code: '<path d="M16 18l6-6-6-6M8 6l-6 6 6 6"/>',
  bolt: '<path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/>',
  box: '<path d="M21 8l-9-5-9 5v8l9 5 9-5V8z"/><path d="M3 8l9 5 9-5M12 13v8"/>',
  target: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.1" fill="currentColor" stroke="none"/>',
  dolphin: '<path d="M3.5 16c1.2-6.5 8-10 13.5-8 2.6.9 3.6 3.4 2.7 6.2-.4 1.3-1.6 2.1-3 2.3-3 .7-6.4 0-8.7-2"/><path d="M7 11.5c1.7 1.3 3.7 2 5.7 2.1"/><path d="M19.7 11.8l2.8-1.3"/><path d="M16 14.8l1 2.4"/>',
  chip: '<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 2.5V6M15 2.5V6M9 18v3.5M15 18v3.5M2.5 9H6M2.5 15H6M18 9h3.5M18 15h3.5"/>',
  image: '<rect x="3" y="4.5" width="18" height="15" rx="2.5"/><circle cx="8.5" cy="9.5" r="1.6"/><path d="M21 16l-5.5-5.5L7 19"/>',
  trash: '<path d="M3.5 6h17M8.5 6V4.5h7V6M6 6l1 14.5h10L18 6M10 10.5v6M14 10.5v6"/>',
  clip: '<path d="M21.5 11.5l-8.6 8.6a5.2 5.2 0 0 1-7.3-7.3l8.6-8.6a3.4 3.4 0 0 1 4.8 4.8l-8.6 8.6a1.7 1.7 0 0 1-2.4-2.4l7.3-7.3"/>',
  shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
  monitor: '<rect x="2.5" y="4.5" width="19" height="13" rx="2"/><path d="M8 21h8M12 17.5V21"/>',
  send: '<path d="M22 2 11 13"/><path d="M22 2 15 22l-4-9-9-4z"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3c3.2 3.6 3.2 14.4 0 18M12 3c-3.2 3.6-3.2 14.4 0 18"/>',
  reason: '<path d="M9 18h6M10 21h4"/><path d="M12 3a6 6 0 0 1 4.2 10.3c-.8.8-1.2 1.6-1.2 2.7h-6c0-1.1-.4-1.9-1.2-2.7A6 6 0 0 1 12 3z"/>',
  spark: '<path d="M12 2v5M12 17v5M2 12h5M17 12h5M4.9 4.9l3.2 3.2M15.9 15.9l3.2 3.2M19.1 4.9l-3.2 3.2M8.1 15.9l-3.2 3.2"/>',
};
function ic(name, size) {
  return `<span class="svg" style="width:${size || 15}px;height:${size || 15}px">` +
         `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" ` +
         `stroke-linecap="round" stroke-linejoin="round">${ICO[name] || ""}</svg></span>`;
}
function esc(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
function toast(text) {
  const el = $("toast");
  el.textContent = text;
  el.classList.remove("hidden");
  requestAnimationFrame(() => el.classList.add("visible"));
  clearTimeout(el._tm);
  el._tm = setTimeout(() => {
    el.classList.remove("visible");
    setTimeout(() => el.classList.add("hidden"), 280);
  }, 2600);
}
function applyI18n() {
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  $("chat-hint").textContent = t("chat.hint");
  $("settings-sub").textContent = t("settings.title");
  $("btn-send").innerHTML = ic("send", 16);
  $("btn-new").innerHTML = ic("plus", 16);
  $("btn-attach").innerHTML = ic("clip", 16);
  $("btn-img").innerHTML = ic("spark", 16);
  $("ico-search").innerHTML = ic("globe", 13);
  $("settings-close").innerHTML = ic("plus", 16);
  $("settings-close").style.transform = "rotate(45deg)";
  $("btn-attach").title = t("chat.attach");
  $("btn-img").title = t("chat.genimg.title");
  $("btn-search").title = t("chat.mode.search");
  $("model-select").title = t("chat.mode.select");
  $("btn-new").title = t("chat.new");
  $("settings-close").title = t("settings.close");
  $("model-pill").title = t("nav.models");
  $("img-go").textContent = t("image.generate");
  $("img-none").textContent = t("chat.genimg.none");
  $("img-install").textContent = t("chat.genimg.install");
  $("cf-no").textContent = t("confirm.no");
  $("cf-yes").textContent = t("confirm.yes");
  syncModes();
  refreshUserChip();
}
function syncModes() {
  $("btn-search").classList.toggle("on", S.searchOn);
  // Le raisonnement n'a plus de bouton : il est TOUJOURS activé, et le bloc
  // s'ouvre tout seul pendant que le modèle réfléchit.
}
function statusClass(st) {
  return st === "ready" ? "ready" : st === "loading" ? "loading"
       : st === "error" ? "error" : "";
}
/* ---------- personnalisation (accent / verre) appliquée au démarrage ---------- */
function applyUiPrefs() {
  const ui = (S.settings && S.settings.ui) || {};
  if (ui.accent) {
    const hex = String(ui.accent);
    if (/^#[0-9a-fA-F]{6}$/.test(hex)) {
      const r = parseInt(hex.slice(1, 3), 16), g = parseInt(hex.slice(3, 5), 16),
            b = parseInt(hex.slice(5, 7), 16);
      const rs = document.documentElement.style;
      rs.setProperty("--accent", hex);
      rs.setProperty("--accent-rgb", `${r},${g},${b}`);
      rs.setProperty("--accent-hover", hex);
      rs.setProperty("--border", `rgba(${r},${g},${b},.15)`);
      rs.setProperty("--border-bright", `rgba(${r},${g},${b},.32)`);
      rs.setProperty("--glow", `0 0 60px rgba(${r},${g},${b},.12)`);
      // texte sur fond accent : noir quand l'accent est clair (blanc, jaune…)
      // sinon du blanc sur blanc devient illisible
      const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b;
      const ink = lum > 150 ? "#0b0b0d" : "#fff";
      rs.setProperty("--accent-ink", ink);
      document.body.toggleAttribute("data-accent-light", lum > 150);
      // les dégradés fond/rouge suivent l'accent choisi
      document.body.style.background =
        `linear-gradient(180deg, rgba(${r},${g},${b},.20) 0%, rgba(20,10,14,.08) 44%, transparent 100%),` +
        `radial-gradient(ellipse 95% 62% at 50% 12%, rgba(${r},${g},${b},.36) 0%, transparent 64%),` +
        `radial-gradient(ellipse 72% 92% at 8% 50%, rgba(${Math.round(r*.45)},${Math.round(g*.45)},${Math.round(b*.45)},.22) 0%, transparent 60%),` +
        `radial-gradient(ellipse 72% 92% at 92% 48%, rgba(${Math.round(r*.45)},${Math.round(g*.45)},${Math.round(b*.45)},.18) 0%, transparent 60%),` +
        `linear-gradient(180deg,#0e0a0d 0%,#070709 64%,#050507 100%)`;
    }
  }
  document.body.classList.toggle("no-glass", ui.glass === false);
}
function userName() {
  return ((S.settings && S.settings.user_name) || "").trim() || "";
}
function refreshUserChip() {
  const n = userName();
  const init = (n || "?")[0].toUpperCase();
  $("top-avatar").textContent = init;
  $("top-user-name").textContent = n || "WormGPT";
  $("top-user").title = t("settings.logged").replace("{name}", n || "?");
}

/* ---------- démarrage ---------- */
async function init() {
  refreshAPI();
  if (!API) {
    // le pont n'est pas encore injecté — on réessaie (max ~6 s), puis on
    // abandonne proprement au lieu de laisser un écran noir.
    if (!S._retries) S._retries = 0;
    if (++S._retries < 30) { setTimeout(init, 200); return; }
    document.body.innerHTML = "<h1>Bridge indisponible</h1>";
    return;
  }
  if (S.booted) return;
  S.booted = true;
  const st = await API.init();
  Object.assign(S, { strings: st.strings, settings: st.settings,
                     presets: st.presets || [] });
  S.reasonOn = true;   // raisonnement toujours visible, plus de bouton
  S.searchOn = st.settings.search;
  S.lang = st.language || "en";
  applyUiPrefs();
  $("side-version").textContent = st.version;
  S.version = st.version;
  $("pill-model").textContent = st.settings.model || "WormGPT";
  S.sessId = st.session_id || "";
  applyI18n();
  renderConvs();
  if (!st.configured) {
    wizardInit();
    show("screen-wizard");
    return;
  }
  appInit();
  show("screen-app");
  welcome(st.user_name || st.ai_name);
  updateModelBar();
}

function show(id) {
  ["screen-wizard", "screen-app"].forEach((s) =>
    $(s).classList.toggle("hidden", s !== id));
}

/* ---------- assistant de configuration ---------- */
const ACCENTS = ["#ff3d57", "#ff2d2d", "#e11d74", "#a855f7", "#3b82f6",
                 "#10b981", "#f59e0b", "#f4f4f5"];
const WIZ_LAST = 5;      // 0 Bienvenue, 1 Identité, 2 Apparence, 3 Modèle,
                         // 4 Assistant, 5 Récapitulatif
let WIZ = { step: 0, lang: "en", userName: "", aiName: "WormGPT",
            preset: "Security Professional", tier: "", presets: [],
            ui: {}, engine: {}, xkiroSaved: false,
            agent: false, agentMode: "ask" };
function wizardInit() {
  WIZ.lang = "en";
  WIZ.aiName = "WormGPT";
  WIZ.userName = "";
  WIZ.preset = S.presets ? S.presets[0].key : "Security Professional";
  WIZ.presets = S.presets || [];
  WIZ.tier = S.settings.recommended;
  const cur = (S.settings && S.settings.ui) || {};
  WIZ.ui = { accent: cur.accent || ACCENTS[0],
             particles: cur.particles !== false,
             glass: cur.glass !== false,
             particles_speed: cur.particles_speed ?? 0.55 };
  // valeurs de départ : celles recommandées pour la machine détectée
  WIZ.engine = { n_ctx: 4096, n_threads: 0 };
  API.system_summary().then((r) => {
    const rec = (r && r.rec) || {};
    WIZ.engine = { n_ctx: rec.n_ctx || 4096, n_threads: rec.threads || 0 };
    if (WIZ.step === 2) renderWizard();
  }).catch(() => {});
  renderWizard();
}
function wizDots() {
  const labels = ["wizard.step1", "wizard.step2", "wizard.step.appearance",
                  "wizard.step3", "wizard.step4", "wizard.step5"];
  $("wiz-dots").innerHTML = labels.map((k, i) =>
    `<div class="wiz-dot ${i < WIZ.step ? "done" : i === WIZ.step ? "on" : ""}">
       <span class="n">${i < WIZ.step ? "✓" : i + 1}</span>${esc(t(k))}</div>`).join("");
}
/* Aperçu immédiat d'une préférence visuelle, dans le wizard lui-même. */
function wizPreviewUi() {
  const keep = S.settings.ui;
  S.settings.ui = WIZ.ui;
  applyUiPrefs();
  restartParticles();
  S.settings.ui = keep;
}
function renderWizard() {
  $("wiz-step-label").textContent = t("wizard.setup");
  wizDots();
  $("wiz-back").style.visibility = WIZ.step === 0 ? "hidden" : "visible";
  $("wiz-back").textContent = t("wizard.back");
  $("wiz-next").textContent = WIZ.step === WIZ_LAST ? t("wizard.launch") : t("wizard.next");
  const nextBtn = $("wiz-next");
  nextBtn.disabled = false;
  nextBtn.classList.add("red");
  const body = $("wiz-body");
  if (WIZ.step === 0) {
    // ---- écran 1 : bienvenue + langue ------------------------------
    body.innerHTML = `
      <div class="wiz-hero">
        <img src="/assets/logo_128.png" alt=""/>
        <h2>Worm<span>GPT</span></h2>
        <p class="tag">${esc(t("brand.tagline"))}</p>
        <p>${esc(t("wizard.welcome_desc"))}</p>
      </div>
      <div class="wiz-field"><label>${esc(t("wizard.language"))}</label>
        <select class="input" id="wiz-lang">
          <option value="fr">Français</option>
          <option value="en">English</option>
          <option value="es">Español</option>
          <option value="de">Deutsch</option>
        </select></div>`;
    $("wiz-lang").value = WIZ.lang;
    $("wiz-lang").addEventListener("change", () => {
      WIZ.lang = $("wiz-lang").value;
      // applique la langue tout de suite côté serveur et repeint le wizard
      API.set_language(WIZ.lang).then((r) => {
        if (r && r.strings) { S.strings = r.strings; S.lang = r.language;
          applyI18n(); renderWizard(); }
      });
    });
  } else if (WIZ.step === 1) {
    // ---- écran 2 : identité (vous + votre IA) ---------------------
    body.innerHTML = `
      <h3 style="margin-bottom:4px">${esc(t("wizard.identity_step"))}</h3>
      <p class="muted" style="margin-bottom:18px">${esc(t("wizard.identity_sub"))}</p>
      <div class="wiz-field"><label>${esc(t("wizard.user_name"))}</label>
        <input class="input" id="wiz-username" placeholder="…" maxlength="24"/></div>
      <div class="wiz-field"><label>${esc(t("wizard.ai_name"))}</label>
        <input class="input" id="wiz-name" value="WormGPT" maxlength="32"/></div>`;
    $("wiz-name").value = WIZ.aiName;
    $("wiz-username").value = WIZ.userName;
    $("wiz-username").addEventListener("input", () => { WIZ.userName = $("wiz-username").value; });
    $("wiz-name").addEventListener("input", () => { WIZ.aiName = $("wiz-name").value; });
    setTimeout(() => $("wiz-username").focus(), 50);
  } else if (WIZ.step === 2) {
    // ---- écran 3 : apparence + performance -------------------------
    body.innerHTML = `
      <h3 style="margin-bottom:4px">${esc(t("wizard.appearance_step"))}</h3>
      <p class="muted" style="margin-bottom:18px">${esc(t("wizard.appearance_sub"))}</p>
      <div class="wiz-field"><label>${esc(t("settings.accent"))}
        <span class="set-note">${esc(t("settings.accent.d"))}</span></label>
        <div class="accent-row" id="wiz-accent">${ACCENTS.map((c) =>
          `<button class="accent-dot${WIZ.ui.accent === c ? " on" : ""}" data-accent="${c}" style="background:${c}"></button>`).join("")}</div></div>
      <div class="wiz-field"><label>${esc(t("settings.particles"))}</label>
        <button class="switch ${WIZ.ui.particles ? "on" : ""}" id="wiz-part"></button></div>
      <div class="wiz-field"><label>${esc(t("settings.glass"))}</label>
        <button class="switch ${WIZ.ui.glass ? "on" : ""}" id="wiz-glass"></button></div>
      <div class="wiz-field"><label>${esc(t("settings.context"))}
        <span class="set-note">${esc(t("settings.context_note"))}</span></label>
        <select class="input" id="wiz-ctx">${[2048, 4096, 8192, 16384, 32768]
          .map((n) => `<option value="${n}"${WIZ.engine.n_ctx === n ? " selected" : ""}>${n} tokens</option>`).join("")}</select></div>
      <div class="wiz-field"><label>${esc(t("settings.threads"))}
        <span class="set-note">${esc(t("settings.threads_note"))}</span></label>
        <input class="input" id="wiz-threads" type="number" min="0" max="64"
               value="${Number(WIZ.engine.n_threads) || 0}"/></div>`;
    body.querySelectorAll("#wiz-accent .accent-dot").forEach((b) =>
      b.addEventListener("click", () => {
        WIZ.ui.accent = b.dataset.accent;
        body.querySelectorAll("#wiz-accent .accent-dot").forEach((d) =>
          d.classList.toggle("on", d === b));
        wizPreviewUi();
      }));
    $("wiz-part").addEventListener("click", () => {
      WIZ.ui.particles = !WIZ.ui.particles;
      $("wiz-part").classList.toggle("on", WIZ.ui.particles);
      wizPreviewUi();
    });
    $("wiz-glass").addEventListener("click", () => {
      WIZ.ui.glass = !WIZ.ui.glass;
      $("wiz-glass").classList.toggle("on", WIZ.ui.glass);
      wizPreviewUi();
    });
    $("wiz-ctx").addEventListener("change", () => {
      WIZ.engine.n_ctx = Number($("wiz-ctx").value) || 4096;
    });
    $("wiz-threads").addEventListener("change", () => {
      WIZ.engine.n_threads = Number($("wiz-threads").value) || 0;
    });
  } else if (WIZ.step === 3) {
    // ---- écran 4 : modèle ------------------------------------------
    body.innerHTML = `<div class="wiz-field"><label>${esc(t("wizard.choose_model"))}</label>
      <div class="wiz-models" id="wiz-models"></div></div>`;
    API.get_catalog().then((cat) => {
      const box = $("wiz-models");
      cat.forEach((m) => {
        const div = document.createElement("div");
        div.className = "wiz-model" + (m.name === WIZ.tier ? " sel" : "");
        div.innerHTML = `<div class="t"><b>${esc(m.name)}</b>
          <span class="badge pow">${esc(m.power)}</span>
          ${m.recommended ? `<span class="badge rec">${esc(t("models.recommended"))}</span>` : ""}
          ${m.installed ? `<span class="badge inst">${esc(t("models.installed"))}</span>` : ""}
          </div>
          <div class="m">${esc(m.params)} · ${esc(m.size)} · ${esc(m.ram)}</div>
          <div class="d">${esc(m.desc)}</div>`;
        div.addEventListener("click", () => {
          WIZ.tier = m.name;
          box.querySelectorAll(".wiz-model").forEach((e) => e.classList.remove("sel"));
          div.classList.add("sel");
        });
        box.appendChild(div);
      });
    });
  } else if (WIZ.step === 4) {
    // ---- écran 5 : personnalité + clé cloud xKiro (optionnel) -----
    body.innerHTML = `
      <h3 style="margin-bottom:4px">${esc(t("wizard.persona_step"))}</h3>
      <p class="muted" style="margin-bottom:18px">${esc(t("wizard.persona_sub"))}</p>
      <div class="wiz-field"><label>${esc(t("wizard.preset"))}</label>
        <select class="input" id="wiz-preset"></select></div>
      <div class="wiz-field"><label>${esc(t("wizard.prompt_preview"))}</label>
        <textarea class="input" id="wiz-prompt" readonly rows="8"></textarea></div>
      <div class="wiz-field"><label>${esc(t("tools.title"))}
        <span class="set-note">${esc(t("wizard.agent_note"))}</span></label>
        <div style="display:flex;gap:8px;align-items:center">
          <button class="switch ${WIZ.agent ? "on" : ""}" id="wiz-agent"></button>
          <select class="input" id="wiz-agent-mode" style="flex:1">
            <option value="ask"${WIZ.agentMode === "ask" ? " selected" : ""}>${esc(t("tools.mode_ask"))}</option>
            <option value="auto"${WIZ.agentMode === "auto" ? " selected" : ""}>${esc(t("tools.mode_auto"))}</option>
          </select></div></div>
      <div class="wiz-field" style="margin-top:14px;padding-top:14px;border-top:1px solid rgba(255,255,255,.07)">
        <label>${esc(t("wizard.api_step"))}</label>
        <p class="muted" style="font-size:11px;margin:2px 0 8px">${esc(t("wizard.api_step.d"))}</p>
        <div style="display:flex;gap:8px">
          <input class="input mono" id="wiz-xkiro-key" type="password" placeholder="sk-xt-…" autocomplete="off" style="flex:1"/>
          <button class="btn sm" id="wiz-xkiro-test">${esc(t("settings.api.load"))}</button>
        </div>
        <span class="set-status" id="wiz-xkiro-msg"></span>
      </div>`;
    const agSw = $("wiz-agent");
    if (agSw) {
      agSw.addEventListener("click", () => {
        WIZ.agent = !WIZ.agent;
        agSw.classList.toggle("on", WIZ.agent);
      });
      $("wiz-agent-mode").addEventListener("change", () => {
        WIZ.agentMode = $("wiz-agent-mode").value;
      });
    }
    const testBtn = $("wiz-xkiro-test");
    // auto-test : coller la clé suffit (blur déclenche le test + sauvegarde)
    const wizKey = $("wiz-xkiro-key");
    wizKey.addEventListener("change", () => {
      if ((wizKey.value || "").trim()) testBtn.click();
    });
    testBtn.addEventListener("click", async () => {
      const key = ($("wiz-xkiro-key").value || "").trim();
      const msg = $("wiz-xkiro-msg");
      if (!key) { msg.textContent = t("settings.api.fail").replace("{err}", "key required");
                  msg.style.color = "var(--err)"; return; }
      msg.textContent = t("settings.api.testing");
      msg.style.color = "var(--muted-2)";
      const r = await API.test_provider("xkiro", { enabled: true,
        base_url: "https://api.xkiro.com/v1", api_key: key, model: "" });
      if (r && r.ok) {
        await API.save_settings({ providers: { xkiro: { enabled: true,
          base_url: "https://api.xkiro.com/v1", api_key: key, model: "" } } });
        msg.textContent = t("settings.api.test_ok").replace("{n}", String(r.count));
        msg.style.color = "var(--ok)";
        WIZ.xkiroSaved = true;
      } else {
        msg.textContent = t("settings.api.fail").replace("{err}", (r && r.error) || "?");
        msg.style.color = "var(--err)";
      }
    });
    const sel = $("wiz-preset");
    WIZ.presets.forEach((p) => sel.add(new Option(p.name, p.key)));
    sel.value = WIZ.preset;
    sel.addEventListener("change", () => {
      WIZ.preset = sel.value;
      const p = WIZ.presets.find((x) => x.key === WIZ.preset);
      if (p) $("wiz-prompt").value = p.text;
    });
    const p0 = WIZ.presets.find((x) => x.key === WIZ.preset);
    $("wiz-prompt").value = p0 ? p0.text : "";
  } else {
    // ---- écran 6 : récapitulatif ----------------------------------
    const preset = WIZ.presets.find((x) => x.key === WIZ.preset);
    body.innerHTML = `
      <div class="wiz-hero">
        <img src="/assets/logo_128.png" alt=""/>
        <h2>${esc(t("wizard.finish_title"))}</h2>
        <p>${esc(t("wizard.finish_sub"))}</p>
      </div>
      <div class="wiz-recap">
        <div class="recap-row"><span>${esc(t("wizard.user_name"))}</span><b>${esc(WIZ.userName || "—")}</b></div>
        <div class="recap-row"><span>${esc(t("wizard.ai_name"))}</span><b>${esc(WIZ.aiName)}</b></div>
        <div class="recap-row"><span>${esc(t("wizard.language"))}</span><b>${esc(WIZ.lang.toUpperCase())}</b></div>
        <div class="recap-row"><span>${esc(t("wizard.row_model"))}</span><b>${esc(WIZ.tier)}</b></div>
        <div class="recap-row"><span>${esc(t("wizard.preset"))}</span><b>${esc(preset ? preset.name : WIZ.preset)}</b></div>
        <div class="recap-row"><span>${esc(t("settings.accent"))}</span>
          <b><span class="accent-dot on" style="background:${esc(WIZ.ui.accent)}"></span></b></div>
        <div class="recap-row"><span>${esc(t("settings.context"))}</span><b>${esc(String(WIZ.engine.n_ctx))} tokens</b></div>
        <div class="recap-row"><span>${esc(t("settings.threads"))}</span><b>${WIZ.engine.n_threads ? esc(String(WIZ.engine.n_threads)) : esc(t("settings.threads_note"))}</b></div>
      </div>`;
  }
}
$("wiz-back").addEventListener("click", () => { WIZ.step--; renderWizard(); });
$("wiz-next").addEventListener("click", async () => {
  if (WIZ.step === 1) {
    WIZ.aiName = ($("wiz-name").value || "WormGPT").trim();
    WIZ.userName = ($("wiz-username").value || "").trim();
  }
  if (WIZ.step === 2) wizPreviewUi();   // on garde l'aperçu choisi
  if (WIZ.step < WIZ_LAST) { WIZ.step++; renderWizard(); return; }
  await API.finish_setup({ language: WIZ.lang, user_name: WIZ.userName,
                           ai_name: WIZ.aiName, preset: WIZ.preset,
                           tier: WIZ.tier, ui: WIZ.ui, engine: WIZ.engine,
                           agent: WIZ.agent, agentMode: WIZ.agentMode });
  location.reload();
});

/* ---------- application ---------- */
function appInit() {
  S.msgs = [];
  S.settings = S.settings || {};
  document.querySelectorAll(".nav-item").forEach((el) => {
    el.querySelector(".ni-ico").innerHTML = ic(el.dataset.view, 16);
    el.addEventListener("click", () => nav(el.dataset.view));
  });
  $("btn-send").addEventListener("click", sendMsg);
  $("btn-attach").addEventListener("click", pickImage);
  $("btn-img").addEventListener("click", openImgCard);
  $("genimg-close").addEventListener("click", closeImgCard);
  $("genimg-go").innerHTML = ic("send", 16);
  $("genimg-go").addEventListener("click", launchImageGen);
  $("genimg-prompt").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); launchImageGen(); }
  });
  $("genimg-opts-toggle").addEventListener("click", () =>
    $("genimg-adv").classList.toggle("hidden"));
  // fermeture fiable de la carte image : croix, Échap, clic à l'extérieur
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !$("genimg-card").classList.contains("hidden"))
      closeImgCard();
  });
  document.addEventListener("click", (e) => {
    const card = $("genimg-card");
    if (card && !card.classList.contains("hidden") &&
        !e.target.closest("#genimg-card") && !e.target.closest("#btn-img"))
      closeImgCard();
  });
  startParticles();
  $("btn-new").addEventListener("click", () => API.clear_chat());
  $("btn-newchat").innerHTML = ic("plus", 15);
  $("btn-newchat").addEventListener("click", () => API.new_conversation());
  $("model-pill").addEventListener("click", () => nav("models"));
  $("model-bar").addEventListener("click", () => nav("models"));
  $("conv-filter").addEventListener("input", renderConvs);
  $("input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMsg(); }
  });
  // bouton « nouvelle conversation » : vide le chat localement puis côté core
  $("btn-new").addEventListener("click", () => {
    S.msgs = []; S.curMsg = null; S.pendingSend = false;
    if (S.view === "chat") renderChat();
    API.new_conversation();
    renderConvs();
  });
  $("input").addEventListener("input", () => autoGrow($("input")));
  // tableau de bord : rafraîchir les mesures / remettre les compteurs à zéro
  $("specs-refresh").addEventListener("click", () => renderSpecs());
  $("specs-reset").addEventListener("click", () => {
    askConfirm(t("specs.reset"), t("specs.reset.confirm"), "", async (ok) => {
      if (!ok) return;
      await API.reset_stats();
      renderSpecs();
    });
  });
  $("btn-search").addEventListener("click", async () => {
    const r = await API.toggle_search();
    S.searchOn = r.on;
    syncModes();
  });
  $("model-select").addEventListener("click", async () => {
    const menu = $("model-menu");
    if (!menu.classList.contains("hidden")) { menu.classList.add("hidden"); return; }
    await renderModelMenu();
    menu.classList.remove("hidden");
  });
  document.addEventListener("click", (e) => {
    ["model-menu"].forEach((mid) => {
      const m = $(mid);
      if (!m.classList.contains("hidden") &&
          !e.target.closest("#model-select") && !e.target.closest("#" + mid))
        m.classList.add("hidden");
    });
    if (!$("settings-overlay").classList.contains("hidden") &&
        e.target.id === "settings-overlay")
      closeSettings();
  });
  $("img-cancel").addEventListener("click", closeModal);
  $("img-go").addEventListener("click", async () => {
    const prompt = $("img-prompt").value.trim();
    if (!prompt) return;
    closeModal();
    await API.generate_image(prompt, $("img-size").value, $("img-steps").value);
  });
  $("img-install").addEventListener("click", () => API.install_image_engine());
  $("settings-close").addEventListener("click", closeSettings);
  $("cf-no").addEventListener("click", () => respondConfirm(false));
  $("cf-yes").addEventListener("click", () => respondConfirm(true));
  nav("home");
  renderHome();
  renderModels();
  pullLoop();
  updateModelBar();
}

function nav(view) {
  S.view = view;
  document.querySelectorAll(".nav-item").forEach((el) =>
    el.classList.toggle("active", el.dataset.view === view));
  if (view === "settings") { openSettings(); return; }
  ["home", "chat", "models", "specs"].forEach((v) =>
    $("view-" + v).classList.toggle("hidden", v !== view));
  if (view === "home") renderHome();
  if (view === "chat") renderChat();
  if (view === "models") renderModels();
  if (view === "specs") renderSpecs();
}
function openSettings() {
  renderSettings();
  $("settings-overlay").classList.remove("hidden");
}
function closeSettings() {
  $("settings-overlay").classList.add("hidden");
  // restaure la surbrillance de la vue réellement affichée
  document.querySelectorAll(".nav-item").forEach((el) =>
    el.classList.toggle("active", el.dataset.view === S.view));
}

/* ---------- historique (sidebar) ---------- */
let CONVS = [];
function convDate(ts) {
  try {
    return new Date(ts * 1000).toLocaleDateString([], {day: "2-digit", month: "short"});
  } catch (e) { return ""; }
}
function renderConvs() {
  API.list_conversations().then((list) => {
    CONVS = list || [];
    const q = ($("conv-filter").value || "").toLowerCase();
    const box = $("conv-list");
    const items = CONVS.filter((c) => !q || (c.title || "").toLowerCase().includes(q));
    if (!items.length) {
      box.innerHTML = `<div class="conv-empty">${esc(t("conv.empty"))}</div>`;
      return;
    }
    box.innerHTML = items.map((c) =>
      `<button class="conv-item ${c.id === S.sessId ? "is-active" : ""}" data-cid="${esc(c.id)}">
        <span class="conv-ico">${ic("chat", 15)}</span>
        <span class="conv-main"><span class="conv-title">${esc(c.title)}</span>
        <span class="conv-date">${esc(convDate(c.date))}</span></span>
        <span class="conv-del" data-del="${esc(c.id)}" title="${esc(t("conv.delete"))}">${ic("trash", 13)}</span>
      </button>`).join("");
    box.querySelectorAll(".conv-item").forEach((b) =>
      b.addEventListener("click", (e) => {
        if (e.target.closest(".conv-del")) return;  // clic sur la poubelle
        S.sessId = b.dataset.cid;
        API.load_conversation(b.dataset.cid);
        renderConvs();
        nav("chat");
      }));
    box.querySelectorAll(".conv-del").forEach((b) =>
      b.addEventListener("click", (e) => {
        e.stopPropagation();
        const cid = b.dataset.del;
        const conv = CONVS.find((c) => c.id === cid);
        askConfirm(t("conv.delete"),
          t("conv.delete_confirm").replace("{title}",
            (conv && conv.title ? conv.title.slice(0, 40) : cid)),
          "", async () => {
            await API.delete_conversation(cid);
            if (S.sessId === cid) S.sessId = "";
            renderConvs();
          });
      }));
  });
}
let _convTimer = null;
function refreshConvsSoon() {
  clearTimeout(_convTimer);
  _convTimer = setTimeout(renderConvs, 900);
}

/* ---------- accueil ---------- */
function renderHome() {
  const feat = [
    ["lock", "feat.privacy.t", "feat.privacy.d"], ["sliders", "feat.depth.t", "feat.depth.d"],
    ["code", "feat.code.t", "feat.code.d"], ["bolt", "feat.fast.t", "feat.fast.d"],
    ["box", "feat.library.t", "feat.library.d"], ["target", "feat.ethical.t", "feat.ethical.d"],
    ["dolphin", "feat.dolphin.t", "feat.dolphin.d"],
  ];
  const uname = userName() || "";
  $("view-home").innerHTML = `
    <div class="hero">
      <img src="/assets/logo_128.png" alt=""/>
      <h1>Worm<span>GPT</span></h1>
      <div class="tag">${esc(t("brand.tagline"))}</div>
      ${uname ? `<div class="greet">${esc(t("welcome.hello"))}, <b>${esc(uname)}</b></div>` : ""}
      <p>${esc(t("home.desc"))}</p>
      <div class="hero-actions">
        <button class="btn primary" id="hero-chat">${esc(t("home.open_chat"))}</button>
        <button class="btn" id="hero-models">${esc(t("home.download_model"))}</button>
      </div>
      <div class="hero-trust">
        <span>${ic("lock")} ${esc(t("home.trust1"))}</span>
        <span>${ic("shield")} ${esc(t("home.trust2"))}</span>
        <span>${ic("monitor")} ${esc(t("home.trust3"))}</span>
      </div>
    </div>
    <div class="f-head"><div class="sec">${esc(t("home.capabilities"))}</div>
      <h2>${esc(t("home.features"))}</h2>
      <p>${esc(t("home.features_sub"))}</p></div>
    <div class="features">
      ${feat.map(([n, a, b]) =>
        `<div class="fcard"><div class="fic">${ic(n, 17)}</div><h3>${esc(t(a))}</h3><p>${esc(t(b))}</p></div>`).join("")}
    </div>
    <div class="home-pills">
      <span>${esc(t("home.pill1"))}</span><span>${esc(t("home.pill2"))}</span><span>${esc(t("home.pill3"))}</span>
    </div>`;
  $("hero-chat").addEventListener("click", () => nav("chat"));
  $("hero-models").addEventListener("click", () => nav("models"));
}

/* ---------- chat ---------- */
function renderTextHTML(text) {
  const parts = String(text).split(/```/);
  let html = "";
  for (let i = 0; i < parts.length; i++) {
    if (!parts[i]) continue;
    if (i % 2 === 1) {
      const lines = parts[i].split("\n");
      const lang = lines[0] && !lines[0].includes(" ") ? esc(lines[0].trim()) : "";
      const code = (lines[0] === lang ? lines.slice(1) : lines).join("\n");
      html += `<div class="codeblock"><div class="cb-head"><span>${lang || "code"}</span>
        <button class="cb-copy">${esc(t("chat.copy"))}</button></div>
        <pre><code>${esc(code)}</code></pre></div>`;
    } else {
      html += esc(parts[i]).replace(/\n/g, "<br/>");
    }
  }
  return html;
}
function bindCopy(container) {
  container.querySelectorAll(".cb-copy").forEach((b) =>
    b.addEventListener("click", () => {
      navigator.clipboard.writeText(b.parentElement.nextElementSibling.textContent)
        .then(() => toast(t("chat.copy")));
    }));
  container.querySelectorAll(".msg-copy").forEach((b) =>
    b.addEventListener("click", () => {
      navigator.clipboard.writeText(b.dataset.text || "")
        .then(() => { b.classList.add("is-copied"); toast(t("chat.copy"));
                      setTimeout(() => b.classList.remove("is-copied"), 1500); });
    }));
}
function renderChat() {
  const sc = $("chat-scroll");
  if (!S.msgs.length) {
    const uname = userName();
    sc.innerHTML = `<div class="empty-state">
      <img class="ambient" src="/assets/logo_160.png" alt=""/>
      <h2>Worm<span>GPT</span></h2>
      <div class="tagline">${uname ? `${esc(t("welcome.hello"))}, <b style="color:var(--accent)">${esc(uname)}</b>` : esc(t("brand.tagline"))}</div>
      <div class="sub">${esc(t("chat.empty_sub"))}</div>
      <div class="pillars">${esc(t("home.pill1"))} · ${esc(t("home.pill2"))} · ${esc(t("home.pill3"))}</div>
      <button class="btn" id="empty-models">${esc(t("chat.go_models"))}</button></div>`;
    const b = $("empty-models");
    if (b) b.addEventListener("click", () => nav("models"));
    return;
  }
  sc.innerHTML = S.msgs.map((m, i) => {
    if (m.kind === "system" || m.kind === "error")
      return `<div class="msg"><div class="avatar">•</div><div class="msg-body"><div class="who"><b>WORMGPT</b></div>
              <div class="${m.kind === "error" ? "err" : "sys"}">${esc(m.text)}</div></div></div>`;
    const tme = m.time ? new Date(m.time).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"}) : "";
    const lat = m.latency ? ` · ${(m.latency / 1000).toFixed(1)} s` : "";
    const tps = m.tps ? ` <span class="tps">· ${esc(t("chat.tps").replace("{tok}", m.tps.toFixed(1)))}</span>` : "";
    const meta = `<div class="msg-meta"><span class="msg-time">${esc(tme)}</span>` +
      (m.latency ? `<span class="msg-latency">${esc(lat)}${tps}</span>` : "") +
      (m.kind === "ai" && !m.thinking ? `<button class="msg-action msg-copy">${esc(t("chat.copy"))}</button>` : "") +
      `</div>`;
    const head = `<div class="who"><b>${m.kind === "user" ? esc(t("chat.you")) : esc(S.settings.ai_name || "WormGPT")}</b>` +
      (m.kind === "ai" && !m.thinking ? `<span class="msg-label">${esc(S.settings.model || "WormGPT")}</span>` : "") +
      `</div>`;
    const reason = m.reasoning ? `<details class="reason" ${m.reasonOpen ? "open" : ""}>
        <summary>${esc(t("reason.label"))}</summary><pre>${esc(m.reasoning)}</pre></details>` : "";
    const img = m.image ? `<img class="inline" src="${m.image}"/>` : "";
    const genwait = (m.genimg && !m.image)
      ? `<div class="bubble genimg-wait"><span class="skel-ring skel-ring--sm"></span>${esc(t("image.running"))}</div>` : "";
    const body = m.kind === "user"
      ? `<div class="bubble">${esc(m.text)}</div>${img}`
      : genwait
        ? genwait
        : m.thinking
        ? `<div class="bubble thinking"><span class="dots"><i></i><i></i><i></i></span>${esc(t("chat.thinking"))}</div>`
        : `${reason}${img}<div class="bubble">${renderTextHTML(m.text)}</div>`;
    const avatar = m.kind === "user"
      ? `<div class="avatar">${esc((t("chat.you") || "U")[0])}</div>`
      : `<div class="avatar"><img class="msg-avatar__mark" src="/assets/logo_28.png" alt=""/></div>`;
    return `<div class="msg ${m.kind}">${avatar}<div class="msg-body">${head}${meta}${body}</div></div>`;
  }).join("");
  sc.querySelectorAll(".msg-copy").forEach((b, j) => {
    const mi = [...sc.querySelectorAll(".msg")].indexOf(b.closest(".msg"));
    const mm = S.msgs[mi];
    if (mm) b.dataset.text = mm.text || "";
  });
  bindCopy(sc);
  sc.scrollTop = sc.scrollHeight;
  // Le chat est ré-rendu à CHAQUE token : sans mémoriser l'état du <details>
  // dans le message, le bloc Raisonnement se refermait tout seul pendant le
  // streaming (impossible à lire). On persiste donc la bascule.
  sc.querySelectorAll(".reason summary").forEach((s) =>
    s.addEventListener("click", () => {
      const msgEl = s.closest(".msg");
      const idx = [...sc.querySelectorAll(".msg")].indexOf(msgEl);
      const m = S.msgs[idx];
      if (m) m.reasonOpen = !m.reasonOpen;
    }));
}
function sendMsg() {
  const input = $("input");
  const text = input.value.trim();
  if ((!text && !S.attachB64) || S.generating) return;
  input.value = "";
  autoGrow(input);
  // rendu optimiste : le message apparaît immédiatement, même sans modèle
  S.sendTime = Date.now();
  S.msgs.push({ kind: "user", text: text,
                image: S.attachB64 ? "data:image/png;base64," + S.attachB64 : "",
                time: S.sendTime });
  S.msgs.push({ kind: "ai", thinking: true, text: "", reasoning: "",
                closed: false, time: S.sendTime });
  if (S.view === "chat") renderChat();
  const b64 = S.attachB64, nm = S.attachName;
  S.attachB64 = null; S.attachName = "";
  $("attach-row").innerHTML = "";
  S.pendingSend = true;
  API.send_chat(text, b64 || null, nm || "");
}
function autoGrow(el) {
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 160) + "px";
}

/* ---------- sélecteur de modèle (menu au-dessus du composer) ---------- */
async function renderModelMenu() {
  const box = $("model-menu-list");
  box.innerHTML = "";
  const cat = await API.get_catalog();
  const installed = cat.filter((m) => m.installed);
  if (!installed.length) {
    box.innerHTML = `<div class="conv-empty">${esc(t("chat.no_models_installed"))}</div>`;
    return;
  }
  installed.forEach((m) => {
    const b = document.createElement("button");
    b.className = "mm-item" + (m.active ? " on" : "");
    b.innerHTML = `<span><b>${esc(m.name)}</b> <span class="mm-sub">· ${esc(m.power)}</span></span>` +
      (m.active ? `<span class="mm-check">✓</span>` : "");
    b.addEventListener("click", async () => {
      $("model-menu").classList.add("hidden");
      await API.select_model(m.name);
    });
    box.appendChild(b);
  });
}
function pickImage() {
  const inp = document.createElement("input");
  inp.type = "file"; inp.accept = "image/*";
  inp.onchange = () => {
    const f = inp.files[0];
    if (!f) return;
    const rd = new FileReader();
    rd.onload = () => {
      S.attachB64 = rd.result.split(",")[1];
      S.attachName = f.name;
      $("attach-row").innerHTML =
        `<div class="attach-chip">${ic("clip", 13)} ${esc(f.name)}
         <button onclick="S.attachB64=null;S.attachName='';this.parentElement.remove()">×</button></div>`;
    };
    rd.readAsDataURL(f);
  };
  inp.click();
}

/* ---------- modèles ---------- */
let MODEL_FILTER = "all";
/* ---------- spécifications & performances ---------- */
function meter(pct, cls) {
  const v = Math.max(0, Math.min(100, Number(pct) || 0));
  return `<div class="meter ${cls || ""}"><i style="width:${v}%"
            class="${v >= 90 ? "hot" : v >= 70 ? "warm" : ""}"></i></div>`;
}
function bigStat(label, value, sub) {
  return `<div class="stat"><div class="stat-v">${esc(String(value))}</div>
    <div class="stat-l">${esc(label)}</div>
    ${sub ? `<div class="stat-s">${esc(sub)}</div>` : ""}</div>`;
}
function clockOf(ts) {
  if (!ts) return "";
  try { return new Date(ts * 1000).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit", second: "2-digit"}); }
  catch (e) { return ""; }
}
function renderSpecs() {
  $("specs-title").textContent = t("specs.title");
  $("specs-sub").textContent = t("specs.sub");
  $("specs-refresh").textContent = t("specs.refresh");
  $("specs-reset").textContent = t("specs.reset");
  const body = $("specs-body");
  body.innerHTML = `<div class="specs-empty">${esc(t("specs.loading"))}</div>`;
  API.get_stats().then(renderSpecsData).catch(() => {
    body.innerHTML = `<div class="specs-empty">${esc(t("specs.error"))}</div>`;
  });
}
function renderSpecsData(st) {
  const body = $("specs-body");
  if (!st) return;
  const live = st.live || {}, eng = st.engine || {}, disk = st.disk || {};
  const gpu = live.gpu;
  const up = st.since ? Math.max(1, Math.round((Date.now() / 1000 - st.since) / 60)) : 0;
  const fmtMin = (m) => m >= 60 ? `${Math.floor(m / 60)} h ${m % 60} min` : `${m} min`;

  const engineCard = `<div class="spec-card">
    <h4>${esc(t("specs.engine"))}</h4>
    <div class="row"><span>${esc(t("models.using"))}</span><b>${esc(eng.model || "—")}</b></div>
    <div class="row"><span>${esc(t("specs.state"))}</span>
      <b class="${eng.state === "ready" ? "ok" : "muted"}">${esc(eng.text || eng.state || "—")}</b></div>
    <div class="row"><span>${esc(t("specs.filesize"))}</span><b>${eng.file_gb ? esc(eng.file_gb + " GB") : "—"}</b></div>
    <div class="row"><span>${esc(t("specs.loadtime"))}</span><b>${eng.load_seconds ? esc(eng.load_seconds + " s") : "—"}</b></div>
    <div class="row"><span>${esc(t("specs.uptime"))}</span><b>${esc(fmtMin(up))}</b></div>
  </div>`;

  const cpu = live.cpu_percent ?? 0;
  const ramPct = live.ram_percent ?? 0;
  const gpuLoad = gpu && gpu.load != null ? Math.round(gpu.load) : null;
  const vramTotal = gpu && gpu.vram_total_mb ? Math.round(gpu.vram_total_mb) : 0;
  const vramUsed = gpu && gpu.vram_used_mb != null ? Math.round(gpu.vram_used_mb) : null;
  const gpuCard = gpu && gpu.name ? `<div class="stat-wide">
      <div class="row"><span>${esc(gpu.name)}</span><b>${gpuLoad != null ? gpuLoad + "%" : "—"}</b></div>
      ${gpuLoad != null ? meter(gpuLoad) : ""}
      ${vramTotal ? `<div class="row"><span>VRAM</span><b>${vramUsed != null ? vramUsed + " / " : ""}${gpu.vram_approx ? "≈" : ""}${vramTotal} MB</b></div>` : ""}
      ${vramTotal && vramUsed != null ? meter(100 * vramUsed / vramTotal) : ""}
      ${gpu.temp_c != null ? `<div class="row"><span>${esc(t("specs.temp"))}</span><b>${esc(String(gpu.temp_c))} °C</b></div>` : ""}
    </div>` : `<div class="stat-wide muted">${esc(t("specs.nogpu"))}</div>`;

  const hwCard = `<div class="spec-card">
    <h4>${esc(t("specs.hardware"))}</h4>
    <div class="row"><span>CPU (${esc(String(live.cpu_cores || "?"))} cores)</span><b>${esc(String(cpu))}%</b></div>
    ${meter(cpu)}
    <div class="row"><span>RAM</span><b>${esc(String(live.ram_used_gb ?? 0))} / ${esc(String(live.ram_total_gb ?? 0))} GB</b></div>
    ${meter(ramPct)}
    ${gpuCard}
    <div class="row"><span>${esc(t("specs.process"))}</span><b>${esc(String(live.proc_mb ?? 0))} MB</b></div>
    <div class="row"><span>${esc(t("specs.disk"))}</span><b>${esc(String(disk.free_gb ?? 0))} GB ${esc(t("specs.free"))}</b></div>
    <div class="row"><span>${esc(t("specs.modelsdisk"))}</span><b>${esc(String(disk.models_gb ?? 0))} GB</b></div>
  </div>`;

  const sessionCard = `<div class="spec-card">
    <h4>${esc(t("specs.session"))}</h4>
    <div class="stats-row">
      ${bigStat(t("specs.turns"), st.turns ?? 0)}
      ${bigStat(t("specs.tokens"), st.tokens ?? 0)}
      ${bigStat(t("specs.avgtime"), (st.avg_seconds ?? 0) + " s")}
      ${bigStat(t("specs.avgtokens"), st.avg_tokens ?? 0)}
      ${bigStat(t("specs.avgtps"), st.avg_tps ?? 0)}
    </div>
    <div class="row"><span>${esc(t("specs.mostused"))}</span><b>${esc(st.most_used || "—")}</b></div>
    <div class="row"><span>${esc(t("specs.lastturn"))}</span><b>${esc(clockOf(st.last_turn) || "—")}</b></div>
  </div>`;

  const rows = (st.models || []).map((m) => `<tr>
      <td>${esc(m.name)}</td><td>${esc(String(m.turns))}</td>
      <td>${esc(String(m.tokens))}</td>
      <td>${esc(String(m.avg_seconds))} s</td>
      <td>${esc(String(m.avg_tps))}</td>
      <td>${esc(clockOf(m.last_used))}</td></tr>`).join("");
  const modelCard = `<div class="spec-card wide">
    <h4>${esc(t("specs.permdev"))}</h4>
    ${rows ? `<table class="specs-table"><thead><tr>
        <th>${esc(t("specs.model"))}</th><th>${esc(t("specs.turns"))}</th>
        <th>${esc(t("specs.tokens"))}</th><th>${esc(t("specs.avgtime"))}</th>
        <th>tok/s</th><th>${esc(t("specs.lastused"))}</th>
      </tr></thead><tbody>${rows}</tbody></table>`
      : `<div class="muted">${esc(t("specs.nodata"))}</div>`}
  </div>`;

  const inst = (st.installed || []).map((m) => `<div class="disk-row">
      <b>${esc(m.name)}</b><span class="muted">${esc(m.base)}${m.params ? " · " + esc(m.params) : ""}</span>
      <span class="tag">${esc(m.size)}</span><span class="tag">${esc(m.ram)}</span></div>`).join("");
  const dlCard = `<div class="spec-card wide">
    <h4>${esc(t("specs.installed"))} <span class="muted">(${(st.installed || []).length}/${st.catalog_total || 0})</span></h4>
    ${inst || `<div class="muted">${esc(t("specs.noinstalled"))}</div>`}
  </div>`;

  const logs = (st.log || []).slice().reverse().map((l) => `<div class="log-line ${esc(l.level || "info")}">
      <span class="log-t">${esc(clockOf(l.t))}</span>${esc(l.text)}</div>`).join("");
  const logCard = `<div class="spec-card wide">
    <h4>${esc(t("specs.logs"))}</h4>
    <div class="log-box">${logs || `<div class="muted">${esc(t("specs.nodata"))}</div>`}</div>
  </div>`;

  body.innerHTML = engineCard + hwCard + sessionCard + modelCard + dlCard + logCard;
}

function renderModels() {
  // filtres par USAGE (pas des catégories) : ce que le modèle sait faire
  const chips = [["all", t("models.all")], ["chat", t("filter.chat")],
    ["vision", t("filter.vision")], ["image", t("filter.image")],
    ["code", t("filter.code")], ["reason", t("filter.reason")],
    ["api", t("filter.api")]];
  $("model-chips").innerHTML = chips.map(([k, l]) =>
    `<button class="chip ${k === MODEL_FILTER ? "on" : ""}" data-f="${k}">${esc(l)}</button>`).join("");
  $("model-chips").querySelectorAll(".chip").forEach((c) =>
    c.addEventListener("click", () => { MODEL_FILTER = c.dataset.f; renderModels(); }));
  API.get_catalog().then((cat) => {
    S.catalog = cat;
    const inst = cat.filter((m) => m.installed).length;
    $("models-stats").textContent = t("models.total")
      .replace("{n}", String(cat.length))
      .replace("{inst}", String(inst));
    const list = cat.filter((m) => {
      if (MODEL_FILTER === "all") return true;
      if (MODEL_FILTER === "chat") return m.category === "general" || m.category === "dolphin";
      if (MODEL_FILTER === "vision") return m.category === "vision";
      if (MODEL_FILTER === "image") return m.category === "genimg";
      if (MODEL_FILTER === "code") return m.category === "code";
      if (MODEL_FILTER === "reason") return m.category === "reason";
      if (MODEL_FILTER === "api") return m.category === "remote";
      return true;
    });
    $("models-grid").innerHTML = list.map((m) => card(m)).join("");
    $("models-grid").querySelectorAll("[data-act]").forEach((b) =>
      b.addEventListener("click", () => modelAction(b.dataset.act, b.dataset.name)));
    $("models-grid").querySelectorAll("[data-del]").forEach((b) =>
      b.addEventListener("click", () => {
        const name = b.dataset.name;
        const job = (S.progress[name] && S.progress[name].downloading);
        if (job) API.cancel_download(name);   // annule le download en cours
        askConfirm(
          t("models.delete_q").replace("{model}", name),
          t("models.confirm_delete").replace("{model}", name),
          "", async (ok) => {
            if (!ok) return;
            await API.delete_model(name);
            delete S.progress[name];
            renderModels();  // carte retirée immédiatement
          });
      }));
  });
}
function card(m) {
  const p = S.progress[m.name] || {};
  const pct = p.pct || 0;
  const spd = p.speed ? `<b>${p.speed.toFixed(1)} Mo/s</b>` : "";
  const done = p.done_mb ? `${(p.done_mb / 1024).toFixed(1)} Go` : "";
  const prog = m.downloading
    ? `<div class="progress"><div class="fill" style="width:${(pct * 100).toFixed(0)}%"></div><div class="lbl">${(pct * 100).toFixed(0)}%${done ? " · " + done : ""}${spd ? " · " : ""}${spd}</div></div>` : "";
  let action;
  if (m.remote) action = m.active
    ? `<span class="badge active">${esc(t("models.active"))}</span>`
    : `<button class="btn primary sm" data-act="select" data-name="${esc(m.name)}">${esc(t("models.use"))}</button>`;
  else if (m.downloading) action = `<button class="btn sm" data-act="cancel" data-name="${esc(m.name)}">${esc(t("models.cancel"))}</button>`;
  else if (m.active) action = `<span class="badge active">${esc(t("models.active"))}</span>`;
  else if (m.installed) action = `<button class="btn sm" data-act="select" data-name="${esc(m.name)}">${esc(t("models.select"))}</button>`;
  else action = `<button class="btn primary sm" data-act="download" data-name="${esc(m.name)}">${esc(t("models.download"))}</button>`;
  return `<div class="mcard ${m.active ? "active" : ""}">
    <div class="mic">${ic(m.category === "remote" ? "globe" : m.category === "genimg" ? "spark" : m.vision ? "image" : m.category === "dolphin" ? "dolphin" : m.category === "reason" ? "reason" : "chip", 18)}</div>
    <div class="body">
      <div class="t"><b>${esc(m.name)}</b>
        <span class="badge pow">${esc(m.power)}</span>
        <span class="badge cat">${esc(t("cat." + (m.category === "genimg" ? "image" : m.category)))}</span>
        ${m.recommended ? `<span class="badge rec">${esc(t("models.recommended"))}</span>` : ""}
        ${m.installed && !m.remote ? `<span class="badge inst">${esc(t("models.installed"))}</span>` : ""}
        ${m.remote ? `<span class="badge cat">${esc(t("models.cloud"))}</span>
                      <span class="badge warn">${esc(t("models.censored"))}</span>` : ""}
      </div>
      <div class="m">${esc(m.params)} · ${esc(m.size)} · ${esc(m.ram)}${m.vision ? " · " + esc(t("models.vision")) : ""}</div>
      <div class="d">${esc(m.desc)}${m.category === "genimg" || m.category === "vision"
        ? "<br/>" + esc(t("models.cat." + m.category)) : ""}</div>
      ${prog}
    </div>
    <div class="actions">${action}
      ${!m.remote && (m.installed || m.downloading) ? `<button class="btn sm danger" data-del="1" data-name="${esc(m.name)}" title="${esc(t("models.delete"))}">${ic("trash", 14)}</button>` : ""}
    </div>
  </div>`;
}
function modelAction(act, name) {
  if (act === "download") API.download_model(name);
  if (act === "cancel") API.cancel_download(name);
  if (act === "select") API.select_model(name);
}

/* ---------- réglages ---------- */
function renderSettings() {
  const s = S.settings;
  const srv = s.server || {};
  const tools = s.tools || {};
  const img = s.image || {};
  $("settings-body").innerHTML = `
    <div class="set-card"><h3>${esc(t("settings.engine_state"))}</h3>
      <div class="set-row"><label>${esc(t("models.using"))}</label>
        <div class="ctrl"><b id="st-engine-model" class="mono" style="color:var(--accent)">${esc(s.model || t("status.pill_none"))}</b></div></div>
      <div class="set-row"><label>${esc(t("specs.state"))}</label>
        <div class="ctrl muted" id="st-engine-text">${esc((s.engine || {}).text || "—")}</div></div>
      <div class="set-foot"><button class="btn sm" id="st-engine-refresh">${esc(t("specs.refresh"))}</button></div>
    </div>
    <div class="set-card"><h3>${esc(t("settings.general"))}</h3>
      <div class="set-row"><label>${esc(t("settings.user_name"))}</label>
        <div class="ctrl"><input class="input" id="st-uname" value="${esc(s.user_name || "")}" maxlength="24" placeholder="…"/></div></div>
      <div class="set-row"><label>${esc(t("wizard.ai_name"))}</label>
        <div class="ctrl"><input class="input" id="st-name" value="${esc(s.ai_name || "WormGPT")}" maxlength="32"/></div></div>
      <div class="set-row"><label>${esc(t("settings.language"))}</label>
        <div class="ctrl"><select class="input" id="st-lang">
          <option value="fr">Français</option><option value="en">English</option>
          <option value="es">Español</option><option value="de">Deutsch</option></select></div></div>
      <div class="set-foot"><button class="btn primary sm" id="st-save-general">${esc(t("settings.save"))}</button>
        <span class="set-status" id="st-general-msg"></span></div>
    </div>
    <div class="set-card"><h3>${esc(t("settings.assistant"))}</h3>
      <div class="set-row"><label>${esc(t("settings.uncensored"))}<span class="set-note" style="margin:4px 0 0">${esc(t("settings.uncensored.d"))}</span></label>
        <div class="ctrl"><button class="switch ${S.settings.uncensored !== false ? "on" : ""}" id="st-unc-on"></button></div></div>
      <div class="set-row"><label>${esc(t("search.toggle"))}<span class="set-note" style="margin:4px 0 0">${esc(t("search.note"))}</span></label>
        <div class="ctrl"><button class="switch ${s.search ? "on" : ""}" id="st-search-on"></button></div></div>
      <div class="set-row"><label>${esc(t("settings.preset"))}</label>
        <div class="ctrl"><select class="input" id="st-preset"></select></div></div>
      <div class="set-row"><label>${esc(t("settings.system_prompt"))}</label>
        <div class="ctrl"><textarea class="input" id="st-prompt" rows="5"></textarea></div></div>
      <div class="set-row"><label>${esc(t("settings.temperature"))}</label>
        <div class="ctrl"><input type="range" class="range" id="st-temp" min="0" max="1.5" step="0.05"/>
        <span class="muted" id="st-temp-v"></span></div></div>
      <div class="set-row"><label>${esc(t("settings.max_tokens"))}</label>
        <div class="ctrl"><input class="input sm" id="st-maxtok" type="number" min="128" max="8192" step="128"/></div></div>
      <div class="set-foot"><button class="btn primary sm" id="st-save-assistant">${esc(t("settings.save"))}</button>
        <span class="set-status" id="st-assistant-msg"></span></div>
    </div>
    <div class="set-card"><h3>${esc(t("settings.image"))}</h3>
      <div class="set-row"><label>${esc(t("image.enable"))}</label>
        <div class="ctrl"><button class="switch ${img.enabled ? "on" : ""}" id="st-img-on"></button></div></div>
      <div class="set-row"><label>${esc(t("image.url"))}</label>
        <div class="ctrl"><input class="input mono" id="st-img-url" value="${esc(img.url || "http://127.0.0.1:7860")}"/></div></div>
      <div class="set-note">${esc(t("image.note"))}</div>
    </div>
    <div class="set-card"><h3>${esc(t("server.title"))}</h3>
      <div class="set-row"><label>${esc(t("server.enable"))}</label>
        <div class="ctrl"><button class="switch ${srv.enabled ? "on" : ""}" id="st-srv-on"></button>
        <span class="set-status" id="st-srv-status"></span></div></div>
      <div class="set-row"><label>${esc(t("server.port"))}</label>
        <div class="ctrl"><input class="input sm" id="st-srv-port" type="number" value="${srv.port || 1234}"/></div></div>
      <div class="set-note mono" id="st-srv-base">${srv.enabled
        ? esc(t("server.base").replace("{host}", srv.host || "127.0.0.1")
              .replace("{port}", String(srv.port || 1234)))
        : esc(t("server.status_stopped"))}</div>
      <div class="set-note">${esc(t("server.note")
        .replace("{port}", String(srv.port || 1234)))}</div>
    </div>
    <div class="set-card"><h3>${esc(t("tools.title"))}</h3>
      <div class="set-row"><label>${esc(t("tools.enable"))}</label>
        <div class="ctrl"><button class="switch ${tools.enabled ? "on" : ""}" id="st-tools-on"></button></div></div>
      <div class="set-row"><label>${esc(t("tools.mode"))}</label>
        <div class="ctrl"><select class="input" id="st-tools-mode">
          <option value="ask">${esc(t("tools.mode_ask"))}</option>
          <option value="auto">${esc(t("tools.mode_auto"))}</option></select></div></div>
      <div class="set-row"><label>${esc(t("tools.osint"))}
        <span class="set-note" style="margin:4px 0 0">${esc(t("tools.osint.d"))}</span></label>
        <div class="ctrl"><button class="switch ${tools.osint !== false ? "on" : ""}" id="st-osint-on"></button></div></div>
    </div>
    <div class="set-card"><h3>${esc(t("settings.api"))}</h3>
      <div class="set-note">${esc(t("settings.api.d"))}</div>
      <div class="set-note" style="color:var(--accent);opacity:.85">${esc(t("settings.api.xkiro_note"))}</div>
      ${apiProviders().map((p) => `
      <div class="api-block">
        <div class="set-row"><label>${esc(p.label)}</label>
          <div class="ctrl"><button class="switch ${p.enabled ? "on" : ""}" id="st-api-${p.key}-on"></button></div></div>
        <div class="set-row"><label>${esc(t("settings.api.base"))}</label>
          <div class="ctrl"><input class="input mono" id="st-api-${p.key}-url" value="${esc(p.base_url)}"/></div></div>
        <div class="set-row"><label>${esc(t("settings.api.key"))}</label>
          <div class="ctrl"><input class="input mono" type="password" id="st-api-${p.key}-key"
            placeholder="${p.api_key ? esc(t("settings.api.keykeep")) : esc(t("settings.api.keyhint"))}" autocomplete="off"/></div></div>
        <div class="set-row"><label>${esc(t("settings.api.model"))}</label>
          <div class="ctrl"><input class="input mono" id="st-api-${p.key}-model"
            list="dl-${p.key}" value="${esc(p.model || "")}"
            placeholder="${esc(t("settings.api.modelhint"))}"/>
            <datalist id="dl-${p.key}"></datalist></div></div>
        <div class="set-foot">
          <button class="btn sm" id="st-api-${p.key}-load">${esc(t("settings.api.load"))}</button>
          <button class="btn primary sm" id="st-api-${p.key}-save">${esc(t("settings.save"))}</button>
          <span class="set-status" id="st-api-${p.key}-msg"></span></div>
      </div>`).join("")}
    </div>
    <div class="set-card"><h3>${esc(t("settings.personalization"))}</h3>
      <div class="set-row"><label>${esc(t("settings.accent"))}
        <span class="set-note" style="margin:4px 0 0">${esc(t("settings.accent.d"))}</span></label>
        <div class="ctrl"><div class="accent-row">${ACCENTS
          .map((c) => `<button class="accent-dot${(S.settings.ui&&S.settings.ui.accent)===c?" on":""}" data-accent="${c}" style="background:${c}"></button>`).join("")}</div></div></div>
      <div class="set-row"><label>${esc(t("settings.particles"))}</label>
        <div class="ctrl"><button class="switch ${!((S.settings.ui||{}).particles === false) ? "on" : ""}" id="st-part-on"></button></div></div>
      <div class="set-row"><label>${esc(t("settings.particles_speed"))}</label>
        <div class="ctrl"><input type="range" class="range" id="st-part-spd" min="0.2" max="2" step="0.05"/>
        <span class="muted" id="st-part-spd-v"></span></div></div>
      <div class="set-row"><label>${esc(t("settings.glass"))}</label>
        <div class="ctrl"><button class="switch ${((S.settings.ui||{}).glass === false) ? "" : "on"}" id="st-glass-on"></button></div></div>
    </div>
    <div class="set-card"><h3>${esc(t("settings.contact"))}</h3>
      <div class="set-note">${esc(t("settings.contact.d"))}</div>
      <div class="set-row"><label>Discord</label>
        <div class="ctrl"><b class="mono" style="color:var(--accent)">cameleonmortis</b></div></div>
      <div class="set-row"><label>${esc(t("settings.version"))}</label>
        <div class="ctrl muted">${esc(S.version || "")}</div></div>
    </div>
    <div class="set-card"><h3>${esc(t("settings.reset.title"))}</h3>
      <div class="set-row"><label>${esc(t("settings.reset"))}</label>
        <div class="ctrl"><button class="btn danger sm" id="st-reset">${esc(t("settings.reset"))}</button></div></div>
      <div class="set-note">${esc(t("settings.reset.confirm"))}</div>
    </div>
    <div class="set-card"><h3>${esc(t("sys.title"))}</h3>
      <div class="set-row"><label>${esc(t("sys.hardware"))}</label>
        <div class="ctrl muted" id="st-hw"></div></div>
      <div class="set-foot"><button class="btn sm" id="st-reco">${esc(t("sys.apply"))}</button>
        <span class="set-status" id="st-reco-msg"></span></div>
    </div>`;
  $("st-lang").value = s.language || "en";
  const selP = $("st-preset");
  (S.presets || []).forEach((p) => selP.add(new Option(p.name, p.key)));
  selP.value = s.preset;
  $("st-prompt").value = s.system_prompt || "";
  $("st-temp").value = s.temperature ?? 0.7;
  $("st-temp-v").textContent = Number($("st-temp").value).toFixed(2);
  $("st-temp").addEventListener("input", () =>
    $("st-temp-v").textContent = Number($("st-temp").value).toFixed(2));
  $("st-maxtok").value = s.max_tokens || 1024;
  $("st-srv-status").textContent = s.server_running ? t("server.status_running")
    .replace("{host}", srv.host || "127.0.0.1").replace("{port}", String(srv.port || 1234))
    : t("server.status_stopped");
  $("st-srv-status").style.color = s.server_running ? "var(--ok)" : "var(--muted-2)";
  const srvBase = $("st-srv-base");
  if (srvBase) srvBase.textContent = s.server_running
    ? t("server.base").replace("{host}", srv.host || "127.0.0.1")
      .replace("{port}", String(srv.port || 1234))
    : t("server.status_stopped");
  $("st-tools-mode").value = tools.mode || "ask";
  API.system_summary().then((r) => {
    $("st-hw").textContent = r.hardware;
    $("st-hw").dataset.rec = JSON.stringify(r.rec);
  });
  bindSettings();
}
/* Les trois fournisseurs d'API, fusionnés avec ce qui est enregistré. */
function apiProviders() {
  const stored = (S.settings && S.settings.providers) || {};
  const defs = [["xkiro", "xKiro (cloud, free models)"],
                ["openai", "OpenAI / compatible"],
                ["anthropic", "Anthropic (Claude)"],
                ["custom", "Custom (Ollama, LM Studio, vLLM…)"]];
  return defs.map(([key, label]) => Object.assign(
    { key, label, enabled: false, base_url: "", api_key: "", model: "" },
    stored[key] || {},
    key === "xkiro" && !stored[key] ? { base_url: "https://api.xkiro.com/v1" } : {}));
}
function bindSettings() {
  // changement de langue INSTANTANÉ : le select s'applique dès le changement,
  // sans cliquer sur Save et sans relancer l'app
  $("st-lang").addEventListener("change", async () => {
    const lang = $("st-lang").value;
    const r = await API.set_language(lang);
    if (r && r.strings) {
      S.strings = r.strings;
      S.settings = S.settings || {};
      S.settings.language = lang;
      S.lang = lang;
      applyI18n();
      syncModes();
      refreshUserChip();
      renderConvs();
      if (S.view === "chat") renderChat();
      renderSettings();
      if (S.view === "models") renderModels();
    }
  });
  $("st-save-general").addEventListener("click", async () => {
    const lang = $("st-lang").value;
    const name = $("st-name").value.trim() || "WormGPT";
    const uname = $("st-uname").value.trim();
    await API.save_settings({ language: lang, ai_name: name, user_name: uname });
    S.settings.user_name = uname;
    S.settings.ai_name = name;
    S.settings.language = lang;
    refreshUserChip();
    $("st-general-msg").textContent = t("settings.saved");
    $("st-general-msg").style.color = "var(--ok)";
    if (lang !== S.lang) {
      // changement de langue SANS relancer l'app : on récupère la nouvelle
      // table de chaînes et on repeint l'interface en place.
      try {
        const st = await API.init();
        S.strings = st.strings;
        S.settings = st.settings;
        S.lang = lang;
        applyI18n();
        syncModes();
        refreshUserChip();
        renderConvs();
        if (S.view === "chat") renderChat();
        renderSettings();
      } catch (e) {
        location.reload();
      }
    }
  });
  $("st-save-assistant").addEventListener("click", async () => {
    await API.save_settings({
      preset: $("st-preset").value,
      system_prompt: $("st-prompt").value,
      engine: { temperature: Number($("st-temp").value),
                max_tokens: Number($("st-maxtok").value) } });
    $("st-assistant-msg").textContent = t("settings.saved");
    $("st-assistant-msg").style.color = "var(--ok)";
    setTimeout(() => $("st-assistant-msg").textContent = "", 2200);
  });
  const sw = (id, get) => $(id).addEventListener("click", async () => {
    const on = !$(id).classList.contains("on");
    $(id).classList.toggle("on", on);
    await get(on);
  });
  sw("st-unc-on", (on) => API.save_settings({ uncensored: { enabled: on } }));
  sw("st-img-on", (on) => API.save_settings({ image: { enabled: on, url: $("st-img-url").value } }));
  $("st-img-url").addEventListener("change", () =>
    API.save_settings({ image: { enabled: $("st-img-on").classList.contains("on"), url: $("st-img-url").value } }));
  sw("st-srv-on", async (on) => {
    if (on) { await API.start_server(); }
    else { await API.stop_server(); }
  });
  $("st-srv-port").addEventListener("change", () =>
    API.save_settings({ server: { port: Number($("st-srv-port").value) } }));
  sw("st-tools-on", (on) => API.save_settings({ tools: { enabled: on, mode: $("st-tools-mode").value } }));
  sw("st-osint-on", (on) => API.save_settings({ tools: {
    osint: on, enabled: $("st-tools-on").classList.contains("on"),
    mode: $("st-tools-mode").value } }));
  $("st-tools-mode").addEventListener("change", () =>
    API.save_settings({ tools: { enabled: $("st-tools-on").classList.contains("on"), mode: $("st-tools-mode").value } }));
  /* personnalisation : accent, particules, verre */
  const ui = S.settings.ui = (S.settings.ui || {});
  const spd = $("st-part-spd");
  spd.value = ui.particles_speed ?? 0.55;
  $("st-part-spd-v").textContent = Number(spd.value).toFixed(2) + "×";
  spd.addEventListener("input", () =>
    $("st-part-spd-v").textContent = Number(spd.value).toFixed(2) + "×");
  // ------------------------------------------------------------------
  // Personnalisation EN DIRECT : accent, vitesse, particules et verre
  // s'appliquent immédiatement — plus aucun rechargement de l'interface.
  // ------------------------------------------------------------------
  spd.addEventListener("change", async () => {
    ui.particles_speed = Number(spd.value);
    applyUiPrefs();
    restartParticles();
    await API.save_settings({ ui: ui });
  });
  sw("st-part-on", async (on) => {
    ui.particles = on;
    applyUiPrefs();
    if (on) restartParticles(); else stopParticles();
    await API.save_settings({ ui: ui });
  });
  sw("st-glass-on", async (on) => {
    ui.glass = on;
    applyUiPrefs();          // la classe no-glass bascule instantanément
    await API.save_settings({ ui: ui });
  });
  document.querySelectorAll(".accent-dot").forEach((b) =>
    b.addEventListener("click", async () => {
      ui.accent = b.dataset.accent;
      applyUiPrefs();        // variables CSS + dégradés de fond
      restartParticles();    // les particules reprennent la nouvelle teinte
      document.querySelectorAll(".accent-dot").forEach((d) =>
        d.classList.toggle("on", d === b));
      await API.save_settings({ ui: ui });
    }));
  const engineRefresh = $("st-engine-refresh");
  if (engineRefresh) engineRefresh.addEventListener("click", async () => {
    const st = await API.settings_state();
    S.settings = st;
    updateModelBar();
    renderSettings();
  });
  const searchSw = $("st-search-on");
  if (searchSw) searchSw.addEventListener("click", async () => {
    searchSw.classList.toggle("on");
    const on = searchSw.classList.contains("on");
    S.settings.search = on;
    await API.save_settings({ search: { enabled: on } });
    syncModes();
  });
  /* ---- APIs distantes (OpenAI compatible / Anthropic) ---- */
  apiProviders().forEach((p) => {
    const k = p.key;
    const onBtn = $("st-api-" + k + "-on");
    if (onBtn) onBtn.addEventListener("click", () => onBtn.classList.toggle("on"));
    const cur = () => ({
      enabled: onBtn.classList.contains("on"),
      base_url: $("st-api-" + k + "-url").value.trim(),
      api_key: $("st-api-" + k + "-key").value.trim(),
      model: $("st-api-" + k + "-model").value.trim(),
    });
    const loadBtn = $("st-api-" + k + "-load");
    if (loadBtn) loadBtn.addEventListener("click", async () => {
      const msg = $("st-api-" + k + "-msg");
      msg.style.color = "var(--muted-2)";
      msg.textContent = t("settings.api.loading");
      const prof = cur();
      const r = await API.list_provider_models(k, prof);
      if (!r || !r.ok) {
        msg.textContent = t("settings.api.fail") + " " + ((r && r.error) || "?");
        msg.style.color = "var(--err)";
        return;
      }
      $("dl-" + k).innerHTML = (r.models || [])
        .map((m) => `<option value="${esc(m)}"></option>`).join("");
      msg.textContent = t("settings.api.found").replace("{n}", String(r.count));
      msg.style.color = "var(--ok)";
      const field = $("st-api-" + k + "-model");
      if (!field.value && (r.models || []).length) field.value = r.models[0];
    });
    const saveBtn = $("st-api-" + k + "-save");
    // auto-save : coller/saisir une clé suffit — test + enregistrement
    // automatiques au blur, pas besoin de cliquer sur Save
    const keyField = $("st-api-" + k + "-key");
    if (keyField) keyField.addEventListener("change", async () => {
      const key = keyField.value.trim();
      if (!key) return;                     // champ vidé : ne rien faire
      if (saveBtn) saveBtn.click();
    });
    if (saveBtn) saveBtn.addEventListener("click", async () => {
      const prof = cur();
      const payload = { providers: {} };
      payload.providers[k] = prof;
      // test en direct avant d'enregistrer : une API morte n'est pas activée
      const test = await API.test_provider(k, prof);
      if (!test || !test.ok) {
        const msg0 = $("st-api-" + k + "-msg");
        msg0.textContent = t("settings.api.fail").replace("{err}", (test && test.error) || "?");
        msg0.style.color = "var(--err)";
        return;
      }
      await API.save_settings(payload);
      const msg = $("st-api-" + k + "-msg");
      msg.textContent = t("settings.api.test_ok").replace("{n}", String(test.count));
      msg.style.color = "var(--ok)";
      $("st-api-" + k + "-key").value = "";
      const st = await API.init();
      S.settings = st.settings;
      updateModelBar();
      // les modèles cloud gratuites xKiro entrent/sortent de la liste tout seuls
      if (S.view === "models") renderModels();
    });
  });
  $("st-reco").addEventListener("click", async () => {
    const r = await API.apply_recommended();
    $("st-reco-msg").textContent = r.ok ? t("sys.applied").replace("{model}", r.tier) : "";
    $("st-reco-msg").style.color = "var(--ok)";
  });
  $("st-reset").addEventListener("click", () => {
    askConfirm(t("settings.reset.title"), t("settings.reset.confirm"), "",
      async (ok) => {
        if (!ok) return;
        await API.factory_reset();
        location.reload();
      });
  });
}

/* ---------- confirmations (commandes outils / suppressions) ---------- */
let CF = { id: 0 };
let CF_CB = null;
function askConfirm(title, text, cmd, cb) {
  $("cf-title").textContent = title;
  $("cf-text").textContent = text;
  $("cf-cmd").textContent = cmd || "";
  $("cf-cmd").style.display = cmd ? "" : "none";
  CF_CB = cb;
  openModal("modal-confirm");
}
function respondConfirm(ok) {
  const cb = CF_CB;
  CF_CB = null;
  closeModal();
  if (cb) cb(ok);
}

/* ---------- modales ---------- */
function openModal(id) {
  $("modal-mask").classList.remove("hidden");
  $(id).classList.remove("hidden");
}
function closeModal() {
  $("modal-mask").classList.add("hidden");
  ["modal-img", "modal-confirm"].forEach((m) => $(m).classList.add("hidden"));
}
$("modal-mask").addEventListener("click", closeModal);

/* ---------- génération d'images (carte façon ChatGPT) ---------- */
async function openImgCard() {
  if (S.view !== "chat") nav("chat");
  $("genimg-card").classList.remove("hidden");
  S.genimgOpen = true;
  await refreshImgModels();
}
function closeImgCard() {
  $("genimg-card").classList.add("hidden");
  S.genimgOpen = false;
}
async function refreshImgModels() {
  const sel = $("genimg-model");
  sel.innerHTML = "";
  const st = await API.image_engine_state();
  if (!st.ready) {
    // moteur préinstallé : il ne manque que le modèle → message clair +
    // bouton d'installation (télécharge uniquement le modèle manquant)
    sel.add(new Option(t("chat.genimg.none"), ""));
    sel.disabled = true;
    S.imgNeedsInstall = true;
    return;
  }
  // le bridge renvoie tous les modèles téléchargés (fichiers réels)
  const label = (f) => {
    if (f.startsWith("dreamshaper")) return "WormGPT Draw-2";
    if (f.startsWith("stable-diffusion")) return "WormGPT Draw-1";
    return f.replace(/\.gguf$/i, "");
  };
  (st.models && st.models.length ? st.models : [st.model_name]).forEach((f) =>
    sel.add(new Option(label(f), f)));
  sel.disabled = false;
  S.imgNeedsInstall = false;
}
function launchImageGen() {
  if (S.imgNeedsInstall) {
    API.install_image_engine();
    toast(t("chat.genimg.installing").replace("{pct}", "0"));
    return;
  }
  const prompt = $("genimg-prompt").value.trim();
  if (!prompt || S.generating) return;
  $("genimg-skel").classList.remove("hidden");
  $("genimg-img").classList.add("hidden");
  $("genimg-bar").classList.remove("hidden");
  $("genimg-fill").style.width = "0%";
  $("genimg-eta").textContent = "…";
  S.msgs.push({ kind: "ai", genimg: true, closed: false, text: "",
                reasoning: "", time: Date.now() });
  if (S.view === "chat") renderChat();
  const steps = parseInt($("genimg-steps").value, 10);
  const cfg = parseFloat($("genimg-cfg").value);
  API.generate_image(prompt, $("genimg-size").value,
                     isNaN(steps) ? 0 : steps,
                     $("genimg-model").value || "",
                     $("genimg-negative").value.trim(),
                     isNaN(cfg) ? 0 : cfg);
}

/* ---------- bienvenue ---------- */
function welcome(name) {
  const w = $("welcome");
  $("wel-title").innerHTML = `${esc(t("welcome.hello"))}, <span>${esc(name || t("brand.tagline"))}</span>`;
  $("wel-sub").textContent = t("wizard.local");
  w.classList.remove("hidden");
  setTimeout(() => w.classList.add("hidden"), 3100);
}

/* ---------- barre du modèle (au-dessus du composer) ---------- */
function updateModelBar() {
  const bar = $("model-bar");
  if (!bar) return;
  const model = (S.settings && S.settings.model) || "WormGPT";
  $("mb-name").textContent = model;
  const st = (S.settings && S.settings.engine && S.settings.engine.state) || "off";
  const txt = (S.settings && S.settings.engine && S.settings.engine.text) || "";
  $("mb-dot").className = "model-bar__dot " + statusClass(st);
  const label = st === "ready" ? t("models.active_ready")
              : st === "loading" ? t("models.loading") : t("models.not_installed");
  $("mb-state").textContent = label;
  bar.classList.toggle("hidden", false);
  bar.title = txt || label;
  // le bouton sélecteur du composer affiche aussi le modèle courant + son état
  const sel = $("model-select");
  if (sel) {
    $("ms-name").textContent = model;
    const d = $("ms-dot");
    if (d) d.className = "model-select__dot " + statusClass(st);
  }
}

/* ---------- événements ---------- */
const RERENDER = new Set(["stream", "reason", "stream_end", "chat_user", "error",
                          "system", "cleared", "img_done", "img_error"]);
async function pullLoop() {
  if (!API) return;
  try {
    const events = await API.pull();
    if (events.length) {
      events.forEach(handleEvent);          // ne fait que muter l'état
      if (S.view === "chat" && events.some((e) => RERENDER.has(e.type)))
        renderChat();                        // un seul rendu par lot
      if (S.view === "models" && events.some((e) =>
          e.type.startsWith("download") || e.type === "models_refresh"))
        renderModels();
    }
  } catch (err) {
    // pywebview peut jeter pendant un rechargement : on ne doit JAMAIS
    // laisser mourir la boucle, sinon plus aucun événement (downloads,
    // chargement de modèle, réponses) n'arrive à l'interface.
  }
  setTimeout(pullLoop, 250);
}
function handleEvent(ev) {
  switch (ev.type) {
    case "status": {
      const dot = $("side-dot");
      dot.className = "dot " + statusClass(ev.state);
      $("side-status").textContent = ev.text;
      if (S.settings) {
        S.settings.engine = { state: ev.state, text: ev.text };
      }
      const pd = $("pill-dot");
      if (pd) pd.className = "model-pill__status " +
        (ev.state === "ready" ? "" : ev.state === "loading" ? "loading" : "off");
      updateModelBar();
      break;
    }
    case "model_changed":
      if (S.settings) S.settings.model = ev.tier;
      const pm = $("pill-model");
      if (pm) pm.textContent = ev.tier;
      if (S.settings) S.settings.model = ev.tier;
      updateModelBar();
      if (S.view === "chat") renderChat();
      break;
    case "chat_user":
      if (S.pendingSend) {
        // déjà affiché en optimiste par sendMsg()
        S.pendingSend = false;
      } else {
        S.sendTime = Date.now();
        S.msgs.push({ kind: "user", text: ev.text, image: ev.image || "",
                      time: S.sendTime });
        S.msgs.push({ kind: "ai", thinking: true, text: "", reasoning: "",
                      closed: false, time: S.sendTime });
      }
      if (S.view === "chat") renderChat();
      refreshConvsSoon();
      break;
    case "stream": {
      if (!S.curMsg || S.curMsg.closed) {
        const last = S.msgs[S.msgs.length - 1];
        if (last && last.thinking) { last.thinking = false; S.curMsg = last; }
        else { S.curMsg = { kind: "ai", text: "", reasoning: "", closed: false,
                            time: Date.now() }; S.msgs.push(S.curMsg); }
        S.curReason = "";
      }
      S.curMsg.text += ev.text;
      if (S.view === "chat") renderChat();
      break;
    }
    case "chat_user_dup":
      break;  // le rendu optimiste existe déjà
    case "reason":
      if (!S.curMsg || S.curMsg.closed) {
        const last = S.msgs[S.msgs.length - 1];
        if (last && last.thinking) { last.thinking = false; S.curMsg = last; }
        else { S.curMsg = { kind: "ai", text: "", reasoning: "", closed: false,
                            time: Date.now() }; S.msgs.push(S.curMsg); }
        // ouvert par défaut : on veut VOIR le raisonnement arriver en direct
        S.curMsg.reasonOpen = true;
      }
      S.curMsg.reasoning += ev.text;
      if (S.view === "chat") renderChat();
      break;
    case "history":
      S.msgs = (ev.msgs || []).map((m) => ({
        kind: m.role === "user" ? "user" : "ai",
        text: m.text || "", reasoning: m.reasoning || "",
        image: m.image || "", closed: true,
        time: Date.now(),
      }));
      S.curMsg = null;
      if (S.view === "chat") renderChat();
      refreshConvsSoon();
      break;
    case "convs_refresh":
      renderConvs();
      break;
    case "stream_end": {
      if (!S.curMsg) {
        // réponse non streamée : le texte complet arrive ici
        S.curMsg = { kind: "ai", text: ev.text || "", reasoning: "", closed: true,
                     time: S.sendTime || Date.now() };
        const last = S.msgs[S.msgs.length - 1];
        if (last && last.thinking) S.msgs[S.msgs.length - 1] = S.curMsg;
        else S.msgs.push(S.curMsg);
      } else {
        // réponse streamée : le texte est déjà accumulé — ne pas ré-appendre
        S.curMsg.text = S.curMsg.text || ev.text || "";
      }
      if (ev.reason && !S.curMsg.reasoning) S.curMsg.reasoning = ev.reason;
      S.curMsg.closed = true;
      S.curMsg.latency = ev.elapsed ? ev.elapsed * 1000
        : (S.sendTime ? Date.now() - S.sendTime : 0);
      const nTok = ev.tok || Math.max(1, Math.round((S.curMsg.text || "").length / 4));
      S.curMsg.tps = nTok / Math.max(0.2, (S.curMsg.latency || 1000) / 1000);
      S.curMsg = null;
      S.pendingSend = false;
      if (S.view === "chat") renderChat();
      refreshConvsSoon();
      break;
    }
    case "error":
      S.msgs.push({ kind: "error", text: ev.text });
      if (S.view === "chat") renderChat();
      toast(ev.text);
      break;
    case "system":
      S.msgs.push({ kind: "system", text: ev.text });
      if (S.view === "chat") renderChat();
      break;
    case "cleared":
      S.msgs = []; S.curMsg = null;
      if (S.view === "chat") renderChat();
      refreshConvsSoon();
      break;
    case "img_done": {
      const card = $("genimg-card");
      if (card && !card.classList.contains("hidden")) {
        $("genimg-skel").classList.add("hidden");
        $("genimg-bar").classList.add("hidden");
        const im = $("genimg-img");
        im.src = "data:image/png;base64," + ev.b64;
        im.classList.remove("hidden");
      }
      // remplace la carte en attente dans le chat par l'image réelle
      const pending = [...S.msgs].reverse().find((m) => m.genimg && !m.image);
      if (pending) {
        pending.image = "data:image/png;base64," + ev.b64;
        pending.genimg = false;
        pending.closed = true;
        pending.latency = ev.elapsed ? ev.elapsed * 1000 : 0;
      } else {
        S.msgs.push({ kind: "ai", text: "", reasoning: "", closed: true,
                      image: "data:image/png;base64," + ev.b64,
                      latency: ev.elapsed ? ev.elapsed * 1000 : 0 });
      }
      S.generating = false;
      if (S.view === "chat") renderChat();
      break;
    }
    case "img_progress": {
      const card = $("genimg-card");
      if (card && !card.classList.contains("hidden") && ev.total) {
        $("genimg-fill").style.width = (100 * ev.step / ev.total).toFixed(0) + "%";
        $("genimg-eta").textContent = t("chat.genimg.step")
          .replace("{step}", ev.step).replace("{total}", ev.total)
          .replace("{sec}", Math.max(1, Math.round(ev.eta || 0)));
      }
      break;
    }
    case "img_install": {
      S.imgInstall = ev;
      toast(t("chat.genimg.installing").replace("{pct}",
            String(Math.round((ev.pct || 0) * 100))));
      break;
    }
    case "img_install_done":
    case "img_install_error":
      if (ev.type === "img_install_error") toast(ev.text || "");
      else toast(t("chat.genimg.ready"));
      refreshImgModels();
      break;
    case "img_error": {
      const card = $("genimg-card");
      if (card) {
        $("genimg-skel").classList.add("hidden");
        $("genimg-bar").classList.add("hidden");
      }
      const pending = [...S.msgs].reverse().find((m) => m.genimg && !m.image);
      if (pending) S.msgs.splice(S.msgs.indexOf(pending), 1);
      S.generating = false;
      toast(ev.text);
      S.msgs.push({ kind: "error", text: ev.text });
      if (S.view === "chat") renderChat();
      break;
    }
    case "download": {
      S.progress[ev.name] = { pct: ev.pct || 0, speed: ev.speed || 0,
                              done_mb: ev.done_mb || 0 };
      // barre rouge dans le coin haut droite (visible partout)
      const dc = $("dl-corner");
      if (dc) {
        dc.classList.remove("hidden");
        $("dl-fill").style.width = ((ev.pct || 0) * 100).toFixed(0) + "%";
        const spd = ev.speed ? " · " + ev.speed.toFixed(1) + " Mo/s" : "";
        $("dl-lbl").textContent = ev.name + " " + ((ev.pct || 0) * 100).toFixed(0) + "%" + spd;
      }
      if (S.view === "models") renderModels();
      break;
    }
    case "download_done":
      delete S.progress[ev.name];
      if ($("dl-corner")) $("dl-corner").classList.add("hidden");
      toast(t("models.ready_toast").replace("{model}", ev.name));
      if (S.view === "models") renderModels();
      API.settings_state().then((st) => {
        if (S.settings) { S.settings.model = st.model; S.settings.engine = st.engine; }
        const pm = $("pill-model");
        if (pm) pm.textContent = st.model;
        updateModelBar();
      });
      refreshConvsSoon();
      break;
    case "download_error":
      delete S.progress[ev.name];
      if ($("dl-corner")) $("dl-corner").classList.add("hidden");
      if (S.view === "models") renderModels();
      toast(ev.text);
      break;
    case "models_refresh":
      if (S.view === "models") renderModels();
      break;
    case "confirm":
      CF.id = ev.id;
      askConfirm(t("tools.confirm_title"), t("tools.confirm").split("\n")[0],
                 ev.cmd + "\n(" + ev.cwd + ")",
                 (ok) => API.confirm_response(CF.id, ok));
      break;
    case "server_state":
      if (!document.getElementById("settings-overlay").classList.contains("hidden"))
        renderSettings();
      break;
  }
}

/* ---------- fond animé : particules rouges réactives à la souris ---------- */
function particleColor() {
  // suit la couleur d'accent choisie (fallback : rouge par défaut)
  const v = getComputedStyle(document.documentElement).getPropertyValue("--accent").trim();
  return (/^#[0-9a-fA-F]{6}$/.test(v) ? v : "#ff3d57");
}
function startParticles() {
  const cv = $("dg-particles");
  if (!cv || cv._running) return;
  if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const ui = (S.settings && S.settings.ui) || {};
  if (ui.particles === false) return;           // réglage : particules off
  const speedMul = Math.max(0.2, Math.min(2, Number(ui.particles_speed) || 0.55));
  const rgb = (() => {
    const h = particleColor();
    return [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16),
            parseInt(h.slice(5, 7), 16)];
  })();
  cv._running = true;
  const ctx = cv.getContext("2d");
  let W = 0, H = 0, mouse = { x: -9999, y: -9999 };
  const P = [];
  // densité douce : moins de particules, mouvement lent et apaisé
  const N = Math.min(90, Math.max(50, Math.floor(window.innerWidth / 18)));
  function resize() {
    W = cv.width = window.innerWidth;
    H = cv.height = window.innerHeight;
  }
  function spawn() {
    for (let i = 0; i < N; i++) {
      const tier = Math.random();
      // 3 familles : lentes de fond, moyennes, quelques rapides —
      // tout est ralenti par le réglage (vitesse par défaut : très douce)
      const spd = (tier < 0.6 ? 0.04 + Math.random() * 0.05
                 : tier < 0.9 ? 0.09 + Math.random() * 0.10
                 : 0.20 + Math.random() * 0.18) * speedMul;
      P.push({
        x: Math.random() * W, y: Math.random() * H,
        vx: (Math.random() - .5) * spd * 2, vy: (Math.random() - .5) * spd * 2,
        r: tier < 0.6 ? Math.random() * 1.1 + .4
         : tier < 0.9 ? Math.random() * 1.5 + .7
         : Math.random() * 2 + 1.1,
        wobble: Math.random() * Math.PI * 2,
        wobbleSpd: (0.0012 + Math.random() * 0.004) * speedMul,
        alpha: tier < 0.6 ? .22 + Math.random() * .16
             : tier < 0.9 ? .34 + Math.random() * .2
             : .5 + Math.random() * .25
      });
    }
  }
  // Handlers mémorisés sur le canvas : sans ça, chaque changement de réglage
  // en direct empilerait de nouveaux écouteurs sur window.
  cv._onResize = resize;
  cv._onMove = (e) => { mouse.x = e.clientX; mouse.y = e.clientY; };
  cv._onLeave = () => { mouse.x = -9999; mouse.y = -9999; };
  window.addEventListener("resize", cv._onResize);
  window.addEventListener("mousemove", cv._onMove);
  window.addEventListener("mouseleave", cv._onLeave);
  resize(); spawn();
  (function frame() {
    ctx.clearRect(0, 0, W, H);
    for (const p of P) {
      // attraction douce vers la souris (réactif, lui aussi ralenti)
      const dx = mouse.x - p.x, dy = mouse.y - p.y;
      const d2 = dx * dx + dy * dy;
      if (d2 < 200 * 200 && d2 > 1) {
        const f = 0.025 / Math.sqrt(d2);
        p.vx += dx * f; p.vy += dy * f;
      }
      // dérive propre : chaque particule ondule différemment (lentement)
      p.wobble += p.wobbleSpd;
      p.vx += Math.cos(p.wobble) * 0.0025;
      p.vy += Math.sin(p.wobble * 0.9) * 0.0025;
      p.vx *= 0.992; p.vy *= 0.992;
      p.x += p.vx; p.y += p.vy;
      if (p.x < -10) p.x = W + 10; if (p.x > W + 10) p.x = -10;
      if (p.y < -10) p.y = H + 10; if (p.y > H + 10) p.y = -10;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${rgb[0]},${rgb[1]},${rgb[2]},${p.alpha})`;
      ctx.fill();
    }
    // lignes entre particules proches
    ctx.lineWidth = 0.6;
    for (let i = 0; i < P.length; i++) for (let j = i + 1; j < P.length; j++) {
      const a = P[i], b = P[j];
      const dx = a.x - b.x, dy = a.y - b.y, d2 = dx * dx + dy * dy;
      if (d2 < 110 * 110) {
        ctx.strokeStyle = `rgba(${rgb[0]},${rgb[1]},${rgb[2]},${(1 - Math.sqrt(d2) / 110) * .16})`;
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
      }
    }
    cv._raf = requestAnimationFrame(frame);
  })();
}
/* Arrête le fond animé proprement (changement de réglage à chaud). */
function stopParticles() {
  const cv = $("dg-particles");
  if (!cv || !cv._running) return;
  cancelAnimationFrame(cv._raf);
  window.removeEventListener("resize", cv._onResize);
  window.removeEventListener("mousemove", cv._onMove);
  window.removeEventListener("mouseleave", cv._onLeave);
  cv._running = false;
  const ctx = cv.getContext("2d");
  if (ctx) ctx.clearRect(0, 0, cv.width, cv.height);
}
/* Redémarre le fond animé avec l'accent et la vitesse courants. */
function restartParticles() {
  stopParticles();
  startParticles();
}

/* pywebview injecte window.pywebview au chargement ; on démarre dès que
   l'API est disponible (ou immédiatement si déjà en place). */
window.addEventListener("pywebviewready", init);
setTimeout(init, 300);