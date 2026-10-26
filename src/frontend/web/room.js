// The VR environment: a modern loft on an upper floor, with a glass wall looking out over
// the sea at golden hour. The sky and sun light the room (image-based lighting plus a sun
// that casts window-frame shadows), so it reads as a real space. Everything is generated
// in code, with no downloads. The participant's head starts at the origin; the floor is
// FLOOR_Y below eye height.
//
// To try a different look, change THEME. The walls listed at the end of buildRoom() are the
// surfaces panels can snap onto.

import * as THREE from "three";
import { Sky } from "./vendor/Sky.js";
import { RoundedBoxGeometry } from "./vendor/RoundedBoxGeometry.js";

export const THEME = {
  sunElevation: 7,          // degrees above the horizon; lower = warmer sunset
  sunAzimuth: -38,          // degrees; 0 = straight ahead, negative = to the left
  exposure: 0.55,
  wall: "#f5efe6",
  ceiling: "#f6f5f1",
  floor: ["#dcb98c", "#d1ac7e", "#e0c299"],
  slats: "#b98d62",
  slatBacking: "#2b2a28",
  frame: "#1b1c1e",
  sofa: "#e2d8c8",
  wood: "#b08860",
  stone: "#d9cdb8",
  concrete: "#b9b5ae",
  rug: "#d9cdbb",
  leaf: "#4f7a45",
  leafDark: "#3c6235",
  water: "#1d4458",
  haze: "#e9c9a6",
  art: [["#e7b98f", "#c97b5a", "#f3e2cc"], ["#9fb6bf", "#5f7f8c", "#e8e2d6"]],
};

export const FLOOR_Y = -1.3;
const CEILING_Y = 2.4;       // 3.7 m ceilings
const HALF_WIDTH = 4.5;      // side walls at x = -4.5 and +4.5
const FRONT_Z = -4.6;        // the glass wall
const BACK_Z = 3.4;          // the wood-slat wall behind the participant
const SEA_Y = FLOOR_Y - 12;  // an upper-floor loft

const standard = (color, extra = {}) => new THREE.MeshStandardMaterial({ color, roughness: 0.85, ...extra });

function canvasTexture(width, height, draw, repeat = [1, 1], colorSpace = THREE.SRGBColorSpace) {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  draw(canvas.getContext("2d"), width, height);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = colorSpace;
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(...repeat);
  texture.anisotropy = 8;
  return texture;
}

// Wide light-oak planks with soft grain. One tile covers 2 m x 2 m.
function oakTexture() {
  return canvasTexture(1024, 1024, (ctx, w, h) => {
    const rows = 10;
    const plank = h / rows;
    let seed = 7;
    const random = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
    for (let row = 0; row < rows; row++) {
      let x = -random() * w;
      while (x < w) {
        const length = w * (0.55 + random() * 0.45);
        ctx.fillStyle = THEME.floor[Math.floor(random() * THEME.floor.length)];
        ctx.fillRect(x, row * plank, length, plank);
        ctx.fillRect(x + w, row * plank, length, plank);   // wrap so the tile repeats
        ctx.strokeStyle = "rgba(70, 50, 30, 0.18)";
        ctx.lineWidth = 1.5;
        ctx.strokeRect(x, row * plank, length, plank);
        x += length;
      }
      for (let i = 0; i < 14; i++) {
        const y = row * plank + random() * plank;
        ctx.strokeStyle = `rgba(110, 80, 50, ${0.04 + random() * 0.05})`;
        ctx.lineWidth = 1 + random() * 1.5;
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.bezierCurveTo(w * 0.33, y + (random() - 0.5) * 6, w * 0.66, y + (random() - 0.5) * 6, w, y);
        ctx.stroke();
      }
    }
  }, [1, 1]);
}

function rugTexture() {
  return canvasTexture(512, 512, (ctx, w, h) => {
    ctx.fillStyle = THEME.rug;
    ctx.fillRect(0, 0, w, h);
    // Fine wool speckle.
    const image = ctx.getImageData(0, 0, w, h);
    for (let i = 0; i < image.data.length; i += 4) {
      const n = (Math.random() - 0.5) * 18;
      image.data[i] += n; image.data[i + 1] += n; image.data[i + 2] += n;
    }
    ctx.putImageData(image, 0, 0);
  });
}

