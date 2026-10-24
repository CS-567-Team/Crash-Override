// WebXR condition. Each section of a trial is a panel on an arc around the participant in
// workflow order (task -> plan -> code before -> code after -> review), with the
// decision panel in front at waist height. Runs the participant's VR trials back to back.
//
// Headset controls
//   Trigger           click a button
//   Grip (hold)       grab the panel you point at; move your hand to move it
//   Thumbstick + grip push the held panel away / pull it closer
//   Left thumbstick   walk
//   Right thumbstick  up/down scrolls the panel you point at, left/right turns
// Laptop preview: drag to look, W A S D to walk, wheel scrolls, click buttons.

import * as THREE from "three";
import { ROLE_COLORS, participantFromUrl, fetchSession, fetchTrial, InteractionLog, submitDecision } from "./common.js";

const PX_PER_M = 1000;
const RADIUS = 2.0;
const PANEL_HEIGHT = 1.4;
const GAP = 0.1;
const DWELL_SECONDS = 0.4;
const WALK_SPEED = 1.5;
const PULL_SPEED = 1.5;
const SNAP_TURN = Math.PI / 6;
const SANS = "system-ui, -apple-system, 'Segoe UI', sans-serif";
const MONO = "ui-monospace, Menlo, Consolas, monospace";
const WIDTHS = { task: 1.4, plan: 1.2, before: 1.6, after: 1.6, review: 1.2 };

const participant = participantFromUrl();
const log = new InteractionLog();
const hint = document.getElementById("hint");

// ---------------------------------------------------------------- panels

class Panel {
  constructor(id, title, widthM, heightM) {
    this.id = id;
    this.title = title;
    this.canvas = document.createElement("canvas");
    this.canvas.width = Math.round(widthM * PX_PER_M);
    this.canvas.height = Math.round(heightM * PX_PER_M);
    this.ctx = this.canvas.getContext("2d");
    this.texture = new THREE.CanvasTexture(this.canvas);
    this.texture.colorSpace = THREE.SRGBColorSpace;
    this.texture.anisotropy = 8;
    this.mesh = new THREE.Mesh(new THREE.PlaneGeometry(widthM, heightM),
                               new THREE.MeshBasicMaterial({ map: this.texture, side: THREE.DoubleSide }));
    this.mesh.userData.panel = this;
    this.buttons = [];
    this.hovered = null;
  }

  buttonAt(uv) {
    const x = uv.x * this.canvas.width;
    const y = (1 - uv.y) * this.canvas.height;
    return this.buttons.find((b) => !b.disabled && !b.hidden && x >= b.x && x <= b.x + b.w && y >= b.y && y <= b.y + b.h) || null;
  }

  setHovered(button) {
    if (button !== this.hovered) {
      this.hovered = button;
      this.draw();
    }
  }

  rememberPlacement() {
    this.home = { position: this.mesh.position.clone(), quaternion: this.mesh.quaternion.clone() };
  }

  resetPlacement() {
    scene.attach(this.mesh);
    this.mesh.position.copy(this.home.position);
    this.mesh.quaternion.copy(this.home.quaternion);
  }

  dispose() {
    this.mesh.removeFromParent();
    this.mesh.geometry.dispose();
    this.mesh.material.dispose();
    this.texture.dispose();
  }

  drawFrame(subtitle = "") {
    const { ctx, canvas } = this;
    const color = ROLE_COLORS[this.id] || "#444";
    ctx.fillStyle = "#fbfbfc";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = color;
    ctx.fillRect(0, 0, canvas.width, 96);
    ctx.fillStyle = "#fff";
    ctx.textBaseline = "middle";
    ctx.font = `600 46px ${SANS}`;
    ctx.fillText(this.title, 40, 50);
    if (subtitle) {
      ctx.font = `30px ${SANS}`;
      ctx.textAlign = "right";
      ctx.fillText(subtitle, canvas.width - 40, 50);
      ctx.textAlign = "left";
    }
    ctx.lineWidth = 6;
    ctx.strokeStyle = color;
    ctx.strokeRect(3, 3, canvas.width - 6, canvas.height - 6);
  }

