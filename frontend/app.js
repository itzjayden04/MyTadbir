/* MyTadbir web app. React 18 + htm, no build step (served by the FastAPI backend). */
const { useState, useEffect, useRef, useMemo, useCallback } = React;
const html = htm.bind(React.createElement);

// ---------------------------------------------------------------- helpers
const store = {
  get(k, d) { try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} },
};
let TOKEN = store.get("mt-token", null);
async function api(path, { method = "GET", body, form } = {}) {
  const headers = TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {};
  if (body) headers["Content-Type"] = "application/json";
  const r = await fetch(path, { method, headers, body: form || (body ? JSON.stringify(body) : undefined) });
  if (!r.ok) { let d = r.statusText; try { d = (await r.json()).detail || d; } catch {} if (d && typeof d === "object") d = (store.get("mt-lang", "en") === "bm" ? d.bm : d.en) || JSON.stringify(d); throw new Error(d); }
  return r.json();
}
const newThreadId = () => "TH-" + Math.random().toString(16).slice(2, 10).toUpperCase();
const fmtTime = (iso) => new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
const fmtDate = (iso) => new Date(iso).toLocaleString([], { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
const rm = (n) => "RM" + Number(n).toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const DEPT_ICON = { health: "✚", education: "✎", local_gov: "⌂", immigration: "✈", road_transport: "⛟", inland_revenue: "₪",
  social_welfare: "♥", police_home: "⛨", agri_env: "❦", cross_agency: "⇄" };
const STATUS_PILL = { done: "good", running: "agent", queued: "", awaiting_approval: "warn", failed: "bad", needs_clarification: "warn",
  paid: "good", pending: "warn", refunded: "accent", approved: "good", rejected: "bad", booked: "accent", dispatched: "agent" };
const TEMPLATES = [
  { en: "Report a clogged drain", bm: "Lapor longkang tersumbat", text: "Longkang depan sekolah tersumbat, air dah naik sampai jalan." },
  { en: "Renew licence + pay summons", bm: "Renew lesen + bayar saman", text: "Saya nak renew lesen memandu dan bayar saman." },
  { en: "Open a café: licence check", bm: "Buka kafe: semak lesen", text: "Saya nak buka kafe di Petaling Jaya, perlu lesen apa?" },
  { en: "Check aid eligibility", bm: "Semak kelayakan bantuan", text: "Saya ibu tunggal, nak mohon bantuan JKM." },
];

function describe(ev, lang) {
  const d = ev.data || {}; const bm = lang === "bm";
  switch (ev.event) {
    case "classified": return bm ? `Mengelas ${d.intents?.length || 0} niat (${d.language?.toUpperCase()})` : `Classified ${d.intents?.length || 0} intent(s) (${d.language?.toUpperCase()})`;
    case "case_created": return `${d.case_id} → ${d.department} / ${d.submodule} · ${Math.round(d.confidence * 100)}%${d.verify_flag ? " · verify" : ""}`;
    case "needs_clarification": return d.question;
    case "dispatch": return bm ? `Serah kepada ${d.department}` : `Hand case to ${d.department}`;
    case "handoff": return bm ? `Serahan berurutan: ${d.from} → ${d.to} (ID kes sama)` : `Sequential handoff: ${d.from} → ${d.to} (same case ID)`;
    case "plan": return (bm ? "Pelan sub-modul: " : "Sub-module plan: ") + (d.submodules || []).join(" → ");
    case "start": return bm ? "Mula" : "Started";
    case "gps": return d.lat ? `GPS ${d.lat}, ${d.lng} (${d.source})` : (bm ? "Tiada GPS dalam foto" : "No GPS in photo");
    case "inspected": return `${bm ? d.subject_bm : d.subject_en} · ${bm ? "keterukan" : "severity"} ${d.severity}`;
    case "api_call": return `${d.method} ${d.url.replace(/\?.*/, "")} · ${d.ok ? d.ms + " ms" : "failed"}${d.source === "live" ? " · LIVE" : ""}`;
    case "sql_write": return `SQL ${d.op} ${d.table}`;
    case "retrieved": return (bm ? `Dapatkan ${d.citations?.length || 0} petikan: ` : `Retrieved ${d.citations?.length || 0} clauses: `) + (d.citations?.[0]?.title_en || "-");
    case "reasoned": return (bm ? "Penaakulan undang-undang" : "Legal reasoning") + (d.priority ? ` · ${d.priority}` : "") + (d.outcome ? ` · ${d.outcome}` : "");
    case "priority": return (bm ? "Keutamaan " : "Priority ") + d.priority;
    case "artifact": return (bm ? "Dokumen dijana: " : "Generated: ") + d.title;
    case "notified": return bm ? d.message_bm : d.message_en;
    case "reused": return bm ? "Identiti diguna semula, tiada semakan kedua" : "Identity reused, no second check";
    case "paused": return bm ? "Dijeda: menunggu keputusan manusia" : "Paused: waiting for a human decision";
    case "decision": return (d.approved ? "✔ " : "✖ ") + (bm ? `Keputusan oleh ${d.by}` : `Decision by ${d.by}`);
    case "case_done": return (bm ? "Kes selesai: " : "Case closed: ") + (d.chain || []).join(" → ");
    case "thread_done": return bm ? "Semua kes dalam urutan selesai" : "All cases in this thread finished";
    case "fallback": return d.note;
    default:
      if (d.summary_en) return bm ? d.summary_bm : d.summary_en;
      if (ev.layer === "always_on") return bm ? (d.summary_bm || "") : (d.summary_en || "");
      return ev.event;
  }
}
const modelOf = (ev) => { const m = ev.data?.llm; return m && m.model ? `${m.model}${m.effort && m.effort !== "-" ? " · " + m.effort : ""}${m.completion_tokens ? " · " + (m.prompt_tokens + m.completion_tokens) + " tok" : ""}` : null; };

// ---------------------------------------------------------------- login
function Login({ t, lang, setLang, onIn }) {
  const [u, setU] = useState(""); const [p, setP] = useState(""); const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  const go = async (fn) => { setBusy(true); setErr(""); try { onIn(await fn()); } catch (e) { setErr(e.message); } setBusy(false); };
  return html`<div class="login">
    <div class="login-top"><div class="seg"><button class=${lang === "en" ? "on" : ""} onClick=${() => setLang("en")}>EN</button><button class=${lang === "bm" ? "on" : ""} onClick=${() => setLang("bm")}>BM</button></div></div>
    <main class="login-card">
      <div class="login-brand"><div class="brand-mark">M</div><b>MyTadbir</b></div>
      <p class="muted login-sub">${lang === "bm" ? "Satu pintu untuk semua perkhidmatan kerajaan" : "One front door to government services"}</p>
      <button class="btn primary login-btn" disabled=${busy} onClick=${() => go(() => api("/api/auth/mydigitalid", { method: "POST" }))}>${t.mydid}</button>
      <div class="or">${lang === "bm" ? "atau" : "or"}</div>
      <form onSubmit=${(e) => { e.preventDefault(); go(() => api("/api/auth/login", { method: "POST", body: { username: u, password: p } })); }}>
        <div class="field"><label for="u">${t.username}</label><input id="u" value=${u} onInput=${(e) => setU(e.target.value)} autocomplete="username" /></div>
        <div class="field"><label for="p">${t.password}</label><input id="p" type="password" value=${p} onInput=${(e) => setP(e.target.value)} autocomplete="current-password" /></div>
        ${err && html`<div class="err">${err}</div>`}
        <button class="btn login-btn" style=${{ marginTop: 16 }} disabled=${busy}>${t.login}</button>
      </form>
    </main>
    <footer class="login-foot muted">© 2026 MyTadbir · ${lang === "bm" ? "Privasi" : "Privacy"} · ${lang === "bm" ? "Kebolehcapaian" : "Accessibility"} · ${lang === "bm" ? "Bantuan" : "Help"}</footer>
  </div>`;
}

// ---------------------------------------------------------------- sidebar
function Sidebar({ t, lang, user, view, setView, catalog, cases, threads, pins, togglePin, openThread, newRequest, launchDept, logout, theme, setTheme }) {
  const [open, setOpen] = useState(store.get("mt-groups", { commands: true, activity: true, live: true, gov: true, conv: true }));
  const tog = (k) => { const n = { ...open, [k]: !open[k] }; setOpen(n); store.set("mt-groups", n); };
  const countBy = useMemo(() => cases.reduce((m, c) => { if (c.status !== "done") m[c.current_department] = (m[c.current_department] || 0) + 1; return m; }, {}), [cases]);
  const active = cases.filter((c) => c.status !== "done").length;
  const Nav = (k, ico, cnt) => html`<button class=${"nav" + (view === k ? " on" : "")} onClick=${() => setView(k)}><span class="ico">${ico}</span>${t[k]}${cnt ? html`<span class="cnt">${cnt}</span>` : null}</button>`;
  const Grp = (k, label, kids) => html`<div class="grp"><button class="grp-h" onClick=${() => tog(k)} aria-expanded=${open[k]}>${label}<svg class=${"chev" + (open[k] ? " open" : "")} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg></button>${open[k] && kids}</div>`;
  const pinned = threads.filter((x) => pins.includes(x.thread_id)); const rest = threads.filter((x) => !pins.includes(x.thread_id));
  const Hist = (th) => html`<div style=${{ display: "flex", alignItems: "center" }}><button class="hist" onClick=${() => openThread(th.thread_id)}>${th.title || th.thread_id}<small>${th.cases.map((c) => c.case_id).join(", ") || th.thread_id}</small></button><button class="icon-btn" title="Pin" onClick=${() => togglePin(th.thread_id)}>${pins.includes(th.thread_id) ? "★" : "☆"}</button></div>`;
  return html`<aside class="side">
    <div class="brand"><div class="brand-mark">MT</div><div><b>MyTadbir</b><small>${t.tagline}</small></div></div>
    <button class="new-btn" onClick=${newRequest}>＋ ${t.newReq}</button>
    <div class="side-scroll">
      ${Grp("commands", t.g_commands, html`
        <div class="launch">${catalog.map((d) => html`<button class="tile" key=${d.key} title=${d.agencies} onClick=${() => launchDept(d.key)}>
          <b>${DEPT_ICON[d.key]} ${lang === "bm" ? d.bm : d.en}</b><span>${d.subs.length} ${lang === "bm" ? "modul" : "modules"}${countBy[d.key] ? " · " + countBy[d.key] + (lang === "bm" ? " aktif" : " active") : ""}</span></button>`)}</div>
        ${Nav("console", "⌘")}${Nav("search", "⌕")}`)}
      ${Grp("activity", t.g_activity, html`${Nav("cases", "▤", active)}${Nav("payments", "＄")}${Nav("documents", "🗎")}${Nav("calendar", "▦")}${Nav("inbox", "✉")}`)}
      ${Grp("live", t.g_live, html`${Nav("map", "⌖")}${Nav("impact", "▲")}`)}
      ${Grp("gov", t.g_gov, html`${Nav("approvals", "✔")}${Nav("policy", "§")}${Nav("audit", "⛓")}`)}
      ${Grp("conv", t.g_conv, html`${pinned.length ? html`<div class="grp-h" style=${{ cursor: "default" }}>${t.pinned}</div>${pinned.map(Hist)}` : null}
        <div class="grp-h" style=${{ cursor: "default" }}>${t.history}</div>${rest.length ? rest.slice(0, 30).map(Hist) : html`<div class="hist" style=${{ color: "var(--side-muted)" }}>${t.none}</div>`}`)}
    </div>
    <div class="side-foot">
      <div class="avatar">${user.name.split(" ").map((x) => x[0]).slice(0, 2).join("")}</div>
      <div class="who"><b>${user.name}</b>${user.verified ? html`<span class="badge-ok">✔ ${t.verified}</span>` : html`<span class="badge-ok" style=${{ color: "var(--side-muted)" }}>${t.officerMode}</span>`}</div>
      <button class="icon-btn" title=${t.settings} onClick=${() => setView("settings")}>⚙</button>
      <button class="icon-btn" title="Theme" onClick=${() => setTheme(theme === "dark" ? "light" : "dark")}>${theme === "dark" ? "☀" : "☾"}</button>
      <button class="icon-btn" title=${t.help} onClick=${() => setView("help")}>?</button>
      <button class="icon-btn" title=${t.signout} onClick=${logout}>⏻</button>
    </div>
  </aside>`;
}

// ---------------------------------------------------------------- trace panel
function TracePanel({ t, lang, events, threadId, onClose }) {
  const ref = useRef(null);
  useEffect(() => { if (ref.current) ref.current.scrollTop = ref.current.scrollHeight; }, [events.length]);
  return html`<aside class="trace">
    <div class="trace-h"><span class=${"dot" + (events.length && events[events.length - 1].event !== "thread_done" ? " live" : "")}></span><b>${t.trace}</b>
      <span class="mono muted" style=${{ marginLeft: "auto" }}>${threadId || ""}</span><button class="icon-btn" style=${{ color: "var(--muted)" }} onClick=${onClose} title="Hide">✕</button></div>
    <div class="trace-list" ref=${ref}>
      ${events.length === 0 && html`<div class="empty" style=${{ padding: 20 }}>${t.traceEmpty}</div>`}
      ${events.map((ev, i) => html`<div class="ev" key=${i}>
        <time>${fmtTime(ev.ts)}</time>
        <div><div class="who"><span class=${"layer " + ev.layer}>${ev.layer.replace("_", " ")}</span><b>${ev.actor}</b>${ev.case_id ? html`<span class="mono muted">${ev.case_id}</span>` : null}</div>
          <div class="line">${describe(ev, lang)}</div>
          ${modelOf(ev) && html`<div class="model">⚙ ${modelOf(ev)}</div>`}
          ${Object.keys(ev.data || {}).length > 0 && html`<details><summary>${lang === "bm" ? "butiran" : "details"}</summary><pre>${JSON.stringify(ev.data, null, 2)}</pre></details>`}</div>
      </div>`)}
    </div>
  </aside>`;
}

// ---------------------------------------------------------------- console
function CaseCard({ t, lang, c, events, user, onDecide, approvals }) {
  const evs = events.filter((e) => e.case_id === c.case_id);
  const steps = evs.filter((e) => ["dispatch", "handoff", "inspected", "api_call", "sql_write", "retrieved", "reasoned", "priority", "artifact", "notified", "paused", "decision", "reused"].includes(e.event));
  const cites = evs.filter((e) => e.event === "retrieved").flatMap((e) => e.data.citations || []).slice(0, 3);
  const findings = evs.filter((e) => e.event === "reasoned").flatMap((e) => e.data.findings || []);
  const artifacts = evs.filter((e) => e.event === "artifact");
  const appr = approvals.find((a) => a.case_id === c.case_id && a.status === "pending");
  const res = c.result; const wrap = c.wrap;
  const chain = c.chain && c.chain.length ? c.chain : [c.current_department];
  return html`<div class="card">
    <div class="card-h"><span class="eyebrow">${t.caseId}</span><b class="mono" style=${{ fontSize: 14 }}>${c.case_id}</b>
      <span class=${"pill " + (STATUS_PILL[c.status] || "")}>${c.status.replace("_", " ")}</span>${c.verify_flag ? html`<span class="pill warn">${t.verify}</span>` : null}</div>
    <div class="muted" style=${{ fontSize: 13.5 }}>“${c.intent}”</div>
    <div class="chain">${chain.map((d, i) => html`${i > 0 ? html`<span class="arrow">→</span>` : null}<span class="pill accent">${DEPT_ICON[d]} ${d}</span>`)}</div>
    <ul class="steps">${steps.map((e, i) => html`<li key=${i} class=${i === steps.length - 1 && c.status === "running" ? "run" : ""}><span class="s">${e.event === "paused" ? "⏸" : "✓"}</span><span>${describe(e, lang)}${modelOf(e) ? html` <span class="mono muted">(${modelOf(e)})</span>` : null}</span></li>`)}</ul>
    ${cites.length > 0 && html`<div style=${{ marginTop: 10 }}><span class="eyebrow">${t.citations}</span>
      ${cites.map((h) => html`<div class="cite"><a href=${h.url} target="_blank" rel="noopener">${lang === "bm" ? h.title_bm : h.title_en}</a>, ${lang === "bm" ? "ms" : "p."} ${h.page}<div class="muted">${h.excerpt.slice(0, 180)}…</div></div>`)}
      ${findings.filter((f) => f.is_assumption).map((f) => html`<div class="cite" style=${{ borderColor: "var(--warn)" }}><b>${t.assumption}:</b> ${lang === "bm" ? f.point_bm : f.point_en}</div>`)}</div>`}
    ${artifacts.length > 0 && html`<div class="artifacts">${artifacts.map((a) => html`<a class="artifact" href=${"/api/documents/" + a.data.doc_id + "/file"} target="_blank">🗎 ${a.data.title}</a>`)}</div>`}
    ${appr && html`<div class="approve"><p><b>${appr.actor === "citizen" ? t.waitingYou : t.waitingOfficer}.</b> ${appr.reason}</p>
      ${appr.actor === user.role && html`<button class="btn good" onClick=${() => onDecide(appr.id, true)}>${appr.actor === "citizen" ? t.confirmPay : t.approve}</button><button class="btn bad" onClick=${() => onDecide(appr.id, false)}>${appr.actor === "citizen" ? t.cancel : t.reject}</button>`}</div>`}
    ${res && html`<div class="result"><b>${lang === "bm" ? res.summary_bm : res.summary_en}</b>
      ${wrap && html`<div style=${{ marginTop: 6 }}>${lang === "bm" ? wrap.summary_bm : wrap.summary_en}</div>
        ${wrap.next_steps?.length > 0 && html`<div class="eyebrow" style=${{ marginTop: 8 }}>${t.nextSteps}</div><ul class="next">${wrap.next_steps.map((s) => html`<li>${lang === "bm" ? s.bm : s.en}</li>`)}</ul>`}`}</div>`}
  </div>`;
}

function Console({ t, lang, user, catalog, thread, events, cases, approvals, send, onDecide, preset, setPreset, draft, setDraft }) {
  const [files, setFiles] = useState([]); const [busy, setBusy] = useState(false); const [chips, setChips] = useState([]); const [err, setErr] = useState("");
  useEffect(() => { api(`/api/suggestions?lang=${lang}`).then(setChips).catch(() => setChips([])); }, [lang, cases.length]);
  const feedRef = useRef(null); const fileRef = useRef(null);
  useEffect(() => { if (feedRef.current) feedRef.current.scrollTop = feedRef.current.scrollHeight; }, [events.length, cases.length, thread?.messages?.length]);
  const submit = async () => {
    if (!draft.trim() && !files.length) return;
    setBusy(true);
    setErr(""); try { await send(draft, files.map((f) => f.file), preset); setDraft(""); setFiles([]); setPreset(null); } catch (e) { setErr(e.message); }
    setBusy(false);
  };
  const routerEv = events.filter((e) => e.event === "classified");
  const clar = events.filter((e) => e.event === "needs_clarification");
  return html`<div class="console">
    <div class="feed" ref=${feedRef}><div class="feed-inner">
      ${!thread?.messages?.length && html`<div class="empty"><h2>${t.emptyTitle}</h2><p>${t.emptyBody}</p></div>`}
      ${(thread?.messages || []).map((m, i) => html`<div class="msg-user" key=${"m" + i}>${m.text}${m.previews.map((p) => html`<img src=${p} alt="" />`)}</div>`)}
      ${routerEv.map((e, i) => html`<div class="card" key=${"r" + i}><div class="card-h"><span class="pill agent">${t.router}</span><b>${(e.data.intents || []).length} ${lang === "bm" ? "niat dikesan" : "intent(s) found"}</b><span class="mono muted">${modelOf(e) || e.data.classifier}</span></div>
        ${(e.data.intents || []).map((g) => html`<div class="intent"><span class="pill accent">${DEPT_ICON[g.department]} ${g.department}</span><span>${g.submodule}<div class="muted" style=${{ fontSize: 12.5 }}>${g.reason}</div></span>
          <span title=${t.confidence}><span class="conf"><i style=${{ width: Math.round(g.confidence * 100) + "%" }}></i></span><span class="mono">${Math.round(g.confidence * 100)}%</span></span></div>`)}
        ${events.filter((x) => x.event === "case_created" && x.data.order_note).map((x) => html`<div class="cite" style=${{ borderColor: "var(--warn)" }}><b>${t.order}:</b> ${x.data.order_note}</div>`)}</div>`)}
      ${clar.map((e, i) => html`<div class="card" key=${"c" + i}><div class="card-h"><span class="pill warn">${t.router}</span><b>${t.clarify}</b></div>${e.data.question}</div>`)}
      ${cases.map((c) => html`<${CaseCard} key=${c.case_id} t=${t} lang=${lang} c=${c} events=${events} user=${user} onDecide=${onDecide} approvals=${approvals} />`)}
    </div></div>
    <div class="composer"><div class="composer-inner">
      <div class="templates">${chips.map((x) => html`<button class="chip" key=${x.key} onClick=${() => setDraft(x.prompt)}>${x.label}</button>`)}
        ${preset && html`<span class="chip on">${t.to}: ${DEPT_ICON[preset]} ${(catalog.find((d) => d.key === preset) || {})[lang === "bm" ? "bm" : "en"]} <button style=${{ border: 0, background: "none" }} onClick=${() => setPreset(null)}>✕</button></span>`}</div>
      <div class="compose-row">
        <button class="btn" onClick=${() => fileRef.current.click()} title=${lang === "bm" ? "Lampirkan foto atau fail (PDF, DOC, DOCX)" : "Attach a photo or file (PDF, DOC, DOCX)"} aria-label="Attach">📎</button>
        <input ref=${fileRef} type="file" accept=".jpg,.jpeg,.png,.webp,.pdf,.doc,.docx" multiple hidden onChange=${(e) => { setFiles([...files, ...[...e.target.files].map((f) => ({ file: f, url: f.type.startsWith("image/") ? URL.createObjectURL(f) : null }))]); e.target.value = ""; }} />
        <textarea id="composer" rows="1" placeholder=${t.placeholder} value=${draft} onInput=${(e) => setDraft(e.target.value)}
          onKeyDown=${(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }}></textarea>
        <button class="btn primary" disabled=${busy} onClick=${submit}>${busy ? "…" : t.send}</button>
      </div>
      ${err && html`<div class="err">${err}</div>`}
      ${files.length > 0 && html`<div class="attach">${files.map((f, i) => html`<div class="thumb">${f.url ? html`<img src=${f.url} alt="" />` : html`<span class="filechip">🗎 ${f.file.name}</span>`}<button onClick=${() => setFiles(files.filter((_, j) => j !== i))}>✕</button></div>`)}</div>`}
    </div></div>
  </div>`;
}

// ---------------------------------------------------------------- other views
const Table = ({ cols, rows, onRow, empty }) => html`<div class="tbl-wrap"><table><thead><tr>${cols.map((c) => html`<th class=${c.num ? "num" : ""}>${c.h}</th>`)}</tr></thead>
  <tbody>${rows.length ? rows.map((r, i) => html`<tr key=${i} class=${onRow ? "click" : ""} onClick=${onRow ? () => onRow(r) : null}>${cols.map((c) => html`<td class=${c.num ? "num" : ""}>${c.v(r)}</td>`)}</tr>`) : html`<tr><td colspan=${cols.length} class="muted">${empty}</td></tr>`}</tbody></table></div>`;
const Pill = (s) => html`<span class=${"pill " + (STATUS_PILL[s] || "")}>${String(s).replace("_", " ")}</span>`;

function useLoad(path, deps = []) {
  const [d, setD] = useState(null);
  const load = useCallback(() => api(path).then(setD).catch(() => setD([])), [path]);
  useEffect(() => { load(); const iv = setInterval(load, 4000); return () => clearInterval(iv); }, [load, ...deps]);
  return [d, load];
}

function CasesView({ t, lang, cases, openThread, openAudit, query }) {
  const [f, setF] = useState(query || ""); const [st, setSt] = useState("");
  const rows = cases.filter((c) => (!st || c.status === st) && (!f || JSON.stringify(c).toLowerCase().includes(f.toLowerCase())));
  return html`<div><div class="toolbar"><input placeholder=${t.searchPh} value=${f} onInput=${(e) => setF(e.target.value)} />
    <select value=${st} onChange=${(e) => setSt(e.target.value)}><option value="">${t.status}: all</option>${["queued", "running", "awaiting_approval", "done", "failed"].map((s) => html`<option>${s}</option>`)}</select></div>
    <${Table} empty=${t.none} rows=${rows} onRow=${(c) => openThread(c.thread_id)} cols=${[
      { h: t.caseId, v: (c) => html`<span class="mono">${c.case_id}</span>` },
      { h: t.dept, v: (c) => (c.chain?.length ? c.chain : [c.current_department]).map((d) => DEPT_ICON[d] + " " + d).join(" → ") },
      { h: lang === "bm" ? "Permohonan" : "Request", v: (c) => c.intent },
      { h: t.status, v: (c) => Pill(c.status) },
      { h: t.date, v: (c) => fmtDate(c.created_at) },
      { h: "", v: (c) => html`<button class="btn" onClick=${(e) => { e.stopPropagation(); openAudit(c.case_id); }}>${t.audit}</button>` },
    ]} /></div>`;
}

function PaymentsView({ t, lang }) {
  const [rows] = useLoad("/api/payments");
  const out = (rows || []).filter((p) => p.direction === "out" && p.status === "paid").reduce((s, p) => s + p.amount, 0);
  const pend = (rows || []).filter((p) => p.status === "pending").reduce((s, p) => s + p.amount, 0);
  const inn = (rows || []).filter((p) => p.direction === "in").reduce((s, p) => s + p.amount, 0);
  return html`<div class="grid cols-4" style=${{ marginBottom: 14 }}>
      <div class="stat"><b>${rm(out)}</b><span>${lang === "bm" ? "Dibayar kepada kerajaan" : "Paid to government"}</span></div>
      <div class="stat"><b>${rm(pend)}</b><span>${lang === "bm" ? "Menunggu" : "Pending"}</span></div>
      <div class="stat"><b>${rm(inn)}</b><span>${lang === "bm" ? "Diterima (bayaran balik / bantuan)" : "Received (refunds / aid)"}</span></div></div>
    <${Table} empty=${t.none} rows=${rows || []} cols=${[
      { h: t.date, v: (p) => fmtDate(p.created_at) }, { h: t.dept, v: (p) => DEPT_ICON[p.department] + " " + p.department },
      { h: lang === "bm" ? "Butiran" : "Item", v: (p) => lang === "bm" ? p.description_bm : p.description_en },
      { h: t.caseId, v: (p) => html`<span class="mono">${p.case_id || "-"}</span>` },
      { h: t.amount, num: true, v: (p) => (p.direction === "in" ? "+" : "") + rm(p.amount) }, { h: t.status, v: (p) => Pill(p.status) },
      { h: t.receipt, v: (p) => p.receipt ? html`<a href=${"/api/payments/" + p.id + "/receipt"} target="_blank">PDF</a>` : "-" },
    ]} />`;
}

function DocumentsView({ t }) {
  const [rows] = useLoad("/api/documents");
  return html`<${Table} empty=${t.none} rows=${rows || []} cols=${[
    { h: t.date, v: (d) => fmtDate(d.created_at) }, { h: "Type", v: (d) => html`<span class="pill">${d.kind.replace("_", " ")}</span>` },
    { h: "Title", v: (d) => d.title }, { h: t.dept, v: (d) => d.department ? DEPT_ICON[d.department] + " " + d.department : "-" },
    { h: t.caseId, v: (d) => html`<span class="mono">${d.case_id || "-"}</span>` },
    { h: "", v: (d) => html`<a class="artifact" href=${"/api/documents/" + d.id + "/file"} target="_blank">${t.open}</a>` }]} />`;
}

function CalendarView({ t, lang }) {
  const [rows] = useLoad("/api/appointments");
  return html`<${Table} empty=${t.none} rows=${rows || []} cols=${[
    { h: t.date, v: (a) => fmtDate(a.when) }, { h: lang === "bm" ? "Temu janji" : "Appointment", v: (a) => lang === "bm" ? a.title_bm : a.title_en },
    { h: lang === "bm" ? "Lokasi" : "Location", v: (a) => a.location }, { h: t.dept, v: (a) => DEPT_ICON[a.department] + " " + a.department },
    { h: t.status, v: (a) => Pill(a.status) }]} />`;
}

function InboxView({ t, lang, openThread }) {
  const [rows] = useLoad("/api/notifications");
  const groups = (rows || []).reduce((m, n) => { (m[n.case_id || n.thread_id] = m[n.case_id || n.thread_id] || []).push(n); return m; }, {});
  return html`<div class="view-narrow grid">${Object.keys(groups).length === 0 && html`<div class="empty">${t.none}</div>`}
    ${Object.entries(groups).map(([k, ns]) => html`<div class="card" key=${k}><div class="card-h"><b class="mono">${k}</b><span class="pill">${ns[0].channel}</span>
      <button class="btn" style=${{ marginLeft: "auto" }} onClick=${() => openThread(ns[0].thread_id)}>${t.open}</button></div>
      ${ns.map((n) => html`<div style=${{ padding: "6px 0", borderTop: "1px dashed var(--line)" }}><span class="mono muted">${fmtDate(n.created_at)}</span> · ${lang === "bm" ? n.bm : n.en}</div>`)}</div>`)}</div>`;
}

function MapView({ lang }) {
  const ref = useRef(null); const mapRef = useRef(null); const layer = useRef(null);
  const [pts] = useLoad("/api/map");
  useEffect(() => {
    if (!mapRef.current) {
      mapRef.current = L.map(ref.current).setView([3.1073, 101.6067], 14);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "© OpenStreetMap" }).addTo(mapRef.current);
      layer.current = L.layerGroup().addTo(mapRef.current);
    }
  }, []);
  useEffect(() => {
    if (!layer.current || !pts) return;
    layer.current.clearLayers();
    const color = { incident: "#c0392b", contractor: "#c98208", school: "#2b4fb8", flood_watch: "#0b6e8a" };
    pts.forEach((p) => {
      if (p.kind === "flood_watch") L.circle([p.lat, p.lng], { radius: p.meta?.radius_m || 400, color: color.flood_watch, fillOpacity: 0.12 }).addTo(layer.current).bindTooltip(p.label);
      else L.circleMarker([p.lat, p.lng], { radius: 9, color: "#fff", weight: 2, fillColor: color[p.kind] || "#555", fillOpacity: 1 }).addTo(layer.current).bindTooltip(p.label + (p.meta?.eta_minutes ? ` · ETA ${p.meta.eta_minutes} min` : ""));
      if (p.kind === "contractor" && p.meta?.to) L.polyline([[p.lat, p.lng], p.meta.to], { color: color.contractor, dashArray: "6 6" }).addTo(layer.current);
    });
  }, [pts]);
  return html`<div><div class="toolbar"><span class="pill bad">● ${lang === "bm" ? "Insiden" : "Incident"}</span><span class="pill agent">● ${lang === "bm" ? "Kontraktor" : "Contractor"}</span><span class="pill accent">◯ ${lang === "bm" ? "Pemantauan banjir" : "Flood watch"}</span><span class="pill">● ${lang === "bm" ? "Sekolah" : "School"}</span></div><div id="map" ref=${ref}></div></div>`;
}

