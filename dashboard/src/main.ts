import "./style.css";
import { getState, getTicket, getMemory, getEvents, getSeries, getProvenance, subscribe, type Dict } from "./api";
import { renderMetrics } from "./charts";

const app = document.getElementById("app")!;
app.innerHTML = `
  <div id="statusbar">
    <span class="brand">PROCURATOR</span>
    <span class="kv">run <b id="sb-run">–</b></span>
    <span class="kv">sprint <b id="sb-sprint">–</b></span>
    <span class="kv">pass <b id="sb-pass">–</b></span>
    <span class="kv">tokens <b id="sb-tok">–</b></span>
    <span class="kv">memory <b id="sb-mem">–</b></span>
    <span class="live"><span class="dot" id="sb-dot"></span><span id="sb-live">connecting</span></span>
  </div>
  <div id="explorer"></div>
  <div id="editor"><div id="tabs"></div><div id="content"></div></div>
  <div id="inspector"><h3>Inspector</h3><div class="row" style="color:var(--text-muted)">select a ticket</div></div>
  <div id="bottom">
    <div id="bottom-tabs">
      <div class="tab active" data-b="events">Events</div>
      <div class="tab" data-b="metrics">Metrics</div>
      <div class="tab" data-b="problems">Problems</div>
    </div>
    <div id="bottom-content"></div>
  </div>`;

const $ = (s: string) => document.querySelector(s) as HTMLElement;
let state: Dict = {}; let events: Dict[] = []; let bottomTab = "events";
let tabs: { id: string; title: string; render: () => void }[] = []; let activeTab = "";

const esc = (s: any) => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;");
const stIcon: Dict = { done: "✓", failed: "✗", claimed: "▶", grading: "⚖", review: "◆", ready: "·", blocked: "░", pending: "·" };

/* ---------------- status bar ---------------- */
function renderStatus() {
  $("#sb-run").textContent = state.run_id;
  $("#sb-sprint").textContent = String(state.sprints?.at(-1)?.sprint ?? 0);
  $("#sb-pass").textContent = `${state.pass.passed}/${state.pass.total || "–"}`;
  $("#sb-tok").textContent = `${(state.tokens / 1000).toFixed(1)}k`;
  $("#sb-mem").textContent = state.memory_enabled ? "ON" : "OFF (ablation)";
}

/* ---------------- explorer ---------------- */
function renderExplorer() {
  const tk = (state.tickets as Dict[]).map(t =>
    `<div class="tree-item" data-ticket="${t._id}"><span class="st">${stIcon[t.status] ?? "·"}</span>${esc(t.module)} <span style="color:var(--text-muted)">${t.status}</span></div>`).join("");
  const ag = (state.agents as Dict[]).map(a =>
    `<div class="tree-item"><span class="st">●</span>${esc(a.agent_id)} <span style="color:var(--text-muted)">${esc(a.status ?? "")}</span></div>`).join("");
  $("#explorer").innerHTML = `
    <div class="section-h">Mandate</div>
    <div class="tree-item" data-open="mandate"><span class="st">▣</span>SPEC.md (v${state.mandate?.version ?? "?"})</div>
    <div class="section-h">Tickets</div>${tk}
    <div class="section-h">Agents</div>${ag}
    <div class="section-h">Memory</div>
    <div class="tree-item" data-open="memory"><span class="st">◈</span>episodes / lessons / playbooks</div>
    <div class="section-h">Stakeholder</div>
    <div class="tree-item" data-open="stakeholder"><span class="st">✉</span>messages (${state.stakeholder_msgs?.length ?? 0})</div>`;
  $("#explorer").querySelectorAll("[data-ticket]").forEach(el =>
    el.addEventListener("click", () => openTicket((el as HTMLElement).dataset.ticket!)));
  $("#explorer").querySelectorAll("[data-open]").forEach(el =>
    el.addEventListener("click", () => openStatic((el as HTMLElement).dataset.open!)));
}

