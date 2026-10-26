// Burstwise review app. Plain ES modules, no build step. Runs against the local API,
// or against a static state.json when the page sets window.BURSTWISE_DEMO (GitHub Pages).
const DEMO = window.BURSTWISE_DEMO === true;
const STATES = ["pick", "review", "alt", "reject"];
const LANGS = [
  ["en", "English"], ["zh-TW", "繁體中文"], ["zh-CN", "简体中文"], ["ja", "日本語"],
  ["ko", "한국어"], ["es", "Español"], ["fr", "Français"], ["de", "Deutsch"],
  ["pt-BR", "Português (Brasil)"],
];
const $ = (id) => document.getElementById(id);

let strings = {};
let fallback = {};
let state = null;
let decisions = {};
let filter = null;
let open = null;
const expanded = new Set();
let view = { compare: false, faces: false, zoom: false };

function h(tag, attrs = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") el.className = v;
    else if (k === "style") el.style.cssText = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (v === true) el.setAttribute(k, "");
    else if (v !== false && v != null) el.setAttribute(k, v);
  }
  for (const kid of kids.flat()) {
    if (kid != null && kid !== false) el.append(kid.nodeType ? kid : document.createTextNode(kid));
  }
  return el;
}

// ---- i18n -------------------------------------------------------------------------
function t(key, vars = {}) {
  const text = strings[key] ?? fallback[key] ?? key;
  return text.replace(/\{(\w+)\}/g, (_, name) => vars[name] ?? "");
}

function pickLanguage() {
  const saved = localStorage.getItem("bw-lang");
  if (saved && LANGS.some(([code]) => code === saved)) return saved;
  for (const raw of navigator.languages || [navigator.language || "en"]) {
    const tag = raw.toLowerCase();
    if (tag.startsWith("zh")) return /tw|hk|mo|hant/.test(tag) ? "zh-TW" : "zh-CN";
    if (tag.startsWith("pt")) return "pt-BR";
    const hit = LANGS.find(([code]) => code.toLowerCase() === tag.slice(0, 2));
    if (hit) return hit[0];
  }
  return "en";
}

async function loadStrings(lang) {
  const get = async (code) => (await fetch(`locales/${code}.json`)).json();
  fallback = fallback.app_title ? fallback : await get("en");
  strings = lang === "en" ? fallback : await get(lang);
  document.documentElement.lang = lang;
  document.querySelectorAll("[data-i18n]").forEach((el) => (el.textContent = t(el.dataset.i18n)));
  document.querySelectorAll("[data-i18n-title]").forEach((el) => {
    el.title = t(el.dataset.i18nTitle);
    el.setAttribute("aria-label", el.title);
  });
}

async function setLanguage(lang) {
  localStorage.setItem("bw-lang", lang);
  await loadStrings(lang);
  $("lang").value = lang;
  render();
  if (open) renderViewer();
}

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem("bw-theme", theme);
}

// ---- data -------------------------------------------------------------------------
async function api(path, method = "GET", body) {
  const res = await fetch(path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText);
  return res.json();
}

const thumbUrl = (p, size) => (DEMO ? `thumbs/${p.id}.jpg` : `api/thumb/${p.id}?size=${size}`);
const eff = (p) => decisions[p.id]?.state || p.state;
const byId = () => Object.fromEntries(state.photos.map((p) => [p.id, p]));

function toast(text) {
  const el = h("div", { class: "toast", role: "status" }, text);
  document.body.append(el);
  setTimeout(() => el.remove(), 3200);
}

async function load() {
  if (DEMO) {
    state = await api("state.json");
    decisions = JSON.parse(localStorage.getItem("bw-demo-decisions") || "{}");
    return render();
  }
  for (;;) {
    state = await api("api/state");
    if (state.job.state === "error") throw new Error(state.job.error);
    if (state.job.state === "done" && state.photos) break;
    renderProgress(state.job);
    await new Promise((r) => setTimeout(r, 400));
  }
  decisions = state.decisions || {};
  $("r-sim").value = state.settings.similarity;
  $("r-soft").value = state.settings.soft_ratio;
  render();
}