function ImpactView({ lang }) {
  const [d] = useLoad("/api/impact");
  const S = (v, en, bm) => html`<div class="stat"><b>${v}</b><span>${lang === "bm" ? bm : en}</span></div>`;
  return html`<div class="grid cols-4">${d && html`
    ${S(d.cases, "Cases handled", "Kes dikendalikan")}${S(d.closed, "Cases closed", "Kes ditutup")}${S(d.dispatched, "Contractors dispatched", "Kontraktor dihantar")}
    ${S(rm(d.fees), "Fees processed", "Yuran diproses")}${S(d.pending_approvals, "Waiting for a human", "Menunggu manusia")}${S(d.audit_entries, "Audit ledger entries", "Entri lejar audit")}`}</div>`;
}

function ApprovalsView({ t, lang, user, onDecide }) {
  const [rows, reload] = useLoad("/api/approvals");
  return html`<div class="view-narrow grid">${(rows || []).length === 0 && html`<div class="empty">${t.none}</div>`}
    ${(rows || []).map((a) => html`<div class="card" key=${a.id}><div class="card-h"><b>${a.action.replaceAll("_", " ")}</b>${Pill(a.status)}<span class="mono muted">${a.case_id}</span>
      <span class="pill">${a.actor === "citizen" ? (lang === "bm" ? "rakyat memutuskan" : "citizen decides") : (lang === "bm" ? "pegawai memutuskan" : "officer decides")}</span></div>
      <div>${a.reason}</div>
      ${a.proposed?.citations?.length > 0 && html`<div class="cite">${a.proposed.citations.join(" · ")}</div>`}
      ${a.status === "pending" && a.actor === user.role && html`<div style=${{ display: "flex", gap: 8, marginTop: 10 }}>
        <button class="btn good" onClick=${async () => { await onDecide(a.id, true); reload(); }}>${t.approve}</button>
        <button class="btn bad" onClick=${async () => { await onDecide(a.id, false); reload(); }}>${t.reject}</button></div>`}
      ${a.status === "pending" && a.actor !== user.role && html`<div class="muted" style=${{ marginTop: 8 }}>${lang === "bm" ? "Baca sahaja dalam paparan ini." : "Read-only in this view."}</div>`}
    </div>`)}</div>`;
}

