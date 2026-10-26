// The VR environment: a calm loft the participant sits in. Built from simple shapes and
// canvas textures (no downloads) so it stays light on a Quest. The participant's head
// starts at the origin; the floor is FLOOR_Y below eye height.
//
// To try a different look, change THEME. Walls listed in buildRoom() are the surfaces
// panels can snap onto.

import * as THREE from "three";

export const THEME = {
  skyTop: "#8fb8de",
  skyHorizon: "#f7dcc0",
  sun: "#fff1d6",
  hillsNear: "#7f9f78",
  hillsFar: "#a7bfa0",
  wall: "#f4eee4",
  frontWall: "#eee6d8",
  ceiling: "#f4efe6",
  beam: "#9a7858",
  floorLight: "#c49a6c",
  floorDark: "#b0875c",
  windowFrame: "#3d4147",
  rug: "#cdbfa9",
  rugPattern: "#a8957b",
  bench: "#9b7553",
  pot: "#b8694a",
  leaf: "#5f8d5a",
  leafDark: "#4b7647",
  lampShade: "#2f3236",
  lampGlow: "#ffd9a0",
  books: ["#7a8fa6", "#b5785a", "#d8c39a", "#6f8a6a", "#9b6f8e"],
};

export const FLOOR_Y = -1.3;
const CEILING_Y = 2.2;
const HALF_WIDTH = 3.6;   // left/right walls at x = -3.6 and +3.6
const FRONT_Z = -4.2;     // the plain wall in front of the participant
const BACK_Z = 3.0;       // the window wall behind them

const lambert = (color, extra = {}) => new THREE.MeshLambertMaterial({ color, ...extra });

function canvasTexture(width, height, draw, repeat = [1, 1]) {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  draw(canvas.getContext("2d"), width, height);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(...repeat);
  texture.anisotropy = 4;
  return texture;
}

function woodFloorTexture() {
  return canvasTexture(512, 512, (ctx, w, h) => {
    const plank = h / 8;
    for (let row = 0; row < 8; row++) {
      const offset = (row % 2) * w * 0.37;
      for (let x = -offset; x < w; x += w * 0.74) {
        const shade = (row * 7 + Math.round(x)) % 3;
        ctx.fillStyle = [THEME.floorLight, THEME.floorDark, THEME.floorLight][shade];
        ctx.fillRect(x, row * plank, w * 0.74, plank);
        ctx.strokeStyle = "rgba(60, 40, 25, 0.35)";
        ctx.lineWidth = 2;
        ctx.strokeRect(x, row * plank, w * 0.74, plank);
      }
      // Soft grain lines.
      ctx.strokeStyle = "rgba(90, 60, 35, 0.12)";
      for (let i = 0; i < 6; i++) {
        const y = row * plank + 6 + i * (plank / 6);
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.bezierCurveTo(w * 0.3, y + 3, w * 0.6, y - 3, w, y + 1);
        ctx.stroke();
      }
    }
  }, [4, 4]);
}

function rugTexture() {
  return canvasTexture(512, 384, (ctx, w, h) => {
    ctx.fillStyle = THEME.rug;
    ctx.fillRect(0, 0, w, h);
    ctx.strokeStyle = THEME.rugPattern;
    ctx.lineWidth = 10;
    ctx.strokeRect(24, 24, w - 48, h - 48);
    ctx.lineWidth = 3;
    ctx.strokeRect(48, 48, w - 96, h - 96);
    ctx.fillStyle = THEME.rugPattern;
    for (let x = 80; x < w - 60; x += 44) {
      for (let y = 80; y < h - 60; y += 44) {
        ctx.beginPath();
        ctx.moveTo(x, y - 7);
        ctx.lineTo(x + 7, y);
        ctx.lineTo(x, y + 7);
        ctx.lineTo(x - 7, y);
        ctx.fill();
      }
    }
  });
}