  drawButton(button) {
    if (button.hidden) return;
    const { ctx } = this;
    const hovered = button === this.hovered;
    ctx.fillStyle = button.disabled ? "#e3e5e9" : button.selected || button.primary ? "#2b5fc0" : hovered ? "#dbe5f8" : "#eef0f3";
    ctx.strokeStyle = hovered || button.selected ? "#163a80" : "#b9bfc9";
    ctx.lineWidth = hovered ? 6 : 3;
    ctx.beginPath();
    ctx.roundRect(button.x, button.y, button.w, button.h, 14);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = (button.selected || button.primary) && !button.disabled ? "#fff" : button.disabled ? "#9aa1ac" : "#1d2330";
    ctx.font = `600 ${button.fontSize || 36}px ${SANS}`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(button.label, button.x + button.w / 2, button.y + button.h / 2 + 2);
    ctx.textAlign = "left";
  }

  finish() {
    this.buttons.forEach((b) => this.drawButton(b));
    this.texture.needsUpdate = true;
  }
}

function wrapProse(ctx, text, maxWidth) {
  const lines = [];
  for (const paragraph of text.split("\n")) {
    const indent = paragraph.match(/^\s*/)[0];
    let line = "";
    for (const word of paragraph.trimStart().split(" ")) {
      const candidate = line ? `${line} ${word}` : indent + word;
      if (ctx.measureText(candidate).width > maxWidth && line) {
        lines.push(line);
        line = indent + word;
      } else {
        line = candidate;
      }
    }
    lines.push(line);
  }
  return lines;
}

function wrapCode(ctx, text, maxWidth) {
  const perLine = Math.max(10, Math.floor(maxWidth / ctx.measureText("M").width));
  const lines = [];
  for (const line of text.split("\n")) {
    if (line.length <= perLine) { lines.push(line); continue; }
    for (let i = 0; i < line.length; i += perLine) lines.push((i ? "  " : "") + line.slice(i, i + perLine));
  }
  return lines;
}

const STYLES = {
  prose: { font: `36px ${SANS}`, color: "#1d2330", height: 48 },
  heading: { font: `700 34px ${SANS}`, color: "#2b3a55", height: 50 },
  file: { font: `600 30px ${MONO}`, color: "#5d6675", height: 46 },
  code: { font: `30px ${MONO}`, color: "#1d2330", height: 40 },
  // Changed lines: tinted red-ish in the old code, green-ish in the new code.
  before: { font: `30px ${MONO}`, color: "#1d2330", height: 40, bg: "#fde2e1" },
  after: { font: `30px ${MONO}`, color: "#1d2330", height: 40, bg: "#dcf3e2" },
};
const GUTTER = 5;  // characters reserved for line numbers

class SectionPanel extends Panel {
  constructor(section) {
    super(section.id, section.title, WIDTHS[section.id] || 1.3, PANEL_HEIGHT);
    this.offset = 0;
    this.lines = this.layout(section);
    const { width, height } = this.canvas;
    this.bodyTop = 125;
    this.bodyBottom = height - 115;
    this.up = { label: "▲ Up", x: width - 380, y: height - 100, w: 160, h: 80, action: () => this.scroll(-1) };
    this.down = { label: "▼ Down", x: width - 200, y: height - 100, w: 160, h: 80, action: () => this.scroll(1) };
    this.buttons = [this.up, this.down];
    this.draw();
  }

  layout(section) {
    const { ctx } = this;
    const maxWidth = this.canvas.width - 80;
    const out = [];
    const prose = (text) => {
      ctx.font = STYLES.prose.font;
      for (const line of wrapProse(ctx, text, maxWidth)) {
        // Lines written in capitals (e.g. "EDGE CASES TO HANDLE") are headings.
        const heading = /^[A-Z][A-Z ]{3,}(:|$)/.test(line);
        out.push({ style: heading ? "heading" : "prose", text: line });
      }
    };
    const code = (file, side) => {
      ctx.font = STYLES.code.font;
      this.charWidth = ctx.measureText("M").width;
      const changed = new Set(file.highlight);
      out.push({ style: "file", text: file.name });
      file.source.replace(/\n$/, "").split("\n").forEach((raw, i) => {
        const style = changed.has(i + 1) ? side : "code";
        wrapCode(ctx, raw, maxWidth - GUTTER * this.charWidth).forEach((text, part) =>
          out.push({ style, text, number: part ? "" : String(i + 1) }));
      });
    };

    if (section.kind === "code") {
      prose(section.note);
      out.push({ style: "prose", text: "" });
      section.files.forEach((file) => code(file, section.side));
    } else {
      prose(section.text);
    }
    return out;
  }