/* ---------------- tabs/editor ---------------- */
function openTab(id: string, title: string, render: () => void) {
  if (!tabs.find(t => t.id === id)) tabs.push({ id, title, render });
  activeTab = id;
  $("#tabs").innerHTML = tabs.map(t =>
    `<div class="tab ${t.id === activeTab ? "active" : ""}" data-tab="${t.id}">${esc(t.title)}</div>`).join("");
  $("#tabs").querySelectorAll("[data-tab]").forEach(el =>
    el.addEventListener("click", () => { activeTab = (el as HTMLElement).dataset.tab!; tabs.find(t => t.id === activeTab)!.render(); openTab(activeTab, tabs.find(t => t.id === activeTab)!.title, tabs.find(t => t.id === activeTab)!.render); }));
  tabs.find(t => t.id === activeTab)!.render();
}

function openStatic(kind: string) {
  if (kind === "mandate") openTab("mandate", "SPEC.md", () => {
    $("#content").innerHTML = `<div class="md"><pre><code>${esc(state.mandate?.spec)}</code></pre></div>`;
  });
  if (kind === "memory") openTab("memory", "memory", async () => {
    const m = await getMemory();
    $("#content").innerHTML = `
      <h1>Memory tiers</h1>
      <h2>L4 Playbooks (${m.playbooks.length})</h2>
      ${m.playbooks.map((p: Dict) => `<pre><code><b style="color:var(--series-1)">${esc(p.ticket_class)} v${p.version}</b>\n${esc(p.text)}</code></pre>`).join("") || "<p>none yet — written at sprint retro</p>"}
      <h2>L2 Lessons (${m.lessons.length})</h2>
      ${m.lessons.map((l: Dict) => `<p>· ${esc(l.text)}</p>`).join("") || "<p>none yet</p>"}
      <h2>L1 Episodes (${m.episodes.length})</h2>
      ${m.episodes.map((e: Dict) => `<pre><code><b>${esc(e.agent)} / sprint ${e.sprint}</b> (${e.n_events} events)\n${esc(e.summary)}</code></pre>`).join("") || "<p>none yet</p>"}`;
  });
  if (kind === "stakeholder") openTab("stakeholder", "stakeholder", () => {
    $("#content").innerHTML = `<h1>Stakeholder channel</h1>` +
      state.stakeholder_msgs.map((m: Dict) =>
        `<pre><code><b style="color:var(--series-2)">${esc(m.from)}</b> · ${new Date(m.created_at).toLocaleTimeString()}\n${esc(m.text)}</code></pre>`).join("");
  });
}

async function openTicket(id: string) {
  const data = await getTicket(id);
  const t = data.ticket;
  openTab(`t-${id}`, t.module, () => {
    const art = data.artifacts[0];
    $("#content").innerHTML = `
      <h1>${esc(t.title)}</h1>
      <p>status <span class="chip ${t.status === "done" ? "good" : t.status === "failed" ? "bad" : "warn"}">${t.status}</span>
        · ACs: ${(t.ac_refs || []).join(", ") || "(infrastructure)"} · attempts ${t.attempts ?? 0} · reaps ${t.reap_count ?? 0}</p>
      <h2>Description</h2><p>${esc(t.description)}</p>
      <h2>Verdicts (${data.verdicts.length})</h2>
      ${data.verdicts.map((v: Dict) => `<p><span class="chip ${v.accepted ? "good" : "bad"}">${v.accepted ? "accept" : "reject"}</span>
        ${v.passed}/${v.total} · new: ${(v.newly_passing || []).join(",") || "–"} · reg: ${(v.regressions || []).join(",") || "–"}</p>`).join("") || "<p>none</p>"}
      ${art ? `<h2>Latest artifact — ${esc(art.worker_id)} · ${esc(art.notes)}</h2>` +
        Object.entries(art.files).map(([n, c]) => `<h2>${esc(n)}</h2><pre><code>${esc(c)}</code></pre>`).join("") : ""}`;
  });
  renderInspector(t, data.verdicts);
}

