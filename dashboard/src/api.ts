export type Dict = Record<string, any>;

const run = new URLSearchParams(location.search).get("run") ?? "";
const q = run ? `?run=${encodeURIComponent(run)}` : "";

export const getState = () => fetch(`/api/state${q}`).then(r => r.json());
export const getTicket = (id: string) => fetch(`/api/ticket/${id}`).then(r => r.json());
export const getMemory = () => fetch(`/api/memory`).then(r => r.json());
export const getEvents = () => fetch(`/api/events${q}`).then(r => r.json());
export const getSeries = () => fetch(`/api/metrics/series${q}`).then(r => r.json());
export const getProvenance = (id: string) => fetch(`/api/provenance/${id}`).then(r => r.json());

export function subscribe(onMsg: (m: Dict) => void, onLive: (ok: boolean) => void) {
  const es = new EventSource(`/api/stream${q}`);
  es.onopen = () => onLive(true);
  es.onerror = () => onLive(false);
  es.onmessage = e => { try { onMsg(JSON.parse(e.data)); } catch {} };
}