  visibleFrom(start) {
    let used = 0, end = start;
    while (end < this.lines.length && used + STYLES[this.lines[end].style].height <= this.bodyBottom - this.bodyTop) {
      used += STYLES[this.lines[end].style].height;
      end++;
    }
    return end;
  }

  scroll(direction) {
    if (direction > 0 && this.visibleFrom(this.offset) >= this.lines.length) return;
    const next = Math.max(0, Math.min(this.offset + direction * 6, this.lines.length - 1));
    if (next === this.offset) return;
    this.offset = next;
    log.add("scroll", `${this.id}:${this.offset}`);
    this.draw();
  }

  draw() {
    const { ctx, canvas } = this;
    this.drawFrame();
    const end = this.visibleFrom(this.offset);
    let y = this.bodyTop;
    ctx.textBaseline = "top";
    for (const line of this.lines.slice(this.offset, end)) {
      const style = STYLES[line.style];
      if (style.bg) {
        ctx.fillStyle = style.bg;
        ctx.fillRect(20, y - 4, canvas.width - 40, style.height);
      }
      ctx.font = style.font;
      if (line.number !== undefined) {
        ctx.fillStyle = "#9aa1ac";
        ctx.fillText(line.number.padStart(GUTTER - 2), 40, y);
        ctx.fillStyle = style.color;
        ctx.fillText(line.text, 40 + GUTTER * this.charWidth, y);
      } else {
        ctx.fillStyle = style.color;
        ctx.fillText(line.text, 40, y);
      }
      y += style.height;
    }
    this.up.disabled = this.offset === 0;
    this.down.disabled = end >= this.lines.length;
    ctx.fillStyle = "#5d6675";
    ctx.font = `30px ${SANS}`;
    ctx.textBaseline = "middle";
    const more = end < this.lines.length ? "  (more below)" : "";
    ctx.fillText(`Lines ${this.offset + 1}–${end} of ${this.lines.length}${more}`, 40, canvas.height - 60);
    this.finish();
  }
}

// Decision panel: ratings + accept/reject while a trial is open, then what happens next.
class DecisionPanel extends Panel {
  constructor() {
    super("decision", "Your decision", 1.4, 1.0);
    this.reset = { label: "Reset layout", x: 1000, y: 870, w: 360, h: 90, fontSize: 32, action: () => resetLayout() };
    this.message("Loading…");
  }

  message(text, next = null) {
    this.mode = "message";
    this.title = "Code review study";
    this.text = text;
    this.nextButton = next && { label: next.label, x: 40, y: 870, w: 420, h: 90, primary: true, action: next.action };
    this.buttons = [this.nextButton, this.reset].filter(Boolean);
    this.draw();
  }

  startTrial(trial, position) {
    this.mode = "trial";
    this.title = "Your decision";
    this.trial = trial;
    this.position = position;
    this.responses = {};
    this.decision = null;
    this.status = "";
    this.sending = false;
    const size = 104, gap = 14;
    this.rows = trial.questions.map((q, row) => {
      const y = 290 + row * 215;
      const buttons = Array.from({ length: 7 }, (_, i) => ({
        label: String(i + 1), x: 40 + i * (size + gap), y, w: size, h: 90, value: i + 1,
        action: () => { this.responses[q.id] = i + 1; log.add("rate", `${q.id}=${i + 1}`); this.draw(); },
      }));
      return { q, y, buttons };
    });
    const choice = (decision, label, x) => ({
      label, x, y: 700, w: 420, h: 110, decision,
      action: () => { this.decision = decision; log.add("choose", decision); this.draw(); },
    });
    this.accept = choice("accept", "Accept change", 40);
    this.reject = choice("reject", "Reject change", 480);
    this.submit = { label: "Submit", x: 940, y: 700, w: 420, h: 110, action: () => this.send() };
    this.buttons = [...this.rows.flatMap((r) => r.buttons), this.accept, this.reject, this.submit, this.reset];
    this.draw();
  }