function MemoryBag({ t, lang, user, onChange }) {
  const [st, setSt] = useState(null); const [busy, setBusy] = useState(""); const [msg, setMsg] = useState("");
  const [form, setForm] = useState({ title_en: "", title_bm: "", dept: "local_gov", kind: "document", agency: "", url: "", as_at: "" });
  const fileRef = useRef(null); const B = lang === "bm"; const isOfficer = user.role === "officer";
  const load = () => api("/api/memory-bag").then(setSt).catch(() => {});
  useEffect(() => { load(); }, []);
  const rescan = async () => { setBusy("scan"); setMsg(""); try { const r = await api("/api/memory-bag/rescan?force=true", { method: "POST" }); setMsg(JSON.stringify(r)); } catch (e) { setMsg(e.message); } setBusy(""); load(); onChange(); };
  const upload = async (e) => {
    e.preventDefault(); const f = fileRef.current.files[0]; if (!f) return;
    const fd = new FormData(); fd.append("file", f); Object.entries(form).forEach(([k, v]) => fd.append(k, v));
    setBusy("up"); setMsg("");
    try { const r = await api("/api/memory-bag/documents", { method: "POST", form: fd }); setMsg(`${r.op}: ${r.doc_id}${r.chunks ? " · " + r.chunks + (B ? " petikan" : " passages") : ""}`); fileRef.current.value = ""; }
    catch (err) { setMsg(err.message); }
    setBusy(""); load(); onChange();
  };
  const OP = { add: "good", update: "accent", delete: "bad", check_failed: "warn" };
  if (!st) return null;
  return html`<div class="card" style=${{ marginBottom: 16 }}>
    <div class="card-h"><b>${B ? "Beg Memori" : "Memory Bag"}</b><span class="pill good">${st.active_documents} ${B ? "dokumen aktif" : "active documents"}</span>
      <span class="pill">${st.chunks.toLocaleString()} ${B ? "petikan" : "passages"}</span>${st.deleted_documents ? html`<span class="pill bad">${st.deleted_documents} ${B ? "dipadam" : "deleted"}</span>` : null}</div>
    <div class="muted" style=${{ fontSize: 13.5 }}>${B ? "Ejen membaca terus dari Beg Memori; dokumen tidak diimbas semula pada setiap permohonan. Imbasan semula automatik sebulan sekali, hanya yang berubah dikemas kini." : "Agents read straight from the Memory Bag; documents are not re-scanned on each request. An automatic re-scan runs once a month and only changes what changed."}
      <br/>${B ? "Imbasan penuh terakhir" : "Last full scan"}: <b>${st.last_full_scan ? fmtDate(st.last_full_scan) : "-"}</b> · ${B ? "Seterusnya" : "Next"}: <b>${st.next_scan ? fmtDate(st.next_scan) : "-"}</b></div>
    ${isOfficer && html`<div style=${{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10 }}><button class="btn" disabled=${!!busy} onClick=${rescan}>${busy === "scan" ? "…" : (B ? "Imbas semula sekarang" : "Re-scan now")}</button></div>
      <form onSubmit=${upload} class="toolbar" style=${{ marginTop: 10 }}>
        <input type="file" ref=${fileRef} accept=".pdf,.html,.htm" style=${{ minWidth: 0, flex: "1 1 200px" }} />
        <input placeholder=${B ? "Tajuk (EN)" : "Title (EN)"} value=${form.title_en} onInput=${(e) => setForm({ ...form, title_en: e.target.value })} style=${{ minWidth: 0, flex: "1 1 180px" }} />
        <input placeholder=${B ? "Tajuk (BM)" : "Title (BM)"} value=${form.title_bm} onInput=${(e) => setForm({ ...form, title_bm: e.target.value })} style=${{ minWidth: 0, flex: "1 1 180px" }} />
        <select value=${form.dept} onChange=${(e) => setForm({ ...form, dept: e.target.value })}>${Object.keys(DEPT_ICON).map((k) => html`<option>${k}</option>`)}</select>
        <input placeholder=${B ? "Pautan sumber rasmi" : "Official source link"} value=${form.url} onInput=${(e) => setForm({ ...form, url: e.target.value })} style=${{ minWidth: 0, flex: "1 1 200px" }} />
        <button class="btn primary" disabled=${!!busy}>${busy === "up" ? "…" : (B ? "Tambah / kemas kini" : "Add / update")}</button></form>
      <div class="muted" style=${{ fontSize: 12.5 }}>${B ? "Untuk laman yang perlu log masuk: muat turun sekali, muat naik di sini. Muat naik semula versi baharu untuk kemas kini." : "For sites that need a login: download once, upload here. Upload a newer version later to update it."}</div>`}
    ${msg && html`<div class="mono" style=${{ marginTop: 8 }}>${msg}</div>`}
    <details style=${{ marginTop: 10 }}><summary class="eyebrow" style=${{ cursor: "pointer" }}>${B ? "Log perubahan" : "Change log"} (${st.recent_changes.length})</summary>
      <div class="tbl-wrap" style=${{ marginTop: 8 }}><table><tbody>${st.recent_changes.map((e) => html`<tr key=${e.id}><td class="mono muted">${fmtDate(e.ts)}</td><td><span class=${"pill " + (OP[e.op] || "")}>${e.op}</span></td><td class="mono">${e.doc_id}</td><td class="muted">${e.detail}</td></tr>`)}</tbody></table></div></details>
  </div>`;
}

