// WebXR condition: each workflow section is a panel placed on an arc around the
// participant in workflow order (task -> plan -> code -> review), with the decision
// panel in front at waist height. Works on a laptop (drag to look, click, scroll wheel)
// and on a Meta Quest (controller ray + trigger, thumbstick to scroll).

import * as THREE from "three";
import { VRButton } from "./vendor/VRButton.js";
import { QUESTIONS, ROLE_COLORS, params, fetchTrial, buildSections, InteractionLog, submitDecision } from "./common.js";

const PX_PER_M = 1000;
const RADIUS = 2.0;
const PANEL_HEIGHT = 1.3;
const GAP = 0.12;
const DWELL_SECONDS = 0.4;
const SANS = "system-ui, -apple-system, 'Segoe UI', sans-serif";
const MONO = "ui-monospace, Menlo, Consolas, monospace";

const { trial, participant } = params();
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
                               new THREE.MeshBasicMaterial({ map: this.texture }));
    this.mesh.userData.panel = this;
    this.buttons = [];
    this.hovered = null;
  }

  // Canvas coordinates of a ray hit, from the mesh UV.
  buttonAt(uv) {
    const x = uv.x * this.canvas.width;
    const y = (1 - uv.y) * this.canvas.height;
    return this.buttons.find((b) => !b.disabled && x >= b.x && x <= b.x + b.w && y >= b.y && y <= b.y + b.h) || null;
  }

  setHovered(button) {
    if (button !== this.hovered) {
      this.hovered = button;
      this.draw();
    }
  }

  drawFrame() {
    const { ctx, canvas } = this;
    ctx.fillStyle = "#fbfbfc";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = ROLE_COLORS[this.id] || "#444";
    ctx.fillRect(0, 0, canvas.width, 90);
    ctx.fillStyle = "#fff";
    ctx.font = `600 44px ${SANS}`;
    ctx.textBaseline = "middle";
    ctx.fillText(this.title, 40, 46);
    ctx.lineWidth = 6;
    ctx.strokeStyle = ROLE_COLORS[this.id] || "#444";
    ctx.strokeRect(3, 3, canvas.width - 6, canvas.height - 6);
  }

  drawButton(button) {
    const { ctx } = this;
    const active = button.selected || button === this.hovered;
    ctx.fillStyle = button.disabled ? "#e3e5e9" : button.selected ? "#2b5fc0" : button === this.hovered ? "#dbe5f8" : "#eef0f3";
    ctx.strokeStyle = active ? "#2b5fc0" : "#b9bfc9";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.roundRect(button.x, button.y, button.w, button.h, 12);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = button.selected ? "#fff" : button.disabled ? "#9aa1ac" : "#1d2330";
    ctx.font = `600 ${button.fontSize || 34}px ${SANS}`;
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
    let line = "";
    for (const word of paragraph.split(" ")) {
      const candidate = line ? `${line} ${word}` : word;
      if (ctx.measureText(candidate).width > maxWidth && line) {
        lines.push(line);
        line = word;
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
  prose: { font: `34px ${SANS}`, color: "#1d2330", height: 46 },
  heading: { font: `700 34px ${SANS}`, color: "#1d2330", height: 46 },
  code: { font: `28px ${MONO}`, color: "#1d2330", height: 38 },
  add: { font: `28px ${MONO}`, color: "#1b6b3a", height: 38, bg: "#e6f4ea" },
  del: { font: `28px ${MONO}`, color: "#a12c2c", height: 38, bg: "#fbe9e9" },
  hunk: { font: `28px ${MONO}`, color: "#2b5fc0", height: 38 },
};

class SectionPanel extends Panel {
  constructor(section, widthM) {
    super(section.id, section.title, widthM, PANEL_HEIGHT);
    this.offset = 0;
    this.lines = this.layout(section);
    const { width, height } = this.canvas;
    this.bodyTop = 120;
    this.bodyBottom = height - 110;
    this.up = { label: "▲ Up", x: width - 360, y: height - 95, w: 150, h: 75, action: () => this.scroll(-1) };
    this.down = { label: "▼ Down", x: width - 190, y: height - 95, w: 150, h: 75, action: () => this.scroll(1) };
    this.buttons = [this.up, this.down];
    this.draw();
  }

  layout(section) {
    const { ctx } = this;
    const maxWidth = this.canvas.width - 80;
    const out = [];
    const add = (style, text) => out.push({ style, text });
    const prose = (text) => {
      ctx.font = STYLES.prose.font;
      for (const line of wrapProse(ctx, text, maxWidth)) {
        add(/^(Steps|Edge cases|Issues|Limitations)$/.test(line) || line.startsWith("Verdict:") ? "heading" : "prose", line);
      }
    };

    if (section.kind === "diff") {
      if (section.summary) { prose(section.summary); add("prose", ""); }
      ctx.font = STYLES.code.font;
      for (const raw of section.text.split("\n")) {
        const style = raw.startsWith("@@") ? "hunk"
          : raw.startsWith("+") && !raw.startsWith("+++") ? "add"
          : raw.startsWith("-") && !raw.startsWith("---") ? "del" : "code";
        wrapCode(ctx, raw, maxWidth).forEach((line) => add(style, line));
      }
    } else {
      prose(section.text);
    }
    return out;
  }

  // Lines that fit from a given start index.
  visibleFrom(start) {
    let used = 0, end = start;
    while (end < this.lines.length && used + STYLES[this.lines[end].style].height <= this.bodyBottom - this.bodyTop) {
      used += STYLES[this.lines[end].style].height;
      end++;
    }
    return end;
  }

  scroll(direction) {
    const step = 6;
    const next = Math.max(0, Math.min(this.offset + direction * step, this.lines.length - 1));
    if (next === this.offset || (direction > 0 && this.visibleFrom(this.offset) >= this.lines.length)) return;
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
      ctx.fillStyle = style.color;
      ctx.fillText(line.text, 40, y);
      y += style.height;
    }
    this.up.disabled = this.offset === 0;
    this.down.disabled = end >= this.lines.length;
    ctx.fillStyle = "#5d6675";
    ctx.font = `28px ${SANS}`;
    ctx.textBaseline = "middle";
    ctx.fillText(this.lines.length ? `Lines ${this.offset + 1}–${end} of ${this.lines.length}` : "", 40, canvas.height - 57);
    this.finish();
  }
}

class DecisionPanel extends Panel {
  constructor() {
    super("decision", "Your decision", 1.3, 0.95);
    this.responses = {};
    this.decision = null;
    this.status = "";
    this.done = false;
    this.layout();
    this.draw();
  }

  layout() {
    const size = 104, gap = 14, left = 40;
    this.rows = QUESTIONS.map((q, row) => {
      const y = 175 + row * 230;
      const buttons = Array.from({ length: 7 }, (_, i) => ({
        label: String(i + 1), x: left + i * (size + gap), y, w: size, h: 90, value: i + 1,
        action: () => {
          this.responses[q.id] = i + 1;
          log.add("rate", `${q.id}=${i + 1}`);
          this.draw();
        },
      }));
      return { q, y, buttons };
    });
    const choice = (decision, label, x) => ({
      label, x, y: 650, w: 380, h: 100, decision,
      action: () => { this.decision = decision; log.add("choose", decision); this.draw(); },
    });
    this.accept = choice("accept", "Accept change", 40);
    this.reject = choice("reject", "Reject change", 440);
    this.submit = { label: "Submit", x: 880, y: 650, w: 380, h: 100, action: () => this.send() };
    this.buttons = [...this.rows.flatMap((r) => r.buttons), this.accept, this.reject, this.submit];
  }

  ready() {
    return this.decision && QUESTIONS.every((q) => this.responses[q.id]);
  }

  async send() {
    if (!this.ready() || this.done) return;
    this.done = true;
    this.status = "Saving…";
    this.draw();
    try {
      await submitDecision({ cacheId: trial, participant, display: "xr", decision: this.decision,
                             responses: this.responses, log });
      this.status = "Decision recorded. You can remove the headset.";
    } catch (error) {
      this.done = false;
      this.status = error.message;
    }
    this.draw();
  }

  draw() {
    const { ctx } = this;
    this.drawFrame();
    ctx.textBaseline = "top";
    for (const { q, y, buttons } of this.rows) {
      ctx.fillStyle = "#1d2330";
      ctx.font = `600 34px ${SANS}`;
      ctx.fillText(q.text, 40, y - 60);
      ctx.fillStyle = "#5d6675";
      ctx.font = `26px ${SANS}`;
      ctx.fillText(`1 = ${q.low}      7 = ${q.high}`, 40, y + 100);
      buttons.forEach((b) => { b.selected = this.responses[q.id] === b.value; b.disabled = this.done; });
    }
    this.accept.selected = this.decision === "accept";
    this.reject.selected = this.decision === "reject";
    this.accept.disabled = this.reject.disabled = this.done;
    this.submit.disabled = this.done || !this.ready();
    ctx.fillStyle = "#1d2330";
    ctx.font = `600 32px ${SANS}`;
    ctx.fillText(this.status, 40, 790);
    this.finish();
  }
}

// ---------------------------------------------------------------- scene

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(window.devicePixelRatio);
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.xr.enabled = true;
// "local": the origin is the participant's head at session start, so the layout
// works the same seated or standing. y = 0 is eye height.
renderer.xr.setReferenceSpaceType("local");
document.body.append(renderer.domElement);
document.body.append(VRButton.createButton(renderer));

const scene = new THREE.Scene();
scene.background = new THREE.Color("#1b1f27");
const floor = new THREE.GridHelper(20, 40, "#3a4150", "#2a303b");
floor.position.y = -1.3;
scene.add(floor);

const camera = new THREE.PerspectiveCamera(70, window.innerWidth / window.innerHeight, 0.05, 50);
scene.add(camera);

const panels = [];

function placeOnArc(sectionPanels) {
  const widths = sectionPanels.map((p) => p.canvas.width / PX_PER_M);
  const total = (widths.reduce((a, b) => a + b, 0) + GAP * (widths.length - 1)) / RADIUS;
  let angle = -total / 2;
  sectionPanels.forEach((panel, i) => {
    const half = widths[i] / 2 / RADIUS;
    angle += half;
    panel.mesh.position.set(RADIUS * Math.sin(angle), 0.15, -RADIUS * Math.cos(angle));
    panel.mesh.lookAt(0, 0.15, 0);
    angle += half + GAP / RADIUS;
  });
}

// ---------------------------------------------------------------- interaction

const raycaster = new THREE.Raycaster();
const meshes = () => panels.map((p) => p.mesh);

function hitFromRay(origin, direction) {
  raycaster.set(origin, direction);
  const hit = raycaster.intersectObjects(meshes(), false)[0];
  if (!hit) return null;
  const panel = hit.object.userData.panel;
  return { panel, button: panel.buttonAt(hit.uv), distance: hit.distance };
}

let hoveredPanel = null;
function hover(hit) {
  if (hoveredPanel && hoveredPanel !== hit?.panel) hoveredPanel.setHovered(null);
  hoveredPanel = hit?.panel || null;
  hoveredPanel?.setHovered(hit.button);
}

function activate(hit) {
  if (hit?.button) {
    log.add("click", `${hit.panel.id}:${hit.button.label}`);
    hit.button.action();
  }
}

// Desktop: drag to look around, click buttons, wheel to scroll the panel under the cursor.
const look = { yaw: 0, pitch: 0, dragging: false, moved: 0, x: 0, y: 0 };
const pointer = new THREE.Vector2();

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
  hover(pointerHit(event));
});
window.addEventListener("pointerup", (event) => {
  if (look.dragging && look.moved < 6) activate(pointerHit(event));
  look.dragging = false;
});
renderer.domElement.addEventListener("wheel", (event) => {
  const hit = pointerHit(event);
  if (hit?.panel.scroll) hit.panel.scroll(Math.sign(event.deltaY));
  event.preventDefault();
}, { passive: false });