  ready() {
    return this.decision && this.rows.every(({ q }) => this.responses[q.id]);
  }

  async send() {
    if (!this.ready() || this.sending) return;
    this.sending = true;
    this.status = "Saving…";
    this.draw();
    try {
      await submitDecision({ cacheId: this.trial.cache_id, participant, decision: this.decision,
                             responses: this.responses, log });
      await showNext();
    } catch (error) {
      this.sending = false;
      this.status = error.message;
      this.draw();
    }
  }

  draw() {
    const { ctx, canvas } = this;
    if (this.mode === "message") {
      this.drawFrame();
      ctx.fillStyle = "#1d2330";
      ctx.font = `36px ${SANS}`;
      ctx.textBaseline = "top";
      wrapProse(ctx, this.text, canvas.width - 80).forEach((line, i) => ctx.fillText(line, 40, 130 + i * 48));
      this.finish();
      return;
    }
    this.drawFrame(`Trial ${this.position} of 6`);
    ctx.textBaseline = "top";
    ctx.fillStyle = "#3a4558";
    ctx.font = `30px ${SANS}`;
    wrapProse(ctx, this.trial.decision_help, canvas.width - 80).forEach((line, i) => ctx.fillText(line, 40, 112 + i * 38));
    for (const { q, y, buttons } of this.rows) {
      ctx.fillStyle = "#1d2330";
      ctx.font = `600 36px ${SANS}`;
      ctx.fillText(q.text, 40, y - 52);
      ctx.fillStyle = "#5d6675";
      ctx.font = `28px ${SANS}`;
      ctx.fillText(`1 = ${q.low}      7 = ${q.high}`, 40, y + 98);
      buttons.forEach((b) => { b.selected = this.responses[q.id] === b.value; b.disabled = this.sending; });
    }
    this.accept.selected = this.decision === "accept";
    this.reject.selected = this.decision === "reject";
    this.accept.disabled = this.reject.disabled = this.sending;
    this.submit.disabled = this.sending || !this.ready();
    this.submit.primary = !this.submit.disabled;
    ctx.fillStyle = "#1d2330";
    ctx.font = `600 32px ${SANS}`;
    ctx.fillText(this.status || (this.ready() ? "" : "Answer both questions and choose Accept or Reject."), 40, 830);
    this.finish();
  }
}