function PolicyView({ t, lang, user }) {
  const [q, setQ] = useState(""); const [hits, setHits] = useState([]); const [docs, setDocs] = useState([]); const [dept, setDept] = useState("");
  const loadDocs = () => api("/api/policy/documents").then(setDocs).catch(() => {});
  useEffect(() => { loadDocs(); }, []);
  const run = async (e) => { e && e.preventDefault(); if (q.trim()) setHits(await api(`/api/policy/search?q=${encodeURIComponent(q)}${dept ? "&dept=" + dept : ""}`)); };
  const B = lang === "bm"; const isOfficer = user.role === "officer";
  const act = async (d) => { await api(d.status === "deleted" ? `/api/memory-bag/documents/${d.doc_id}/restore` : `/api/memory-bag/documents/${d.doc_id}`, { method: d.status === "deleted" ? "POST" : "DELETE" }); loadDocs(); };
  const ACCESS = { public: ["good", t.public], login: ["warn", t.needsLogin] };
  return html`<div>
    <${MemoryBag} t=${t} lang=${lang} user=${user} onChange=${loadDocs} />
    <form class="toolbar" onSubmit=${run}><input placeholder=${t.policyPh} value=${q} onInput=${(e) => setQ(e.target.value)} />
      <select value=${dept} onChange=${(e) => setDept(e.target.value)}><option value="">${t.dept}: all</option>${[...new Set(docs.map((d) => d.dept))].map((k) => html`<option>${k}</option>`)}</select>
      <button class="btn primary">${t.search}</button></form>
    ${hits.length > 0 && html`<div class="grid" style=${{ marginBottom: 18 }}>${hits.map((h) => html`<div class="card"><div class="card-h"><b>${B ? h.title_bm : h.title_en}</b><span class="pill">${B ? "ms" : "p."} ${h.page}</span><span class="pill accent">${h.dept}</span><a style=${{ marginLeft: "auto" }} href=${h.url} target="_blank" rel="noopener">${B ? "Sumber rasmi" : "Official source"} ↗</a></div><div class="muted" style=${{ fontSize: 13.5 }}>${h.excerpt}…</div></div>`)}</div>`}
    <div class="h2">${B ? `Korpus (${docs.length} dokumen)` : `Corpus (${docs.length} documents)`}</div>
    <${Table} empty=${t.none} rows=${docs} cols=${[
      { h: B ? "Dokumen" : "Document", v: (d) => html`${d.url ? html`<a href=${d.url} target="_blank" rel="noopener">${B ? d.title_bm : d.title_en}</a>` : (B ? d.title_bm : d.title_en)}<div class="muted" style=${{ fontSize: 12 }}>${d.agency}</div>` },
      { h: t.dept, v: (d) => DEPT_ICON[d.dept] + " " + d.dept }, { h: "Type", v: (d) => html`<span class="pill">${d.kind}</span>` },
      { h: B ? "Setakat" : "As at", v: (d) => d.as_at || "-" },
      { h: t.access, v: (d) => { const a = ACCESS[d.access] || ACCESS.public; return html`<span class=${"pill " + a[0]}>${a[1]}</span>`; } },
      { h: B ? "Disemak" : "Checked", v: (d) => html`<span class="mono muted">${d.last_checked ? fmtDate(d.last_checked) : "-"}</span>` },
      { h: t.status, v: (d) => html`<span class=${"pill " + (d.status === "active" ? "good" : "bad")}>${d.status}</span> <span class="mono muted">${d.n_chunks}</span>` },
      ...(isOfficer ? [{ h: "", v: (d) => html`<button class=${"btn " + (d.status === "deleted" ? "" : "bad")} onClick=${() => act(d)}>${d.status === "deleted" ? (B ? "Pulihkan" : "Restore") : (B ? "Padam" : "Delete")}</button>` }] : []),
    ]} />
  </div>`;
}

