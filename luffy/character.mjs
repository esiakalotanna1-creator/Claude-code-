// Luffy (fan-made, inspired by the One Piece character) — procedurally built, rigged and animated game character.
// buildCharacter() returns { root, mesh, skeleton, clips } ready for GLTFExporter.
// Units: metres. Y up, facing +Z, feet at the origin, T-pose bind.
import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import * as BGU from 'three/addons/utils/BufferGeometryUtils.js';

const HALF_PI = Math.PI / 2;

// ---------------------------------------------------------------- skeleton
const BONES = [
  ['Hips', null, [0, 0.96, 0]],
  ['Spine', 'Hips', [0, 1.06, 0]],
  ['Chest', 'Spine', [0, 1.2, 0]],
  ['Neck', 'Chest', [0, 1.44, 0]],
  ['Head', 'Neck', [0, 1.5, 0]],
  ['LeftShoulder', 'Chest', [0.06, 1.4, 0]],
  ['LeftArm', 'LeftShoulder', [0.215, 1.4, 0]],
  ['LeftForeArm', 'LeftArm', [0.46, 1.4, 0]],
  ['LeftHand', 'LeftForeArm', [0.715, 1.4, 0]],
  ['RightShoulder', 'Chest', [-0.06, 1.4, 0]],
  ['RightArm', 'RightShoulder', [-0.215, 1.4, 0]],
  ['RightForeArm', 'RightArm', [-0.46, 1.4, 0]],
  ['RightHand', 'RightForeArm', [-0.715, 1.4, 0]],
  ['LeftUpLeg', 'Hips', [0.1, 0.92, 0]],
  ['LeftLeg', 'LeftUpLeg', [0.1, 0.52, 0]],
  ['LeftFoot', 'LeftLeg', [0.1, 0.1, 0]],
  ['LeftToeBase', 'LeftFoot', [0.1, 0.03, 0.11]],
  ['RightUpLeg', 'Hips', [-0.1, 0.92, 0]],
  ['RightLeg', 'RightUpLeg', [-0.1, 0.52, 0]],
  ['RightFoot', 'RightLeg', [-0.1, 0.1, 0]],
  ['RightToeBase', 'RightFoot', [-0.1, 0.03, 0.11]],
];

// --------------------------------------------------------------- materials
function makeMaterials() {
  const m = (name, color, roughness, metalness = 0, extra = {}) =>
    Object.assign(new THREE.MeshStandardMaterial({ color, roughness, metalness, ...extra }), { name });
  return {
    Skin: m('Skin', 0xf0b48c, 0.62),
    Hair: m('Hair', 0x15110f, 0.55),
    Vest: m('Vest', 0xd4201f, 0.7, 0, { side: THREE.DoubleSide }),
    Shorts: m('Shorts', 0x2f5fb0, 0.8),
    Straw: m('Straw', 0xf2c75c, 0.85),
    Band: m('Band', 0xc8201e, 0.6),
    Sandal: m('Sandal', 0x6b4a2e, 0.8),
    Eye: m('Eye', 0xffffff, 0.35),
    Dark: m('Dark', 0x1c0f0c, 0.4),
    Scar: m('Scar', 0x8c3a30, 0.6),
  };
}

// ------------------------------------------------------- geometry helpers
function profile(points, samples = 14) {
  const curve = new THREE.SplineCurve(points.map(([r, y]) => new THREE.Vector2(r, y)));
  return curve.getPoints(samples).map((p) => new THREE.Vector2(Math.max(0, p.x), p.y));
}
// Revolve a [radius, height] profile (ascending height) around Y.
function lathe(points, seg = 20, samples = 14, smooth = true) {
  const pts = smooth ? profile(points, samples) : points.map(([r, y]) => new THREE.Vector2(r, y));
  return new THREE.LatheGeometry(pts, seg);
}
const rbox = (w, h, d, r, seg = 3) => new RoundedBoxGeometry(w, h, d, seg, r);
const sphere = (r, ws = 20, hs = 14) => new THREE.SphereGeometry(r, ws, hs);
const cyl = (rt, rb, h, seg = 20) => new THREE.CylinderGeometry(rt, rb, h, seg);
// Lay a Y-up shape along +X.
const alongX = (g) => g.rotateZ(-HALF_PI);
// Lay a Y-up shape along +Z.
const alongZ = (g) => g.rotateX(HALF_PI);

