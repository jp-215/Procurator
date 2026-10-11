// Flow view: the whole collaboration as a live pipeline.
// Stages: Collection (phone) -> Ingestion -> Agent mesh (change-stream bus)
// -> Atlas collections -> Delivery. Nodes pulse as SSE events arrive.
import type { Dict } from "./api";

interface Node { id: string; x: number; y: number; w: number; h?: number; title: string; sub?: string; kind: string }

const W = 1480, H = 760;

const NODES: Node[] = [
  // stage 1 — collection
  { id: "caller",   x: 20,  y: 240, w: 150, title: "📞 Stakeholder", sub: "the human on the phone", kind: "ext" },
  { id: "twilio",   x: 20,  y: 340, w: 150, title: "Twilio", sub: "PSTN · speech→text", kind: "ext" },
  { id: "eleven",   x: 20,  y: 440, w: 150, title: "ElevenLabs", sub: "the PM's voice", kind: "ext" },
  // stage 2 — ingestion
  { id: "gateway",  x: 240, y: 290, w: 170, title: "Voice Gateway", sub: "/voice/* webhooks", kind: "svc" },
  { id: "intake",   x: 240, y: 410, w: 170, title: "Intake", sub: "hangup → classify →\nseed mandate → launch", kind: "svc" },
  // stage 3 — the mesh around the bus
  { id: "bus",      x: 640, y: 330, w: 190, h: 90, title: "Atlas Change Streams", sub: "the message bus", kind: "bus" },
  { id: "procurator", x: 640, y: 160, w: 190, title: "Procurator", sub: "PM · standups · governor", kind: "agent" },
  { id: "legatus",  x: 480, y: 250, w: 140, title: "Legatus", sub: "spec → ticket DAG", kind: "agent" },
  { id: "legionarius-1", x: 460, y: 460, w: 150, title: "Legionarius-1", sub: "worker · claims", kind: "agent" },
  { id: "legionarius-2", x: 460, y: 560, w: 150, title: "Legionarius-2", sub: "worker · claims", kind: "agent" },
  { id: "censor",   x: 860, y: 250, w: 150, title: "Censor", sub: "hidden-suite gate", kind: "agent" },
  { id: "scriba",   x: 700, y: 490, w: 150, title: "Scriba", sub: "memory · compact/distill", kind: "agent" },
  { id: "quaestor", x: 880, y: 490, w: 140, title: "Quaestor", sub: "token & test ledger", kind: "agent" },
  // stage 4 — atlas
  { id: "db-control", x: 1120, y: 120, w: 190, title: "Control plane", sub: "", kind: "db" },
  { id: "db-memory",  x: 1120, y: 300, w: 190, title: "Memory tiers", sub: "", kind: "db" },
  { id: "db-signal",  x: 1120, y: 490, w: 190, title: "Signal plane", sub: "", kind: "db" },
  // stage 5 — delivery
  { id: "github",   x: 1340, y: 250, w: 130, title: "GitHub", sub: "workbench repo\nrun/<id> commits", kind: "ext" },
  { id: "callback", x: 1340, y: 400, w: 130, title: "📱 Callback", sub: "PM rings you\nwith the standup", kind: "ext" },
];

const EDGES: [string, string][] = [
  ["caller", "twilio"], ["twilio", "gateway"], ["eleven", "twilio"], ["gateway", "eleven"],
  ["gateway", "bus"], ["gateway", "intake"], ["intake", "bus"],
  ["procurator", "bus"], ["legatus", "bus"], ["legionarius-1", "bus"], ["legionarius-2", "bus"],
  ["censor", "bus"], ["scriba", "bus"], ["quaestor", "bus"],
  ["bus", "db-control"], ["bus", "db-memory"], ["bus", "db-signal"],
  ["censor", "github"], ["procurator", "callback"],
];

const AGENT_TO_NODE: Dict = {
  procurator: "procurator", "procurator-voice": "gateway", "procurator-intake": "intake",
  legatus: "legatus", censor: "censor", scriba: "scriba", quaestor: "quaestor",
};

function center(n: Node): [number, number] { return [n.x + n.w / 2, n.y + (n.h ?? 64) / 2]; }