function AuditView({ t, lang, cases, caseId, setCaseId }) {
  const [rows, setRows] = useState([]); const [health, setHealth] = useState(null);
  useEffect(() => { if (caseId) api(`/api/cases/${caseId}/timeline`).then(setRows); api("/api/health").then(setHealth); }, [caseId]);
  return html`<div class="view-narrow">
    <div class="toolbar"><select value=${caseId || ""} onChange=${(e) => setCaseId(e.target.value)}><option value="">${t.caseId}…</option>${cases.map((c) => html`<option>${c.case_id}</option>`)}</select>
      ${health && html`<span class=${"pill " + (health.audit_chain_valid ? "good" : "bad")}>${health.audit_chain_valid ? (lang === "bm" ? "Rantai hash sah" : "Hash chain valid") : (lang === "bm" ? "Rantai rosak" : "Chain broken")}</span>`}
      ${rows.length > 0 && html`<a class="btn" href=${"data:application/json;charset=utf-8," + encodeURIComponent(JSON.stringify(rows, null, 2))} download=${caseId + "-audit.json"}>Export JSON</a>`}</div>
    ${!caseId ? html`<div class="empty">${lang === "bm" ? "Pilih kes untuk melihat lejar audit." : "Pick a case to see its audit ledger."}</div>` : html`<ul class="timeline">${rows.map((r) => html`<li key=${r.id}>
      <div><span class="mono muted">${fmtTime(r.ts)}</span> · <b>${r.actor}</b> · ${r.action.replaceAll("_", " ")}</div>
      <div class="hash">#${r.id} · ${r.hash.slice(0, 24)}…</div>
      <details><summary class="muted" style=${{ fontSize: 12 }}>payload</summary><pre class="mono" style=${{ whiteSpace: "pre-wrap" }}>${JSON.stringify(r.payload, null, 2)}</pre></details></li>`)}</ul>`}
  </div>`;
}