// ---------------------------------------------------------------- scene

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(window.devicePixelRatio);
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.xr.enabled = true;
// "local": the origin is the participant's head at session start, so the layout works
// seated or standing. y = 0 is eye height.
renderer.xr.setReferenceSpaceType("local");
document.body.append(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color("#1b1f27");
const floor = new THREE.GridHelper(40, 80, "#3a4150", "#2a303b");
floor.position.y = -1.3;
scene.add(floor);

// Moving the rig moves the participant (camera and controllers together).
const rig = new THREE.Group();
scene.add(rig);
const camera = new THREE.PerspectiveCamera(70, window.innerWidth / window.innerHeight, 0.05, 60);
rig.add(camera);

const decisionPanel = new DecisionPanel();
let sectionPanels = [];
const allPanels = () => [...sectionPanels, decisionPanel];

function placeDecisionPanel(inFront) {
  decisionPanel.mesh.position.set(0, inFront ? 0 : -0.8, inFront ? -1.6 : -1.25);
  decisionPanel.mesh.lookAt(0, 0, 0);
  decisionPanel.rememberPlacement();
}

function placeOnArc(panels) {
  const widths = panels.map((p) => p.canvas.width / PX_PER_M);
  const total = (widths.reduce((a, b) => a + b, 0) + GAP * (widths.length - 1)) / RADIUS;
  let angle = -total / 2;
  panels.forEach((panel, i) => {
    const half = widths[i] / 2 / RADIUS;
    angle += half;
    panel.mesh.position.set(RADIUS * Math.sin(angle), 0.2, -RADIUS * Math.cos(angle));
    panel.mesh.lookAt(0, 0.2, 0);
    panel.rememberPlacement();
    angle += half + GAP / RADIUS;
  });
}

function resetLayout() {
  log.add("reset_layout", "");
  allPanels().forEach((panel) => panel.resetPlacement());
  controllers.forEach((c) => { c.userData.held = null; });
  rig.position.set(0, 0, 0);
  rig.rotation.set(0, 0, 0);
}

scene.add(decisionPanel.mesh);
placeDecisionPanel(true);

// ---------------------------------------------------------------- session flow

const VR_INTRO =
  "Welcome to the VR part. Each trial puts panels around you: start with 'Your task' on the far left, " +
  "then look right through each panel. Make your decision on the panel in front of you.\n\n" +
  "Trigger: click. Grip (hold): grab and move a panel; while holding, the thumbstick pushes it away " +
  "or pulls it closer. Left thumbstick: walk. Right thumbstick: scroll a panel (up/down) or turn (left/right).\n\n";

// While the participant is on the laptop, check every few seconds so the headset is
// ready by itself when it is their turn in VR.
let waiting = null;
function waitForVrTurn() {
  clearTimeout(waiting);
  waiting = setTimeout(async () => {
    try {
      const { next } = await fetchSession(participant);
      if (next?.display === "xr") return showNext();
    } catch {
      // Server unreachable for a moment; keep checking.
    }
    waitForVrTurn();
  }, 3000);
}

async function showNext() {
  clearTimeout(waiting);
  const session = await fetchSession(participant);
  const next = session.next;
  const vrStarted = session.trials.some((t) => t.display === "xr" && t.done);
  sectionPanels.forEach((panel) => panel.dispose());
  sectionPanels = [];
  resetLayout();
  placeDecisionPanel(true);

  if (!next) {
    decisionPanel.message("All trials are complete. Thank you for taking part! You can remove the headset.");
  } else if (!next.cache_id) {
    decisionPanel.message(`Trial ${next.position} has no generated agent output yet (${next.task}, ${next.architecture}). Please tell the researcher.`);
  } else if (next.display !== "xr") {
    decisionPanel.message(vrStarted
      ? "The VR part is complete. Please remove the headset and continue on the laptop."
      : `Hello, ${participant}. The VR part starts after the laptop trials. This screen will update by itself when it is time.`);
    waitForVrTurn();
  } else {
    decisionPanel.message(`${vrStarted ? "" : VR_INTRO}Trial ${next.position} of 6 is ready.`,
      { label: "Start trial", action: () => startTrial(next) });
  }
}

async function startTrial(next) {
  const trial = await fetchTrial(next.cache_id);
  sectionPanels = trial.sections.map((section) => new SectionPanel(section));
  placeOnArc(sectionPanels);
  sectionPanels.forEach((panel) => scene.add(panel.mesh));
  placeDecisionPanel(false);
  decisionPanel.startTrial(trial, next.position);
  log.restart();
  gaze.logged = null;
  log.add("trial_start", trial.cache_id);
}

// ---------------------------------------------------------------- pointing

const raycaster = new THREE.Raycaster();

function hitFromRay(origin, direction) {
  raycaster.set(origin, direction);
  const hit = raycaster.intersectObjects(allPanels().map((p) => p.mesh), false)[0];
  if (!hit) return null;
  const panel = hit.object.userData.panel;
  return { panel, button: panel.buttonAt(hit.uv), distance: hit.distance };
}

function activate(hit) {
  if (hit?.button) {
    log.add("click", `${hit.panel.id}:${hit.button.label}`);
    hit.button.action();
  }
}

function applyHover(hits) {
  const hovered = new Map(hits.filter(Boolean).map((hit) => [hit.panel, hit.button]));
  allPanels().forEach((panel) => panel.setHovered(hovered.get(panel) || null));
}

// Laptop preview: drag to look, WASD to walk, click buttons, wheel scrolls.
const look = { yaw: 0, pitch: 0, dragging: false, moved: 0, x: 0, y: 0 };
const pointer = new THREE.Vector2();
const keys = new Set();

function pointerHit(event) {
  pointer.set((event.clientX / window.innerWidth) * 2 - 1, -(event.clientY / window.innerHeight) * 2 + 1);
  raycaster.setFromCamera(pointer, camera);
  return hitFromRay(raycaster.ray.origin.clone(), raycaster.ray.direction.clone());
}

renderer.domElement.addEventListener("pointerdown", (event) => {
  Object.assign(look, { dragging: true, moved: 0, x: event.clientX, y: event.clientY });
});
window.addEventListener("pointermove", (event) => {
  if (renderer.xr.isPresenting) return;
  if (look.dragging) {
    const dx = event.clientX - look.x, dy = event.clientY - look.y;
    look.moved += Math.abs(dx) + Math.abs(dy);
    look.yaw += dx * 0.004;
    look.pitch = Math.max(-1.2, Math.min(1.2, look.pitch + dy * 0.004));
    look.x = event.clientX;
    look.y = event.clientY;
    camera.rotation.set(look.pitch, look.yaw, 0, "YXZ");
  }
  applyHover([pointerHit(event)]);
});
window.addEventListener("pointerup", (event) => {
  if (look.dragging && look.moved < 6) activate(pointerHit(event));
  look.dragging = false;
});
renderer.domElement.addEventListener("wheel", (event) => {
  pointerHit(event)?.panel.scroll?.(Math.sign(event.deltaY));
  event.preventDefault();
}, { passive: false });
window.addEventListener("keydown", (event) => keys.add(event.key.toLowerCase()));
window.addEventListener("keyup", (event) => keys.delete(event.key.toLowerCase()));

// Headset: a ray from each controller.
const controllers = [0, 1].map((index) => {
  const controller = renderer.xr.getController(index);
  const ray = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, 0, -1)]),
    new THREE.LineBasicMaterial({ color: "#8fb3ff" }));
  ray.scale.z = 5;
  controller.add(ray);
  controller.userData = { ray, held: null, inputSource: null, turned: false, lastScroll: 0 };
  controller.addEventListener("connected", (event) => { controller.userData.inputSource = event.data; });
  controller.addEventListener("disconnected", () => { controller.userData.inputSource = null; });
  controller.addEventListener("selectstart", () => activate(controllerHit(controller)));
  controller.addEventListener("squeezestart", () => {
    const hit = controllerHit(controller);
    if (!hit) return;
    controller.userData.held = hit.panel;
    controller.attach(hit.panel.mesh);  // keeps its world position; now follows the hand
    log.add("grab", hit.panel.id);
  });
  controller.addEventListener("squeezeend", () => {
    const panel = controller.userData.held;
    if (!panel) return;
    scene.attach(panel.mesh);
    controller.userData.held = null;
    log.add("release", panel.id);
  });
  rig.add(controller);
  return controller;
});