// Headset: a ray from each controller; trigger clicks, thumbstick scrolls.
const controllers = [0, 1].map((index) => {
  const controller = renderer.xr.getController(index);
  const ray = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, 0, -1)]),
    new THREE.LineBasicMaterial({ color: "#8fb3ff" }));
  ray.scale.z = 5;
  controller.add(ray);
  controller.userData = { ray, lastScroll: 0, inputSource: null };
  controller.addEventListener("connected", (event) => { controller.userData.inputSource = event.data; });
  controller.addEventListener("disconnected", () => { controller.userData.inputSource = null; });
  controller.addEventListener("selectstart", () => activate(controllerHit(controller)));
  scene.add(controller);
  return controller;
});

const rotation = new THREE.Matrix4();
function controllerHit(controller) {
  rotation.identity().extractRotation(controller.matrixWorld);
  const origin = new THREE.Vector3().setFromMatrixPosition(controller.matrixWorld);
  const direction = new THREE.Vector3(0, 0, -1).applyMatrix4(rotation);
  return hitFromRay(origin, direction);
}

function updateControllers(time) {
  for (const controller of controllers) {
    const hit = controllerHit(controller);
    controller.userData.ray.scale.z = hit ? hit.distance : 5;
    if (hit) hover(hit);
    const axes = controller.userData.inputSource?.gamepad?.axes || [];
    const y = axes[3] || 0;
    if (hit?.panel.scroll && Math.abs(y) > 0.6 && time - controller.userData.lastScroll > 150) {
      hit.panel.scroll(Math.sign(y));
      controller.userData.lastScroll = time;
    }
  }
}