function DemoView({ t, lang, quick, logout }) {
  const [pace, setPace] = useState(0);
  useEffect(() => { api("/api/demo/pace").then((d) => setPace(d.pace)); }, []);
  const setP = async (v) => { setPace(v); await api("/api/demo/pace", { method: "POST", body: { seconds: v } }); };
  const C = (title, body, btn, fn) => html`<div class="card"><b>${title}</b><p>${body}</p><button class="btn primary" onClick=${fn}>${btn}</button></div>`;
  const B = lang === "bm";
  return html`<div>
    <div class="card" style=${{ marginBottom: 14 }}><b>${t.pace}</b> <span class="mono">${pace.toFixed(1)}s</span>
      <input type="range" min="0" max="1.5" step="0.1" value=${pace} onInput=${(e) => setP(parseFloat(e.target.value))} style=${{ width: "100%" }} />
      <span class="muted" style=${{ fontSize: 13 }}>${B ? "Perlahankan setiap langkah ejen supaya penonton dapat ikut." : "Slows each agent step so the audience can follow."}</span></div>
    <div class="demo-grid">
      ${C(B ? "Aduan Sivil" : "Aduan Civil", B ? "Longkang tersumbat dekat sekolah, hujan dijangka." : "Blocked drain near a school, rain forecast.", B ? "Isi" : "Prefill", () => quick("Longkang depan sekolah tersumbat, air dah naik sampai jalan."))}
      ${C(B ? "Pelbagai niat" : "Multi-intent", B ? "Satu mesej, dua kes, dijalankan mengikut giliran." : "One message, two cases, run in order.", B ? "Isi" : "Prefill", () => quick("Saya nak renew lesen memandu dan bayar saman."))}
      ${C(B ? "Keyakinan rendah" : "Low confidence", B ? "Penghala bertanya satu soalan, tidak meneka." : "The router asks one question instead of guessing.", B ? "Isi" : "Prefill", () => quick("tolong saya"))}
      ${C(B ? "Gerbang kelulusan" : "Approval gate", B ? "Insiden kritikal: kos melebihi had, pegawai mesti lulus." : "Critical incident: cost above the limit, an officer must approve.", B ? "Isi" : "Prefill", () => quick("Longkang besar runtuh, air deras masuk rumah dan murid sekolah dalam bahaya!"))}
      ${C(t.reset, B ? "Padam semua kes dan log keluar." : "Clears all cases and signs everyone out.", t.reset, async () => { await api("/api/demo/reset", { method: "POST" }); logout(); })}
    </div></div>`;
}