function renderProgress(job) {
  const pct = job.total ? Math.round((100 * job.done) / job.total) : 0;
  $("main").replaceChildren(
    h("div", { class: "progress" },
      h("h2", {}, t("analyzing", { done: job.done, total: job.total })),
      h("div", { class: "meter", role: "progressbar", "aria-valuenow": pct },
        h("span", { style: `width:${pct}%` })),
      h("p", {}, t("analyzing.hint")),
      h("small", {}, job.name || ""))
  );
}

async function decide(id, patch, advance = false) {
  const before = decisions[id];
  const next = patch === null ? {} : { ...(before || {}), ...patch };
  for (const key of Object.keys(next)) if (next[key] == null) delete next[key];
  const list = visible();
  const after = advance && open === id ? list[list.findIndex((q) => q.id === id) + 1] : null;
  if (Object.keys(next).length) decisions[id] = next;
  else delete decisions[id];
  const p = state.photos.find((q) => q.id === id);
  if (open && advance) toast(`${p.name}: ${t(`state.${eff(p)}`)}`);
  refresh(p);
  if (after) {
    open = after.id;
    view.zoom = false;
  }
  if (open) renderViewer();
  try {
    if (DEMO) localStorage.setItem("bw-demo-decisions", JSON.stringify(decisions));
    else await api(`api/decision/${id}`, "PUT", next);
  } catch (e) {
    if (before) decisions[id] = before;
    else delete decisions[id];
    refresh(p);
    if (open) renderViewer();
    toast(e.message);
  }
}

// Only the group that changed is redrawn unless a filter is on, so a long grid keeps its
// scroll position, its images and the focused card.
function refresh(p) {
  if (filter || !document.querySelector(`.card[data-id="${p.id}"]`)) return render();
  renderCounts();
  rebuildGroup(p.group);
}

// ---- grid -------------------------------------------------------------------------
function visible() {
  return state.photos.filter((p) => !filter || eff(p) === filter);
}

function renderCounts() {
  const tally = Object.fromEntries(STATES.map((s) => [s, 0]));
  state.photos.forEach((p) => tally[eff(p)]++);
  const chips = STATES.map((s) =>
    h("button", {
      class: "chip", style: `--c:var(--${s})`, "aria-pressed": filter === s,
      onclick: () => { filter = filter === s ? null : s; render(); },
    }, h("i"), t(`state.${s}`), " ", h("b", {}, tally[s])));
  $("counts").replaceChildren(
    h("span", { class: "chip" }, t("photos", { n: state.photos.length }), " · ",
      t("groups", { n: state.groups.length })),
    ...chips
  );
}

function card(p, hero = false) {
  const s = eff(p);
  const note = [...p.reasons, ...p.problems].map(reasonText)[0] || "";
  const own = decisions[p.id];
  return h("button", {
    class: hero ? "card hero" : "card", "data-state": s, "data-id": p.id, onclick: () => openViewer(p.id),
    "aria-label": `${p.name}, ${t(`state.${s}`)}${note ? `, ${note}` : ""}`,
  },
    h("img", { src: thumbUrl(p, hero ? 960 : 480), loading: "lazy", alt: "", decoding: "async" }),
    h("span", { class: "badge", style: `--c:var(--${s})` }, t(`state.${s}`)),
    own && h("span", { class: "own" }, [own.state && t("override"), own.rating && `★${own.rating}`]
      .filter(Boolean).join(" ")),
    note && h("span", { class: "why" }, note));
}

// A group of more than this many frames shows its best frame large and only the frames
// that matter until it is expanded.
const COLLAPSE_FROM = 12;
const COLLAPSED_SHOWS = 9;

// The best frame of a group: the one you picked, else the top ranked frame that is not rejected.
function heroOf(members) {
  const live = members.filter((p) => eff(p) !== "reject").sort((a, b) => a.rank - b.rank);
  return live.find((p) => decisions[p.id]?.state === "pick") || live[0] || null;
}