// Tileable ripple normal map for the sea: many integer-frequency waves in random
// directions, so it tiles seamlessly without looking like a grid.
function waterNormals() {
  const size = 256;
  let seed = 11;
  const random = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  const waves = Array.from({ length: 28 }, () => {
    const kx = Math.round((random() - 0.5) * 24), ky = Math.round((random() - 0.5) * 24) || 1;
    return { kx, ky, amplitude: 1 / Math.hypot(kx, ky), phase: random() * Math.PI * 2 };
  });
  return canvasTexture(size, size, (ctx) => {
    const image = ctx.createImageData(size, size);
    for (let y = 0; y < size; y++) {
      for (let x = 0; x < size; x++) {
        let dx = 0, dy = 0;
        for (const { kx, ky, amplitude, phase } of waves) {
          const c = Math.cos((2 * Math.PI * (kx * x + ky * y)) / size + phase) * amplitude;
          dx += c * kx;
          dy += c * ky;
        }
        const n = new THREE.Vector3(-dx * 0.04, -dy * 0.04, 1).normalize();
        const i = (y * size + x) * 4;
        image.data[i] = (n.x * 0.5 + 0.5) * 255;
        image.data[i + 1] = (n.y * 0.5 + 0.5) * 255;
        image.data[i + 2] = (n.z * 0.5 + 0.5) * 255;
        image.data[i + 3] = 255;
      }
    }
    ctx.putImageData(image, 0, 0);
  }, [260, 260], THREE.NoColorSpace);
}

function abstractArt(colors) {
  return canvasTexture(512, 640, (ctx, w, h) => {
    ctx.fillStyle = colors[2];
    ctx.fillRect(0, 0, w, h);
    ctx.globalAlpha = 0.9;
    ctx.fillStyle = colors[0];
    ctx.beginPath();
    ctx.arc(w * 0.42, h * 0.4, w * 0.3, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = colors[1];
    ctx.beginPath();
    ctx.ellipse(w * 0.62, h * 0.7, w * 0.26, h * 0.12, -0.3, 0, Math.PI * 2);
    ctx.fill();
  });
}

function box(width, height, depth, material, x, y, z, radius = 0) {
  const geometry = radius ? new RoundedBoxGeometry(width, height, depth, 3, radius) : new THREE.BoxGeometry(width, height, depth);
  const mesh = new THREE.Mesh(geometry, material);
  mesh.position.set(x, y, z);
  mesh.castShadow = mesh.receiveShadow = true;
  return mesh;
}

function sofa() {
  const group = new THREE.Group();
  const fabric = standard(THEME.sofa, { roughness: 1, envMapIntensity: 0.45 });
  group.add(box(2.7, 0.36, 0.98, fabric, 0, 0.22, 0, 0.08));
  group.add(box(2.7, 0.5, 0.26, fabric, 0, 0.6, 0.36, 0.1));
  for (const x of [-1.24, 1.24]) group.add(box(0.24, 0.56, 0.98, fabric, x, 0.32, 0, 0.1));
  for (const x of [-0.62, 0.62]) group.add(box(1.18, 0.16, 0.74, fabric, x, 0.46, -0.08, 0.07));
  return group;
}

function plant(height) {
  const group = new THREE.Group();
  const pot = new THREE.Mesh(new THREE.CylinderGeometry(0.26, 0.22, 0.5, 32), standard(THEME.concrete, { roughness: 0.95 }));
  pot.position.y = 0.25;
  pot.castShadow = pot.receiveShadow = true;
  group.add(pot);
  const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.025, 0.035, height, 8), standard("#6b5442"));
  trunk.position.y = 0.5 + height / 2;
  group.add(trunk);
  const leafMaterials = [standard(THEME.leaf, { side: THREE.DoubleSide, roughness: 0.7 }),
                         standard(THEME.leafDark, { side: THREE.DoubleSide, roughness: 0.7 })];
  const leaf = new THREE.SphereGeometry(0.13, 10, 6);
  for (let i = 0; i < 46; i++) {
    const t = i / 46;
    const pivot = new THREE.Group();
    pivot.position.y = 0.5 + height * (0.35 + 0.65 * t);
    pivot.rotation.set(0, i * 2.39996, 0.9 - t * 0.5);
    const mesh = new THREE.Mesh(leaf, leafMaterials[i % 2]);
    mesh.scale.set(0.75, 1.5, 0.12);
    mesh.position.set(0, 0.1, 0.12 + (1 - t) * 0.18);
    mesh.castShadow = true;
    pivot.add(mesh);
    group.add(pivot);
  }
  return group;
}