function SettingsView({ t, lang, setLang, theme, setTheme, user }) {
  return html`<div class="view-narrow grid">
    <div class="card"><b>${lang === "bm" ? "Profil" : "Profile"}</b><p>${user.name}<br/><span class="mono muted">${user.mykad || user.profile?.agency || ""}</span><br/>${user.profile?.address || ""}</p></div>
    <div class="card"><b>${lang === "bm" ? "Bahasa" : "Language"}</b><div style=${{ marginTop: 8 }}><div class="seg"><button class=${lang === "en" ? "on" : ""} onClick=${() => setLang("en")}>English</button><button class=${lang === "bm" ? "on" : ""} onClick=${() => setLang("bm")}>Bahasa Malaysia</button></div></div></div>
    <div class="card"><b>${lang === "bm" ? "Tema" : "Theme"}</b><div style=${{ marginTop: 8 }}><div class="seg"><button class=${theme === "light" ? "on" : ""} onClick=${() => setTheme("light")}>Light</button><button class=${theme === "dark" ? "on" : ""} onClick=${() => setTheme("dark")}>Dark</button></div></div></div>
    <div class="card"><b>${lang === "bm" ? "Notifikasi & privasi" : "Notifications & privacy"}</b><p class="muted">${lang === "bm" ? "Notifikasi dalam aplikasi sahaja dalam demo. SMS dan e-mel disimulasikan. Data demo adalah rekaan." : "In-app notifications only in the demo; SMS and email are simulated. Demo data is fictitious."}</p></div>
  </div>`;
}

function HelpView({ lang }) {
  const B = lang === "bm";
  return html`<div class="view-narrow grid"><div class="card"><b>${B ? "Cara ia berfungsi" : "How it works"}</b>
    <ol><li>${B ? "Penghala Niat mengelas permohonan anda dan mencipta ID Kes. Ia tidak melaksanakan apa-apa." : "The Intent Router classifies your request and creates a Case ID. It never carries anything out."}</li>
    <li>${B ? "Satu modul utama jabatan memiliki kes dan memilih sub-modulnya sendiri." : "One department main module owns the case and picks its own sub-modules."}</li>
    <li>${B ? "Jabatan lain hanya terlibat melalui serahan berurutan, dengan ID Kes yang sama." : "Other departments join only by sequential handoff, with the same Case ID."}</li>
    <li>${B ? "Setiap tindakan direkod dalam lejar audit berantai hash." : "Every action is written to a hash-chained audit ledger."}</li></ol></div>
    <div class="card"><b>${B ? "Maklum balas" : "Feedback"}</b><p class="muted">${B ? "Laporkan pepijat kepada pasukan MyTadbir semasa demo." : "Report bugs to the MyTadbir team during the demo."}</p></div></div>`;
}

