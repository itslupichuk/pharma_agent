/* RXTERM desktop window — single-page app talking to the local RXTERM service. */
"use strict";

// ── plumbing ──────────────────────────────────────────────────────────
const TOKEN = new URLSearchParams(location.search).get("t") || sessionStorage.getItem("rxt") || "";
sessionStorage.setItem("rxt", TOKEN);

async function api(method, params = {}, post = false) {
  const opts = { headers: { "X-RX-Token": TOKEN } };
  let url = "/api/" + method;
  if (post) {
    opts.method = "POST";
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(params);
  } else {
    const q = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== "") q.set(k, v);
    if ([...q].length) url += "?" + q;
  }
  const r = await fetch(url, opts);
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || r.statusText);
  return r.json();
}

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
function h(html) { const t = document.createElement("template"); t.innerHTML = html.trim(); return t.content.firstElementChild; }

// ── formatting ────────────────────────────────────────────────────────
const NA = '<span class="faint">—</span>';
const cls = (v) => (v == null ? "" : v > 0 ? "up" : v < 0 ? "down" : "");
function pct(v, d = 2, sign = true) {
  if (v == null) return NA;
  const s = (v * 100).toFixed(d);
  return `<span class="${cls(v)}">${sign && v > 0 ? "+" : ""}${s}%</span>`;
}
const pctu = (v, d = 0) => (v == null ? NA : `${(v * 100).toFixed(d)}%`);
const num = (v, d = 2) => (v == null ? NA : Number(v).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d }));
function big(v) {
  if (v == null) return NA;
  const a = Math.abs(v);
  return a >= 1e12 ? (v / 1e12).toFixed(2) + "T" : a >= 1e9 ? (v / 1e9).toFixed(1) + "B" : a >= 1e6 ? (v / 1e6).toFixed(0) + "M" : num(v, 0);
}
function rsi(v) { if (v == null) return NA; const c = v >= 70 ? "down" : v <= 30 ? "up" : ""; return `<span class="${c}">${v.toFixed(0)}</span>`; }
function sig(s) {
  if (!s || s === "—" || s === "NEUTRAL") return `<span class="faint">${s === "NEUTRAL" ? "Neutral" : "—"}</span>`;
  const c = s.includes("BUY") ? "LONG" : "SHORT";
  return `<span class="sig ${c}">${esc(s)}</span>`;
}
function fmt(v, f) {
  switch (f) {
    case "pct": return pct(v);
    case "pct0u": return pctu(v, 0);
    case "pct1u": return pctu(v, 1);
    case "num1": return num(v, 1);
    case "num2": return num(v, 2);
    case "int": return v == null ? NA : Math.round(v).toString();
    case "big": return big(v);
    case "x": return v == null ? NA : v.toFixed(2) + "×";
    case "rsi": return rsi(v);
    case "signal": return sig(v);
    case "cat": return v ? `<span class="tag ${esc(String(v).split(" ")[0])}">${esc(v)}</span>` : NA;
    default: return v == null || v === "" ? NA : esc(v);
  }
}
const NUMERIC = new Set(["pct", "pct0u", "pct1u", "num1", "num2", "int", "big", "x", "rsi"]);
function spark(vals, w = 70, hgt = 18) {
  const v = (vals || []).filter((x) => x != null);
  if (v.length < 2) return "";
  const lo = Math.min(...v), hi = Math.max(...v), r = hi - lo || 1;
  const pts = v.map((x, i) => `${((i / (v.length - 1)) * w).toFixed(1)},${(hgt - 1 - ((x - lo) / r) * (hgt - 2)).toFixed(1)}`).join(" ");
  const col = v[v.length - 1] >= v[0] ? "#26d07c" : "#ff4d4f";
  return `<svg class="spark" width="${w}" height="${hgt}"><polyline fill="none" stroke="${col}" stroke-width="1.3" points="${pts}"/></svg>`;
}
const conv = (n) => "●".repeat(n) + '<span class="faint">' + "●".repeat(Math.max(0, 5 - n)) + "</span>";

// ── toasts, beep, clipboard ───────────────────────────────────────────
function toast(html, kind = "", ms = 3500) {
  const t = h(`<div class="toast ${kind}">${html}</div>`);
  $("#toasts").appendChild(t);
  setTimeout(() => t.remove(), ms);
}
function beep() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    [880, 1320].forEach((f, i) => {
      const o = ctx.createOscillator(), g = ctx.createGain();
      o.frequency.value = f; o.connect(g); g.connect(ctx.destination);
      g.gain.setValueAtTime(0.12, ctx.currentTime + i * 0.18);
      g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + i * 0.18 + 0.16);
      o.start(ctx.currentTime + i * 0.18); o.stop(ctx.currentTime + i * 0.18 + 0.17);
    });
  } catch (e) { /* no audio */ }
}
async function copy(text, what = "Copied") {
  try { await navigator.clipboard.writeText(text); }
  catch (e) { await api("copy", { text }, true).catch(() => {}); }
  toast(`<b>${esc(what)}</b><br><span class="mono">${esc(text)}</span>`);
}
const openUrl = (url) => api("open_url", { url }, true);