function arcLamp() {
  const group = new THREE.Group();
  const marble = standard("#ecebe7", { roughness: 0.4 });
  const metal = standard("#2a2a2a", { roughness: 0.35, metalness: 0.8 });
  const base = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.2, 0.05, 32), marble);
  base.position.y = 0.025;
  const curve = new THREE.CatmullRomCurve3([
    new THREE.Vector3(0, 0.05, 0), new THREE.Vector3(0, 1.4, 0), new THREE.Vector3(0.35, 2.05, 0),
    new THREE.Vector3(1.0, 2.15, 0), new THREE.Vector3(1.5, 1.95, 0)]);
  const arm = new THREE.Mesh(new THREE.TubeGeometry(curve, 48, 0.015, 8), metal);
  const shade = new THREE.Mesh(new THREE.SphereGeometry(0.2, 24, 12, 0, Math.PI * 2, 0, Math.PI / 2), metal);
  shade.material.side = THREE.DoubleSide;
  shade.position.set(1.5, 1.85, 0);
  const bulb = new THREE.Mesh(new THREE.SphereGeometry(0.06, 12, 8), new THREE.MeshBasicMaterial({ color: "#fff1d6" }));
  bulb.position.set(1.5, 1.82, 0);
  for (const mesh of [base, arm, shade]) mesh.castShadow = true;
  group.add(base, arm, shade, bulb);
  return group;
}

function framedArt(colors, width, height) {
  const group = new THREE.Group();
  group.add(box(width + 0.06, height + 0.06, 0.03, standard(THEME.frame, { roughness: 0.5 }), 0, 0, 0));
  const canvas = new THREE.Mesh(new THREE.PlaneGeometry(width, height), standard("#ffffff", { map: abstractArt(colors), roughness: 0.95 }));
  canvas.position.z = 0.016;
  group.add(canvas);
  return group;
}