function groupCards(g, members) {
  const hero = filter || members.length < 3 ? null : heroOf(members);
  const rest = members.filter((p) => p !== hero);
  const total = members.length;
  const folded = !filter && total > COLLAPSE_FROM && !expanded.has(g);
  let keep = rest;
  if (folded) {
    const matters = (p) => eff(p) === "pick" || eff(p) === "review" || decisions[p.id];
    const room = Math.max(0, COLLAPSED_SHOWS - 1 - rest.filter(matters).length);
    let spare = room;
    keep = rest.filter((p) => matters(p) || spare-- > 0);
  }
  return { hero, keep, hidden: total - keep.length - (hero ? 1 : 0), collapsible: !filter && total > COLLAPSE_FROM };
}

function section(g, photos, shown) {
  const ids = state.groups[g];
  const members = ids.filter((id) => shown.has(id)).map((id) => photos[id]);
  if (!members.length) return null;
  const all = ids.map((id) => photos[id]);
  const span = Math.round(all[all.length - 1].taken - all[0].taken);
  const { hero, keep, hidden, collapsible } = groupCards(g, members);
  const shownCards = hero ? [hero, ...keep] : keep;
  return h("section", { class: "group", "data-group": g },
    h("h3", {}, h("b", {}, t("group.title", { n: g + 1 })), t("group.frames", { n: ids.length }), "·",
      t("group.span", { s: span }),
      collapsible && h("button", {
        class: "more", "aria-expanded": String(hidden === 0),
        onclick: () => { expanded[hidden ? "add" : "delete"](g); rebuildGroup(g); },
      }, hidden ? t("group.more", { n: ids.length }) : t("group.less"))),
    h("div", { class: "strip" }, shownCards.map((p) => card(p, p === hero))));
}

function renderGroup(g) {
  const shown = new Set(visible().map((p) => p.id));
  return section(g, byId(), shown);
}

// Redraws one group in place, keeping the loaded images and the focused card.
function rebuildGroup(g) {
  const old = document.querySelector(`.group[data-group="${g}"]`);
  const fresh = renderGroup(g);
  if (!old || !fresh) return render();
  const imgs = new Map([...old.querySelectorAll(".card img")].map((i) => [i.closest(".card").dataset.id, i]));
  const focused = old.contains(document.activeElement) && document.activeElement.closest(".card")?.dataset.id;
  fresh.querySelectorAll(".card img").forEach((img) => {
    const had = imgs.get(img.closest(".card").dataset.id);
    if (had && had.getAttribute("src") === img.getAttribute("src")) img.replaceWith(had);
  });
  old.replaceWith(fresh);
  if (focused) fresh.querySelector(`.card[data-id="${focused}"]`)?.focus({ preventScroll: true });
}

function render() {
  if (!state || !state.photos) return;
  renderCounts();
  $("banner").hidden = !DEMO;
  $("btn-settings").hidden = DEMO;
  if (!state.photos.length) return $("main").replaceChildren(h("p", { class: "empty" }, t("empty")));
  const shown = new Set(visible().map((p) => p.id));
  const photos = byId();
  $("main").replaceChildren(...state.groups.map((_, g) => section(g, photos, shown)).filter(Boolean));
}

function reasonText(item) {
  return t(`reason.${item.code}`, item);
}

// ---- viewer -----------------------------------------------------------------------
function groupPick(p) {
  const ids = state.groups[p.group];
  const photos = byId();
  const group = ids.map((id) => photos[id]);
  const chosen = group.find((q) => decisions[q.id]?.state === "pick" && q.id !== p.id);
  const best = chosen || group.find((q) => q.rank === 1) || group[0];
  return best.id !== p.id ? best : group.find((q) => q.id !== p.id && q.rank === 2) || null;
}

function openViewer(id) {
  open = id;
  $("viewer").hidden = false;
  document.body.style.overflow = "hidden";
  renderViewer();
  $("viewer").querySelector("[data-close]")?.focus();
}