function sky() {
  const material = new THREE.ShaderMaterial({
    side: THREE.BackSide,
    depthWrite: false,
    uniforms: {
      top: { value: new THREE.Color(THEME.skyTop) },
      horizon: { value: new THREE.Color(THEME.skyHorizon) },
      sun: { value: new THREE.Color(THEME.sun) },
      sunDirection: { value: new THREE.Vector3(0.3, 0.25, 1).normalize() },
    },
    vertexShader: `
      varying vec3 vDirection;
      void main() {
        vDirection = normalize(position);
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }`,
    fragmentShader: `
      uniform vec3 top; uniform vec3 horizon; uniform vec3 sun; uniform vec3 sunDirection;
      varying vec3 vDirection;
      void main() {
        float height = max(vDirection.y, 0.0);
        vec3 color = mix(horizon, top, pow(height, 0.55));
        float glow = pow(max(dot(vDirection, sunDirection), 0.0), 24.0);
        gl_FragColor = vec4(color + sun * glow * 0.6, 1.0);
        #include <colorspace_fragment>
      }`,
  });
  return new THREE.Mesh(new THREE.SphereGeometry(60, 32, 16), material);
}

function hills(group) {
  // Rolling hills on all sides, seen through the windows.
  const rings = [{ radius: 34, color: THEME.hillsFar, height: 7 }, { radius: 22, color: THEME.hillsNear, height: 4 }];
  for (const { radius, color, height } of rings) {
    for (let i = 0; i < 14; i++) {
      const angle = (i / 14) * Math.PI * 2 + radius;
      const hill = new THREE.Mesh(new THREE.SphereGeometry(1, 16, 8), lambert(color));
      hill.scale.set(radius * 0.35, height * (0.7 + ((i * 37) % 10) / 20), radius * 0.2);
      hill.position.set(Math.sin(angle) * radius, FLOOR_Y - 2, Math.cos(angle) * radius);
      hill.lookAt(0, hill.position.y, 0);
      group.add(hill);
    }
  }
}

// A wall in the XY plane (bottom edge at y = 0) with window openings, plus frames and
// mullions. All windows in one wall share the same height band. The wall is built from
// slightly overlapping rectangles so no cracks show the sky through it.
function wallWithWindows(width, height, windows, color) {
  const group = new THREE.Group();
  const material = lambert(color, { side: THREE.DoubleSide });
  const rect = (x0, x1, y0, y1) => {
    const mesh = new THREE.Mesh(new THREE.PlaneGeometry(x1 - x0, y1 - y0), material);
    mesh.position.set((x0 + x1) / 2, (y0 + y1) / 2, 0);
    group.add(mesh);
  };
  const overlap = 0.01;

  if (!windows.length) {
    rect(-width / 2, width / 2, 0, height);
  } else {
    const { y0, y1 } = windows[0];
    rect(-width / 2, width / 2, 0, y0 + overlap);
    rect(-width / 2, width / 2, y1 - overlap, height);
    let x = -width / 2;
    for (const win of [...windows].sort((a, b) => a.x0 - b.x0)) {
      rect(x - overlap, win.x0 + overlap, y0, y1);
      x = win.x1;
    }
    rect(x - overlap, width / 2, y0, y1);
  }

  const frame = lambert(THEME.windowFrame);
  const bar = (w, h, x, y) => {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, 0.08), frame);
    mesh.position.set(x, y, 0);
    group.add(mesh);
  };
  for (const win of windows) {
    const t = 0.06;
    const cx = (win.x0 + win.x1) / 2, cy = (win.y0 + win.y1) / 2;
    bar(win.x1 - win.x0 + t, t, cx, win.y0);
    bar(win.x1 - win.x0 + t, t, cx, win.y1);
    bar(t, win.y1 - win.y0, win.x0, cy);
    bar(t, win.y1 - win.y0, win.x1, cy);
    for (let i = 1; i < (win.columns || 1); i++) {
      bar(0.035, win.y1 - win.y0, win.x0 + ((win.x1 - win.x0) * i) / win.columns, cy);
    }
    if (win.transom) bar(win.x1 - win.x0, 0.035, cx, win.y0 + (win.y1 - win.y0) * win.transom);
  }
  return group;
}

function plant(scale = 1) {
  const group = new THREE.Group();
  const pot = new THREE.Mesh(new THREE.CylinderGeometry(0.17, 0.13, 0.32, 16), lambert(THEME.pot));
  pot.position.y = 0.16;
  group.add(pot);
  const leaves = [lambert(THEME.leaf, { side: THREE.DoubleSide }), lambert(THEME.leafDark, { side: THREE.DoubleSide })];
  const leafShape = new THREE.SphereGeometry(0.1, 8, 6);
  for (let i = 0; i < 16; i++) {
    const angle = i * 2.39996;            // golden angle spreads leaves evenly
    const lift = 0.4 + (i / 16) * 0.55;
    const reach = 0.06 + (1 - i / 16) * 0.16;
    const stemPivot = new THREE.Group();
    stemPivot.position.set(0, 0.3, 0);
    stemPivot.rotation.set(0, angle, 0.35 + (1 - i / 16) * 0.5);
    const leaf = new THREE.Mesh(leafShape, leaves[i % 2]);
    leaf.scale.set(0.55, 1.7, 0.18);
    leaf.position.set(0, lift - 0.3, reach);
    stemPivot.add(leaf);
    group.add(stemPivot);
  }
  group.scale.setScalar(scale);
  return group;
}