function mirrorX(src) {
  const g = src.clone();
  const p = g.attributes.position, n = g.attributes.normal;
  for (let i = 0; i < p.count; i++) { p.setX(i, -p.getX(i)); n.setX(i, -n.getX(i)); }
  for (const name of ['position', 'normal', 'uv']) {
    const a = g.attributes[name], s = a.itemSize, arr = a.array;
    for (let i = 0; i < a.count; i += 3) {
      for (let k = 0; k < s; k++) {
        const t = arr[(i + 1) * s + k]; arr[(i + 1) * s + k] = arr[(i + 2) * s + k]; arr[(i + 2) * s + k] = t;
      }
    }
  }
  return g;
}

// Stylised proportions: everything below the hips is compressed vertically.
const HIP_Y = 0.96, LEG_SCALE = 0.84;
const warpY = (y) => (y <= HIP_Y ? y * LEG_SCALE : y - HIP_Y * (1 - LEG_SCALE));
function warp(g) {
  const p = g.attributes.position, n = g.attributes.normal, v = new THREE.Vector3();
  for (let i = 0; i < p.count; i++) {
    const y = p.getY(i);
    if (y <= HIP_Y) {
      v.set(n.getX(i), n.getY(i) / LEG_SCALE, n.getZ(i)).normalize();
      n.setXYZ(i, v.x, v.y, v.z);
    }
    p.setY(i, warpY(y));
  }
}