/* ---------------- inspector (provenance) ---------------- */
async function renderInspector(t: Dict, verdicts: Dict[]) {
  let chainHtml = `<div class="row" style="color:var(--text-muted)">no decisions recorded</div>`;
  const decisions = await fetch(`/api/decisions`).then(r => r.json()).catch(() => []);
  const verdictDec = decisions.filter((d: Dict) => d.data?.ticket_id === t._id).at(-1);
  if (verdictDec) {
    const chain = await getProvenance(verdictDec._id);
    chainHtml = `<div class="chain">` + chain.map((d: Dict) =>
      `<div class="node"><span class="k">${esc(d.kind ?? "root")}</span> ${esc(d.text ?? d.data?.text ?? "")}<br>
       <span style="color:var(--text-muted)">${esc(d.agent ?? "")} · ${d.created_at ? new Date(d.created_at).toLocaleTimeString() : ""}</span></div>`).join("") + `</div>`;
  }
  $("#inspector").innerHTML = `
    <h3>Ticket</h3>
    <div class="row"><b>${esc(t.module)}</b></div>
    <div class="row">worker: ${esc(t.worker_id ?? "–")}</div>
    <div class="row">class: ${esc(t.ticket_class)}</div>
    <div class="row">deps: ${(t.deps || []).length}</div>
    <h3>Provenance ($graphLookup)</h3>${chainHtml}
    <h3>Gate history</h3>
    ${verdicts.map((v: Dict) => `<div class="row"><span class="chip ${v.accepted ? "good" : "bad"}">${v.passed}/${v.total}</span> ${new Date(v.created_at).toLocaleTimeString()}</div>`).join("") || "<div class='row'>–</div>"}`;
}

/* ---------------- bottom panel ---------------- */
function evLine(e: Dict): string {
  const k = e.kind ?? "";
  const cls = k.includes("accept") ? "accept" : (k.includes("reject") || k.includes("error")) ? "reject" : "";
  const ts = e.created_at ? new Date(e.created_at).toLocaleTimeString() : "";
  return `<div class="ev ${cls}"><span class="t">${ts}</span> <span class="a">${esc(e.agent)}</span> <span class="k">${esc(k)}</span> ${esc(e.text)}</div>`;
}
async function renderBottom() {
  const el = $("#bottom-content");
  if (bottomTab === "events") { el.innerHTML = events.map(evLine).join(""); el.scrollTop = el.scrollHeight; }
  if (bottomTab === "metrics") renderMetrics(el, await getSeries(), state);
  if (bottomTab === "problems") {
    const probs = events.filter(e => /reject|error|halt|reaper/.test(e.kind ?? ""));
    el.innerHTML = probs.map(evLine).join("") || `<div style="color:var(--text-muted)">no problems</div>`;
  }
}
document.querySelectorAll("#bottom-tabs .tab").forEach(el => el.addEventListener("click", () => {
  document.querySelectorAll("#bottom-tabs .tab").forEach(t => t.classList.remove("active"));
  el.classList.add("active");
  bottomTab = (el as HTMLElement).dataset.b!;
  renderBottom();
}));

/* ---------------- live loop ---------------- */
async function refresh() {
  state = await getState();
  renderStatus(); renderExplorer(); renderBottom();
}
(async () => {
  events = await getEvents();
  await refresh();
  openStatic("mandate");
  subscribe(m => {
    if (m.type === "event" && m.op === "insert") { events.push(m.doc); if (events.length > 500) events.shift(); }
    // any write refreshes the snapshot cheaply (debounced)
    clearTimeout((window as any).__rt); (window as any).__rt = setTimeout(refresh, 400);
    if (bottomTab !== "metrics") renderBottom();
  }, ok => { $("#sb-dot").className = `dot ${ok ? "on" : ""}`; $("#sb-live").textContent = ok ? "live" : "reconnecting"; });
  setInterval(refresh, 10000); // fallback poll
})();