function closeViewer() {
  const last = open;
  open = null;
  $("viewer").hidden = true;
  document.body.style.overflow = "";
  let card = last && document.querySelector(`.card[data-id="${last}"]`);
  if (last && !card) {
    expanded.add(state.photos.find((q) => q.id === last).group);
    rebuildGroup(state.photos.find((q) => q.id === last).group);
    card = document.querySelector(`.card[data-id="${last}"]`);
  }
  card?.scrollIntoView({ block: "center" });
  card?.focus({ preventScroll: true });
}

function pane(p, caption) {
  const blinkAt = state.settings.blink_closed;
  const inner = h("div", { class: "inner" },
    h("img", { src: thumbUrl(p, 1600), alt: p.name }),
    view.faces && h("div", { class: "faces" }, p.faces.map((f) => {
      const [x, y, w, hgt] = f.box;
      const closed = f.blink >= blinkAt;
      return h("div", {
        class: `fbox${closed ? " closed" : ""}`,
        style: `left:${x * 100}%;top:${y * 100}%;width:${w * 100}%;height:${hgt * 100}%`,
      }, h("em", {}, t("detail.blink", { n: Math.round(f.blink * 100) })));
    })));
  const zoomer = h("div", { class: `zoomer${view.zoom && p.faces.length ? " zoomed" : ""}` }, inner);
  if (p.faces.length) {
    const big = p.faces.reduce((a, b) => (a.box[2] * a.box[3] >= b.box[2] * b.box[3] ? a : b));
    zoomer.style.setProperty("--ox", `${(big.box[0] + big.box[2] / 2) * 100}%`);
    zoomer.style.setProperty("--oy", `${(big.box[1] + big.box[3] / 2) * 100}%`);
  }
  return h("figure", { class: "v-pane", style: "margin:0" }, zoomer, h("figcaption", {}, caption));
}

function renderViewer() {
  const list = visible();
  const index = list.findIndex((p) => p.id === open);
  const p = state.photos.find((q) => q.id === open);
  if (!p) return closeViewer();
  const s = eff(p);
  const other = view.compare ? groupPick(p) : null;
  const btn = (key, label, fn, on) =>
    h("button", { onclick: fn, "aria-pressed": on == null ? null : String(on) }, t(label), key && h("span", { class: "k" }, ` (${key})`));
  const head = h("div", { class: "v-head" },
    h("h2", {}, p.name, " ", h("span", { class: "badge", style: `position:static;--c:var(--${s})` }, t(`state.${s}`))),
    h("button", { onclick: () => step(-1) }, h("span", { class: "arrow", "aria-hidden": "true" }, "←"), h("span", { class: "lbl" }, t("viewer.prev")), h("span", { class: "k" }, " (←)")),
    h("button", { onclick: () => step(1) }, h("span", { class: "arrow", "aria-hidden": "true" }, "→"), h("span", { class: "lbl" }, t("viewer.next")), h("span", { class: "k" }, " (→)")),
    btn("C", "viewer.compare", () => { view.compare = !view.compare; renderViewer(); }, view.compare),
    btn("F", "viewer.faces", () => { view.faces = !view.faces; renderViewer(); }, view.faces),
    btn("Z", "viewer.zoom", () => { view.zoom = !view.zoom; renderViewer(); }, view.zoom),
    h("button", { "data-close": true, onclick: closeViewer }, t("viewer.close"), h("span", { class: "k" }, " (Esc)")));
  const stage = h("div", { class: `v-stage${other ? " two" : ""}` },
    other && pane(other, t("compare.with")),
    pane(p, other ? t("compare.this") : `${index + 1} / ${list.length}`));
  const good = p.reasons.map((r) => h("li", { class: "good" }, reasonText(r)));
  const bad = p.problems.map((r) => h("li", { class: "bad" }, reasonText(r)));
  const info = h("div", { class: "v-info" },
    h("div", {}, h("ul", {}, good, bad), !good.length && !bad.length && t("detail.nothing")),
    h("dl", {},
      h("dt", {}, t("detail.sharp")), h("dd", {}, p.sharp),
      h("dt", {}, t("detail.highlights")), h("dd", {}, `${(p.highlights * 100).toFixed(1)}%`),
      h("dt", {}, t("detail.shadows")), h("dd", {}, `${(p.shadows * 100).toFixed(1)}%`),
      h("dt", {}, t("detail.faces")), h("dd", {}, p.faces.length),
      h("dt", {}, t("detail.rank")), h("dd", {}, `${p.rank} / ${state.groups[p.group].length}`)));
  const own = decisions[p.id] || {};
  const act = h("div", { class: "v-act" },
    h("button", { onclick: () => decide(p.id, { state: "pick" }, true) }, t("state.pick"), h("span", { class: "k" }, " (P)")),
    h("button", { onclick: () => decide(p.id, { state: "reject" }, true) }, t("state.reject"), h("span", { class: "k" }, " (X)")),
    h("button", { onclick: () => decide(p.id, null, true) }, t("viewer.auto"), h("span", { class: "k" }, " (U)")),
    h("span", { class: "stars", role: "group" }, [1, 2, 3, 4, 5].map((n) =>
      h("button", {
        onclick: () => decide(p.id, { rating: own.rating === n ? null : n }),
        "aria-label": `${n}`, "aria-pressed": String(own.rating === n),
      }, `★${n}`))));
  $("viewer").replaceChildren(head, stage, info, act);
  const upcoming = list[index + 1];
  if (upcoming) new Image().src = thumbUrl(upcoming, 1600);
}