// ------------------------------------------------------------------ build
export function buildCharacter() {
  const materials = makeMaterials();
  const matNames = Object.keys(materials);
  const boneIndex = Object.fromEntries(BONES.map((b, i) => [b[0], i]));
  const buckets = Object.fromEntries(matNames.map((n) => [n, []]));

  function add(geo, bone, mat) {
    let g = geo.index ? geo.toNonIndexed() : geo;
    for (const k of Object.keys(g.attributes)) if (!['position', 'normal', 'uv'].includes(k)) g.deleteAttribute(k);
    warp(g);
    const n = g.attributes.position.count;
    const si = new Uint16Array(n * 4), sw = new Float32Array(n * 4);
    for (let i = 0; i < n; i++) { si[i * 4] = boneIndex[bone]; sw[i * 4] = 1; }
    g.setAttribute('skinIndex', new THREE.Uint16BufferAttribute(si, 4));
    g.setAttribute('skinWeight', new THREE.Float32BufferAttribute(sw, 4));
    buckets[mat].push(g);
  }
  // Add a left-side part (+X) and its mirror on the right.
  function addLR(geo, bone, mat) {
    const g = geo.index ? geo.toNonIndexed() : geo;
    add(g.clone(), 'Left' + bone, mat);
    add(mirrorX(g), 'Right' + bone, mat);
  }

  // Add a part and its mirror, both on the same bone.
  function addBoth(geo, bone, mat) {
    const g = geo.index ? geo.toNonIndexed() : geo;
    add(g.clone(), bone, mat);
    add(mirrorX(g), bone, mat);
  }
  const latheArc = (pts, seg, a0, a1, smooth = true, samples = 12) =>
    new THREE.LatheGeometry(smooth ? profile(pts, samples) : pts.map(([r, y]) => new THREE.Vector2(r, y)), seg, a0, a1);
  const box = (w, h, d) => new THREE.BoxGeometry(w, h, d);
  function cone(len, rad, dir, pos) {
    const g = new THREE.ConeGeometry(rad, len, 6).translate(0, len / 2, 0);
    g.applyQuaternion(new THREE.Quaternion().setFromUnitVectors(AX.y, dir.clone().normalize()));
    return g.translate(pos.x, pos.y, pos.z);
  }

  // ---- head (built at 1:1, then enlarged about the neck for a stylised look) ----
  const HY = 1.64, HEAD_SCALE = 1.22;
  const big = (g) => g.translate(0, -1.5, 0).scale(HEAD_SCALE, HEAD_SCALE, HEAD_SCALE).translate(0, 1.5, 0);
  const hAdd = (g, bone, mat) => add(big(g), bone, mat);
  const hBoth = (g, bone, mat) => addBoth(big(g), bone, mat);

  hAdd(sphere(1, 32, 22).scale(0.125, 0.135, 0.13).translate(0, HY, 0), 'Head', 'Skin');
  hBoth(sphere(1, 12, 8).scale(0.02, 0.03, 0.018).translate(0.126, HY - 0.005, -0.005), 'Head', 'Skin');
  // eyes, brows
  for (const sd of [-1, 1]) {
    hAdd(sphere(1, 16, 12).scale(0.03, 0.042, 0.014).translate(sd * 0.052, HY + 0.012, 0.118), 'Head', 'Eye');
    hAdd(sphere(1, 12, 10).scale(0.017, 0.026, 0.01).translate(sd * 0.052, HY + 0.012, 0.128), 'Head', 'Dark');
    hAdd(box(0.05, 0.009, 0.01).rotateZ(sd * -0.12).translate(sd * 0.055, HY + 0.062, 0.113), 'Head', 'Hair');
  }
  // scar under his left eye
  hAdd(box(0.004, 0.024, 0.012).translate(0.056, HY - 0.036, 0.111), 'Head', 'Scar');
  hAdd(box(0.004, 0.02, 0.012).rotateZ(0.5).translate(0.064, HY - 0.034, 0.108), 'Head', 'Scar');
  // nose + big grin
  hAdd(sphere(0.016, 10, 8).translate(0, HY - 0.028, 0.128), 'Head', 'Skin');
  hAdd(sphere(1, 20, 12).scale(0.058, 0.03, 0.012).translate(0, HY - 0.058, 0.112), 'Head', 'Dark');
  hAdd(sphere(1, 16, 8).scale(0.05, 0.009, 0.008).translate(0, HY - 0.044, 0.119), 'Head', 'Eye');
  // hair: cap, back mass, bangs and tufts under the brim
  hAdd(new THREE.SphereGeometry(1, 28, 16, 0, Math.PI * 2, 0, 1.15).scale(0.136, 0.142, 0.14).translate(0, HY + 0.006, -0.002), 'Head', 'Hair');
  hAdd(sphere(1, 24, 16).scale(0.131, 0.105, 0.125).translate(0, HY + 0.012, -0.03), 'Head', 'Hair');
  for (let k = 0; k < 5; k++) {
    const x = -0.08 + k * 0.04;
    hAdd(cone(0.05, 0.022, new THREE.Vector3(x * 2.5, -1, 0.5), new THREE.Vector3(x, HY + 0.058, 0.108)), 'Head', 'Hair');
  }
  for (let k = 0; k < 11; k++) {
    const a = 0.95 + k * ((Math.PI * 2 - 1.9) / 10);
    const y = HY + 0.02 - (k % 3) * 0.012;
    hAdd(cone(0.065 + (k % 2) * 0.018, 0.026, new THREE.Vector3(Math.sin(a), -0.6, Math.cos(a)),
      new THREE.Vector3(Math.sin(a) * 0.12, y, Math.cos(a) * 0.12 - 0.01)), 'Head', 'Hair');
  }
  // straw hat
  const hat = (g) => g.rotateX(-0.1).translate(0, HY + 0.07, -0.006);
  hAdd(hat(latheArc([[0, 0.102], [0.06, 0.099], [0.1, 0.082], [0.118, 0.035], [0.123, 0.0]], 32, 0, Math.PI * 2, true, 14)), 'Head', 'Straw');
  hAdd(hat(latheArc([[0.1, -0.007], [0.2, -0.01], [0.262, 0.0], [0.274, 0.018], [0.262, 0.019], [0.2, 0.004], [0.1, 0.007]], 40, 0, Math.PI * 2, false)), 'Head', 'Straw');
  hAdd(hat(latheArc([[0.1215, 0.003], [0.1265, 0.004], [0.1245, 0.034], [0.1195, 0.034]], 32, 0, Math.PI * 2, false)), 'Head', 'Band');
  // neck
  add(cyl(0.048, 0.054, 0.14, 16).translate(0, 1.49, 0), 'Neck', 'Skin');

  // ---- torso ----
  add(lathe([[0, 1.165], [0.09, 1.17], [0.125, 1.21], [0.15, 1.29], [0.16, 1.38], [0.135, 1.445], [0.08, 1.475], [0, 1.48]], 24, 16).scale(1, 1, 0.72), 'Chest', 'Skin');
  // X scar across the chest
  for (const s of [-1, 1]) add(box(0.007, 0.15, 0.012).rotateZ(s * 0.75).translate(0, 1.33, 0.108), 'Chest', 'Scar');
  // open vest: wraps the back and sides, front left open
  add(latheArc([[0.114, 1.17], [0.137, 1.21], [0.161, 1.29], [0.171, 1.38], [0.15, 1.43], [0.122, 1.455]], 28, 0.55, Math.PI * 2 - 1.1, true, 12).scale(1, 1, 0.72), 'Chest', 'Vest');
  for (const s of [-1, 1]) add(rbox(0.045, 0.012, 0.1, 0.005, 2).rotateZ(s * -0.35).translate(s * 0.1, 1.462, 0), 'Chest', 'Vest');
  // abdomen
  add(lathe([[0, 0.98], [0.105, 0.99], [0.112, 1.06], [0.118, 1.15], [0.114, 1.21], [0, 1.22]], 20, 10).scale(1, 1, 0.76), 'Spine', 'Skin');
  // shorts (pelvis) + yellow sash
  add(lathe([[0, 0.85], [0.06, 0.855], [0.118, 0.905], [0.138, 0.97], [0.132, 1.035], [0.1, 1.05], [0, 1.055]], 22, 12).scale(1, 1, 0.78), 'Hips', 'Shorts');
  add(latheArc([[0.139, 0.995], [0.15, 1.0], [0.15, 1.06], [0.139, 1.066]], 24, 0, Math.PI * 2, false).scale(1, 1, 0.78), 'Hips', 'Straw');
  add(rbox(0.05, 0.045, 0.03, 0.012, 2).translate(0.07, 1.03, 0.118), 'Hips', 'Straw');
  add(rbox(0.02, 0.075, 0.012, 0.005, 2).rotateZ(0.2).translate(0.088, 0.975, 0.126), 'Hips', 'Straw');
  add(rbox(0.02, 0.06, 0.012, 0.005, 2).rotateZ(-0.25).translate(0.052, 0.98, 0.126), 'Hips', 'Straw');

  // ---- arms (left side, mirrored) ----
  const AY = 1.4;
  addLR(sphere(0.056, 16, 12).translate(0.205, AY, 0), 'Arm', 'Skin');
  addLR(alongX(lathe([[0, 0], [0.043, 0.01], [0.047, 0.1], [0.041, 0.24], [0, 0.26]], 14, 10)).translate(0.215, AY, 0), 'Arm', 'Skin');
  addLR(sphere(0.043, 14, 10).translate(0.46, AY, 0), 'ForeArm', 'Skin');
  addLR(alongX(lathe([[0, 0], [0.043, 0.005], [0.046, 0.06], [0.037, 0.2], [0.031, 0.25], [0, 0.256]], 14, 10)).translate(0.475, AY, 0), 'ForeArm', 'Skin');
  addLR(rbox(0.1, 0.056, 0.078, 0.022, 3).translate(0.775, AY - 0.002, 0), 'Hand', 'Skin');
  addLR(new THREE.CapsuleGeometry(0.017, 0.035, 4, 8).rotateX(HALF_PI).rotateY(0.5).translate(0.755, AY - 0.012, 0.05), 'Hand', 'Skin');

  // ---- legs (left side, mirrored) ----
  const LX = 0.1;
  addLR(lathe([[0, 0.5], [0.048, 0.51], [0.056, 0.6], [0.066, 0.8], [0.064, 0.9], [0, 0.92]], 14, 10).translate(LX, 0, 0), 'UpLeg', 'Skin');
  addLR(lathe([[0.07, 0.69], [0.088, 0.71], [0.095, 0.8], [0.09, 0.93], [0.07, 0.945]], 18, 10).translate(LX, 0, 0), 'UpLeg', 'Shorts');
  addLR(sphere(0.05, 14, 10).translate(LX, 0.52, 0), 'Leg', 'Skin');
  addLR(lathe([[0, 0.07], [0.044, 0.075], [0.05, 0.14], [0.05, 0.3], [0.056, 0.38], [0.05, 0.47], [0, 0.485]], 16, 12).translate(LX, 0, 0), 'Leg', 'Skin');
  // sandals
  addLR(rbox(0.085, 0.06, 0.15, 0.025, 3).translate(LX, 0.07, 0.02), 'Foot', 'Skin');
  addLR(rbox(0.1, 0.036, 0.2, 0.014, 2).translate(LX, 0.018, 0.012), 'Foot', 'Sandal');
  addLR(rbox(0.095, 0.014, 0.03, 0.005, 2).translate(LX, 0.1, 0.05), 'Foot', 'Sandal');
  addLR(rbox(0.085, 0.045, 0.06, 0.02, 3).translate(LX, 0.058, 0.145), 'ToeBase', 'Skin');
  addLR(rbox(0.1, 0.036, 0.07, 0.014, 2).translate(LX, 0.018, 0.15), 'ToeBase', 'Sandal');

  // index each material's vertices, then merge with one group per material
  const perMat = matNames.map((n) => BGU.mergeVertices(BGU.mergeBufferGeometries(buckets[n], false), 1e-5));
  const geometry = BGU.mergeBufferGeometries(perMat, true);
  geometry.computeBoundingBox();
  geometry.computeBoundingSphere();

  // ---- skeleton ----
  const bones = [];
  const world = {};
  for (const [name, parent, pos] of BONES) {
    const b = new THREE.Bone();
    b.name = name;
    world[name] = new THREE.Vector3(pos[0], warpY(pos[1]), pos[2]);
    if (parent) { b.position.copy(world[name]).sub(world[parent]); bones[boneIndex[parent]].add(b); }
    else b.position.copy(world[name]);
    bones.push(b);
  }
  const skeleton = new THREE.Skeleton(bones);
  const mesh = new THREE.SkinnedMesh(geometry, matNames.map((n) => materials[n]));
  mesh.name = 'Luffy';
  const root = new THREE.Group();
  root.name = 'LuffyRig';
  root.add(bones[0]);
  root.add(mesh);
  root.updateMatrixWorld(true);
  mesh.bind(skeleton);

  const clips = buildClips(root, bones, boneIndex, world);
  return { root, mesh, skeleton, clips, materials };
}