function pendantLamp(x, z, drop) {
  const group = new THREE.Group();
  const cord = new THREE.Mesh(new THREE.CylinderGeometry(0.008, 0.008, drop, 6), lambert("#222"));
  cord.position.y = CEILING_Y - drop / 2;
  const shade = new THREE.Mesh(new THREE.ConeGeometry(0.22, 0.24, 20, 1, true),
                               lambert(THEME.lampShade, { side: THREE.DoubleSide }));
  shade.position.y = CEILING_Y - drop;
  const bulb = new THREE.Mesh(new THREE.SphereGeometry(0.07, 12, 8),
                              new THREE.MeshBasicMaterial({ color: THEME.lampGlow }));
  bulb.position.y = CEILING_Y - drop - 0.1;
  group.add(cord, shade, bulb);
  group.position.set(x, 0, z);
  return group;
}

function bench(width) {
  const group = new THREE.Group();
  const top = new THREE.Mesh(new THREE.BoxGeometry(width, 0.06, 0.45), lambert(THEME.bench));
  top.position.y = 0.42;
  group.add(top);
  for (const x of [-width / 2 + 0.1, width / 2 - 0.1]) {
    const leg = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.4, 0.4), lambert(THEME.bench));
    leg.position.set(x, 0.2, 0);
    group.add(leg);
  }
  // A few books leaning together.
  let x = -width / 2 + 0.3;
  THEME.books.forEach((color, i) => {
    const book = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.26 + (i % 3) * 0.03, 0.2), lambert(color));
    book.position.set(x, 0.45 + book.geometry.parameters.height / 2, 0);
    group.add(book);
    x += 0.055;
  });
  return group;
}