function jumpGroup(delta) {
  const list = visible();
  const here = state.photos.find((q) => q.id === open).group;
  const groups = [...new Set(list.map((q) => q.group))].sort((a, b) => a - b);
  const target = delta > 0 ? groups.find((g) => g > here) : groups.reverse().find((g) => g < here);
  if (target == null) return;
  open = list.find((q) => q.group === target).id;
  view.zoom = false;
  renderViewer();
}

function step(delta) {
  const list = visible();
  const i = list.findIndex((p) => p.id === open);
  const next = list[(i + delta + list.length) % list.length];
  if (next) {
    open = next.id;
    view.zoom = false;
    renderViewer();
  }
}

// ---- actions ----------------------------------------------------------------------
function sidecarText(p) {
  const s = eff(p);
  const own = decisions[p.id] || {};
  let rating = own.rating;
  let label = null;
  if (s === "pick") { rating ??= 4; label = "Green"; }
  else if (s === "reject") { rating = -1; label = "Red"; }
  else if (s === "review") label = "Yellow";
  const lines = [`xmp:Rating="${rating ?? ""}"`, `xmp:Label="${label ?? ""}"`,
    `burstwise:Verdict="${s}"`, `burstwise:Reason="${[...p.reasons, ...p.problems].map(reasonText).join("; ")}"`];
  return `<rdf:Description rdf:about=""\n  ${lines.filter((l) => !l.endsWith('=""')).join("\n  ")}/>`;
}

function showDialog(title, body, actions) {
  const dialog = $("dialog");
  dialog.replaceChildren(h("h2", {}, title), body,
    h("div", { class: "row" }, actions.map(([label, fn, primary]) =>
      h("button", { class: primary ? "primary" : "", onclick: async () => {
        if (await fn?.() !== false) dialog.close();
      } }, label))));
  if (!dialog.open) dialog.showModal();
}