const rotation = new THREE.Matrix4();
function controllerHit(controller) {
  rotation.identity().extractRotation(controller.matrixWorld);
  const origin = new THREE.Vector3().setFromMatrixPosition(controller.matrixWorld);
  const direction = new THREE.Vector3(0, 0, -1).applyMatrix4(rotation);
  return hitFromRay(origin, direction);
}

// ---------------------------------------------------------------- movement

const head = new THREE.Vector3();
const forward = new THREE.Vector3();
const right = new THREE.Vector3();
const UP = new THREE.Vector3(0, 1, 0);

function walk(x, z, dt) {
  const view = renderer.xr.isPresenting ? renderer.xr.getCamera() : camera;
  view.getWorldDirection(forward);
  forward.y = 0;
  if (forward.lengthSq() < 1e-6) return;
  forward.normalize();
  right.crossVectors(forward, UP);
  rig.position.addScaledVector(forward, -z * WALK_SPEED * dt).addScaledVector(right, x * WALK_SPEED * dt);
}

function snapTurn(direction) {
  // Rotate around the participant's head so they turn in place.
  renderer.xr.getCamera().getWorldPosition(head);
  rig.position.sub(head).applyAxisAngle(UP, -direction * SNAP_TURN).add(head);
  rig.rotateY(-direction * SNAP_TURN);
}