// ── state ─────────────────────────────────────────────────────────────
const S = {
  status: null, version: -1, monitor: null, order: [], prefs: {},
  get(k, d) { try { const v = localStorage.getItem("rx." + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem("rx." + k, JSON.stringify(v)); } catch (e) { /* ignore */ } },
};
let current = null; // active page object {name, refresh?, destroy?}

// ── routing ───────────────────────────────────────────────────────────
function go(hash) { if (location.hash === hash) route(); else location.hash = hash; }
function parseHash() {
  const raw = location.hash.replace(/^#\/?/, "");
  const [path, qs] = raw.split("?");
  const parts = path.split("/").filter(Boolean).map(decodeURIComponent);
  return { name: parts[0] || "monitor", args: parts.slice(1), q: new URLSearchParams(qs || "") };
}
const PAGES = {};
async function route() {
  closeCtx(); hideSuggest();
  const r = parseHash();
  const page = PAGES[r.name] || PAGES.monitor;
  $$("#nav a").forEach((a) => a.classList.toggle("on", a.dataset.route === (r.name === "stock" ? "" : r.name)));
  if (current && current.destroy) current.destroy();
  const root = $("#page");
  root.innerHTML = "";
  current = { name: r.name };
  if (!S.status || !S.status.ready) { root.appendChild(splash()); return; }
  try { await page(root, r, current); }
  catch (e) { console.error(e); root.innerHTML = `<div class="empty">Something went wrong loading this page: ${esc(e.message)}</div>`; }
}
window.addEventListener("hashchange", route);
function splash() {
  return h(`<div class="splash"><div class="logo"><span>RX</span>TERM</div><div class="spinner"></div>
    <div id="splash-msg">${esc((S.status && S.status.loading) || "Loading market data…")}</div></div>`);
}

// ── shared widgets ────────────────────────────────────────────────────
function sortable(table, rows, cols, renderRow, state, onClick) {
  // cols: [{key,label,fmt,num?,sort?:false}] ; state: {key, desc}
  const thead = table.querySelector("thead"), tbody = table.querySelector("tbody");
  function draw() {
    const k = state.key;
    const sorted = k ? [...rows].sort((a, b) => {
      const x = a[k], y = b[k];
      if (x == null && y == null) return 0; if (x == null) return 1; if (y == null) return -1;
      const c = typeof x === "string" ? x.localeCompare(y) : x - y;
      return state.desc ? -c : c;
    }) : rows;
    thead.innerHTML = "<tr>" + cols.map((c) => {
      const n = c.num ?? NUMERIC.has(c.fmt);
      const arrow = c.key === k ? (state.desc ? " ▼" : " ▲") : "";
      return `<th class="${n ? "n" : ""} ${c.sort === false ? "" : "sort"}" data-k="${c.key}" title="${c.sort === false ? "" : "Click to sort"}">${esc(c.label)}${arrow}</th>`;
    }).join("") + "</tr>";
    tbody.innerHTML = sorted.map(renderRow).join("");
    state.sorted = sorted;
  }
  thead.onclick = (e) => {
    const th = e.target.closest("th.sort"); if (!th) return;
    const key = th.dataset.k;
    if (state.key === key) state.desc = !state.desc; else { state.key = key; state.desc = !(typeof rows.find((r) => r[key] != null)?.[key] === "string"); }
    draw(); if (state.onSort) state.onSort();
  };
  tbody.onclick = (e) => {
    const star = e.target.closest("[data-star]");
    if (star) { e.stopPropagation(); toggleWatch(star.dataset.star, star); return; }
    const tr = e.target.closest("tr[data-t]"); if (tr && onClick) onClick(tr.dataset.t, tr, e);
  };
  tbody.oncontextmenu = (e) => {
    const tr = e.target.closest("tr[data-t]"); if (!tr) return;
    e.preventDefault(); stockMenu(tr.dataset.t, e.clientX, e.clientY);
  };
  draw();
  return { draw, setRows(r) { rows = r; draw(); } };
}

async function toggleWatch(t, el) {
  const r = await api("watch_toggle", { ticker: t }, true);
  if (el) { el.classList.toggle("on", r.watch); el.textContent = r.watch ? "★" : "☆"; }
  toast(r.watch ? `<b>${t}</b> added to your watchlist` : `<b>${t}</b> removed from your watchlist`);
  return r.watch;
}
const starHtml = (t, on) => `<span class="star ${on ? "on" : ""}" data-star="${t}" title="Add/remove from watchlist">${on ? "★" : "☆"}</span>`;

function newsList(items, onPick) {
  if (!items.length) return `<div class="empty">No stories right now.</div>`;
  return items.map((n, i) => `<div class="news-item" data-i="${i}">
      <div class="t">${esc(n.title)}</div>
      <div class="m"><span>${esc(n.time)}</span><span>${esc(n.source)}</span>${n.tickers.slice(0, 4).map((t) => `<b>${t}</b>`).join("")}
      ${n.tone !== "NEU" ? `<span class="tag ${n.tone}">${n.tone === "POS" ? "Positive" : "Negative"}</span>` : ""}
      ${n.tags.slice(0, 2).map((t) => `<span class="tag">${esc(t)}</span>`).join("")}</div></div>`).join("");
}

function newsModal(n) {
  modal(`News · ${n.source}`, `
    <h2 style="margin:0 0 8px;font-size:17px;line-height:1.35">${esc(n.title)}</h2>
    <div class="dim mono" style="margin-bottom:10px">${esc(n.time)} · ${esc(n.age)} ago · ${esc(n.source)}</div>
    <p style="color:#c9d1d9;line-height:1.6">${esc(n.summary) || '<span class="faint">No summary in the feed — open the article to read it.</span>'}</p>
    <div style="display:flex;gap:6px;flex-wrap:wrap">${n.tickers.map((t) => `<button class="chip" data-go="#/stock/${t}">${t}</button>`).join("")}</div>`,
    [["Open article in browser", "primary", () => { openUrl(n.link); return true; }], ["Copy link", "", () => { copy(n.link, "Link copied"); return true; }], ["Close", "", () => true]], 640);
}

// ── context menu ──────────────────────────────────────────────────────
function stockMenu(t, x, y) {
  const m = $("#ctx");
  const items = [
    ["Open chart & details", () => go(`#/stock/${t}`)],
    ["Options chain", () => go(`#/options/${t}`)],
    ["News for " + t, () => go(`#/news?t=${t}`)],
    ["Compare with sector (XBI)", () => go(`#/compare/${t},XBI`)],
    ["Add / remove watchlist", () => toggleWatch(t)],
    ["Set price alert…", () => alertDialog(t)],
    ["Copy ticker", () => copy(t)],
  ];
  m.innerHTML = `<div class="hdr">${esc(t)}</div>` + items.map((it, i) => `<div data-i="${i}">${esc(it[0])}</div>`).join("");
  m.onclick = (e) => { const d = e.target.closest("[data-i]"); if (d) { closeCtx(); items[+d.dataset.i][1](); } };
  m.classList.remove("hidden");
  const r = m.getBoundingClientRect();
  m.style.left = Math.min(x, innerWidth - r.width - 6) + "px";
  m.style.top = Math.min(y, innerHeight - r.height - 6) + "px";
}
function closeCtx() { $("#ctx").classList.add("hidden"); }
document.addEventListener("click", (e) => { if (!e.target.closest("#ctx")) closeCtx(); });

// ── modals ────────────────────────────────────────────────────────────
function modal(title, bodyHtml, buttons = [["Close", "", () => true]], width = 520) {
  const ov = h(`<div class="overlay"><div class="modal" style="width:${width}px"><h3>${esc(title)}<button class="x" title="Close">✕</button></h3>
    <div class="mb">${bodyHtml}</div><div class="mf"></div></div></div>`);
  const close = () => { ov.remove(); document.removeEventListener("keydown", onKey); };
  const onKey = (e) => { if (e.key === "Escape") close(); };
  document.addEventListener("keydown", onKey);
  ov.addEventListener("mousedown", (e) => { if (e.target === ov) close(); });
  $(".x", ov).onclick = close;
  const mf = $(".mf", ov);
  buttons.forEach(([label, kind, fn]) => {
    const b = h(`<button class="btn ${kind}">${esc(label)}</button>`);
    b.onclick = async () => { if (await fn(ov)) close(); };
    mf.appendChild(b);
  });
  ov.addEventListener("click", (e) => { const g = e.target.closest("[data-go]"); if (g) { close(); go(g.dataset.go); } });
  $("#modal-root").appendChild(ov);
  ov.close = close;
  return ov;
}

function pickTicker(title, exclude = []) {
  return new Promise(async (resolve) => {
    const all = await api("search", { q: "" });
    let done = false;
    const ov = modal(title, `<input class="big" id="pk-q" placeholder="Type to filter, or scroll and click" autocomplete="off">
      <div class="plist" id="pk-list"></div>`, [["Cancel", "", () => true]], 560);
    const list = $("#pk-list", ov), q = $("#pk-q", ov);
    function fill() {
      const s = q.value.trim().toUpperCase();
      const rows = all.filter((x) => !exclude.includes(x.ticker) && (!s || x.ticker.startsWith(s) || x.name.toUpperCase().includes(s)));
      rows.sort((a, b) => (s ? (b.ticker.startsWith(s) - a.ticker.startsWith(s)) : 0));
      list.innerHTML = rows.map((x, i) => `<div class="sug ${i === 0 && s ? "on" : ""}" data-t="${x.ticker}"><b>${x.ticker}</b><span>${esc(x.name)}</span><span class="seg">${esc(x.segment)}</span></div>`).join("")
        || '<div class="empty">No match</div>';
    }
    list.onclick = (e) => { const d = e.target.closest("[data-t]"); if (d) { done = true; ov.close(); resolve(d.dataset.t); } };
    q.oninput = fill;
    q.onkeydown = (e) => { if (e.key === "Enter") { const d = $("[data-t]", list); if (d) { done = true; ov.close(); resolve(d.dataset.t); } } };
    const obs = new MutationObserver(() => { if (!ov.isConnected) { obs.disconnect(); if (!done) resolve(null); } });
    obs.observe($("#modal-root"), { childList: true });
    fill(); setTimeout(() => q.focus(), 30);
  });
}

async function alertDialog(t, preset) {
  const st = await api("stock", { ticker: t });
  const last = st.last;
  const ov = modal(`Price alert · ${t}`, `
    <div class="dim" style="margin-bottom:8px">${esc(st.name || "")} — now <b class="mono" style="color:#fff">${num(last)}</b></div>
    <input class="big" id="al-px" value="${(preset ?? last ?? "").toString() && Number(preset ?? last).toFixed(2)}" inputmode="decimal">
    <div class="pctrow">${[-10, -5, -2, 2, 5, 10].map((p) => `<button class="btn ${p < 0 ? "red" : "green"}" data-p="${p}">${p > 0 ? "+" : ""}${p}%</button>`).join("")}</div>
    <div class="dim">You'll get a pop-up and a chime while RXTERM is open when the price crosses your level.</div>
    <div class="err-text" id="al-err"></div>`,
    [["Alert when ABOVE ▲", "green", () => save(">")], ["Alert when BELOW ▼", "red", () => save("<")], ["Cancel", "", () => true]], 540);
  const inp = $("#al-px", ov);
  $(".pctrow", ov).onclick = (e) => { const b = e.target.closest("[data-p]"); if (b && last) inp.value = (last * (1 + b.dataset.p / 100)).toFixed(2); };
  setTimeout(() => inp.select(), 30);
  async function save(op) {
    const lv = parseFloat(String(inp.value).replace(/,/g, ""));
    if (!(lv > 0)) { $("#al-err", ov).textContent = "Enter a price, or click one of the % buttons."; return false; }
    const r = await api("alert_add", { ticker: t, op, level: lv }, true);
    toast(`Alert set: <b>${esc(r.alert)}</b>`);
    if (current && current.refresh) current.refresh(true);
    pollStatus();
    return true;
  }
}

// ── top bar: search with suggestions ──────────────────────────────────
let sugIdx = 0, sugRows = [], sugTimer = null;
const search = $("#search"), sug = $("#suggest");
function hideSuggest() { sug.classList.add("hidden"); }
async function showSuggest() {
  const q = search.value.trim();
  if (!q) { hideSuggest(); return; }
  sugRows = (await api("search", { q })).slice(0, 12);
  sugIdx = 0;
  sug.innerHTML = sugRows.map((x, i) => `<div class="sug ${i === 0 ? "on" : ""}" data-t="${x.ticker}"><b>${x.ticker}</b><span>${esc(x.name)}</span><span class="seg">${esc(x.segment)}</span></div>`).join("")
    || '<div class="sug dim">No matching stock in the RXTERM universe</div>';
  sug.classList.remove("hidden");
}
search.addEventListener("input", () => { clearTimeout(sugTimer); sugTimer = setTimeout(showSuggest, 60); });
search.addEventListener("focus", () => { if (search.value) showSuggest(); });
search.addEventListener("keydown", (e) => {
  const items = $$(".sug[data-t]", sug);
  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    e.preventDefault(); if (!items.length) return;
    sugIdx = (sugIdx + (e.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
    items.forEach((x, i) => x.classList.toggle("on", i === sugIdx));
  } else if (e.key === "Enter") {
    const t = items[sugIdx]?.dataset.t || search.value.trim().toUpperCase();
    if (t) { search.value = ""; hideSuggest(); search.blur(); go(`#/stock/${t}`); }
  } else if (e.key === "Escape") { search.value = ""; hideSuggest(); search.blur(); }
});
sug.addEventListener("mousedown", (e) => {
  const d = e.target.closest("[data-t]"); if (!d) return;
  e.preventDefault(); search.value = ""; hideSuggest(); search.blur(); go(`#/stock/${d.dataset.t}`);
});
document.addEventListener("mousedown", (e) => { if (!e.target.closest("#searchbox")) hideSuggest(); });
// start typing anywhere (outside inputs) to search
document.addEventListener("keydown", (e) => {
  if (e.ctrlKey || e.altKey || e.metaKey || $(".overlay")) return;
  const tag = (document.activeElement && document.activeElement.tagName) || "";
  if (tag === "INPUT" || tag === "TEXTAREA") return;
  if (/^[a-zA-Z]$/.test(e.key)) { search.focus(); }
  if (e.key === "Backspace" && location.hash.startsWith("#/stock")) { e.preventDefault(); history.back(); }
});
$("#back-btn").onclick = () => history.back();
document.addEventListener("click", (e) => {
  const g = e.target.closest("[data-go]");
  if (g && !e.target.closest(".overlay")) { e.preventDefault(); go(g.dataset.go); }
});
// mouse side buttons (back/forward) — handled here once, so the window doesn't also navigate
window.addEventListener("mousedown", (e) => { if (e.button === 3 || e.button === 4) e.preventDefault(); });
window.addEventListener("mouseup", (e) => {
  if (e.button === 3) { e.preventDefault(); history.back(); }
  if (e.button === 4) { e.preventDefault(); history.forward(); }
});
$("#refresh-btn").onclick = async () => { await api("refresh", {}, true); toast("Refreshing all data in the background…"); pollStatus(); };

// ── status polling ────────────────────────────────────────────────────
async function pollStatus() {
  let st;
  try { st = await api("status"); } catch (e) { $("#st-msg").textContent = "RXTERM service not responding…"; $("#st-msg").className = "err"; return; }
  const wasReady = S.status && S.status.ready;
  S.status = st;
  $("#mkt").textContent = st.market; $("#mkt").className = "badge " + st.market;
  const msg = $("#st-msg");
  if (st.error) { msg.textContent = st.error; msg.className = "err"; }
  else if (st.loading) { msg.textContent = st.loading; msg.className = "busy"; }
  else { msg.textContent = "Live · prices refresh every minute while the market is open"; msg.className = ""; }
  const sm = $("#splash-msg"); if (sm && st.loading) sm.textContent = st.loading;
  $("#st-src").textContent = st.provider ? `Data: ${st.provider}` : "";
  $("#st-upd").textContent = st.updated ? `Updated ${st.updated}` : "";
  $("#st-alerts").textContent = st.alerts ? `🔔 ${st.alerts} alert${st.alerts > 1 ? "s" : ""} armed` : "";
  for (const ev of st.events || []) { beep(); toast(`🔔 <b>Price alert</b><br>${esc(ev.text)}`, "alert", 15000); }
  if (st.ready && !wasReady) { loadTape(); route(); }
  else if (st.ready && st.version !== S.version && S.version !== -1) {
    loadTape();
    if (current && current.refresh) current.refresh(false);
  }
  S.version = st.version;
}
function tickClock() {
  try {
    $("#clock").textContent = new Date().toLocaleString("en-US", { timeZone: "America/New_York", weekday: "short", month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }) + " ET";
  } catch (e) { $("#clock").textContent = new Date().toLocaleTimeString(); }
}
async function loadTape() {
  const rows = await api("tape");
  const html = rows.map((r) => `<span class="tk" data-go="#/stock/${r.ticker}"><b>${r.ticker}</b>${num(r.last)} ${pct(r.chg)}</span>`).join("");
  $("#tape-inner").innerHTML = html + html;
  $("#tape-inner").style.animationDuration = Math.max(60, rows.length * 3.2) + "s";
}

// ══ PAGES ═════════════════════════════════════════════════════════════

// ── Monitor ───────────────────────────────────────────────────────────
const MON_FILTERS = [["ALL", "All stocks"], ["Big Pharma", "Big Pharma"], ["Large-Cap Biotech", "Large-cap biotech"], ["SMID Biotech", "Small/mid biotech"],
  ["Specialty & Generics", "Specialty & generics"], ["WATCH", "★ My watchlist"], ["BUY", "Buy signals"], ["SELL", "Sell signals"], ["CAT", "Catalyst ≤ 30 days"]];
const MON_COLS = [
  { key: "watch", label: "★", sort: false }, { key: "ticker", label: "Ticker" }, { key: "name", label: "Company" },
  { key: "last", label: "Last", fmt: "num2" }, { key: "chg1d", label: "Today", fmt: "pct" }, { key: "chg5d", label: "5 day", fmt: "pct" },
  { key: "chg1m", label: "1 month", fmt: "pct" }, { key: "ytd", label: "YTD", fmt: "pct" }, { key: "spark", label: "3 months", sort: false },
  { key: "rsi", label: "RSI", fmt: "rsi" }, { key: "vol_ratio", label: "Volume×", fmt: "x" }, { key: "signal", label: "Signal" },
  { key: "long_score", label: "Score", fmt: "int" }, { key: "cat_days", label: "Catalyst", num: false },
];
PAGES.monitor = async (root, r, page) => {
  const seg = r.q.get("f") || S.get("monfilter", "ALL");
  const state = S.get("monsort", { key: "chg1d", desc: true });
  root.appendChild(h(`<div id="mon">
    <div class="panel main"><div class="toolbar" id="mon-filters"></div>
      <div class="scroll" style="flex:1"><table class="grid" id="mon-table"><thead></thead><tbody></tbody></table></div></div>
    <div class="col scroll" id="mon-side"></div></div>`));
  $("#mon-filters").innerHTML = MON_FILTERS.map(([k, l]) => `<button class="chip ${k === seg ? "on" : ""}" data-f="${k}">${esc(l)}</button>`).join("") +
    `<span class="grow"></span><span class="dim" id="mon-count"></span>`;
  $("#mon-filters").onclick = (e) => { const b = e.target.closest("[data-f]"); if (b) { S.set("monfilter", b.dataset.f); go(`#/monitor?f=${encodeURIComponent(b.dataset.f)}`); } };
  let table;
  state.onSort = () => { S.set("monsort", { key: state.key, desc: state.desc }); S.order = state.sorted.map((x) => x.ticker); };
  const rowHtml = (x) => `<tr class="click" data-t="${x.ticker}"><td>${starHtml(x.ticker, x.watch)}</td><td class="tkr">${x.ticker}</td><td class="name" title="${esc(x.name)}">${esc(x.name)}</td>
      <td class="n">${num(x.last)}</td><td class="n">${pct(x.chg1d)}</td><td class="n">${pct(x.chg5d)}</td><td class="n">${pct(x.chg1m)}</td><td class="n">${pct(x.ytd)}</td>
      <td>${spark(x.spark)}</td><td class="n">${rsi(x.rsi)}</td><td class="n">${fmt(x.vol_ratio, "x")}</td><td>${sig(x.signal)}</td><td class="n">${fmt(x.long_score, "int")}</td>
      <td>${x.cat_type ? `<span class="tag ${x.cat_type}">${x.cat_type}</span><span class="mono dim">${x.cat_days}d</span>` : ""}</td></tr>`;
  const filt = (rows) => rows.filter((x) => seg === "ALL" ? true : seg === "WATCH" ? x.watch : seg === "BUY" ? x.signal.includes("BUY")
    : seg === "SELL" ? x.signal.includes("SELL") : seg === "CAT" ? x.cat_type && x.cat_days <= 30 : x.segment === seg);
  async function load(first) {
    const m = await api("monitor");
    if (!m.ready) return;
    S.monitor = m;
    const rows = filt(m.rows);
    $("#mon-count").textContent = `${rows.length} stocks · click a row to open · right-click for more`;
    if (first) table = sortable($("#mon-table"), rows, MON_COLS, rowHtml, state, (t) => go(`#/stock/${t}`));
    else { const sc = $("#mon-table").parentElement.scrollTop; table.setRows(rows); $("#mon-table").parentElement.scrollTop = sc; }
    S.order = state.sorted.map((x) => x.ticker);
    side(m);
  }
  function side(m) {
    const b = m.breadth, adv = b.advancers || 0, dec = b.decliners || 0;
    const el = $("#mon-side");
    const sc = el.scrollTop;
    el.innerHTML = `
      <div class="panel"><h3>Benchmarks</h3><div class="bench">${m.benchmarks.map((x) => `<div class="bcard" data-go="#/stock/${x.ticker}">
        <b>${x.ticker}</b><div class="px">${num(x.last)}</div><div class="ch">${pct(x.chg1d)}</div><div class="ch dim">YTD ${pct(x.ytd, 1)}</div></div>`).join("")}</div>
        <div class="breadth"><span>Up <b class="up">${adv}</b></span><span>Down <b class="down">${dec}</b></span><span>Above 50-day <b>${pctu(b.above50)}</b></span><span>Above 200-day <b>${pctu(b.above200)}</b></span><span>New highs <b>${b.new_highs ?? 0}</b></span></div>
        <div class="bar2"><div style="width:${(adv / Math.max(1, adv + dec)) * 100}%"></div></div></div>
      <div class="panel"><h3>Sectors</h3><table class="grid"><thead><tr><th>Segment</th><th class="n">Today</th><th class="n">5D</th><th class="n">1M</th><th class="n">YTD</th></tr></thead><tbody>
        ${m.segments.map((s) => `<tr class="click" data-f="${esc(s.segment)}"><td>${esc(s.segment)}</td><td class="n">${pct(s.chg1d)}</td><td class="n">${pct(s.chg5d)}</td><td class="n">${pct(s.chg1m)}</td><td class="n">${pct(s.ytd, 1)}</td></tr>`).join("")}</tbody></table></div>
      <div class="panel"><h3>Today's trade ideas <span class="grow"></span><button class="btn small" data-go="#/trades">Open all ›</button></h3>
        ${m.ideas.map((i) => `<div class="mini-idea" data-go="#/trades?t=${i.ticker}"><span class="tierlbl">${i.tier.slice(0, 5)}</span><b>${i.ticker}</b><span>${esc(i.structure)}</span><span class="dir ${i.direction.replace(" ", "")}">${i.direction}</span></div>`).join("") || '<div class="empty">Building trade ideas…</div>'}</div>
      <div class="panel"><h3>Top news <span class="grow"></span><button class="btn small" data-go="#/news">All news ›</button></h3><div id="mon-news">${newsList(m.news.slice(0, 14))}</div></div>`;
    el.scrollTop = sc;
    $$("tr[data-f]", el).forEach((tr) => tr.onclick = () => { S.set("monfilter", tr.dataset.f); go(`#/monitor?f=${encodeURIComponent(tr.dataset.f)}`); });
    $("#mon-news").onclick = (e) => { const d = e.target.closest("[data-i]"); if (d) newsModal(m.news[+d.dataset.i]); };
  }
  page.refresh = () => load(false);
  await load(true);
};

// ── Stock page ────────────────────────────────────────────────────────
const TFS = ["1D", "5D", "1M", "3M", "6M", "YTD", "1Y", "2Y", "5Y", "10Y"];
function makeChart(el, opts = {}) {
  return LightweightCharts.createChart(el, Object.assign({
    autoSize: true,
    layout: { background: { type: "solid", color: "#0a0c0f" }, textColor: "#8b949e", fontFamily: "Cascadia Mono, Consolas, monospace", fontSize: 11 },
    grid: { vertLines: { color: "#14181d" }, horzLines: { color: "#14181d" } },
    rightPriceScale: { borderColor: "#262b33" },
    timeScale: { borderColor: "#262b33", rightOffset: 3 },
    crosshair: { mode: 0, vertLine: { color: "#ff9e1b55", labelBackgroundColor: "#ff9e1b" }, horzLine: { color: "#ff9e1b55", labelBackgroundColor: "#ff9e1b" } },
  }, opts));
}
function sma(bars, n) {
  const out = []; let s = 0;
  for (let i = 0; i < bars.length; i++) {
    s += bars[i].close; if (i >= n) s -= bars[i - n].close;
    if (i >= n - 1) out.push({ time: bars[i].time, value: s / n });
  }
  return out;
}
PAGES.stock = async (root, r, page) => {
  const t = (r.args[0] || "LLY").toUpperCase();
  let tf = r.q.get("tf") || S.get("tf", "6M");
  const ch = S.get("chartopts", { type: "candle", ma: true, vol: true });
  root.appendChild(h(`<div id="stk"><div class="shead" id="sh"></div>
    <div class="body2">
      <div class="panel"><div class="toolbar">
          <div class="seg-btns" id="tfs">${TFS.map((x) => `<button data-tf="${x}" class="${x === tf ? "on" : ""}">${x}</button>`).join("")}</div>
          <span class="lbl">Chart</span><div class="seg-btns" id="ctype"><button data-c="candle">Candles</button><button data-c="line">Line</button><button data-c="area">Area</button></div>
          <button class="chip" id="t-ma" title="Moving averages">Moving avgs</button><button class="chip" id="t-vol">Volume</button>
          <span class="grow"></span><button class="btn small" id="fit" title="Show the whole period">Reset zoom</button></div>
        <div class="chartwrap"><div class="legend" id="lg"></div><div class="chart" id="chart"></div></div></div>
      <div class="panel" style="grid-row: span 2"><h3>Key stats</h3><div class="body" style="padding:0"><div class="statgrid" id="stats"></div></div></div>
      <div class="row" style="min-height:0">
        <div class="panel" style="flex:1.3"><h3>News · ${t}<span class="grow"></span><button class="btn small" data-go="#/news?t=${t}">More ›</button></h3><div class="body" style="padding:0" id="snews"></div></div>
        <div class="panel" style="flex:1"><h3 id="about-h">About</h3><div class="body" id="about"></div></div>
      </div></div></div>`));
  const chart = makeChart($("#chart"));
  let main = null, vol = null, mas = [], bars = [], maShown = [], levels = [];
  function series() {
    if (main) chart.removeSeries(main); if (vol) { chart.removeSeries(vol); vol = null; } mas.forEach((m) => chart.removeSeries(m)); mas = [];
    if (ch.type === "candle") main = chart.addCandlestickSeries({ upColor: "#26d07c", downColor: "#ff4d4f", borderVisible: false, wickUpColor: "#26d07c", wickDownColor: "#ff4d4f" });
    else if (ch.type === "line") main = chart.addLineSeries({ color: "#ff9e1b", lineWidth: 2 });
    else main = chart.addAreaSeries({ lineColor: "#ff9e1b", topColor: "#ff9e1b44", bottomColor: "#ff9e1b05", lineWidth: 2 });
    main.priceScale().applyOptions({ scaleMargins: { top: 0.08, bottom: ch.vol ? 0.24 : 0.05 } });
    main.setData(ch.type === "candle" ? bars : bars.map((b) => ({ time: b.time, value: b.close })));
    if (ch.vol) {
      vol = chart.addHistogramSeries({ priceFormat: { type: "volume" }, priceScaleId: "", lastValueVisible: false, priceLineVisible: false });
      vol.priceScale().applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
      vol.setData(bars.map((b) => ({ time: b.time, value: b.volume || 0, color: b.close >= b.open ? "#26d07c55" : "#ff4d4f55" })));
    }
    maShown = [];
    if (ch.ma) [[20, "#58a6ff"], [50, "#c18cff"], [200, "#e6edf3"]].forEach(([n, c]) => {
      if (bars.length > n + 2) { const s = chart.addLineSeries({ color: c, lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false }); s.setData(sma(bars, n)); mas.push(s); maShown.push([n, c]); }
    });
    levels.forEach((l) => main.createPriceLine({ price: l.price, color: l.color, lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: l.title }));
    $("#t-ma").classList.toggle("on", ch.ma); $("#t-vol").classList.toggle("on", ch.vol);
    $$("#ctype button").forEach((b) => b.classList.toggle("on", b.dataset.c === ch.type));
    legend();
  }
  function legend(b) {
    b = b || bars[bars.length - 1]; if (!b) { $("#lg").innerHTML = "No price data for this period."; return; }
    const first = bars[0], chg = first ? b.close / first.close - 1 : null;
    const when = typeof b.time === "number" ? new Date(b.time * 1000).toISOString().slice(0, 16).replace("T", " ") : b.time;
    $("#lg").innerHTML = `<span>${when}</span><span>O <b>${num(b.open)}</b></span><span>H <b>${num(b.high)}</b></span><span>L <b>${num(b.low)}</b></span><span>C <b>${num(b.close)}</b></span>
      <span>Vol <b>${big(b.volume)}</b></span><span>${tf} ${pct(chg)}</span>${maShown.map(([n, c]) => `<span style="color:${c}">MA${n}</span>`).join("")}`;
  }
  chart.subscribeCrosshairMove((p) => {
    if (!p || !p.time) { legend(); return; }
    const b = bars.find((x) => x.time === p.time); if (b) legend(b);
  });
  async function loadBars() {
    $$("#tfs button").forEach((b) => b.classList.toggle("on", b.dataset.tf === tf));
    const d = await api("bars", { ticker: t, tf });
    bars = d.bars;
    chart.applyOptions({ timeScale: { timeVisible: d.intraday, secondsVisible: false } });
    series(); chart.timeScale().fitContent();
  }
  $("#tfs").onclick = (e) => { const b = e.target.closest("[data-tf]"); if (b) { tf = b.dataset.tf; S.set("tf", tf); history.replaceState(null, "", `#/stock/${t}?tf=${tf}`); loadBars(); } };
  $("#ctype").onclick = (e) => { const b = e.target.closest("[data-c]"); if (b) { ch.type = b.dataset.c; S.set("chartopts", ch); series(); } };
  $("#t-ma").onclick = () => { ch.ma = !ch.ma; S.set("chartopts", ch); series(); };
  $("#t-vol").onclick = () => { ch.vol = !ch.vol; S.set("chartopts", ch); series(); };
  $("#fit").onclick = () => chart.timeScale().fitContent();

  async function loadInfo(first) {
    const d = await api("stock", { ticker: t });
    if (!d.ready) { $("#sh").innerHTML = `<div class="tkr">${esc(t)}</div><div class="dim">Not in the RXTERM universe or no data yet.</div>`; return; }
    const order = S.order.length ? S.order : (S.monitor ? S.monitor.rows.map((x) => x.ticker) : []);
    const i = order.indexOf(t);
    const prev = i > 0 ? order[i - 1] : null, next = i >= 0 && i < order.length - 1 ? order[i + 1] : null;
    $("#sh").innerHTML = `<div><div class="tkr">${d.ticker}</div></div><div><div class="nm">${esc(d.name)}</div><div class="sg">${esc(d.segment)}</div></div>
      <div class="px">${num(d.last)}</div><div class="ch">${pct(d.chg1d)} <span class="dim" style="font-size:12px">today</span>${d.premkt != null ? `<div class="dim" style="font-size:12px">pre/post ${pct(d.premkt)}</div>` : ""}</div>
      <div>${sig(d.signal)}<div class="dim mono" style="font-size:11px;margin-top:3px">Long ${fmt(d.long_score, "int")} · Short ${fmt(d.short_score, "int")}</div></div>
      <div class="acts">
        <button class="btn ${d.watch ? "on" : ""}" id="a-watch">${d.watch ? "★ On watchlist" : "☆ Add to watchlist"}</button>
        <button class="btn" id="a-alert">🔔 Price alert</button>
        <button class="btn" data-go="#/options/${t}">Options</button>
        <button class="btn" data-go="#/compare/${t},XBI">Compare</button>
        <button class="btn" ${prev ? `data-go="#/stock/${prev}"` : "disabled"} title="Previous stock in the list">◀ ${prev || ""}</button>
        <button class="btn" ${next ? `data-go="#/stock/${next}"` : "disabled"} title="Next stock in the list">${next || ""} ▶</button></div>`;
    $("#a-watch").onclick = async (e) => { const on = await toggleWatch(t); e.target.classList.toggle("on", on); e.target.textContent = on ? "★ On watchlist" : "☆ Add to watchlist"; };
    $("#a-alert").onclick = () => alertDialog(t);
    const lv = d.alerts.filter((a) => a.armed && a.level).map((a) => ({ price: a.level, color: "#ff9e1b", title: "Alert" }));
    if (d.idea && d.idea.basis !== "premium") lv.push({ price: d.idea.target, color: "#26d07c", title: "Target" }, { price: d.idea.stop, color: "#ff4d4f", title: "Stop" });
    const changed = JSON.stringify(lv) !== JSON.stringify(levels);
    levels = lv;
    if (changed && main) series();
    $("#stats").innerHTML = d.stats.map((s) => `<div>${esc(s.label)}</div><div>${fmt(s.value, s.fmt)}</div>`).join("") +
      (d.alerts.length ? `<div class="amber">Your alerts</div><div>${d.alerts.map((a) => `<div>${esc(a.text)} ${a.armed ? "" : "✓"}</div>`).join("")}</div>` : "");
    if (first) {
      const showNews = (items) => {
        $("#snews").innerHTML = newsList(items);
        $("#snews").onclick = (e) => { const x = e.target.closest("[data-i]"); if (x) newsModal(items[+x.dataset.i]); };
      };
      if (d.news.length) showNews(d.news); else $("#snews").innerHTML = '<div class="empty">Loading news…</div>';
      api("stock_news", { ticker: t }).then((n) => { if ($("#snews")) showNews(n.items); }).catch(() => showNews(d.news));
      const idea = d.idea;
      $("#about").innerHTML = (idea ? `<div class="idea-card"><div style="display:flex;gap:8px;align-items:center;margin-bottom:6px"><span class="tierlbl">${idea.tier}</span><span class="dir ${idea.direction.replace(" ", "")}">${idea.direction}</span><b>${esc(idea.structure)}</b>
          <span class="grow"></span><button class="btn small" data-go="#/trades?t=${t}">Full trade ›</button></div>
          <div class="mono" style="color:#fff;margin-bottom:6px">${esc(idea.trade_line)}</div><div style="font-weight:700;margin-bottom:4px">${esc(idea.headline)}</div><div class="about">${esc(idea.thesis)}</div></div>` : "") +
        (d.catalyst ? `<div style="margin-bottom:10px"><span class="tag PDUFA">Catalyst</span> ${esc(d.catalyst)}</div>` : "") +
        `<div class="about">${esc(d.summary) || '<span class="faint">No company description available.</span>'}</div>` +
        (d.website ? `<div style="margin-top:10px"><button class="btn small" id="site">Company website ↗</button></div>` : "");
      if (d.website) $("#site").onclick = () => openUrl(d.website);
      $("#about-h").textContent = idea ? "Trade idea & company" : "About the company";
    }
  }
  page.refresh = () => loadInfo(false);
  page.destroy = () => chart.remove();
  await Promise.all([loadInfo(true), loadBars()]);
};

// ── Trade ideas ───────────────────────────────────────────────────────
function tradeCard(i) {
  const lv = i.basis === "premium"
    ? [["Premium", num(i.net_premium)], ["Target", num(i.target)], ["Stop", num(i.stop)], ["Reward:risk", i.rr ? i.rr.toFixed(1) + ":1" : "—"], ["Horizon", esc(i.horizon)]]
    : [["Entry", num(i.entry)], ["Target", num(i.target)], ["Stop", num(i.stop)], ["Reward:risk", i.rr ? i.rr.toFixed(1) + ":1" : "—"], ["Horizon", esc(i.horizon)]];
  const extra = [i.max_gain != null ? `Max gain <b class="up">${num(i.max_gain)}</b>` : "", i.max_loss != null ? `Max loss <b class="down">${num(i.max_loss)}</b>` : "",
    i.breakeven != null ? `Breakeven <b>${num(i.breakeven)}</b>` : "", i.iv != null ? `IV <b>${pctu(i.iv)}</b>` : "", i.rv != null ? `Realized vol <b>${pctu(i.rv)}</b>` : ""].filter(Boolean);
  return `<div class="tcard" id="tc-${i.ticker}">
    <div class="hd"><span class="tkr" data-go="#/stock/${i.ticker}">${i.ticker}</span><span class="nm">${esc(i.name)}</span>
      <span class="dir ${i.direction.replace(" ", "")}">${i.direction}</span><b>${esc(i.structure)}</b><span class="conv" title="Conviction">${conv(i.conviction)}</span></div>
    <div class="tl">${esc(i.trade_line)}</div>
    <div class="lv">${lv.map(([k, v]) => `<div><small>${k}</small><span>${v}</span></div>`).join("")}</div>
    ${extra.length ? `<div class="dim mono" style="padding:6px 12px;border-bottom:1px solid var(--line);display:flex;gap:16px;flex-wrap:wrap;font-size:12px">${extra.join("")}</div>` : ""}
    <div class="hl">${esc(i.headline)}</div><div class="th">${esc(i.thesis)}</div>
    ${i.drivers.length ? `<div class="sec">Why</div><ul>${i.drivers.map((d) => `<li>${esc(d)}</li>`).join("")}</ul>` : ""}
    ${i.risks.length ? `<div class="sec">Risks</div><ul>${i.risks.map((d) => `<li>${esc(d)}</li>`).join("")}</ul>` : ""}
    <div class="ft"><button class="btn primary small" data-go="#/stock/${i.ticker}">Chart</button><button class="btn small" data-go="#/options/${i.ticker}">Options chain</button>
      <button class="btn small" data-copy="${esc(i.ticker + ": " + i.trade_line)}">Copy trade</button>
      <button class="btn small green" data-alert="${i.ticker}" data-lv="${i.basis === "premium" ? "" : i.target}">Alert at target</button>
      <button class="btn small red" data-alert="${i.ticker}" data-lv="${i.basis === "premium" ? "" : i.stop}">Alert at stop</button></div></div>`;
}
PAGES.trades = async (root, r, page) => {
  const d = await api("ideas");
  const cons = d.ideas.filter((i) => i.tier === "CONSERVATIVE"), aggr = d.ideas.filter((i) => i.tier !== "CONSERVATIVE");
  root.appendChild(h(`<div id="trades" class="scroll">
    ${d.market_take ? `<div class="take"><b class="amber">MARKET TAKE</b> <span class="dim">· theses by ${esc(d.writer)}</span><br>${esc(d.market_take)}</div>` : ""}
    <div class="tcols">
      <div><div class="ph" style="margin-bottom:10px">Conservative <span class="sub">liquid names · defined-risk spreads · 30–60 days</span></div>${cons.map(tradeCard).join("") || '<div class="empty">No ideas yet.</div>'}</div>
      <div><div class="ph" style="margin-bottom:10px">Aggressive <span class="sub">higher-volatility names · catalysts · outright options</span></div>${aggr.map(tradeCard).join("") || '<div class="empty">No ideas yet.</div>'}</div>
    </div>
    <div class="dim" style="padding:0 14px 16px;font-size:11.5px">Ideas are generated from public data for research and education. Not investment advice. Size positions so a stop-out is a small loss.</div></div>`));
  root.onclick = (e) => {
    const c = e.target.closest("[data-copy]"); if (c) copy(c.dataset.copy, "Trade copied");
    const a = e.target.closest("[data-alert]"); if (a) alertDialog(a.dataset.alert, a.dataset.lv ? parseFloat(a.dataset.lv) : undefined);
  };
  const want = r.q.get("t");
  if (want) { const el = $("#tc-" + want); if (el) { el.scrollIntoView({ block: "center" }); el.style.borderColor = "var(--amber)"; } }
};

// ── Screener ──────────────────────────────────────────────────────────
PAGES.screener = async (root, r, page) => {
  const screens = await api("screens");
  const code = (r.args[0] || S.get("screen", "TOPLONG")).toUpperCase();
  root.appendChild(h(`<div id="scr"><div class="panel"><h3>Screens</h3><div class="body slist" style="padding:0">${screens.map((s) => `<div class="si ${s.code === code ? "on" : ""}" data-c="${s.code}"><b>${esc(s.title)}</b><small>${esc(s.description)}</small></div>`).join("")}</div></div>
    <div class="panel" id="scr-r"><h3 id="scr-t"></h3><div class="sdesc" id="scr-d"></div><div class="scroll" style="flex:1"><table class="grid" id="scr-table"><thead></thead><tbody></tbody></table></div></div></div>`));
  $(".slist").onclick = (e) => { const d = e.target.closest("[data-c]"); if (d) { S.set("screen", d.dataset.c); go(`#/screener/${d.dataset.c}`); } };
  const state = { key: null, desc: true };
  let table;
  async function load(first) {
    const d = await api("screen", { code });
    $("#scr-t").innerHTML = `${esc(d.title)} <span class="sub">${d.rows.length} matches · click a row to open</span>`;
    $("#scr-d").textContent = d.description;
    const cols = [{ key: "ticker", label: "Ticker" }, { key: "name", label: "Company" }, ...d.columns];
    const rowHtml = (x) => `<tr class="click" data-t="${x.ticker}"><td class="tkr">${x.ticker}</td><td class="name">${esc(x.name)}</td>${d.columns.map((c) => `<td class="${NUMERIC.has(c.fmt) ? "n" : ""} ${c.key === "headline" || c.key === "cat_event" ? "wrap" : ""}">${fmt(x[c.key], c.fmt)}</td>`).join("")}</tr>`;
    if (first) table = sortable($("#scr-table"), d.rows, cols, rowHtml, state, (t) => go(`#/stock/${t}`));
    else table.setRows(d.rows);
    S.order = state.sorted.map((x) => x.ticker);
    state.onSort = () => { S.order = state.sorted.map((x) => x.ticker); };
  }
  page.refresh = () => load(false);
  await load(true);
};

// ── Calendar ──────────────────────────────────────────────────────────
PAGES.calendar = async (root, r, page) => {
  const typ = r.q.get("type") || "ALL";
  root.appendChild(h(`<div id="cal"><div class="toolbar" id="cal-f"></div><div class="scroll" style="flex:1"><table class="grid" id="cal-t"><thead></thead><tbody></tbody></table></div></div>`));
  async function load() {
    const d = await api("calendar");
    const types = ["ALL", ...new Set(d.rows.map((x) => x.type))];
    $("#cal-f").innerHTML = `<span class="lbl">Show</span>` + types.map((x) => `<button class="chip ${x === typ ? "on" : ""}" data-ty="${x}">${x === "ALL" ? "Everything" : x}</button>`).join("") +
      `<span class="grow"></span><span class="dim">FDA decision dates (PDUFA), advisory committees, trial readouts and earnings · click a row to open the stock</span>`;
    $("#cal-f").onclick = (e) => { const b = e.target.closest("[data-ty]"); if (b) go(`#/calendar?type=${b.dataset.ty}`); };
    const rows = d.rows.filter((x) => typ === "ALL" || x.type === typ);
    let lastDate = "";
    $("#cal-t thead").innerHTML = `<tr><th>Date</th><th class="n">In</th><th>Type</th><th>Ticker</th><th>Company</th><th>Event</th><th class="n">Last</th><th class="n">1 month</th><th>Source</th></tr>`;
    $("#cal-t tbody").innerHTML = rows.map((x) => {
      const showDate = x.date !== lastDate; lastDate = x.date;
      return `<tr class="click" data-t="${x.ticker}" ${showDate ? 'style="border-top:1px solid #262b33"' : ""}><td class="mono ${showDate ? "" : "faint"}">${showDate ? esc(x.label) : ""}</td><td class="n">${x.days}d</td>
        <td><span class="tag ${x.type}">${x.type}</span></td><td class="tkr">${x.ticker}</td><td class="name">${esc(x.name)}</td><td class="wrap">${esc(x.event)}</td>
        <td class="n">${num(x.last)}</td><td class="n">${pct(x.chg1m)}</td><td class="dim">${esc(x.source)}</td></tr>`;
    }).join("") || `<tr><td colspan="9" class="empty">Nothing scheduled.</td></tr>`;
    $("#cal-t tbody").onclick = (e) => { const tr = e.target.closest("tr[data-t]"); if (tr) go(`#/stock/${tr.dataset.t}`); };
    $("#cal-t tbody").oncontextmenu = (e) => { const tr = e.target.closest("tr[data-t]"); if (tr) { e.preventDefault(); stockMenu(tr.dataset.t, e.clientX, e.clientY); } };
  }
  page.refresh = load;
  await load();
};

// ── News ──────────────────────────────────────────────────────────────
PAGES.news = async (root, r, page) => {
  const t = (r.q.get("t") || "").toUpperCase();
  let tone = "ALL", text = "", sel = 0, items = [];
  root.appendChild(h(`<div id="nws"><div class="panel"><div class="toolbar">
      ${t ? `<button class="chip on" data-go="#/news" title="Show all news">${t} ✕</button>` : ""}
      <button class="chip on" data-tone="ALL">All</button><button class="chip" data-tone="POS">Positive</button><button class="chip" data-tone="NEG">Negative</button>
      <input class="filter" id="nf" placeholder="Filter headlines…"><span class="grow"></span><span class="dim" id="ncount"></span></div>
      <div class="scroll" style="flex:1" id="nlist"></div></div>
    <div class="panel"><h3>Story</h3><div class="body preview" id="nprev"></div></div></div>`));
  function draw() {
    const q = text.toLowerCase();
    const rows = items.filter((n) => (tone === "ALL" || n.tone === tone) && (!q || n.title.toLowerCase().includes(q) || n.tickers.join(" ").toLowerCase().includes(q)));
    $("#ncount").textContent = `${rows.length} stories`;
    $("#nlist").innerHTML = newsList(rows);
    $("#nlist").onclick = (e) => { const d = e.target.closest("[data-i]"); if (d) { sel = +d.dataset.i; show(rows[sel]); $$(".news-item", $("#nlist")).forEach((x) => x.classList.toggle("sel", x === d)); } };
    $("#nlist").ondblclick = (e) => { const d = e.target.closest("[data-i]"); if (d) openUrl(rows[+d.dataset.i].link); };
    if (rows.length) { show(rows[0]); $(".news-item").classList.add("sel"); } else $("#nprev").innerHTML = '<div class="empty">No stories match.</div>';
  }
  function show(n) {
    $("#nprev").innerHTML = `<h2>${esc(n.title)}</h2><div class="meta"><span>${esc(n.time)}</span><span>${esc(n.age)} ago</span><span>${esc(n.source)}</span>
      ${n.tone !== "NEU" ? `<span class="tag ${n.tone}">${n.tone === "POS" ? "Positive" : "Negative"}</span>` : ""}${n.tags.map((x) => `<span class="tag">${esc(x)}</span>`).join("")}</div>
      <p>${esc(n.summary) || '<span class="faint">The feed carries only the headline — open the article to read it.</span>'}</p>
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin:14px 0"><button class="btn primary" id="np-open">Open article in browser ↗</button><button class="btn" id="np-copy">Copy link</button></div>
      ${n.tickers.length ? `<div class="dim" style="margin-bottom:6px">Stocks in this story</div><div style="display:flex;gap:6px;flex-wrap:wrap">${n.tickers.map((x) => `<button class="chip" data-go="#/stock/${x}">${x}</button>`).join("")}</div>` : ""}`;
    $("#np-open").onclick = () => openUrl(n.link);
    $("#np-copy").onclick = () => copy(n.link, "Link copied");
  }
  root.querySelector(".toolbar").addEventListener("click", (e) => {
    const b = e.target.closest("[data-tone]"); if (!b) return;
    tone = b.dataset.tone; $$("[data-tone]").forEach((x) => x.classList.toggle("on", x === b)); draw();
  });
  $("#nf").oninput = (e) => { text = e.target.value; draw(); };
  async function load() { items = (await api("news", { ticker: t })).items; draw(); }
  await load();
};

// ── Options ───────────────────────────────────────────────────────────
const MON3 = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
function expLabel(iso) { const [y, m, d] = iso.split("-"); return `${+d} ${MON3[+m - 1]} '${y.slice(2)}`; }
PAGES.options = async (root, r, page) => {
  const t = (r.args[0] || S.get("optticker", "LLY")).toUpperCase();
  S.set("optticker", t);
  root.appendChild(h(`<div id="opt"><div class="toolbar"><span class="tkr mono amber" style="font-size:18px;font-weight:800">${t}</span>
      <button class="btn small" id="o-pick">Change stock…</button><button class="btn small" data-go="#/stock/${t}">Chart</button>
      <span class="lbl">Expiry</span><div id="o-exp" style="display:flex;gap:4px;flex-wrap:wrap"></div></div>
    <div class="ostats" id="o-st"></div>
    <div class="scroll" style="flex:1" id="o-body"><div class="splash" style="height:200px"><div class="spinner"></div><div>Loading the options chain…</div></div></div></div>`));
  $("#o-pick").onclick = async () => { const x = await pickTicker("Options chain for…"); if (x) go(`#/options/${x}`); };
  async function load(exp) {
    const d = await api("chain", { ticker: t, expiry: exp || r.q.get("exp") || "" });
    if (!d.ok) { $("#o-body").innerHTML = `<div class="empty">${esc(d.message)}</div>`; return; }
    $("#o-exp").innerHTML = d.expiries.map((e) => `<button class="chip ${e === d.expiry ? "on" : ""}" data-e="${e}">${expLabel(e)}</button>`).join("");
    $("#o-exp").onclick = (e) => { const b = e.target.closest("[data-e]"); if (b) { history.replaceState(null, "", `#/options/${t}?exp=${b.dataset.e}`); load(b.dataset.e); } };
    $("#o-st").innerHTML = `<span><small>Stock</small>${num(d.spot)}</span><span><small>Days to expiry</small>${d.dte}</span><span><small>At-the-money IV</small>${pctu(d.atm_iv, 1)}</span>
      <span><small>Realized vol 20d</small>${pctu(d.rv20, 1)}</span><span><small>Implied move</small>±${pctu(d.implied_move, 1)} (±${num(d.implied_move != null ? d.implied_move * d.spot : null)})</span>
      <span><small>Put/call volume</small>${num(d.pc_vol)}</span><span><small>Put/call open int.</small>${num(d.pc_oi)}</span><span class="dim">Click any price to copy the contract · amber = volume above open interest</span>`;
    const cell = (s, k, kind, f, key) => {
      if (!s) return `<td class="faint">—</td>`;
      const itm = kind === "C" ? k < d.spot : k > d.spot;
      const v = s[key];
      const txt = key === "iv" ? pctu(v, 0) : key === "delta" ? (v == null ? NA : v.toFixed(2)) : key === "vol" || key === "oi" ? (v ? v.toLocaleString() : NA) : num(v);
      const hot = key === "vol" && s.hot ? "hot" : "";
      return `<td class="cell ${itm ? (kind === "C" ? "itm" : "itmp") : ""} ${hot}" data-k="${k}" data-kind="${kind}" data-px="${s.ask ?? s.last ?? ""}">${txt}</td>`;
    };
    const keys = ["bid", "ask", "last", "iv", "delta", "vol", "oi"];
    const heads = ["Bid", "Ask", "Last", "IV", "Delta", "Volume", "Open int."];
    $("#o-body").innerHTML = `<table class="grid chain"><thead>
      <tr><th class="side" colspan="7">CALLS</th><th class="k">${new Date(d.expiry + "T12:00").toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}</th><th class="side" colspan="7">PUTS</th></tr>
      <tr>${heads.map((x) => `<th>${x}</th>`).join("")}<th class="k">Strike</th>${heads.map((x) => `<th>${x}</th>`).join("")}</tr></thead><tbody>
      ${d.rows.map((row) => `<tr class="${row.atm ? "atm" : ""}">${keys.map((k) => cell(row.call, row.strike, "C", null, k)).join("")}<td class="k">${num(row.strike, row.strike % 1 ? 1 : 0)}</td>${keys.map((k) => cell(row.put, row.strike, "P", null, k)).join("")}</tr>`).join("")}
      </tbody></table>`;
    const atm = $("tr.atm", $("#o-body")); if (atm) atm.scrollIntoView({ block: "center" });
    $("#o-body").onclick = (e) => {
      const c = e.target.closest("td.cell"); if (!c) return;
      const dt = new Date(d.expiry + "T12:00").toLocaleDateString("en-US", { day: "2-digit", month: "short", year: "2-digit" }).toUpperCase();
      copy(`${t} ${dt} ${c.dataset.k} ${c.dataset.kind === "C" ? "CALL" : "PUT"}${c.dataset.px ? " @ " + Number(c.dataset.px).toFixed(2) : ""}`, "Contract copied");
    };
  }
  await load();
};

// ── Compare ───────────────────────────────────────────────────────────
const COLORS = ["#ff9e1b", "#58a6ff", "#26d07c", "#c18cff", "#ff4d4f", "#e6edf3"];
PAGES.compare = async (root, r, page) => {
  let tickers = (r.args[0] || S.get("cmp", "LLY,NVO,XBI")).toUpperCase().split(",").filter(Boolean).slice(0, 6);
  let tf = r.q.get("tf") || S.get("cmptf", "1Y");
  root.appendChild(h(`<div id="cmp"><div class="toolbar"><div class="cmpchips" id="cc"></div><button class="btn small primary" id="c-add">+ Add stock</button>
      <span class="lbl">Period</span><div class="seg-btns" id="c-tf">${TFS.map((x) => `<button data-tf="${x}">${x}</button>`).join("")}</div></div>
    <div class="chartwrap" style="margin:10px"><div class="legend" id="c-lg"></div><div class="chart" id="c-chart"></div></div></div>`));
  const chart = makeChart($("#c-chart"), { rightPriceScale: { borderColor: "#262b33", mode: 0 }, localization: { priceFormatter: (v) => (v > 0 ? "+" : "") + v.toFixed(1) + "%" } });
  let lines = [];
  function nav() { S.set("cmp", tickers.join(",")); S.set("cmptf", tf); history.replaceState(null, "", `#/compare/${tickers.join(",")}?tf=${tf}`); }
  async function load() {
    nav();
    $$("#c-tf button").forEach((b) => b.classList.toggle("on", b.dataset.tf === tf));
    const d = await api("compare", { tickers: tickers.join(","), tf });
    lines.forEach((l) => chart.removeSeries(l)); lines = [];
    chart.applyOptions({ timeScale: { timeVisible: d.intraday } });
    $("#cc").innerHTML = d.series.map((s, i) => `<span class="cchip" title="${esc(s.name)}"><i style="background:${COLORS[i]}"></i><span data-go="#/stock/${s.ticker}" style="cursor:pointer">${s.ticker}</span> ${pct(s.change / 100, 1)}<button data-rm="${s.ticker}" title="Remove">✕</button></span>`).join("");
    d.series.forEach((s, i) => { const l = chart.addLineSeries({ color: COLORS[i], lineWidth: 2, priceLineVisible: false }); l.setData(s.points); lines.push(l); });
    chart.timeScale().fitContent();
    $("#c-lg").innerHTML = `% change over ${tf}`;
  }
  $("#cc").onclick = (e) => { const b = e.target.closest("[data-rm]"); if (b) { tickers = tickers.filter((x) => x !== b.dataset.rm); load(); } };
  $("#c-add").onclick = async () => {
    if (tickers.length >= 6) { toast("Up to 6 lines — remove one first."); return; }
    const x = await pickTicker("Add a stock to the comparison", tickers); if (x) { tickers.push(x); load(); }
  };
  $("#c-tf").onclick = (e) => { const b = e.target.closest("[data-tf]"); if (b) { tf = b.dataset.tf; load(); } };
  page.destroy = () => chart.remove();
  await load();
};

// ── Watchlist & alerts ────────────────────────────────────────────────
PAGES.watchlist = async (root, r, page) => {
  root.appendChild(h(`<div id="wl" class="scroll" style="padding:10px;gap:10px">
    <div class="panel"><h3>My watchlist<span class="grow"></span><button class="btn small" id="w-add" style="background:#000;color:var(--amber)">+ Add stock</button></h3>
      <table class="grid" id="w-t"><thead></thead><tbody></tbody></table></div>
    <div class="panel" style="margin-top:10px"><h3>Price alerts<span class="grow"></span><button class="btn small" id="al-add" style="background:#000;color:var(--amber)">+ New alert</button></h3>
      <table class="grid" id="al-t"><thead><tr><th>Alert</th><th class="n">Price now</th><th class="n">Distance</th><th>Status</th><th></th></tr></thead><tbody></tbody></table></div></div>`));
  const state = S.get("wsort", { key: "chg1d", desc: true });
  let table;
  const cols = [{ key: "ticker", label: "Ticker" }, { key: "name", label: "Company" }, { key: "last", label: "Last", fmt: "num2" }, { key: "chg1d", label: "Today", fmt: "pct" },
    { key: "chg5d", label: "5 day", fmt: "pct" }, { key: "chg1m", label: "1 month", fmt: "pct" }, { key: "ytd", label: "YTD", fmt: "pct" }, { key: "spark", label: "3 months", sort: false },
    { key: "rsi", label: "RSI", fmt: "rsi" }, { key: "signal", label: "Signal" }, { key: "cat_days", label: "Catalyst", num: false }, { key: "x", label: "", sort: false }];
  const rowHtml = (x) => `<tr class="click" data-t="${x.ticker}"><td class="tkr">${x.ticker}</td><td class="name">${esc(x.name)}</td><td class="n">${num(x.last)}</td><td class="n">${pct(x.chg1d)}</td>
    <td class="n">${pct(x.chg5d)}</td><td class="n">${pct(x.chg1m)}</td><td class="n">${pct(x.ytd)}</td><td>${spark(x.spark)}</td><td class="n">${rsi(x.rsi)}</td><td>${sig(x.signal)}</td>
    <td>${x.cat_type ? `<span class="tag ${x.cat_type}">${x.cat_type}</span><span class="mono dim">${x.cat_days}d</span>` : ""}</td>
    <td><button class="x" data-star="${x.ticker}" title="Remove from watchlist">✕</button></td></tr>`;
  async function load(first) {
    const d = await api("watchlist");
    if (first) table = sortable($("#w-t"), d.rows, cols, rowHtml, state, (t) => go(`#/stock/${t}`));
    else table.setRows(d.rows);
    if (!d.rows.length) $("#w-t tbody").innerHTML = `<tr><td colspan="12" class="empty">Your watchlist is empty — click “+ Add stock”, or the ☆ next to any stock.</td></tr>`;
    S.order = (state.sorted || []).map((x) => x.ticker);
    state.onSort = () => { S.set("wsort", { key: state.key, desc: state.desc }); S.order = state.sorted.map((x) => x.ticker); };
    $("#al-t tbody").innerHTML = d.alerts.map((a) => `<tr><td><b class="mono amber" data-go="#/stock/${a.ticker}" style="cursor:pointer">${esc(a.text)}</b></td><td class="n">${num(a.now)}</td><td class="n">${pct(a.away, 1)}</td>
      <td>${a.armed ? '<span class="tag POS">Armed</span>' : `<span class="tag">Triggered ${esc(a.triggered)}</span>`}</td><td><button class="x" data-del="${a.index}" title="Delete alert">✕</button></td></tr>`).join("")
      || `<tr><td colspan="5" class="empty">No alerts. Click “+ New alert”, or use “Price alert” on any stock page.</td></tr>`;
  }
  // removing with ✕ goes through toggleWatch via data-star (handled by sortable); reload afterwards
  $("#w-t").addEventListener("click", (e) => { if (e.target.closest("[data-star]")) setTimeout(() => load(false), 150); }, true);
  $("#al-t").onclick = async (e) => { const b = e.target.closest("[data-del]"); if (b) { await api("alert_del", { index: b.dataset.del }, true); toast("Alert deleted"); load(false); pollStatus(); } };
  $("#w-add").onclick = async () => {
    const d = await api("watchlist");
    const x = await pickTicker("Add to watchlist", d.rows.map((r) => r.ticker));
    if (x) { await api("watch_toggle", { ticker: x }, true); toast(`<b>${x}</b> added to your watchlist`); load(false); }
  };
  $("#al-add").onclick = async () => { const x = await pickTicker("Price alert for…"); if (x) alertDialog(x); };
  page.refresh = () => load(false);
  await load(true);
};

// ── Help ──────────────────────────────────────────────────────────────
PAGES.help = async (root) => {
  const d = await api("help");
  root.appendChild(h(`<div id="help" class="scroll"><div class="help">
    <h1>RXTERM · pharma & biotech trading terminal</h1>
    <p>Everything works with the mouse. Click any stock anywhere to open it; right-click a stock in a table for more options; use the ◀ button (or your mouse's back button) to go back.</p>
    <h2>Pages</h2>
    <p><b>Monitor</b> — the whole pharma/biotech universe. Click the chips to filter by sector, your watchlist, buy/sell signals or upcoming catalysts. Click a column heading to sort. Click ☆ to add to your watchlist.<br>
    <b>Stock page</b> — chart with time ranges 1D through 10Y, candles/line/area, moving averages and volume (hover the chart for exact prices; scroll to zoom, drag to pan, “Reset zoom” to see it all), key stats, news, company profile, and today's trade idea if there is one. ◀ ▶ step through the list you came from.<br>
    <b>Trade Ideas</b> — three conservative and three aggressive trades, each with the exact contracts, entry/target/stop, reward:risk, thesis, drivers and risks. “Copy trade” puts the order on your clipboard.<br>
    <b>Screener</b> — ${d.screens.length} preset screens (momentum, oversold, catalysts, short squeeze candidates and more). Click a screen on the left.<br>
    <b>Calendar</b> — FDA decision dates (PDUFA), advisory committees, clinical-trial readouts and earnings.<br>
    <b>News</b> — the pharma newswire, scored for sentiment. Click a story to preview it, double-click (or “Open article”) to read it in your browser.<br>
    <b>Options</b> — full call/put chain with implied volatility, delta, volume and open interest. Click any price to copy the contract.<br>
    <b>Compare</b> — up to six stocks or ETFs on one % chart.<br>
    <b>Watchlist</b> — your stocks and your price alerts. Alerts pop up with a chime while RXTERM is open.</p>
    <h2>Search</h2><p>Click the search box (or just start typing anywhere) and pick a stock from the list.</p>
    <h2>Data</h2><p>Prices refresh every minute during market hours (every 5 minutes otherwise); news, fundamentals and catalysts reload on start and when you click <b>⟳ Refresh</b> at the bottom right. RXTERM opens instantly with your last session and updates in the background. Your settings live in <code>${esc(d.home)}</code>.</p>
    <h2>Morning email</h2><p>The 8:15 AM ET brief is sent by GitHub Actions in the cloud, so your computer does not need to be on.</p>
    <h2>Important</h2><div class="disc">${esc(d.disclaimer)}</div>
    <h2>Credits</h2><p>Charts by <a href="#" id="tvlink" class="amber">TradingView Lightweight Charts™</a> (Apache-2.0). Market data from Yahoo Finance, news from public RSS feeds, trials from ClinicalTrials.gov. RXTERM ${esc(d.version)}.</p>
    </div></div>`));
  $("#tvlink").onclick = (e) => { e.preventDefault(); openUrl("https://www.tradingview.com/"); };
};

// ── boot ──────────────────────────────────────────────────────────────
tickClock(); setInterval(tickClock, 1000);
route();
pollStatus();
setInterval(pollStatus, 3000);