async function xmpDialog() {
  if (DEMO) {
    const sample = state.photos.find((p) => eff(p) === "pick") || state.photos[0];
    return showDialog(t("xmp.title"), h("div", {}, h("p", {}, t("xmp.demo")),
      h("pre", {}, `${sample.name}\n${sidecarText(sample)}`)), [[t("cancel")]]);
  }
  const naming = h("select", {}, ["both", "adobe", "darktable"].map((n) => h("option", { value: n }, t(`xmp.naming.${n}`))));
  const overwrite = h("input", { type: "checkbox" });
  const summary = h("p", {});
  const refresh = async () => {
    const { tally } = await api("api/xmp", "POST", { naming: naming.value, overwrite: overwrite.checked, dry_run: true });
    summary.textContent = t("xmp.dry", tally);
  };
  naming.onchange = overwrite.onchange = refresh;
  await refresh();
  showDialog(t("xmp.title"), h("div", {}, summary, h("label", {}, t("xmp.naming"), naming),
    h("label", {}, overwrite, t("xmp.overwrite")), h("p", {}, h("small", {}, t("xmp.safe")))),
  [[t("cancel")], [t("xmp.write"), async () => {
    const { tally } = await api("api/xmp", "POST", { naming: naming.value, overwrite: overwrite.checked });
    toast(t("xmp.done", tally));
  }, true]]);
}

function exportDialog() {
  if (DEMO) return showDialog(t("action.export"), h("p", {}, t("demo.local")), [[t("cancel")]]);
  const dest = h("input", { type: "text", placeholder: "/path/to/keepers" });
  showDialog(t("action.export"), h("label", {}, t("export.dest"), dest), [[t("cancel")],
    [t("export.copy"), async () => {
      try {
        const out = await api("api/export", "POST", { dest: dest.value });
        toast(t("export.done", { n: out.copied }));
      } catch (e) { toast(e.message); return false; }
    }, true]]);
}

async function undo() {
  if (DEMO) return toast(t("demo.local"));
  const { restored } = await api("api/undo", "POST");
  toast(restored ? t("undo.done", { n: restored }) : t("undo.none"));
}

function helpDialog() {
  const rows = [["← →", "help.nav"], ["↑ ↓", "help.group"], ["P", "help.pick"], ["X", "help.reject"], ["U", "help.auto"],
    ["1 – 5", "help.rate"], ["C", "help.compare"], ["F", "help.faces"], ["Z", "help.zoom"], ["Esc", "help.close"]];
  showDialog(t("action.help"), h("div", {}, h("table", {}, rows.map(([k, label]) =>
    h("tr", {}, h("td", {}, h("kbd", {}, k)), h("td", {}, t(label))))),
  h("p", {}, h("small", {}, t("help.grid")))), [[t("viewer.close")]]);
}

let timer;
function settingsChanged() {
  $("o-sim").textContent = Number($("r-sim").value).toFixed(2);
  $("o-soft").textContent = Number($("r-soft").value).toFixed(2);
  clearTimeout(timer);
  timer = setTimeout(async () => {
    const next = await api("api/settings", "POST",
      { similarity: Number($("r-sim").value), soft_ratio: Number($("r-soft").value) });
    state = { ...next, decisions };
    render();
  }, 250);
}

// A horizontal swipe on the photo moves to the previous or next one. The stage sets
// touch-action: pan-y pinch-zoom, so the browser leaves horizontal drags to us.
let swipe = null;
function onSwipe(e) {
  if (e.pointerType === "mouse" || !open || !e.target.closest(".v-stage")) return;
  if (e.type === "pointerdown") swipe = { x: e.clientX, y: e.clientY };
  else if (e.type === "pointerup" && swipe) {
    const dx = e.clientX - swipe.x;
    const dy = e.clientY - swipe.y;
    swipe = null;
    if (Math.abs(dx) > 50 && Math.abs(dx) > 2 * Math.abs(dy)) step(dx < 0 ? 1 : -1);
  } else swipe = null;
}

function trapFocus(e) {
  const items = [...$("viewer").querySelectorAll("button:not([disabled])")];
  const at = items.indexOf(document.activeElement);
  if (!items.length || (e.shiftKey ? at > 0 : at >= 0 && at < items.length - 1)) return;
  e.preventDefault();
  items[e.shiftKey ? items.length - 1 : 0].focus();
}