export function buildRoom(scene, renderer) {
  const height = CEILING_Y - FLOOR_Y;
  const depth = BACK_Z - FRONT_Z;
  const width = HALF_WIDTH * 2;
  const midZ = (FRONT_Z + BACK_Z) / 2;

  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = THEME.exposure;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.shadowMap.autoUpdate = false;   // the room never moves, so draw its shadows once
  renderer.shadowMap.needsUpdate = true;

  // --- Sky, sun and sea ---------------------------------------------------------------
  const sun = new THREE.Vector3().setFromSphericalCoords(
    1, THREE.MathUtils.degToRad(90 - THEME.sunElevation), THREE.MathUtils.degToRad(180 - THEME.sunAzimuth));
  const sky = new Sky();
  sky.scale.setScalar(1000);
  sky.material.uniforms.turbidity.value = 9;
  sky.material.uniforms.rayleigh.value = 2.2;
  sky.material.uniforms.mieCoefficient.value = 0.004;
  sky.material.uniforms.mieDirectionalG.value = 0.85;
  sky.material.uniforms.sunPosition.value.copy(sun);

  // Light the room with the same sky it looks out on.
  const pmrem = new THREE.PMREMGenerator(renderer);
  const skyScene = new THREE.Scene();
  skyScene.add(sky);
  scene.environment = pmrem.fromScene(skyScene).texture;
  scene.add(sky);
  scene.fog = new THREE.Fog(THEME.haze, 250, 2600);

  const sea = new THREE.Mesh(new THREE.PlaneGeometry(6000, 6000), standard(THEME.water, {
    roughness: 0.12, metalness: 0.1, normalMap: waterNormals(), normalScale: new THREE.Vector2(0.25, 0.25) }));
  sea.rotation.x = -Math.PI / 2;
  sea.position.y = SEA_Y;
  scene.add(sea);

  // Distant headlands framing the view, softened by haze.
  for (const [x, z, sx, sy] of [[-900, -1500, 520, 70], [-400, -2100, 380, 40], [1100, -1700, 600, 95], [600, -2300, 300, 35]]) {
    const land = new THREE.Mesh(new THREE.SphereGeometry(1, 24, 12), standard("#6f7f86", { roughness: 1 }));
    land.scale.set(sx, sy, sx * 0.4);
    land.position.set(x, SEA_Y, z);
    scene.add(land);
  }

  const sunLight = new THREE.DirectionalLight("#ffd6a8", 3.2);
  sunLight.position.copy(sun).multiplyScalar(30).add(new THREE.Vector3(0, FLOOR_Y, midZ));
  sunLight.target.position.set(0, FLOOR_Y, midZ);
  sunLight.castShadow = true;
  sunLight.shadow.mapSize.set(2048, 2048);
  Object.assign(sunLight.shadow.camera, { left: -9, right: 9, top: 9, bottom: -9, near: 1, far: 70 });
  sunLight.shadow.bias = -0.0004;
  sunLight.shadow.normalBias = 0.03;
  scene.add(sunLight, sunLight.target);
  // Stands in for light bouncing off the floor and walls, so the ceiling isn't left grey.
  scene.add(new THREE.HemisphereLight("#fff0dc", "#f0dcc0", 1.6));

  // --- The room --------------------------------------------------------------------------
  const room = new THREE.Group();
  // Interior surfaces take only part of the (blue) sky light so whites stay warm.
  const wallMaterial = standard(THEME.wall, { roughness: 0.95, envMapIntensity: 0.4 });

  const floor = new THREE.Mesh(new THREE.PlaneGeometry(width, depth), standard("#ffffff", {
    map: oakTexture(), roughness: 0.42, envMapIntensity: 0.4 }));
  floor.material.map.repeat.set(width / 2, depth / 2);
  floor.rotation.x = -Math.PI / 2;
  floor.position.set(0, FLOOR_Y, midZ);
  floor.receiveShadow = true;
  room.add(floor);

  const ceiling = new THREE.Mesh(new THREE.PlaneGeometry(width, depth), standard(THEME.ceiling, {
    envMapIntensity: 0.4, emissive: THEME.ceiling, emissiveIntensity: 0.35 }));
  ceiling.rotation.x = Math.PI / 2;
  ceiling.position.set(0, CEILING_Y, midZ);
  ceiling.castShadow = true;   // keeps the low sun from reaching over the roof
  room.add(ceiling);
  const strip = new THREE.MeshBasicMaterial({ color: "#fffaf0" });
  for (const x of [-2.4, 0, 2.4]) {
    const light = new THREE.Mesh(new THREE.PlaneGeometry(0.06, depth - 2), strip);
    light.rotation.x = Math.PI / 2;
    light.position.set(x, CEILING_Y - 0.005, midZ);
    room.add(light);
  }

  // Side and back walls are solid boxes so they block the sun and cast shadows.
  for (const side of [-1, 1]) room.add(box(0.2, height, depth, wallMaterial, side * (HALF_WIDTH + 0.1), FLOOR_Y + height / 2, midZ));
  room.add(box(width + 0.4, height, 0.2, wallMaterial, 0, FLOOR_Y + height / 2, BACK_Z + 0.1));
  room.add(box(width + 0.4, 0.3, 0.3, wallMaterial, 0, CEILING_Y + 0.15, FRONT_Z));   // lintel above the glass

  // Floor-to-ceiling glass wall: thin black frames, then a balcony and glass railing.
  const frame = standard(THEME.frame, { roughness: 0.45, metalness: 0.3 });
  for (let x = -HALF_WIDTH; x <= HALF_WIDTH + 0.01; x += width / 6) room.add(box(0.05, height, 0.1, frame, x, FLOOR_Y + height / 2, FRONT_Z));
  room.add(box(width, 0.06, 0.1, frame, 0, FLOOR_Y + 0.03, FRONT_Z));
  room.add(box(width, 0.06, 0.1, frame, 0, CEILING_Y - 0.03, FRONT_Z));
  const glass = new THREE.Mesh(new THREE.PlaneGeometry(width, height), new THREE.MeshStandardMaterial({
    color: "#cfe3ea", transparent: true, opacity: 0.06, roughness: 0.05, metalness: 0.0 }));
  glass.position.set(0, FLOOR_Y + height / 2, FRONT_Z);
  room.add(glass);
  room.add(box(width + 0.4, 0.25, 2.2, standard("#c9c4bb", { roughness: 0.9 }), 0, FLOOR_Y - 0.125, FRONT_Z - 1.1));
  room.add(box(width + 0.4, 0.04, 0.05, frame, 0, FLOOR_Y + 1.05, FRONT_Z - 2.15));
  const railing = new THREE.Mesh(new THREE.PlaneGeometry(width + 0.4, 1.0), glass.material);
  railing.position.set(0, FLOOR_Y + 0.52, FRONT_Z - 2.15);
  room.add(railing);

  // Wood-slat feature wall behind the participant.
  const slatWidth = 5.2;
  room.add(box(slatWidth + 0.1, height, 0.02, standard(THEME.slatBacking, { roughness: 0.9 }), 0, FLOOR_Y + height / 2, BACK_Z - 0.01));
  const slatGeometry = new THREE.BoxGeometry(0.045, height, 0.045);
  const count = Math.floor(slatWidth / 0.075);
  const slats = new THREE.InstancedMesh(slatGeometry, standard(THEME.slats, { roughness: 0.6 }), count);
  const matrix = new THREE.Matrix4();
  for (let i = 0; i < count; i++) {
    slats.setMatrixAt(i, matrix.makeTranslation(-slatWidth / 2 + 0.04 + i * 0.075, FLOOR_Y + height / 2, BACK_Z - 0.045));
  }
  slats.castShadow = slats.receiveShadow = true;
  room.add(slats);

  // Furniture.
  const couch = sofa();
  couch.position.set(0, FLOOR_Y, BACK_Z - 0.75);
  room.add(couch);
  const table = new THREE.Group();
  const top = new THREE.Mesh(new THREE.CylinderGeometry(0.55, 0.55, 0.06, 48), standard(THEME.stone, { roughness: 0.5 }));
  top.position.y = 0.4;
  const stem = new THREE.Mesh(new THREE.CylinderGeometry(0.28, 0.32, 0.37, 32), standard(THEME.stone, { roughness: 0.6 }));
  stem.position.y = 0.185;
  for (const mesh of [top, stem]) mesh.castShadow = mesh.receiveShadow = true;
  table.add(top, stem);
  table.position.set(0, FLOOR_Y, BACK_Z - 2.0);
  room.add(table);

  const rug = new THREE.Mesh(new THREE.PlaneGeometry(4.2, 3.2), standard("#ffffff", { map: rugTexture(), roughness: 1, envMapIntensity: 0.4 }));
  rug.rotation.x = -Math.PI / 2;
  rug.position.set(0, FLOOR_Y + 0.004, 0.6);
  rug.receiveShadow = true;
  room.add(rug);

  const credenza = box(2.6, 0.6, 0.48, standard(THEME.wood, { roughness: 0.55 }), -HALF_WIDTH + 0.26, FLOOR_Y + 0.3, 0.4, 0.02);
  credenza.rotation.y = Math.PI / 2;
  room.add(credenza);
  const leftArt = framedArt(THEME.art[0], 1.1, 1.4);
  leftArt.position.set(-HALF_WIDTH + 0.03, FLOOR_Y + 1.75, 0.4);
  leftArt.rotation.y = Math.PI / 2;
  room.add(leftArt);
  const rightArt = framedArt(THEME.art[1], 1.6, 1.1);
  rightArt.position.set(HALF_WIDTH - 0.03, FLOOR_Y + 1.7, 1.2);
  rightArt.rotation.y = -Math.PI / 2;
  room.add(rightArt);

  const lamp = arcLamp();
  lamp.position.set(-1.9, FLOOR_Y, BACK_Z - 0.6);
  lamp.rotation.y = Math.PI / 6;
  room.add(lamp);

  for (const [x, z, h] of [[-HALF_WIDTH + 0.55, FRONT_Z + 0.6, 1.9], [HALF_WIDTH - 0.55, FRONT_Z + 0.6, 1.5], [HALF_WIDTH - 0.6, BACK_Z - 0.6, 1.7]]) {
    const tree = plant(h);
    tree.position.set(x, FLOOR_Y, z);
    room.add(tree);
  }

  scene.add(room);

  const span = { bottom: FLOOR_Y, top: CEILING_Y };
  const walls = [
    { name: "back", point: new THREE.Vector3(0, 0, BACK_Z - 0.07), normal: new THREE.Vector3(0, 0, -1), along: new THREE.Vector3(1, 0, 0), halfLength: HALF_WIDTH, ...span },
    { name: "left", point: new THREE.Vector3(-HALF_WIDTH, 0, midZ), normal: new THREE.Vector3(1, 0, 0), along: new THREE.Vector3(0, 0, 1), halfLength: depth / 2, ...span },
    { name: "right", point: new THREE.Vector3(HALF_WIDTH, 0, midZ), normal: new THREE.Vector3(-1, 0, 0), along: new THREE.Vector3(0, 0, 1), halfLength: depth / 2, ...span },
  ];
  const walkable = { minX: -HALF_WIDTH + 0.4, maxX: HALF_WIDTH - 0.4, minZ: FRONT_Z + 0.4, maxZ: BACK_Z - 2.7 };

  const ripples = sea.material.normalMap;
  const update = (seconds) => {
    ripples.offset.set(seconds * 0.004, seconds * 0.0025);
  };
  return { walls, walkable, update };
}

const SNAP_DISTANCE = 0.7;   // how close a held panel must be to a wall to snap
const WALL_GAP = 0.05;       // panels sit just in front of the wall (and any art on it)

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