// -------------------------------------------------------------- animation
const AX = { x: new THREE.Vector3(1, 0, 0), y: new THREE.Vector3(0, 1, 0), z: new THREE.Vector3(0, 0, 1) };
// Compose axis rotations; the first step is applied first.
function rot(...steps) {
  const q = new THREE.Quaternion(), t = new THREE.Quaternion();
  for (let i = 0; i < steps.length; i += 2) q.premultiply(t.setFromAxisAngle(AX[steps[i]], steps[i + 1]));
  return q;
}
const ease = (x) => { x = Math.min(1, Math.max(0, x)); return x * x * (3 - 2 * x); };
const ARM_DOWN = 1.3;

// A standing pose: arms lowered from the T-pose, elbows relaxed.
function stand() {
  return {
    LeftArm: ['z', -ARM_DOWN], RightArm: ['z', ARM_DOWN],
    LeftForeArm: ['y', -0.28], RightForeArm: ['y', 0.28],
  };
}
// Legs: fwd = thigh swing forward, knee = flex, flat = how level the sole stays.
function leg(P, side, fwd, knee, flat = 1, extra = 0) {
  P[side + 'UpLeg'] = ['x', -fwd];
  P[side + 'Leg'] = ['x', knee];
  P[side + 'Foot'] = ['x', -(knee - fwd) * flat + extra];
}
// Arms: swing forward (+) / back (-), elbow bend, with the arm hanging down.
function arm(P, side, swing, bend, down = ARM_DOWN, out = 0) {
  const s = side === 'Left' ? -1 : 1;
  P[side + 'Arm'] = ['z', s * (down - out), 'x', -swing];
  P[side + 'ForeArm'] = ['y', s * bend];
}

