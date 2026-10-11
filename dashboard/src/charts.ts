// Hand-rolled SVG charts per the dataviz method: thin 2px lines, recessive grid,
// one axis per chart (two measures = two charts), hover crosshair + tooltip,
// text in text tokens — series color only on marks.
import type { Dict } from "./api";

const css = (v: string) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();

export interface Pt { x: number; y: number; label: string }

export function lineChart(el: HTMLElement, pts: Pt[], opts: { color: string; yMax: number; yFmt: (v: number) => string; title: string }) {
  el.innerHTML = `<div class="title">${opts.title}</div>`;
  if (pts.length === 0) { el.insertAdjacentHTML("beforeend", `<div style="color:var(--text-muted)">no data yet</div>`); return; }
  const W = 600, H = 120, PL = 44, PR = 10, PT = 8, PB = 18;
  const x0 = pts[0].x, x1 = pts[pts.length - 1].x || x0 + 1;
  const sx = (x: number) => PL + ((x - x0) / Math.max(x1 - x0, 1)) * (W - PL - PR);
  const sy = (y: number) => PT + (1 - y / opts.yMax) * (H - PT - PB);
  const d = pts.map((p, i) => `${i ? "L" : "M"}${sx(p.x).toFixed(1)},${sy(p.y).toFixed(1)}`).join(" ");
  const gridY = [0, 0.5, 1].map(f => f * opts.yMax);
  const last = pts[pts.length - 1];
  const svg = `
  <svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="${opts.title}">
    ${gridY.map(g => `<line x1="${PL}" y1="${sy(g)}" x2="${W - PR}" y2="${sy(g)}" stroke="${css("--border")}" stroke-width="1"/>
      <text x="${PL - 6}" y="${sy(g) + 4}" text-anchor="end" font-size="10" fill="${css("--text-muted")}">${opts.yFmt(g)}</text>`).join("")}
    <path d="${d}" fill="none" stroke="${opts.color}" stroke-width="2" stroke-linejoin="round"/>
    <circle cx="${sx(last.x)}" cy="${sy(last.y)}" r="4" fill="${opts.color}"/>
    <text x="${Math.min(sx(last.x) + 7, W - 4)}" y="${sy(last.y) - 6}" font-size="11" fill="${css("--text-primary")}">${opts.yFmt(last.y)}</text>
    <line class="xh" y1="${PT}" y2="${H - PB}" stroke="${css("--text-muted")}" stroke-width="1" visibility="hidden"/>
  </svg>`;
  el.insertAdjacentHTML("beforeend", svg);

  // hover layer: crosshair + tooltip on nearest point
  const svgEl = el.querySelector("svg")!;
  const xh = svgEl.querySelector(".xh") as SVGLineElement;
  let tip = document.querySelector(".tooltip") as HTMLElement;
  if (!tip) { tip = document.createElement("div"); tip.className = "tooltip"; document.body.appendChild(tip); }
  svgEl.addEventListener("mousemove", (e: MouseEvent) => {
    const rect = svgEl.getBoundingClientRect();
    const mx = ((e.clientX - rect.left) / rect.width) * W;
    let best = pts[0], bd = Infinity;
    for (const p of pts) { const dd = Math.abs(sx(p.x) - mx); if (dd < bd) { bd = dd; best = p; } }
    xh.setAttribute("x1", String(sx(best.x))); xh.setAttribute("x2", String(sx(best.x)));
    xh.setAttribute("visibility", "visible");
    tip.style.display = "block";
    tip.style.left = `${e.clientX + 12}px`; tip.style.top = `${e.clientY - 10}px`;
    tip.textContent = `${best.label} — ${opts.yFmt(best.y)}`;
  });
  svgEl.addEventListener("mouseleave", () => { xh.setAttribute("visibility", "hidden"); tip.style.display = "none"; });
}

export function renderMetrics(el: HTMLElement, series: Dict[], state: Dict) {
  const passPts: Pt[] = [], tokPts: Pt[] = [];
  for (const m of series) {
    const t = new Date(m.ts).getTime();
    tokPts.push({ x: t, y: m.tokens_cum, label: new Date(m.ts).toLocaleTimeString() });
    if (m.total) passPts.push({ x: t, y: m.passed, label: `${new Date(m.ts).toLocaleTimeString()} · ${m.agent}` });
  }
  const total = state.pass?.total || 25;
  el.innerHTML = `
    <div id="metrics-wrap">
      <div class="tile"><div class="big">${state.pass.passed}/${state.pass.total || "–"}</div><div class="lbl">hidden suite (M1)</div></div>
      <div class="tile"><div class="big">${(state.tokens / 1000).toFixed(1)}k</div><div class="lbl">tokens spent</div></div>
      <div class="tile"><div class="big">${state.tickets.filter((t: Dict) => t.status === "done").length}/${state.tickets.length}</div><div class="lbl">tickets done</div></div>
      <div class="chart-box" id="c-pass"></div>
      <div class="chart-box" id="c-tok"></div>
    </div>`;
  lineChart(el.querySelector("#c-pass")!, passPts, { color: css("--series-1"), yMax: total, yFmt: v => `${Math.round(v)}`, title: "tests passing over time" });
  lineChart(el.querySelector("#c-tok")!, tokPts, { color: css("--series-2"), yMax: Math.max(...tokPts.map(p => p.y), 1), yFmt: v => `${(v / 1000).toFixed(0)}k`, title: "cumulative tokens" });
}