// Gaze: log which panel is in the center of view once it has been held for a moment.
const gaze = { candidate: null, since: 0, logged: null };
const headPosition = new THREE.Vector3();
const headDirection = new THREE.Vector3();

function updateGaze(time) {
  const head = renderer.xr.isPresenting ? renderer.xr.getCamera() : camera;
  head.getWorldPosition(headPosition);
  head.getWorldDirection(headDirection);
  const id = hitFromRay(headPosition, headDirection)?.panel.id || null;
  if (id !== gaze.candidate) {
    gaze.candidate = id;
    gaze.since = time;
  } else if (id && id !== gaze.logged && time - gaze.since > DWELL_SECONDS * 1000) {
    gaze.logged = id;
    log.add("view", id);
  }
}

renderer.xr.addEventListener("sessionstart", () => {
  // Decision time is measured from when the participant is in the headset.
  log.restart();
  log.events.length = 0;
  log.add("xr_session_start", "");
  gaze.logged = null;
});

window.addEventListener("resize", () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

// ---------------------------------------------------------------- start

try {
  if (!trial || !participant) throw new Error("Open this page from the trial launcher.");
  const payload = await fetchTrial(trial);
  const sectionPanels = buildSections(payload).map((section) =>
    new SectionPanel(section, section.kind === "diff" ? 1.6 : 1.1));
  placeOnArc(sectionPanels);
  const decision = new DecisionPanel();
  decision.mesh.position.set(0, -0.85, -1.25);
  decision.mesh.lookAt(0, 0, 0);
  panels.push(...sectionPanels, decision);
  panels.forEach((p) => scene.add(p.mesh));
  hint.textContent = "Drag to look around, click buttons, scroll over a panel. On a headset, press Enter VR: " +
                     "point and pull the trigger to click, thumbstick to scroll.";
} catch (error) {
  hint.textContent = error.message;
}

renderer.setAnimationLoop((time) => {
  if (renderer.xr.isPresenting) updateControllers(time);
  updateGaze(time);
  renderer.render(scene, camera);
});