export function renderFlow(el: HTMLElement) {
  const byId: Record<string, Node> = Object.fromEntries(NODES.map(n => [n.id, n]));
  const lines = EDGES.map(([a, b]) => {
    const [x1, y1] = center(byId[a]); const [x2, y2] = center(byId[b]);
    return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" class="flow-edge" data-edge="${a}-${b}"/>`;
  }).join("");
  const stages = `
    <text x="95"  y="200" class="stage-lbl">1 · COLLECTION</text>
    <text x="325" y="200" class="stage-lbl">2 · INGESTION</text>
    <text x="735" y="90"  class="stage-lbl">3 · AGENT MESH</text>
    <text x="1215" y="90" class="stage-lbl">4 · ATLAS</text>
    <text x="1405" y="200" class="stage-lbl">5 · DELIVERY</text>`;
  el.innerHTML = `
    <div id="flow-wrap">
      <svg id="flow-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet">${lines}${stages}</svg>
      ${NODES.map(n => `
        <div class="flow-node k-${n.kind}" id="fn-${n.id}"
             style="left:${(n.x / W) * 100}%;top:${(n.y / H) * 100}%;width:${(n.w / W) * 100}%">
          <div class="fn-title">${n.title}</div>
          <div class="fn-sub">${(n.sub ?? "").replace(/\n/g, "<br>")}</div>
          <div class="fn-extra" id="fx-${n.id}"></div>
        </div>`).join("")}
      <div id="flow-ticker"></div>
    </div>`;
  refreshFlowCounts();
}

export async function refreshFlowCounts() {
  const run = new URLSearchParams(location.search).get("run") ?? "";
  const d = await fetch(`/api/flow${run ? `?run=${run}` : ""}`).then(r => r.json()).catch(() => null);
  if (!d) return;
  const c = d.counts;
  const set = (id: string, html: string) => { const e = document.getElementById(`fx-${id}`); if (e) e.innerHTML = html; };
  set("db-control", `mandate <b>${c.mandate}</b> · tickets <b>${c.tickets}</b><br>stakeholder msgs <b>${c.stakeholder_msgs}</b>`);
  set("db-memory", `L0 events <b>${c.events}</b> · L1 episodes <b>${c.episodes}</b><br>L2 facts <b>${c.memory}</b> · L3 decisions <b>${c.decisions}</b><br>L4 playbooks <b>${c.playbooks_all}</b>`);
  set("db-signal", `metrics <b>${c.metrics}</b> · verdicts <b>${c.verdicts}</b><br>artifacts <b>${c.artifacts}</b>`);
  set("bus", `run <b>${d.run_id}</b>`);
  set("censor", `gate: <b>${d.pass.passed}/${d.pass.total || "–"}</b>`);
  set("quaestor", `<b>${(d.tokens / 1000).toFixed(1)}k</b> tokens`);
}

let tickerTimer: number | undefined;

export function flowPulse(msg: Dict) {
  const doc = msg.doc ?? {};
  const targets: string[] = [];
  if (msg.type === "event") {
    const n = AGENT_TO_NODE[doc.agent] ?? (String(doc.agent).startsWith("legionarius") ? doc.agent : null);
    if (n) targets.push(n);
    if (String(doc.kind).startsWith("voice")) targets.push("gateway", "twilio");
    if (doc.kind === "run.launched") targets.push("intake");
    if (String(doc.kind).startsWith("verdict")) targets.push("github");
    targets.push("db-memory");
  }
  if (msg.type === "ticket") targets.push("db-control", "bus");
  if (msg.type === "verdict") targets.push("censor", "db-signal");
  if (msg.type === "stakeholder") targets.push("caller", "gateway", "db-control");
  if (msg.type === "agent") targets.push("bus");
  for (const t of targets) {
    const e = document.getElementById(`fn-${t}`);
    if (!e) continue;
    e.classList.remove("pulse"); void e.offsetWidth; e.classList.add("pulse");
  }
  const ticker = document.getElementById("flow-ticker");
  if (ticker && msg.type === "event" && doc.text) {
    ticker.textContent = `${doc.agent}: ${doc.kind} — ${doc.text}`.slice(0, 160);
    clearTimeout(tickerTimer);
    tickerTimer = window.setTimeout(() => (ticker.textContent = ""), 6000);
  }
  refreshFlowCounts();
}