// On the grid, the arrow keys move between cards and the verdict keys act on the focused card.
function gridKey(e) {
  const el = document.activeElement?.closest?.(".card");
  if (!el) return;
  const cards = [...document.querySelectorAll(".card")];
  const here = el.getBoundingClientRect();
  const dist = (r) => Math.abs(r.left + r.width / 2 - (here.left + here.width / 2));
  let target;
  if (e.key === "ArrowLeft" || e.key === "ArrowRight") target = cards[cards.indexOf(el) + (e.key === "ArrowLeft" ? -1 : 1)];
  else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    const down = e.key === "ArrowDown";
    const rows = cards.map((c) => [c, c.getBoundingClientRect()])
      .filter(([, r]) => (down ? r.top >= here.bottom - 2 : r.bottom <= here.top + 2));
    const edge = down ? Math.min(...rows.map(([, r]) => r.top)) : Math.max(...rows.map(([, r]) => r.bottom));
    target = rows.filter(([, r]) => Math.abs((down ? r.top : r.bottom) - edge) < 2)
      .sort((a, b) => dist(a[1]) - dist(b[1]))[0]?.[0];
  } else {
    const id = el.dataset.id;
    const rated = /^[1-5]$/.test(e.key) ? Number(e.key) : null;
    if (e.key === "p" || e.key === "x" || e.key === "u") decide(id, e.key === "u" ? null : { state: e.key === "p" ? "pick" : "reject" });
    else if (rated) decide(id, { rating: decisions[id]?.rating === rated ? null : rated });
    else return;
    return e.preventDefault();
  }
  if (target) { e.preventDefault(); target.focus(); }
}

function onKey(e) {
  if (e.target.matches("input, select, textarea") || $("dialog").open || e.metaKey || e.ctrlKey) return;
  if (e.key === "?") return helpDialog();
  if (!open) return gridKey(e);
  if (e.key === "Tab") return trapFocus(e);
  const p = state.photos.find((q) => q.id === open);
  const keys = {
    Escape: closeViewer, ArrowLeft: () => step(-1), ArrowRight: () => step(1),
    ArrowUp: () => jumpGroup(-1), ArrowDown: () => jumpGroup(1),
    p: () => decide(p.id, { state: "pick" }, true), x: () => decide(p.id, { state: "reject" }, true),
    u: () => decide(p.id, null, true),
    c: () => { view.compare = !view.compare; renderViewer(); },
    f: () => { view.faces = !view.faces; renderViewer(); },
    z: () => { view.zoom = !view.zoom; renderViewer(); },
  };
  if (/^[1-5]$/.test(e.key)) return decide(p.id, { rating: decisions[p.id]?.rating === Number(e.key) ? null : Number(e.key) });
  const fn = keys[e.key] || keys[e.key.toLowerCase()];
  if (fn) { e.preventDefault(); fn(); }
}

async function main() {
  setTheme(localStorage.getItem("bw-theme") || (matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark"));
  const select = $("lang");
  LANGS.forEach(([code, name]) => select.append(h("option", { value: code }, name)));
  select.onchange = () => setLanguage(select.value);
  await loadStrings(pickLanguage());
  select.value = document.documentElement.lang;
  $("btn-theme").onclick = () => setTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
  $("btn-settings").onclick = () => {
    const panel = $("panel");
    panel.hidden = !panel.hidden;
    $("btn-settings").setAttribute("aria-expanded", String(!panel.hidden));
  };
  $("btn-xmp").onclick = xmpDialog;
  $("btn-export").onclick = exportDialog;
  $("btn-undo").onclick = undo;
  $("btn-help").onclick = helpDialog;
  $("r-sim").oninput = $("r-soft").oninput = settingsChanged;
  $("r-sim").value = 0.8;
  $("r-soft").value = 0.55;
  $("o-sim").textContent = "0.80";
  $("o-soft").textContent = "0.55";
  document.addEventListener("keydown", onKey);
  for (const type of ["pointerdown", "pointerup", "pointercancel"]) $("viewer").addEventListener(type, onSwipe);
  try {
    await load();
  } catch (e) {
    $("main").replaceChildren(h("p", { class: "empty" }, `${t("error.load")}: ${e.message}`));
  }
}

main();
