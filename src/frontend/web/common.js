// Shared by the 2D and XR views so both display conditions present identical content.
// Only presentation differs: 2D uses tabs, XR uses one spatial panel per section.

export const QUESTIONS = [
  { id: "trust", text: "I trust that this change is correct.", low: "Strongly disagree", high: "Strongly agree" },
  { id: "confidence", text: "I am confident in my decision.", low: "Not at all", high: "Completely" },
];

export const ROLE_COLORS = {
  task: "#5b6b7f",
  plan: "#7a4fd1",
  diff: "#1f7a5a",
  review: "#c0612b",
  decision: "#2b5fc0",
};

export function params() {
  const query = new URLSearchParams(location.search);
  return { trial: query.get("trial"), participant: query.get("participant") || "" };
}

export async function fetchTrial(cacheId) {
  const response = await fetch(`/api/trials/${encodeURIComponent(cacheId)}`);
  if (!response.ok) throw new Error(`Could not load trial ${cacheId}`);
  return response.json();
}

function bullets(items) {
  return items.length ? items.map((item) => `• ${item}`).join("\n") : "(none)";
}

// Turn the participant payload into ordered sections, following the workflow order.
export function buildSections(payload) {
  const byRole = Object.fromEntries(payload.agents.map((agent) => [agent.role, agent.data]));
  const sections = [{
    id: "task", title: "Task", kind: "text",
    text: `${payload.task.title}\n\n${payload.task.prompt}`,
  }];

  if (byRole.planner) {
    const plan = byRole.planner;
    sections.push({
      id: "plan", title: "Planner: Implementation Plan", kind: "text",
      text: `${plan.summary}\n\nSteps\n${plan.steps.map((s, i) => `${i + 1}. ${s}`).join("\n")}` +
            `\n\nEdge cases\n${bullets(plan.edge_cases)}`,
    });
  }

  sections.push({
    id: "diff", title: "Programmer: Code Changes", kind: "diff",
    summary: byRole.programmer ? byRole.programmer.summary : "",
    text: payload.diff || "(no changes)",
  });

  if (byRole.reviewer) {
    const review = byRole.reviewer;
    const verdict = review.verdict === "approve" ? "APPROVE" : "REQUEST CHANGES";
    sections.push({
      id: "review", title: "Reviewer: Feedback", kind: "text", verdict: review.verdict,
      text: `Verdict: ${verdict}\n\n${review.summary}\n\nIssues\n${bullets(review.issues)}` +
            `\n\nLimitations\n${bullets(review.limitations)}`,
    });
  }

  return sections;
}

// Timestamped interaction events, e.g. when each section was first looked at.
export class InteractionLog {
  constructor() {
    this.start = performance.now();
    this.events = [];
  }

  restart() {
    this.start = performance.now();
  }

  elapsed() {
    return (performance.now() - this.start) / 1000;
  }

  add(type, target) {
    this.events.push({ t: Number(this.elapsed().toFixed(3)), type, target });
  }
}

export async function submitDecision({ cacheId, participant, display, decision, responses, log }) {
  const response = await fetch("/api/decisions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      cache_id: cacheId, participant_id: participant, display, decision, responses,
      decision_seconds: log.elapsed(), interactions: log.events,
    }),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Could not save decision");
  return data;
}