const POSES = {
  Idle: { duration: 4, loop: true, fn(t) {
    const P = stand(), b = Math.sin((t / 4) * Math.PI * 2), b2 = Math.sin((t / 4) * Math.PI * 2 + 1.1);
    P.Spine = ['x', 0.012 * b]; P.Chest = ['x', 0.025 * b];
    P.Head = ['y', 0.07 * b2, 'x', -0.02 * b];
    arm(P, 'Left', 0.03 * b2, 0.3 + 0.04 * b, ARM_DOWN + 0.02 * b);
    arm(P, 'Right', -0.03 * b2, 0.3 + 0.04 * b, ARM_DOWN + 0.02 * b);
    leg(P, 'Left', 0.02, 0.05); leg(P, 'Right', 0.02, 0.05);
    P.LeftUpLeg = ['x', -0.02, 'z', 0.03]; P.RightUpLeg = ['x', -0.02, 'z', -0.03];
    return { P, shift: [0.004 * b2, 0, 0] };
  } },

  Walk: { duration: 1, loop: true, fn(t) {
    const P = stand(), a = t * Math.PI * 2, s = Math.sin(a);
    const side = (name, ph) => {
      const f = 0.5 * Math.sin(a + ph);
      const sw = 0.5 + 0.5 * Math.cos(a + ph); // 1 while the leg swings forward
      leg(P, name, f, 0.12 + 0.85 * sw * sw, 1 - 0.35 * sw, 0);
      arm(P, name, -0.45 * Math.sin(a + ph), 0.4 + 0.25 * Math.max(0, -Math.sin(a + ph)));
    };
    side('Left', 0); side('Right', Math.PI);
    P.Hips = ['y', -0.1 * s, 'z', 0.025 * s];
    P.Spine = ['y', 0.1 * s, 'x', 0.03]; P.Chest = ['y', 0.09 * s, 'x', 0.03];
    P.Head = ['y', -0.09 * s, 'x', -0.04];
    return { P };
  } },

  Run: { duration: 0.64, loop: true, fn(t) {
    const P = stand(), a = (t / 0.64) * Math.PI * 2, s = Math.sin(a);
    const side = (name, ph) => {
      const f = 0.85 * Math.sin(a + ph) + 0.2;
      const sw = 0.5 + 0.5 * Math.cos(a + ph - 0.35);
      leg(P, name, f, 0.3 + 1.45 * Math.pow(sw, 1.4), 0.55, 0.1);
      arm(P, name, -0.95 * Math.sin(a + ph), 1.45 + 0.2 * Math.sin(a + ph), ARM_DOWN + 0.1);
    };
    side('Left', 0); side('Right', Math.PI);
    P.Hips = ['y', -0.16 * s, 'x', 0.14];
    P.Spine = ['y', 0.16 * s, 'x', 0.1]; P.Chest = ['y', 0.14 * s, 'x', 0.08];
    P.Head = ['y', -0.14 * s, 'x', -0.24];
    return { P, lift: 0.05 * s * s };
  } },

  Jump: { duration: 1.3, loop: false, fn(t) {
    const P = stand(), u = t / 1.3;
    let c, air = 0;
    if (u < 0.22) c = ease(u / 0.22);
    else if (u < 0.3) c = 1 - ease((u - 0.22) / 0.08);
    else if (u < 0.7) { c = 0; air = (u - 0.3) / 0.4; }
    else if (u < 0.8) c = 0.75 * ease((u - 0.7) / 0.1);
    else c = 0.75 * (1 - ease((u - 0.8) / 0.2));
    const h = air > 0 ? 4 * air * (1 - air) : 0;
    const tuck = Math.sin(Math.PI * air) * 0.55;
    for (const sd of ['Left', 'Right']) {
      leg(P, sd, 0.8 * c + 0.55 * tuck, 1.6 * c + 1.1 * tuck, air > 0 ? 0.3 : 1, 0.5 * h);
      arm(P, sd, -0.7 * c + 2.5 * ease(h * 1.4), 0.3 + 0.5 * c, ARM_DOWN, 0.15 * h);
    }
    P.Hips = ['x', 0.25 * c]; P.Spine = ['x', 0.2 * c - 0.06 * h]; P.Chest = ['x', 0.12 * c - 0.06 * h];
    P.Head = ['x', -0.3 * c - 0.12 * h];
    return { P, lift: 0.55 * h };
  } },

  Wave: { duration: 2.4, loop: false, fn(t) {
    const P = stand(), u = t / 2.4;
    const e = ease(u / 0.2) * (1 - ease((u - 0.8) / 0.2));
    const w = Math.sin(t * Math.PI * 2 * 2.2);
    P.RightArm = ['z', ARM_DOWN + (-0.75 - ARM_DOWN) * e, 'x', -0.15 * e];
    P.RightForeArm = ['y', 0.28 * (1 - e), 'z', (-0.95 + 0.4 * w) * e];
    P.RightHand = ['z', 0.25 * w * e];
    P.Head = ['z', -0.1 * e, 'y', -0.1 * e];
    P.Chest = ['z', -0.04 * e]; P.Spine = ['z', -0.03 * e];
    arm(P, 'Left', 0, 0.3, ARM_DOWN + 0.03 * e);
    leg(P, 'Left', 0.02, 0.05); leg(P, 'Right', 0.02, 0.05);
    P.LeftUpLeg = ['x', -0.02, 'z', 0.03]; P.RightUpLeg = ['x', -0.02, 'z', -0.03];
    return { P };
  } },
};