function updateControllers(time, dt) {
  const hits = [];
  for (const controller of controllers) {
    const { held, inputSource } = controller.userData;
    const axes = inputSource?.gamepad?.axes || [];
    const x = Math.abs(axes[2] || 0) > 0.2 ? axes[2] : 0;
    const y = Math.abs(axes[3] || 0) > 0.2 ? axes[3] : 0;

    if (held) {
      // Push away / pull closer along the pointing ray, between 0.3 m and 8 m.
      const mesh = held.mesh;
      mesh.position.z = Math.max(-8, Math.min(-0.3, mesh.position.z + y * PULL_SPEED * dt));
      controller.userData.ray.scale.z = -mesh.position.z;
      continue;
    }

    const hit = controllerHit(controller);
    hits.push(hit);
    controller.userData.ray.scale.z = hit ? hit.distance : 5;

    if (inputSource?.handedness === "left") {
      walk(x, y, dt);
    } else {
      if (hit?.panel.scroll && Math.abs(y) > 0.6 && time - controller.userData.lastScroll > 150) {
        hit.panel.scroll(Math.sign(y));
        controller.userData.lastScroll = time;
      }
      if (Math.abs(x) > 0.7 && !controller.userData.turned) {
        snapTurn(Math.sign(x));
        controller.userData.turned = true;
      } else if (Math.abs(x) < 0.3) {
        controller.userData.turned = false;
      }
    }
  }
  applyHover(hits);
}

function updateKeyboard(dt) {
  const x = (keys.has("d") || keys.has("arrowright") ? 1 : 0) - (keys.has("a") || keys.has("arrowleft") ? 1 : 0);
  const z = (keys.has("s") || keys.has("arrowdown") ? 1 : 0) - (keys.has("w") || keys.has("arrowup") ? 1 : 0);
  if (x || z) walk(x, z, dt);
}

// Gaze: log which panel is in the center of view once it has been held for a moment.
const gaze = { candidate: null, since: 0, logged: null };
const headDirection = new THREE.Vector3();

function updateGaze(time) {
  const view = renderer.xr.isPresenting ? renderer.xr.getCamera() : camera;
  view.getWorldPosition(head);
  view.getWorldDirection(headDirection);
  const id = hitFromRay(head, headDirection)?.panel.id || null;
  if (id !== gaze.candidate) {
    gaze.candidate = id;
    gaze.since = time;
  } else if (id && id !== gaze.logged && time - gaze.since > DWELL_SECONDS * 1000) {
    gaze.logged = id;
    log.add("view", id);
  }
}

window.addEventListener("resize", () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

// ---------------------------------------------------------------- start

// A large Enter VR button, since this is the participant's first step in the headset.
const enterButton = document.getElementById("enter");

async function setUpEnterButton() {
  const supported = navigator.xr && await navigator.xr.isSessionSupported("immersive-vr").catch(() => false);
  if (!supported) {
    enterButton.disabled = true;
    enterButton.textContent = window.isSecureContext ? "VR not available here (preview only)" : "VR needs https:// or localhost";
    return;
  }
  enterButton.onclick = async () => {
    try {
      const session = await navigator.xr.requestSession("immersive-vr", { optionalFeatures: ["local-floor", "bounded-floor"] });
      await renderer.xr.setSession(session);
    } catch (error) {
      hint.textContent = `Could not enter VR: ${error.message}`;
    }
  };
}

renderer.xr.addEventListener("sessionstart", () => { enterButton.hidden = true; });
renderer.xr.addEventListener("sessionend", () => { enterButton.hidden = false; });
setUpEnterButton();

if (!participant) {
  decisionPanel.message("No participant ID. Open this page from the VR start page.");
} else {
  hint.textContent = `Participant ${participant}. Press Enter VR to begin. ` +
                     "(Laptop preview: drag to look, W A S D to walk, click buttons, scroll wheel over a panel.)";
  showNext().catch((error) => decisionPanel.message(error.message));
}

let last = 0;
renderer.setAnimationLoop((time) => {
  const dt = Math.min(0.1, (time - last) / 1000);
  last = time;
  if (renderer.xr.isPresenting) updateControllers(time, dt);
  else updateKeyboard(dt);
  updateGaze(time);
  renderer.render(scene, camera);
});
