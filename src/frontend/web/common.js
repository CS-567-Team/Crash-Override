// Helpers for the headset view. Trial content (sections, questions) comes from the server,
// built by the same Python code the Streamlit 2D app uses.

export const ROLE_COLORS = {
  task: "#4a5a70",
  original: "#5b6b7f",
  plan: "#7a4fd1",
  diff: "#1f7a5a",
  review: "#c0612b",
  decision: "#2b5fc0",
};

export function participantFromUrl() {
  return new URLSearchParams(location.search).get("participant") || "";
}

async function getJson(url) {
  const response = await fetch(url);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `Request failed: ${url}`);
  return data;
}

export const fetchSession = (participant) => getJson(`/api/session/${encodeURIComponent(participant)}`);
export const fetchTrial = (cacheId) => getJson(`/api/trials/${encodeURIComponent(cacheId)}`);

// Timestamped interaction events, e.g. when each section was first looked at.
export class InteractionLog {
  constructor() {
    this.start = performance.now();
    this.events = [];
  }

  restart() {
    this.start = performance.now();
    this.events = [];
  }

  elapsed() {
    return (performance.now() - this.start) / 1000;
  }

  add(type, target) {
    this.events.push({ t: Number(this.elapsed().toFixed(3)), type, target });
  }
}

export async function submitDecision({ cacheId, participant, decision, responses, log }) {
  const response = await fetch("/api/decisions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      cache_id: cacheId, participant_id: participant, display: "xr", decision, responses,
      decision_seconds: log.elapsed(), interactions: log.events,
    }),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Could not save decision");
  return data;
}