function buildClips(root, bones, boneIndex, world) {
  const FPS = 30;
  // sole contact points, expressed in each foot bone's space
  const soles = [];
  for (const side of ['Left', 'Right']) {
    const bone = bones[boneIndex[side + 'Foot']], base = world[side + 'Foot'];
    for (const dx of [-0.07, 0.07]) for (const z of [-0.085, 0.22]) {
      soles.push({ bone, local: new THREE.Vector3(base.x + dx, 0, z).sub(base) });
    }
  }
  const hips = bones[boneIndex.Hips], hipsBind = world.Hips.clone(), v = new THREE.Vector3();
  const ident = new THREE.Quaternion();

  function applyPose(def, t) {
    const { P, shift = [0, 0, 0], lift = 0 } = def.fn(t);
    for (const b of bones) b.quaternion.copy(P[b.name] ? rot(...P[b.name]) : ident);
    hips.position.set(hipsBind.x + shift[0], hipsBind.y, hipsBind.z + shift[2]);
    root.updateMatrixWorld(true);
    let minY = Infinity;
    for (const s of soles) minY = Math.min(minY, v.copy(s.local).applyMatrix4(s.bone.matrixWorld).y);
    hips.position.y = hipsBind.y - minY + lift; // keep the lowest sole on the ground
  }

  const clips = [];
  for (const [name, def] of Object.entries(POSES)) {
    const n = Math.round(def.duration * FPS);
    const times = [], pos = [], quats = bones.map(() => []);
    for (let i = 0; i <= n; i++) {
      const t = (i / n) * def.duration;
      applyPose(def, def.loop && i === n ? 0 : t);
      times.push(t);
      pos.push(hips.position.x, hips.position.y, hips.position.z);
      bones.forEach((b, k) => quats[k].push(b.quaternion.x, b.quaternion.y, b.quaternion.z, b.quaternion.w));
    }
    const tracks = [new THREE.VectorKeyframeTrack('Hips.position', times, pos)];
    bones.forEach((b, k) => {
      const q = quats[k];
      let animated = false;
      for (let i = 4; i < q.length && !animated; i++) if (Math.abs(q[i] - q[i % 4]) > 1e-6) animated = true;
      const still = !animated && Math.abs(q[3] - 1) < 1e-6;
      if (!still) tracks.push(new THREE.QuaternionKeyframeTrack(b.name + '.quaternion', times, q));
    });
    clips.push(new THREE.AnimationClip(name, def.duration, tracks));
  }
  // leave the rig in its bind pose
  for (const b of bones) b.quaternion.identity();
  hips.position.copy(hipsBind);
  root.updateMatrixWorld(true);
  return clips;
}