// ---------------------------------------------------------------- app
function App() {
  const [lang, setLangS] = useState(store.get("mt-lang", "en"));
  const [theme, setThemeS] = useState(store.get("mt-theme", "light"));
  const [user, setUser] = useState(null); const [booted, setBooted] = useState(false);
  const [view, setView] = useState("console");
  const [catalog, setCatalog] = useState([]); const [cases, setCases] = useState([]); const [threads, setThreads] = useState([]); const [approvals, setApprovals] = useState([]);
  const [pins, setPins] = useState(store.get("mt-pins", []));
  const [threadId, setThreadId] = useState(null);
  const [msgs, setMsgs] = useState({}); // thread -> [{text, previews}]
  const [evs, setEvs] = useState({});   // thread -> events
  const [threadCases, setThreadCases] = useState([]);
  const [traceOn, setTraceOn] = useState(true); const [navOpen, setNavOpen] = useState(false); const [traceOpen, setTraceOpen] = useState(false); const [preset, setPreset] = useState(null); const [draft, setDraft] = useState("");
  const [auditCase, setAuditCase] = useState(null); const [search, setSearch] = useState("");
  const esRef = useRef(null);
  const t = I18N[lang];
  const setLang = (l) => { setLangS(l); store.set("mt-lang", l); };
  const setTheme = (x) => { setThemeS(x); store.set("mt-theme", x); };
  useEffect(() => { document.documentElement.dataset.theme = theme; }, [theme]);
  useEffect(() => { document.documentElement.lang = lang === "bm" ? "ms" : "en"; }, [lang]);

  useEffect(() => { (async () => { if (TOKEN) { try { setUser(await api("/api/me")); } catch { TOKEN = null; store.set("mt-token", null); } } setBooted(true); })(); }, []);
  const refresh = useCallback(async () => {
    if (!user) return;
    const [c, th, ap] = await Promise.all([api("/api/cases"), api("/api/threads"), api("/api/approvals")]).catch(() => [[], [], []]);
    setCases(c); setThreads(th); setApprovals(ap);
    if (threadId) setThreadCases(await api(`/api/threads/${threadId}`).catch(() => []));
  }, [user, threadId]);
  useEffect(() => { if (user) api("/api/catalog").then(setCatalog); }, [user]);
  useEffect(() => { refresh(); const iv = setInterval(refresh, 3000); return () => clearInterval(iv); }, [refresh]);

  const subscribe = (tid) => new Promise((resolve) => {
    if (esRef.current) esRef.current.close();
    const es = new EventSource(`/api/threads/${tid}/trace`); esRef.current = es;
    let done = false; const fin = () => { if (!done) { done = true; resolve(); } };
    es.onopen = () => setTimeout(fin, 50); setTimeout(fin, 1500);
    es.addEventListener("trace", (m) => { const ev = JSON.parse(m.data); setEvs((s) => ({ ...s, [tid]: [...(s[tid] || []), ev] })); refresh(); });
  });
  const openThread = async (tid) => {
    setThreadId(tid); setView("console");
    if (!evs[tid]) {
      // Rebuild the trace for an older thread from the audit ledger.
      const cs = await api(`/api/threads/${tid}`); const rebuilt = [];
      for (const c of cs) for (const r of await api(`/api/cases/${c.case_id}/timeline`)) rebuilt.push({ ts: r.ts, thread_id: tid, case_id: c.case_id, layer: "service", actor: r.actor, event: r.action, data: r.payload });
      rebuilt.sort((a, b) => a.ts.localeCompare(b.ts));
      setEvs((s) => ({ ...s, [tid]: rebuilt }));
      setMsgs((s) => ({ ...s, [tid]: s[tid] || (cs[0] ? [{ text: cs.map((c) => c.intent).join(" · "), previews: [] }] : []) }));
    }
    subscribe(tid);
  };
  const send = async (text, files, dept) => {
    let tid = threadId;
    if (!tid) { tid = newThreadId(); setThreadId(tid); }
    await subscribe(tid);
    setMsgs((s) => ({ ...s, [tid]: [...(s[tid] || []), { text, previews: files.map((f) => URL.createObjectURL(f)) }] }));
    const fd = new FormData(); fd.append("text", text); fd.append("thread_id", tid); if (dept) fd.append("department", dept);
    files.forEach((f) => fd.append(f.type.startsWith("image/") ? "photos" : "files", f));
    await api("/api/requests", { method: "POST", form: fd });
    refresh();
  };
  const newRequest = () => { setThreadId(null); setThreadCases([]); setView("console"); setPreset(null); if (esRef.current) esRef.current.close(); };
  const onDecide = async (id, ok) => { await api(`/api/approvals/${id}/decide`, { method: "POST", body: { approved: ok } }); refresh(); };
  const logout = async () => { try { await api("/api/auth/logout", { method: "POST" }); } catch {} TOKEN = null; store.set("mt-token", null); setUser(null); newRequest(); setEvs({}); setMsgs({}); };
  const quick = (txt) => { newRequest(); setDraft(txt); setTimeout(() => document.getElementById("composer")?.focus(), 50); };
  const togglePin = (tid) => { const n = pins.includes(tid) ? pins.filter((x) => x !== tid) : [...pins, tid]; setPins(n); store.set("mt-pins", n); };

  if (!booted) return null;
  if (!user) return html`<${Login} t=${t} lang=${lang} setLang=${setLang} onIn=${(r) => { TOKEN = r.token; store.set("mt-token", r.token); setUser(r.user); setView(r.user.role === "officer" ? "approvals" : "console"); }} />`;

  const events = threadId ? evs[threadId] || [] : [];
  const last = [...events].reverse().find((e) => e.layer !== "case_manager");
  const titleKey = view === "search" ? "search" : view;
  let body;
  switch (view) {
    case "cases": body = html`<${CasesView} t=${t} lang=${lang} cases=${cases} openThread=${openThread} openAudit=${(id) => { setAuditCase(id); setView("audit"); }} />`; break;
    case "search": body = html`<${CasesView} t=${t} lang=${lang} cases=${cases} query=${search} openThread=${openThread} openAudit=${(id) => { setAuditCase(id); setView("audit"); }} />`; break;
    case "payments": body = html`<${PaymentsView} t=${t} lang=${lang} />`; break;
    case "documents": body = html`<${DocumentsView} t=${t} />`; break;
    case "calendar": body = html`<${CalendarView} t=${t} lang=${lang} />`; break;
    case "inbox": body = html`<${InboxView} t=${t} lang=${lang} openThread=${openThread} />`; break;
    case "map": body = html`<${MapView} lang=${lang} />`; break;
    case "impact": body = html`<${ImpactView} lang=${lang} />`; break;
    case "approvals": body = html`<${ApprovalsView} t=${t} lang=${lang} user=${user} onDecide=${onDecide} />`; break;
    case "policy": body = html`<${PolicyView} t=${t} lang=${lang} user=${user} />`; break;
    case "audit": body = html`<${AuditView} t=${t} lang=${lang} cases=${cases} caseId=${auditCase} setCaseId=${setAuditCase} />`; break;
    case "settings": body = html`<${SettingsView} t=${t} lang=${lang} setLang=${setLang} theme=${theme} setTheme=${setTheme} user=${user} />`; break;
    case "help": body = html`<${HelpView} lang=${lang} />`; break;
    default: body = null;
  }
  const wide = () => window.innerWidth > 1280;
  const go = (v) => { setView(v); setNavOpen(false); };
  return html`<div class=${"shell" + (traceOn ? "" : " trace-off") + (navOpen ? " nav-open" : "") + (traceOpen ? " trace-open" : "")}>
    ${(navOpen || traceOpen) && html`<div class="backdrop" onClick=${() => { setNavOpen(false); setTraceOpen(false); }}></div>`}
    <${Sidebar} t=${t} lang=${lang} user=${user} view=${view} setView=${go} catalog=${catalog} cases=${cases} threads=${threads} pins=${pins} togglePin=${togglePin}
      openThread=${(id) => { setNavOpen(false); openThread(id); }} newRequest=${() => { setNavOpen(false); newRequest(); }} launchDept=${(k) => { setNavOpen(false); newRequest(); setPreset(k); }} logout=${logout} theme=${theme} setTheme=${setTheme} />
    <main class="main">
      <div class="top"><button class="btn hamburger" aria-label="Menu" onClick=${() => setNavOpen(true)}>☰</button><h1>${t[titleKey] || titleKey}</h1>
        ${view === "search" && html`<input class="btn" style=${{ fontWeight: 400, minWidth: 260 }} placeholder=${t.searchPh} value=${search} onInput=${(e) => setSearch(e.target.value)} />`}
        <span class="sp"></span>
        <span class="agent-badge" title="Active agent"><span class=${"dot" + (last && last.event !== "thread_done" && last.event !== "case_done" ? " live" : "")}></span>${last ? `${last.actor}${modelOf(last) ? " · " + modelOf(last) : ""}` : (user.role === "officer" ? t.officerMode : t.citizenMode)}</span>
        <div class="seg"><button class=${lang === "en" ? "on" : ""} onClick=${() => setLang("en")}>EN</button><button class=${lang === "bm" ? "on" : ""} onClick=${() => setLang("bm")}>BM</button></div>
        <button class=${"btn trace-btn" + (traceOn ? " when-narrow" : "")} onClick=${() => { setTraceOn(true); if (!wide()) setTraceOpen(true); }}>⚡ <span class="lbl">${t.trace}</span></button>
      </div>
      ${view === "console" ? html`<${Console} t=${t} lang=${lang} user=${user} catalog=${catalog} thread=${threadId ? { messages: msgs[threadId] || [] } : null} events=${events}
          cases=${threadCases} approvals=${approvals} send=${send} onDecide=${onDecide} preset=${preset} setPreset=${setPreset} draft=${draft} setDraft=${setDraft} />`
        : html`<div class="view">${body}</div>`}
    </main>
    ${traceOn && html`<${TracePanel} t=${t} lang=${lang} events=${events} threadId=${threadId} onClose=${() => { if (wide()) setTraceOn(false); setTraceOpen(false); }} />`}
  </div>`;
}

ReactDOM.createRoot(document.getElementById("root")).render(html`<${App} />`);