// Returns the snap surfaces (walls) and the area the participant can walk in.
export function buildRoom(scene) {
  const room = new THREE.Group();
  const roomHeight = CEILING_Y - FLOOR_Y;
  const depth = BACK_Z - FRONT_Z;
  const width = HALF_WIDTH * 2;

  scene.background = new THREE.Color(THEME.skyHorizon);
  scene.fog = new THREE.Fog(THEME.skyHorizon, 14, 55);
  scene.add(sky());
  hills(scene);

  scene.add(new THREE.HemisphereLight("#fffaf2", "#b39478", 2.6));
  scene.add(new THREE.AmbientLight("#fff4e6", 0.9));
  const sunLight = new THREE.DirectionalLight("#fff0d8", 1.4);
  sunLight.position.set(2, 4, 6);
  scene.add(sunLight);

  const floor = new THREE.Mesh(new THREE.PlaneGeometry(width, depth), lambert("#ffffff", { map: woodFloorTexture() }));
  floor.rotation.x = -Math.PI / 2;
  floor.position.set(0, FLOOR_Y, (FRONT_Z + BACK_Z) / 2);
  room.add(floor);

  const rug = new THREE.Mesh(new THREE.PlaneGeometry(3.4, 2.6), lambert("#ffffff", { map: rugTexture() }));
  rug.rotation.x = -Math.PI / 2;
  rug.position.set(0, FLOOR_Y + 0.005, -0.4);
  room.add(rug);

  const ceiling = new THREE.Mesh(new THREE.PlaneGeometry(width, depth), lambert(THEME.ceiling));
  ceiling.rotation.x = Math.PI / 2;
  ceiling.position.set(0, CEILING_Y, (FRONT_Z + BACK_Z) / 2);
  room.add(ceiling);
  for (let x = -HALF_WIDTH + 0.6; x < HALF_WIDTH; x += 1.2) {
    const beam = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.22, depth), lambert(THEME.beam));
    beam.position.set(x, CEILING_Y - 0.11, (FRONT_Z + BACK_Z) / 2);
    room.add(beam);
  }

  // Front wall: plain, so panels in front of it are easy to read.
  const front = wallWithWindows(width, roomHeight, [], THEME.frontWall);
  front.position.set(0, FLOOR_Y, FRONT_Z);
  room.add(front);

  // Back wall: a large window looking out at the hills.
  const back = wallWithWindows(width, roomHeight, [{ x0: -2.6, x1: 2.6, y0: 0.45, y1: 2.95, columns: 4, transom: 0.72 }], THEME.wall);
  back.position.set(0, FLOOR_Y, BACK_Z);
  back.rotation.y = Math.PI;
  room.add(back);

  // Side walls: high windows above panel height.
  const sideWindows = [{ x0: -3.0, x1: -0.8, y0: 2.45, y1: 3.2, columns: 3 }, { x0: 0.6, x1: 2.6, y0: 2.45, y1: 3.2, columns: 3 }];
  for (const side of [-1, 1]) {
    const wall = wallWithWindows(depth, roomHeight, sideWindows, THEME.wall);
    wall.position.set(side * HALF_WIDTH, FLOOR_Y, (FRONT_Z + BACK_Z) / 2);
    wall.rotation.y = side * -Math.PI / 2;
    room.add(wall);
  }

  const underWindow = bench(4.4);
  underWindow.position.set(0, FLOOR_Y, BACK_Z - 0.3);
  room.add(underWindow);

  for (const [x, z, scale] of [[-3.1, BACK_Z - 0.5, 1.6], [3.1, BACK_Z - 0.5, 1.3], [-3.15, FRONT_Z + 0.45, 1.3], [3.15, FRONT_Z + 0.45, 1.0]]) {
    const pot = plant(scale);
    pot.position.set(x, FLOOR_Y, z);
    room.add(pot);
  }
  room.add(pendantLamp(-2.4, 1.6, 1.0), pendantLamp(2.4, 1.6, 1.0), pendantLamp(0, 2.2, 0.8));

  scene.add(room);

  const wallHeight = { bottom: FLOOR_Y, top: CEILING_Y };
  const walls = [
    { name: "front", point: new THREE.Vector3(0, 0, FRONT_Z), normal: new THREE.Vector3(0, 0, 1), along: new THREE.Vector3(1, 0, 0), halfLength: HALF_WIDTH, ...wallHeight },
    { name: "back", point: new THREE.Vector3(0, 0, BACK_Z), normal: new THREE.Vector3(0, 0, -1), along: new THREE.Vector3(1, 0, 0), halfLength: HALF_WIDTH, ...wallHeight },
    { name: "left", point: new THREE.Vector3(-HALF_WIDTH, 0, (FRONT_Z + BACK_Z) / 2), normal: new THREE.Vector3(1, 0, 0), along: new THREE.Vector3(0, 0, 1), halfLength: depth / 2, ...wallHeight },
    { name: "right", point: new THREE.Vector3(HALF_WIDTH, 0, (FRONT_Z + BACK_Z) / 2), normal: new THREE.Vector3(-1, 0, 0), along: new THREE.Vector3(0, 0, 1), halfLength: depth / 2, ...wallHeight },
  ];
  const walkable = { minX: -HALF_WIDTH + 0.4, maxX: HALF_WIDTH - 0.4, minZ: FRONT_Z + 0.4, maxZ: BACK_Z - 0.7 };
  return { walls, walkable };
}

const SNAP_DISTANCE = 0.7;   // how close a held panel must be to a wall to snap
const WALL_GAP = 0.03;       // panels sit just in front of the wall surface

// Where a panel would land if released now: the nearest wall within reach, with the panel
// kept inside the wall's edges, floor and ceiling. Returns null if no wall is close enough.
export function snapTarget(walls, position, width, height) {
  let best = null;
  for (const wall of walls) {
    const offset = position.clone().sub(wall.point);
    const distance = offset.dot(wall.normal);
    if (distance > SNAP_DISTANCE || distance < -0.5) continue;
    if (best && distance >= best.distance) continue;
    const limit = Math.max(0, wall.halfLength - width / 2 - 0.05);
    const along = THREE.MathUtils.clamp(offset.dot(wall.along), -limit, limit);
    const y = THREE.MathUtils.clamp(position.y, wall.bottom + height / 2 + 0.05, wall.top - height / 2 - 0.05);
    const target = wall.point.clone()
      .addScaledVector(wall.along, along)
      .addScaledVector(wall.normal, WALL_GAP)
      .setY(y);
    best = { wall: wall.name, distance, position: target, normal: wall.normal };
  }
  return best;
}
