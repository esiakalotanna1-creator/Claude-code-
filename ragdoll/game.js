/* 40 Ways to Kill the Ragdoll — a cartoon physics sandbox (Three.js r128 + Cannon.js 0.6.2).
 *
 * This first build is the stage: a closed grey 3D room and a fully jointed ragdoll you can grab anywhere,
 * drag around, drop and fling against the walls, plus the 40 "ways" (weapons, traps, disasters) to wreck him with.
 *
 * Structure of this file
 *   1. config + helpers
 *   2. renderer, fixed front camera, the wooden back wall + screen-edge collision walls
 *   3. ragdoll: 15 rigid bodies joined by cone-twist / point constraints, with a soft cartoon look
 *   4. grabbing: raycast -> kinematic "finger" body -> point constraint, so you hold the doll by any limb
 *   5. feedback: vibration + thump sounds on hard impacts
 *   6. main loop and run(mode) entry (edit mode only shows the static stage)
 */
import { preloadImages, setLoaderProgress, hideLoader } from './loader.js';
import { TIERS, initialTier, AutoQuality } from './quality.js';
import { makeSpriteBatch } from './batch.js';

(function () {
  'use strict';
  const THREE = window.THREE, CANNON = window.CANNON;
  const PI = Math.PI, clamp = (v, a, b) => Math.max(a, Math.min(b, v));

  /* ------------------------------------------------------------------ 1. config */
  const DEF = { gravity: 24, bounce: 0.25, scale: 0.9, grab: 1, unlockAll: false };
  const cfg = () => Object.assign({}, DEF, window.gameConfig || {});
  let RW = 4.3, RH = 7.6, RD = 1.6;            // play box (x, y, z): matches the screen edges; floor at y = 0, centred on x/z
  let CAMD = 20;                                // fixed camera distance (set from the box size)
  let FIX = 1 / 120, MAXSUB = 6;            // physics step + max steps per frame (both set by the quality tier)

  /* ------------------------------------------------------------------ 2. scene */
  let renderer, scene, camera, world, host, sun, mode = 'play';
  let Q = TIERS[2], qTier = 2, autoQ = null, fxKeep = 1, decalCap = 130; const batches = [];
  const cam = { yaw: 0, pitch: 0, dist: CAMD, tx: 0, ty: RH * 0.5, tz: 0 };
  const walls = [];
  const wallMat = new CANNON.Material('wall'), dollMat = new CANNON.Material('doll');
  let dollWallContact = null, dollDollContact = null;

  /* cardboard box look (like Kick the Buddy): lighter back panel with a soft glow, darker folded walls, a floor and ceiling strip seen in perspective */
  const texCache = {};
  function boxTex(kind) {
    if (texCache[kind]) return texCache[kind];
    const W = 256, H = 512, c = document.createElement('canvas'); c.width = W; c.height = H; const g = c.getContext('2d');
    const base = { back: '#d8a05a', floor: '#d0803e', ceil: '#dd9048', side: '#d07a38' }[kind];
    g.fillStyle = base; g.fillRect(0, 0, W, H);
    if (kind === 'back') {
      const rg = g.createRadialGradient(W / 2, H / 2, 10, W / 2, H / 2, H * 0.62); rg.addColorStop(0, 'rgba(255,214,130,.75)'); rg.addColorStop(.55, 'rgba(255,200,120,.25)'); rg.addColorStop(1, 'rgba(120,60,20,.45)');
      g.fillStyle = rg; g.fillRect(0, 0, W, H);
    }
    // cardboard corrugation
    g.globalAlpha = 0.07; g.fillStyle = '#4a230c';
    if (kind === 'back' || kind === 'floor' || kind === 'ceil') { for (let y = 0; y < H; y += 6) g.fillRect(0, y, W, 2); } else { for (let x = 0; x < W; x += 6) g.fillRect(x, 0, 2, H); }
    g.globalAlpha = 1;
    // darkening toward the edges and corners so the box has depth
    const dark = (x0, y0, x1, y1, a) => { const lg = g.createLinearGradient(x0, y0, x1, y1); lg.addColorStop(0, 'rgba(40,16,4,' + a + ')'); lg.addColorStop(1, 'rgba(40,16,4,0)'); g.fillStyle = lg; g.fillRect(0, 0, W, H); };
    if (kind === 'side') dark(0, 0, W, 0, 0.18);
    if (kind === 'floor') dark(0, H, 0, 0, 0.3);
    if (kind === 'ceil') dark(0, 0, 0, H, 0.15);
    const t = new THREE.CanvasTexture(c); t.anisotropy = 4; texCache[kind] = t; return t;
  }

  let roomObjs = [], woodImg = null;
  // real wood-plank picture for the back panel (generated asset); the canvas cardboard stays as the fallback
  function loadWood() {
    const a = window.lib && lib.getAsset && lib.getAsset('wood_back'); if (!a || !a.url) return;
    const ldr = new THREE.TextureLoader(); ldr.setCrossOrigin('anonymous');
    ldr.load(a.url, (tex) => { woodImg = tex; tex.anisotropy = 4; applyWood(); }, undefined, () => {});
  }
  const SHADE = { back: 1, left: 0.8, right: 0.8, ceiling: 0.95, floor: 0.82 };
  function applyWood() {
    if (!woodImg || !woodImg.image) return;
    const ia = (woodImg.image.width || 1) / (woodImg.image.height || 1);
    for (const o of roomObjs) {
      const m = o.mesh; if (!m) continue;
      const g = m.geometry.parameters, wa = g.width / g.height;
      const t = woodImg.clone(); t.needsUpdate = true; t.anisotropy = 4;
      if (ia > wa) { t.repeat.set(wa / ia, 1); t.offset.set((1 - wa / ia) / 2, 0); } else { t.repeat.set(1, ia / wa); t.offset.set(0, (1 - ia / wa) / 2); }
      if (m.material.map && m.material.map !== woodImg && m.material.map.isWoodClone) m.material.map.dispose();
      t.isWoodClone = true; m.material.map = t; const sh = SHADE[m.name] || 1; m.material.color.setRGB(sh, sh, sh); m.material.needsUpdate = true;
    }
  }
  function clearRoom() {
    for (const o of roomObjs) { if (o.mesh) { scene.remove(o.mesh); o.mesh.geometry.dispose(); o.mesh.material.dispose(); } if (o.body) world.removeBody(o.body); }
    roomObjs = []; walls.length = 0;
  }

  // The play area is exactly what the screen shows: collision walls sit on the screen edges (the open front of the box), with a modest depth.
  function buildRoom() {
    clearRoom();
    const w = Math.max(1, host.clientWidth || window.innerWidth), h = Math.max(1, host.clientHeight || window.innerHeight), asp = w / h;
    RD = 2.0; const t = Math.tan(camera.fov * PI / 360);
    RH = 7.6; RW = RH * asp; CAMD = RD / 2 + RH / (2 * t); cam.dist = CAMD; cam.ty = RH / 2; camera.aspect = asp; camera.updateProjectionMatrix();
    const defs = [ // name, position, rotation, plane size, texture kind
      ['floor', [0, 0, 0], [-PI / 2, 0], [RW, RD], 'floor'], ['ceiling', [0, RH, 0], [PI / 2, 0], [RW, RD], 'ceil'], ['back', [0, RH / 2, -RD / 2], [0, 0], [RW, RH], 'back'],
      ['front', [0, RH / 2, RD / 2], [0, PI], [RW, RH], null], ['left', [-RW / 2, RH / 2, 0], [0, PI / 2], [RD, RH], 'side'], ['right', [RW / 2, RH / 2, 0], [0, -PI / 2], [RD, RH], 'side']
    ];
    for (const [name, p, r, size, kind] of defs) {
      if (kind) {
        const m = new THREE.Mesh(new THREE.PlaneGeometry(size[0], size[1]), (kind === 'back' ? new THREE.MeshLambertMaterial({ map: boxTex(kind) }) : new THREE.MeshBasicMaterial({ map: boxTex(kind) })));
        m.name = name; m.position.set(p[0], p[1], p[2]); m.rotation.set(r[0], r[1], 0); m.receiveShadow = true; scene.add(m); roomObjs.push({ mesh: m });
      }
      const b = new CANNON.Body({ mass: 0, material: wallMat }); b.addShape(new CANNON.Plane());
      b.position.set(p[0], p[1], p[2]); b.quaternion.setFromEuler(r[0], r[1], 0, 'XYZ'); b.isWall = true; b.collisionFilterGroup = 2; b.collisionFilterMask = 1;
      world.addBody(b); walls.push(b); roomObjs.push({ body: b });
    }
    applyWood();
  }

  function initWorld() {
    world = new CANNON.World(); world.gravity.set(0, -cfg().gravity, 0);
    world.broadphase = new CANNON.NaiveBroadphase(); world.solver.iterations = 22; world.solver.tolerance = 0.0005; world.allowSleep = false;
    dollWallContact = new CANNON.ContactMaterial(dollMat, wallMat, { friction: 0.55, restitution: cfg().bounce, contactEquationStiffness: 2e7, contactEquationRelaxation: 3, frictionEquationStiffness: 1e7 });
    dollDollContact = new CANNON.ContactMaterial(dollMat, dollMat, { friction: 0.25, restitution: 0.05, contactEquationStiffness: 1e7, contactEquationRelaxation: 3 });
    world.addContactMaterial(dollWallContact); world.addContactMaterial(dollDollContact);
  }

  function initScene() {
    host = document.getElementById('gl');
    qTier = guessTier(); autoQ = new AutoQuality(qTier);
    renderer = new THREE.WebGLRenderer({ antialias: qTier >= 2, powerPreference: 'high-performance', precision: qTier === 0 ? 'mediump' : 'highp' });
    renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap; renderer.setClearColor(0x3a3d43);
    host.appendChild(renderer.domElement);
    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(22, 9 / 16, 0.5, 160);
    scene.add(new THREE.HemisphereLight(0xffffff, 0x5d6066, 0.62));
    sun = new THREE.DirectionalLight(0xffffff, 0.55); sun.position.set(2, 9, 12); sun.castShadow = true;
    sun.shadow.mapSize.set(1024, 1024); const sc = sun.shadow.camera; sc.left = -5; sc.right = 5; sc.top = 6; sc.bottom = -6; sc.near = 1; sc.far = 30; sun.shadow.bias = -0.0008;
    scene.add(sun);
    buildRoom(); loadWood();
    applyQuality(qTier, true); onResize(); window.addEventListener('resize', onResize);
  }

  /* ---- auto graphics quality: start from a device guess, then follow the measured fps (quality.js) ---- */
  function guessTier() {
    const n = navigator, d = { cores: n.hardwareConcurrency, memory: n.deviceMemory, mobile: /Android|iPhone|iPad|iPod|Mobile/i.test(n.userAgent) || (n.maxTouchPoints > 1 && /Mac/.test(n.platform || '')) };
    try { const c = document.createElement('canvas'), gl = c.getContext('webgl'), ext = gl && gl.getExtension('WEBGL_debug_renderer_info'); if (ext) d.gpu = gl.getParameter(ext.UNMASKED_RENDERER_WEBGL); if (gl && gl.getParameter(gl.MAX_TEXTURE_SIZE) < 4096) d.lowGpu = true; const lc = gl && gl.getExtension('WEBGL_lose_context'); if (lc) lc.loseContext(); } catch (e) {}
    return initialTier(d);
  }
  function applyQuality(t, first) {
    qTier = t; Q = TIERS[t]; fxKeep = Q.fx; FIX = 1 / Q.step; MAXSUB = Q.sub; if (world) world.solver.iterations = Q.iters;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, Q.pr));
    if (!first) { const w = Math.max(1, host.clientWidth || window.innerWidth), h = Math.max(1, host.clientHeight || window.innerHeight); renderer.setSize(w, h, false); }
    const on = Q.shadow > 0, type = Q.shadow > 1 ? THREE.PCFSoftShadowMap : THREE.PCFShadowMap;
    if (first || on !== renderer.shadowMap.enabled || type !== renderer.shadowMap.type || (on && sun.shadow.mapSize.x !== Q.map)) {
      renderer.shadowMap.enabled = on; renderer.shadowMap.type = type; sun.castShadow = on;
      if (on) { sun.shadow.mapSize.set(Q.map, Q.map); if (sun.shadow.map) { sun.shadow.map.dispose(); sun.shadow.map = null; } }
      if (!first) scene.traverse((o) => { const m = o.material; if (m) (Array.isArray(m) ? m : [m]).forEach((x) => { x.needsUpdate = true; }); });
    }
    decalCap = Q.decals; for (let i = decalCap; i < bdecals.length; i++) bdecals[i].visible = false;
  }
  function watchQuality(ms) { if (!autoQ || document.hidden) return; const t = autoQ.sample(ms); if (t != null) applyQuality(t); }

  function onResize() {
    const w = Math.max(1, host.clientWidth || window.innerWidth), h = Math.max(1, host.clientHeight || window.innerHeight);
    renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
    buildRoom();
  }

  function placeCamera() {
    const cp = Math.cos(cam.pitch);
    camera.position.set(cam.tx + Math.sin(cam.yaw) * cp * cam.dist, cam.ty + Math.sin(cam.pitch) * cam.dist, cam.tz + Math.cos(cam.yaw) * cp * cam.dist);
    camera.lookAt(cam.tx, cam.ty, cam.tz);
    if (shakeAmp > 0) { camera.position.x += (Math.random() - 0.5) * shakeAmp; camera.position.y += (Math.random() - 0.5) * shakeAmp; }
  }

  /* ------------------------------------------------------------------ 3. ragdoll */
  const COL = { skin: 0xf4c38a, shirt: 0xe2573e, pants: 0x3b5f94, shoe: 0x5a3a2a, dark: 0x1e1e22, white: 0xffffff };
  const mats = {}; const matFor = (c) => mats[c] || (mats[c] = new THREE.MeshLambertMaterial({ color: c }));

  function roundBox(w, h, d, r, seg) {
    const g = new THREE.BoxGeometry(w, h, d, seg, seg, seg), p = g.attributes.position, n = g.attributes.normal, v = new THREE.Vector3(), inner = new THREE.Vector3();
    const hx = w / 2 - r, hy = h / 2 - r, hz = d / 2 - r;
    for (let i = 0; i < p.count; i++) {
      v.fromBufferAttribute(p, i); inner.set(clamp(v.x, -hx, hx), clamp(v.y, -hy, hy), clamp(v.z, -hz, hz)); v.sub(inner);
      if (v.lengthSq() > 1e-12) { v.normalize(); n.setXYZ(i, v.x, v.y, v.z); p.setXYZ(i, inner.x + v.x * r, inner.y + v.y * r, inner.z + v.z * r); }
    }
    return g;
  }
  function capsule(r, len, color) {
    const g = new THREE.Group(), m = matFor(color), c = new THREE.Mesh(new THREE.CylinderGeometry(r, r, Math.max(0.001, len), 14), m);
    const a = new THREE.Mesh(new THREE.SphereGeometry(r, 14, 10), m), b = a.clone(); a.position.y = len / 2; b.position.y = -len / 2;
    g.add(c, a, b); return g;
  }

  let doll = null; // { parts: {name: {body, group}}, joints: [], list: [] }
  const hitMeshes = [];

  function buildDoll(spawnY) {
    const S = cfg().scale, parts = {}, list = [], joints = [];
    const V = (x, y, z) => new CANNON.Vec3(x * S, y * S, z * S);
    function add(name, kind, dim, mass, pos, color, o) {
      o = o || {};
      const body = new CANNON.Body({ mass: mass * S, material: dollMat, linearDamping: 0.06, angularDamping: o.ad == null ? 0.45 : o.ad });
      let group = new THREE.Group();
      if (kind === 'sphere') { body.addShape(new CANNON.Sphere(dim[0] * S)); }
      else { body.addShape(new CANNON.Box(new CANNON.Vec3(dim[0] * S, dim[1] * S, dim[2] * S))); }
      body.position.set(pos[0] * S, pos[1] * S + (spawnY || 0), pos[2] * S);
      body.collisionFilterGroup = 1; body.collisionFilterMask = 3; body.allowSleep = false;
      // visuals
      if (kind === 'sphere') group.add(new THREE.Mesh(new THREE.SphereGeometry(dim[0] * S, 22, 16), matFor(color)));
      else if (o.look === 'capsule') group.add(capsule(dim[0] * S, (dim[1] * 2 - dim[0] * 2) * S, color));
      else group.add(new THREE.Mesh(roundBox(dim[0] * 2 * S, dim[1] * 2 * S, dim[2] * 2 * S, (o.r || 0.09) * S, 6), matFor(color)));
      if (o.face) addFace(group, dim[0] * S);
      group.traverse((m) => { if (m.isMesh) { m.castShadow = true; m.userData.part = name; hitMeshes.push(m); } });
      scene.add(group); world.addBody(body);
      const part = { name, body, group }; body.partRef = part; parts[name] = part; list.push(part);
      body.addEventListener('collide', (ev) => onImpact(ev, part));
      return part;
    }
    function joint(a, b, pivot, axis, angle, twist) {
      const A = parts[a].body, B = parts[b].body, pw = V(pivot[0], pivot[1], pivot[2]); pw.y += spawnY || 0; // body positions already include the spawn height
      const pa = new CANNON.Vec3(), pb = new CANNON.Vec3(); pw.vsub(A.position, pa); pw.vsub(B.position, pb);
      const ax = axis ? new CANNON.Vec3(axis[0], axis[1], axis[2]) : null;
      const c = angle == null ? new CANNON.PointToPointConstraint(A, pa, B, pb) : new CANNON.ConeTwistConstraint(A, B, { pivotA: pa, pivotB: pb, axisA: ax, axisB: ax.clone(), angle, twistAngle: twist == null ? 0.5 : twist, maxForce: 1e5 });
      c.collideConnected = false; world.addConstraint(c); joints.push({ c, a, b, pw });
    }
    // torso
    add('pelvis', 'box', [0.3, 0.16, 0.17], 4, [0, 1.30, 0], COL.pants, { r: 0.1 });
    add('chest', 'box', [0.34, 0.30, 0.19], 5, [0, 1.72, 0], COL.shirt, { r: 0.12 });
    add('head', 'sphere', [0.4], 2.5, [0, 2.43, 0], COL.skin, { face: true, ad: 0.6 });
    joint('pelvis', 'chest', [0, 1.44, 0], [0, 1, 0], 0.5, 0.35);
    joint('chest', 'head', [0, 2.03, 0], [0, 1, 0], 0.85, 0.6);
    // legs and arms (left = -x, right = +x as seen from the front)
    for (const s of [-1, 1]) {
      const n = s < 0 ? 'L' : 'R';
      add('thigh' + n, 'box', [0.12, 0.27, 0.12], 2, [s * 0.17, 0.93, 0], COL.pants, { look: 'capsule' });
      add('shin' + n, 'box', [0.1, 0.26, 0.1], 1.5, [s * 0.17, 0.40, 0], COL.pants, { look: 'capsule' });
      add('foot' + n, 'box', [0.11, 0.07, 0.2], 0.8, [s * 0.17, 0.07, 0.09], COL.shoe, { r: 0.06 });
      add('uarm' + n, 'box', [0.1, 0.25, 0.1], 1, [s * 0.44, 1.72, 0], COL.shirt, { look: 'capsule' });
      add('farm' + n, 'box', [0.09, 0.24, 0.09], 0.8, [s * 0.44, 1.23, 0], COL.skin, { look: 'capsule' });
      add('hand' + n, 'sphere', [0.11], 0.35, [s * 0.44, 0.88, 0], COL.skin);
      joint('pelvis', 'thigh' + n, [s * 0.17, 1.2, 0], [0, -1, 0], 1.15, 0.4);
      joint('thigh' + n, 'shin' + n, [s * 0.17, 0.66, 0], [0, -1, 0], 1.45, 0.15);
      joint('shin' + n, 'foot' + n, [s * 0.17, 0.14, 0], [0, -1, 0], 0.7, 0.2);
      joint('chest', 'uarm' + n, [s * 0.44, 1.97, 0], [0, -1, 0], 2.0, 0.6);
      joint('uarm' + n, 'farm' + n, [s * 0.44, 1.47, 0], [0, -1, 0], 1.45, 0.25);
      joint('farm' + n, 'hand' + n, [s * 0.44, 0.99, 0], null);
    }
    return { parts, list, joints };
  }

  function addFace(group, R) {
    const w = matFor(COL.white), d = matFor(COL.dark), F = { R, eyes: [], pups: [], brows: [], mouth: null };
    for (const s of [-1, 1]) {
      const e = new THREE.Mesh(new THREE.SphereGeometry(R * 0.25, 12, 10), w); e.position.set(s * R * 0.4, R * 0.2, R * 0.8); e.scale.set(1, 1.15, 0.7); group.add(e); F.eyes.push(e);
      const p = new THREE.Mesh(new THREE.SphereGeometry(R * 0.12, 10, 8), d); p.position.set(s * R * 0.4, R * 0.18, R * 0.95); group.add(p); F.pups.push(p);
      const b = new THREE.Mesh(new THREE.BoxGeometry(R * 0.34, R * 0.06, R * 0.05), d); b.position.set(s * R * 0.42, R * 0.52, R * 0.82); b.rotation.z = -s * 0.22; b.userData.s = s; group.add(b); F.brows.push(b);
    }
    const m = new THREE.Mesh(new THREE.TorusGeometry(R * 0.3, R * 0.045, 6, 18, PI), d); m.position.set(0, -R * 0.12, R * 0.88); m.rotation.z = PI; group.add(m); F.mouth = m;
    group.userData.face = F;
  }

  function removeDoll() {
    if (!doll) return;
    for (const j of doll.joints) world.removeConstraint(j.c);
    for (const p of doll.list) { world.removeBody(p.body); scene.remove(p.group); p.group.traverse((m) => { if (m.isMesh) { m.geometry.dispose(); const i = hitMeshes.indexOf(m); if (i >= 0) hitMeshes.splice(i, 1); } }); }
    doll = null;
  }
  function resetDoll() {
    release(); clearWays(); removeDoll(); doll = buildDoll(mode === 'play' ? RH * 0.55 : 0.02); for (const q of doll.list) buildBones(q);
    if (mode === 'play') for (const p of doll.list) { p.body.angularVelocity.set((Math.random() - 0.5) * 4, (Math.random() - 0.5) * 4, (Math.random() - 0.5) * 4); }
    sync();
  }
  function sync() { if (!doll) return; for (const p of doll.list) { p.group.position.copy(p.body.position); p.group.quaternion.copy(p.body.quaternion); } }

  /* ------------------------------------------------------------------ 4. grabbing */
  const hold = { on: false, body: null, con: null, target: new THREE.Vector3(), plane: new THREE.Plane(), id: -1, dot: null };
  const wv = new CANNON.Vec3(), ray = new THREE.Raycaster(), ndc = new THREE.Vector2(), tmp = new THREE.Vector3();
  const rayFrom = (cx, cy) => { const r = renderer.domElement.getBoundingClientRect(); ndc.set(((cx - r.left) / r.width) * 2 - 1, -(((cy - r.top) / r.height) * 2 - 1)); ray.setFromCamera(ndc, camera); };

  function grab(cx, cy) {
    if (!doll) return false; rayFrom(cx, cy);
    const hit = ray.intersectObjects(hitMeshes, false)[0]; if (!hit) return false;
    const part = doll.parts[hit.object.userData.part]; if (!part) return false;
    const wp = new CANNON.Vec3(hit.point.x, hit.point.y, hit.point.z);
    const hb = new CANNON.Body({ mass: 0, type: CANNON.Body.KINEMATIC }); hb.position.copy(wp); hb.collisionFilterGroup = 4; hb.collisionFilterMask = 0; world.addBody(hb);
    const local = part.body.pointToLocalFrame ? part.body.pointToLocalFrame(wp) : wp.vsub(part.body.position);
    const con = new CANNON.PointToPointConstraint(hb, new CANNON.Vec3(0, 0, 0), part.body, local, 2600 * cfg().grab * (part.body.mass + 4));
    world.addConstraint(con);
    hold.on = true; hold.body = hb; hold.con = con; hold.part = part; hold.local = local;
    camera.getWorldDirection(tmp); hold.plane.setFromNormalAndCoplanarPoint(tmp, hit.point); hold.target.copy(hit.point);
    haptic('tap'); const h = document.getElementById('hint'); if (h) h.classList.add('off');
    return true;
  }
  function moveHold(cx, cy) {
    if (!hold.on) return; rayFrom(cx, cy);
    if (ray.ray.intersectPlane(hold.plane, tmp)) {
      const mx = RW / 2 - 0.4, mz = RD / 2 - 0.4;
      hold.target.set(clamp(tmp.x, -mx, mx), clamp(tmp.y, 0.35, RH - 0.4), clamp(tmp.z, -mz, mz));
    }
  }
  function release() {
    if (!hold.on) return; world.removeConstraint(hold.con); world.removeBody(hold.body); hold.on = false; hold.con = null; hold.body = null; if (hold.dot) hold.dot.visible = false;
  }
  function driveHold() {
    if (!hold.on) return; const b = hold.body, k = 16 * cfg().grab;
    let vx = (hold.target.x - b.position.x) * k, vy = (hold.target.y - b.position.y) * k, vz = (hold.target.z - b.position.z) * k;
    const sp = Math.hypot(vx, vy, vz), cap = 55; if (sp > cap) { vx *= cap / sp; vy *= cap / sp; vz *= cap / sp; }
    b.velocity.set(vx, vy, vz);
  }

  /* ------------------------------------------------------------------ 5. feedback */
  let AC = null, lastImpact = 0;
  function audioInit() { if (AC) { if (AC.state === 'suspended') AC.resume(); return; } try { AC = new (window.AudioContext || window.webkitAudioContext)(); } catch (e) { AC = null; } }
  function thump(v) {
    if (!AC) return; const t = AC.currentTime, o = AC.createOscillator(), g = AC.createGain();
    o.type = 'sine'; o.frequency.setValueAtTime(150 + 60 * v, t); o.frequency.exponentialRampToValueAtTime(45, t + 0.14);
    g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.35 * v + 0.05, t + 0.01); g.gain.exponentialRampToValueAtTime(0.0001, t + 0.18);
    o.connect(g); g.connect(AC.destination); o.start(t); o.stop(t + 0.2);
  }
  function haptic(e) { try { if (window.lib && lib.haptics) lib.haptics.play(e); } catch (x) {} }
  function onImpact(ev, part) {
    const now = performance.now(); if (now - lastImpact < 90) return;
    const other = ev.body; if (!other || !other.isWall) return;
    const v = Math.abs(ev.contact.getImpactVelocityAlongNormal()); if (v < 6) return;
    lastImpact = now; const k = clamp((v - 6) / 22, 0, 1); if (v > 11) hurt(part, (v - 11) * 1.6, null, false, 'slam');
    haptic({ intensity: 0.25 + 0.75 * k, sharpness: 0.3 + 0.2 * k }); thump(k);
  }

  /* ------------------------------------------------------------------ 7. ways: tools, damage, effects */
  const TOOLS = [
    { id: 'hand', name: 'GRAB', asset: 'item_hand', emo: '✋', hint: 'DRAG THE RAGDOLL TO GRAB & FLING IT' },
    { id: 'hammer', name: 'HAMMER', asset: 'item_hammer', emo: '🔨', hint: 'TAP TO SMASH' },
    { id: 'pistol', name: 'PISTOL', asset: 'item_pistol', emo: '🔫', hint: 'HOLD TO SHOOT' },
    { id: 'shotgun', name: 'SHOTGUN', asset: 'item_shotgun', emo: '💥', hint: 'TAP TO BLAST' },
    { id: 'dynamite', name: 'DYNAMITE', asset: 'item_dynamite', emo: '🧨', hint: 'TAP TO DROP DYNAMITE' },
    { id: 'rocket', name: 'ROCKET', asset: 'item_rocket', emo: '🚀', hint: 'TAP TO FIRE A ROCKET' },
    { id: 'anvil', name: 'ANVIL', asset: 'item_anvil', emo: '⚓', hint: 'TAP TO DROP AN ANVIL' },
    { id: 'taser', name: 'TASER', asset: 'item_taser', emo: '⚡', hint: 'HOLD TO ZAP' },
    { id: 'flame', name: 'FLAMER', asset: 'item_flamethrower', emo: '🔥', hint: 'HOLD TO BURN' },
    { id: 'saw', name: 'BUZZSAW', asset: 'item_saw', emo: '🔄', hint: 'TAP TO THROW A BUZZSAW' },
    { id: 'hole', name: 'BLACK HOLE', asset: 'item_blackhole', emo: '🌀', hint: 'TAP TO OPEN A BLACK HOLE' },
    { id: 'katana', name: 'KATANA', asset: 'item_katana', emo: '\uD83D\uDDE1', hint: 'SWIPE TO SLICE' },
    { id: 'chainsaw', name: 'CHAINSAW', asset: 'item_chainsaw', emo: '\uD83E\uDE9A', hint: 'HOLD TO SHRED' },
    { id: 'grenade', name: 'GRENADE', asset: 'item_grenade', emo: '\uD83D\uDCA3', hint: 'TAP TO THROW A GRENADE' },
    { id: 'mine', name: 'LANDMINE', asset: 'item_landmine', emo: '\uD83D\uDFE2', hint: 'TAP TO PLANT A MINE' },
    { id: 'freeze', name: 'FREEZE RAY', asset: 'item_freezeray', emo: '\u2744', hint: 'HOLD TO FREEZE - THEN HIT HIM' },
    { id: 'ball', name: 'WRECK BALL', asset: 'item_wreckingball', emo: '\u26AB', hint: 'TAP TO DROP THE WRECKING BALL' },
    { id: 'lightning', name: 'LIGHTNING', asset: 'item_lightning', emo: '\u26C8', hint: 'TAP TO CALL A LIGHTNING STRIKE' },
    { id: 'guillotine', name: 'GUILLOTINE', asset: 'item_guillotine', emo: '\u2702', hint: 'TAP TO DROP THE GUILLOTINE' },
    { id: 'meteor', name: 'METEOR', asset: 'item_meteor', emo: '\u2604', hint: 'TAP TO CALL A METEOR' },
    { id: 'crossbow', name: 'CROSSBOW', asset: 'item_crossbow', emo: '\uD83C\uDFF9', hint: 'TAP TO NAIL HIM TO THE WALL' },
    { id: 'minigun', name: 'MINIGUN', asset: 'item_minigun', emo: '\uD83D\uDCA5', hint: 'HOLD - IT SPINS UP FAST' },
    { id: 'lasergrid', name: 'LASER GRID', asset: 'item_lasergrid', emo: '\uD83D\uDD34', hint: 'TAP TO DICE HIM' },
    { id: 'acid', name: 'ACID', asset: 'item_acid', emo: '\u2623', hint: 'TAP TO POUR ACID' },
    { id: 'beartrap', name: 'BEAR TRAP', asset: 'item_beartrap', emo: '\uD83E\uDDB7', hint: 'TAP TO SET A TRAP' },
    { id: 'nuke', name: 'NUKE', asset: 'item_nuke', emo: '\u2622', hint: 'TAP TO DROP THE NUKE' },
    { id: 'magnet', name: 'MAGNET', asset: 'item_magnet', emo: '\uD83E\uDDF2', hint: 'TAP TO LIFT HIM - THEN SLAM' },
    { id: 'cannon', name: 'CANNON', asset: 'item_cannon', emo: '\uD83D\uDCA3', hint: 'TAP TO FIRE THE CANNON' },
    { id: 'wasps', name: 'WASPS', asset: 'item_wasps', emo: '\uD83D\uDC1D', hint: 'TAP TO DROP A WASP NEST' },
    { id: 'airstrike', name: 'AIRSTRIKE', asset: 'item_airstrike', emo: '\u2708', hint: 'TAP TO CALL AN AIRSTRIKE' },
    { id: 'crusher', name: 'SPIKE CRUSH', asset: 'item_spikecrusher', emo: '\u2B07', hint: 'TAP TO DROP THE SPIKES' },
    { id: 'glove', name: 'BOXING GLOVE', asset: 'item_glove', emo: '\uD83E\uDD4A', hint: 'TAP TO PUNCH' },
    { id: 'piano', name: 'PIANO', asset: 'item_piano', emo: '\uD83C\uDFB9', hint: 'TAP TO DROP A PIANO' },
    { id: 'tornado', name: 'TORNADO', asset: 'item_tornado', emo: '\uD83C\uDF2A', hint: 'TAP TO SUMMON A TORNADO' },
    { id: 'sniper', name: 'SNIPER', asset: 'item_sniper', emo: '\uD83C\uDFAF', hint: 'TAP TO SNIPE - AIM FOR THE HEAD' },
    { id: 'fireworks', name: 'FIREWORKS', asset: 'item_fireworks', emo: '\uD83C\uDF86', hint: 'TAP TO LAUNCH FIREWORKS' },
    { id: 'ufo', name: 'UFO', asset: 'item_ufo', emo: '\uD83D\uDEF8', hint: 'TAP TO CALL THE UFO' },
    { id: 'shuriken', name: 'SHURIKEN', asset: 'item_shuriken', emo: '\u2734', hint: 'TAP TO THROW SHURIKENS' },
    { id: 'car', name: 'CAR', asset: 'item_car', emo: '\uD83D\uDE97', hint: 'TAP TO RUN HIM OVER' },
    { id: 'lava', name: 'LAVA', asset: 'item_lava', emo: '\uD83C\uDF0B', hint: 'TAP THE FLOOR TO ERUPT LAVA' }
  ];
  // where the muzzle sits on each 2D gun picture (fractions of its width / height from the centre) and how long it is drawn
  const GUNS = { sniper: { asset: 'item_sniper', L: 2.4, mx: 0.48, my: 0.06 }, pistol: { asset: 'item_pistol', L: 1.4, mx: 0.49, my: 0.31 }, shotgun: { asset: 'item_shotgun', L: 2.1, mx: 0.5, my: 0.37 }, rocket: { asset: 'item_rocket', L: 2.2, mx: 0.5, my: 0.06 }, taser: { asset: 'item_taser', L: 1.1, mx: 0.5, my: 0.2 }, chainsaw: { asset: 'item_chainsaw', L: 2.3, mx: 0.5, my: -0.25 }, freeze: { asset: 'item_freezeray', L: 1.8, mx: 0.5, my: 0.12 }, crossbow: { asset: 'item_crossbow', L: 2.0, mx: 0.5, my: 0.03 }, minigun: { asset: 'item_minigun', L: 2.4, mx: 0.475, my: -0.057 }, cannon: { asset: 'item_cannon', L: 2.5, mx: 0.475, my: 0.2486, rot: 0.35 }, katana: { asset: 'item_katana', L: 1.9, mx: 0, my: 0 }, flame: { asset: 'item_flamethrower', L: 1.9, mx: 0.5, my: 0.2 } };

  let tool = 'hand', totalDmg = 0, mood = 0, grace = 0, cd = 0, shakeAmp = 0, faceHurt = false;
  const assetUrl = (id) => { try { const a = window.lib && lib.getAsset && lib.getAsset(id); return a && a.url ? a.url : null; } catch (e) { return null; } };
  const assetAsp = (id, d) => { try { const a = lib.getAsset(id); if (a && a.aspect_ratio) return a.aspect_ratio[0] / a.aspect_ratio[1]; } catch (e) {} return d; };
  const rnd = (a, b) => a + Math.random() * (b - a);
  const V3 = (x, y, z) => new THREE.Vector3(x, y, z);

  /* ---- panel ---- */
  function buildPanel() {
    const grid = document.getElementById('grid'); if (!grid) return; grid.innerHTML = '';
    TOOLS.forEach((t) => {
      const c = document.createElement('div'); c.className = 'cell'; c.dataset.id = t.id;
      const u = assetUrl(t.asset);
      if (u) { const im = new Image(); im.src = u; im.alt = ''; im.draggable = false; c.appendChild(im); } else { const e = document.createElement('em'); e.textContent = t.emo; c.appendChild(e); }
      const l = document.createElement('i'); l.textContent = t.name; c.appendChild(l);
      const lk = document.createElement('div'); lk.className = 'lk'; c.appendChild(lk);
      c.addEventListener('click', () => { audioInit(); if (!isOwned(t.id)) { tryBuy(t.id, c); return; } setTool(t.id); });
      grid.appendChild(c);
    });
    refreshPanel(); coinHud();
  }
  /* ---- shop: coins earned by wrecking the ragdoll buy the locked ways ---- */
  const FREE = ['hand', 'hammer', 'pistol', 'shotgun', 'dynamite', 'rocket', 'anvil', 'taser', 'flame', 'saw'];
  const BUY_ORDER = ['hole', 'katana', 'grenade', 'mine', 'chainsaw', 'freeze', 'ball', 'lightning', 'guillotine', 'crossbow', 'minigun', 'lasergrid', 'acid', 'beartrap', 'magnet', 'cannon', 'meteor', 'wasps', 'crusher', 'airstrike', 'nuke', 'glove', 'shuriken', 'car', 'fireworks', 'piano', 'sniper', 'tornado', 'lava', 'ufo'];
  const PRICE = {}; BUY_ORDER.forEach((id, i) => { PRICE[id] = Math.round((100 + 50 * i) / 10) * 10; });
  let coins = 0, lastDmgC = 0; const owned = new Set(FREE);
  // progress lives in Astrocade's per-player save (lib.saveUserGameState); localStorage is blocked in the sandbox
  let shopReady = false, shopTimer = null, shopDirty = false;
  function applyShop(sv) { if (!sv || typeof sv !== 'object') return; coins = Math.max(coins, Number(sv.coins) || 0); (Array.isArray(sv.owned) ? sv.owned : []).forEach((i) => owned.add(i)); }
  function loadShop() {
    const done = () => { shopReady = true; coinHud(); refreshPanel(); if (shopDirty) saveShop(true); };
    try {
      Promise.resolve(lib.getUserGameState()).then((r) => { applyShop(r && (r.state !== undefined ? r.state : r)); done(); }).catch(done);
    } catch (e) { done(); }
  }
  function flushShop() {
    shopTimer = null; shopDirty = false;
    try { Promise.resolve(lib.saveUserGameState({ coins: Math.floor(coins), owned: Array.from(owned) })).catch(() => {}); } catch (e) {}
  }
  function saveShop(now) {
    shopDirty = true; if (!shopReady) return; // never overwrite the saved game before it has loaded
    if (now) { clearTimeout(shopTimer); flushShop(); } else if (!shopTimer) shopTimer = setTimeout(flushShop, 1500);
  }
  const isOwned = (id) => !!cfg().unlockAll || owned.has(id) || PRICE[id] == null; // unlockAll: creator test switch in the settings panel
  function coinHud(bump) { const v = document.getElementById('cv'); if (v) v.textContent = Math.floor(coins).toLocaleString('en-US'); const c = document.getElementById('coins'); if (c && bump) { c.classList.add('bump'); clearTimeout(coinHud.t); coinHud.t = setTimeout(() => c.classList.remove('bump'), 140); } }
  function addCoins(n) { if (!(n > 0)) return; coins += n; coinHud(true); const f = Math.floor(coins / 5); if (f !== addCoins.f) { addCoins.f = f; saveShop(); } }
  function refreshPanel() {
    document.querySelectorAll('.cell').forEach((c) => { const id = c.dataset.id, lockd = !isOwned(id); c.classList.toggle('locked', lockd); const lk = c.querySelector('.lk'); if (lk) lk.innerHTML = lockd ? '<s>\uD83D\uDD12</s><b>' + PRICE[id] + '</b>' : ''; });
  }
  function tryBuy(id, cell) {
    const pr = PRICE[id], t = TOOLS.find((x) => x.id === id);
    if (Math.floor(coins) >= pr) {
      coins -= pr; owned.add(id); saveShop(true); coinHud(true); refreshPanel(); if (cell) { cell.classList.remove('buy'); void cell.offsetWidth; cell.classList.add('buy'); }
      sfx.clank && sfx.clank(); sfx.beep && sfx.beep(); haptic('thud'); flash(0.25, '#ffe36a'); setTool(id); hint('UNLOCKED! ' + t.hint);
    } else {
      if (cell) { cell.classList.remove('shk'); void cell.offsetWidth; cell.classList.add('shk'); } haptic('tick');
      hint('NEED ' + (pr - Math.floor(coins)) + ' MORE COINS - WRECK HIM!');
    }
  }
  function hint(txt) { const h = document.getElementById('hint'); if (!h) return; h.textContent = txt; h.classList.remove('off'); clearTimeout(hint.t); hint.t = setTimeout(() => h.classList.add('off'), 2600); }
  function setTool(id) {
    endUse(); release(); hold.id = -1; tool = id;
    document.querySelectorAll('.cell').forEach((c) => c.classList.toggle('on', c.dataset.id === id));
    hint(TOOLS.find((t) => t.id === id).hint); haptic('tick');
  }

  /* ---- sound (all synthesised) ---- */
  let noiseB = null;
  function noiseBuf() { if (noiseB || !AC) return noiseB; noiseB = AC.createBuffer(1, AC.sampleRate * 2, AC.sampleRate); const d = noiseB.getChannelData(0); for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1; return noiseB; }
  function sNoise(dur, f0, f1, gain, type, q) {
    if (!AC) return; const t = AC.currentTime, s = AC.createBufferSource(), f = AC.createBiquadFilter(), g = AC.createGain();
    s.buffer = noiseBuf(); f.type = type || 'lowpass'; f.Q.value = q || 0.8; f.frequency.setValueAtTime(f0, t); f.frequency.exponentialRampToValueAtTime(Math.max(30, f1), t + dur);
    g.gain.setValueAtTime(gain, t); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    s.connect(f); f.connect(g); g.connect(AC.destination); s.start(t, Math.random()); s.stop(t + dur + 0.05);
  }
  function sTone(type, f0, f1, dur, gain) {
    if (!AC) return; const t = AC.currentTime, o = AC.createOscillator(), g = AC.createGain();
    o.type = type; o.frequency.setValueAtTime(f0, t); o.frequency.exponentialRampToValueAtTime(Math.max(20, f1), t + dur);
    g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(gain, t + 0.008); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(g); g.connect(AC.destination); o.start(t); o.stop(t + dur + 0.05);
  }
  const sfx = {
    shot() { sNoise(0.13, 4200, 500, 0.45); sTone('square', 200, 60, 0.1, 0.18); },
    shotgun() { sNoise(0.34, 3000, 160, 0.8); sTone('sawtooth', 120, 36, 0.28, 0.35); },
    boom(k) { sNoise(0.95, 1800, 70, 0.9 * k); sTone('sine', 95, 26, 0.85, 0.85 * k); },
    clank() { sTone('square', 340, 150, 0.2, 0.18); sTone('triangle', 190, 85, 0.35, 0.3); sNoise(0.14, 6000, 1500, 0.3, 'highpass'); },
    smash() { sTone('sine', 150, 45, 0.18, 0.55); sNoise(0.1, 2200, 400, 0.35); },
    launch() { sNoise(0.6, 900, 3000, 0.4, 'bandpass', 0.6); sTone('sawtooth', 90, 220, 0.4, 0.14); },
    tick() { sTone('square', 1900, 1500, 0.025, 0.08); },
    screech() { sTone('sawtooth', 1500, 1000, 0.09, 0.07); sNoise(0.08, 7000, 3000, 0.16, 'highpass'); },
    hole() { sTone('sine', 55, 260, 3.2, 0.5); sNoise(3.2, 250, 1400, 0.22, 'bandpass', 1.2); },
    pop() { sTone('sine', 400, 40, 0.3, 0.6); sNoise(0.35, 5000, 200, 0.5); },
    thud() { sTone('sine', 110, 40, 0.22, 0.6); },
    snap() { sNoise(0.06, 5200, 1500, 0.6, 'highpass'); sTone('square', 190, 60, 0.09, 0.3); setTimeout(() => { sNoise(0.14, 900, 200, 0.5); sTone('sine', 90, 35, 0.2, 0.5); }, 45); },
    whoosh() { sNoise(0.35, 400, 2400, 0.25, 'bandpass', 0.7); }
  };
  const loops = {};
  function loopStart(name) {
    if (!AC || loops[name]) return; const t = AC.currentTime, g = AC.createGain(), src = [];
    g.gain.value = 0.0001; g.gain.exponentialRampToValueAtTime(name === 'flame' ? 0.34 : name === 'chainsaw' ? 0.3 : 0.22, t + 0.06); g.connect(AC.destination);
    const n = AC.createBufferSource(); n.buffer = noiseBuf(); n.loop = true; const f = AC.createBiquadFilter();
    if (name === 'flame') { f.type = 'bandpass'; f.frequency.value = 520; f.Q.value = 0.55; } else if (name === 'chainsaw') { f.type = 'lowpass'; f.frequency.value = 2200; } else { f.type = 'highpass'; f.frequency.value = 2600; }
    n.connect(f); f.connect(g); n.start(); src.push(n);
    if (name === 'taser') { const o = AC.createOscillator(), lfo = AC.createOscillator(), lg = AC.createGain(), og = AC.createGain(); o.type = 'sawtooth'; o.frequency.value = 118; lfo.frequency.value = 31; lg.gain.value = 0.09; og.gain.value = 0.09; lfo.connect(lg); lg.connect(og.gain); o.connect(og); og.connect(g); o.start(); lfo.start(); src.push(o, lfo); }
    if (name === 'chainsaw') { const o = AC.createOscillator(), lfo = AC.createOscillator(), lg = AC.createGain(), og = AC.createGain(); o.type = 'sawtooth'; o.frequency.value = 78; lfo.frequency.value = 23; lg.gain.value = 0.12; og.gain.value = 0.16; lfo.connect(lg); lg.connect(og.gain); o.connect(og); og.connect(g); o.start(); lfo.start(); src.push(o, lfo); }
    loops[name] = { g, src };
  }
  function loopStop(name) { const l = loops[name]; if (!l) return; const t = AC.currentTime; try { l.g.gain.cancelScheduledValues(t); l.g.gain.setValueAtTime(l.g.gain.value, t); l.g.gain.exponentialRampToValueAtTime(0.0001, t + 0.12); l.src.forEach((s) => s.stop(t + 0.15)); } catch (e) {} delete loops[name]; }
  function hapStart(i, s) { try { if (window.lib && lib.haptics && lib.haptics.start) lib.haptics.start({ intensity: i, sharpness: s }); } catch (e) {} }
  function hapStop() { try { if (window.lib && lib.haptics && lib.haptics.stop) lib.haptics.stop(); } catch (e) {} }

  /* ---- particles, rings, bolts, decals ---- */
  let glowT = null, smokeT = null; const P = { add: [], norm: [], live: [] };
  function radialTex(stops) {
    const c = document.createElement('canvas'); c.width = c.height = 128; const g = c.getContext('2d'), gr = g.createRadialGradient(64, 64, 0, 64, 64, 64);
    stops.forEach((s) => gr.addColorStop(s[0], s[1])); g.fillStyle = gr; g.fillRect(0, 0, 128, 128); const t = new THREE.CanvasTexture(c); return t;
  }
  function initFx() {
    glowT = radialTex([[0, 'rgba(255,255,255,1)'], [0.25, 'rgba(255,255,255,.75)'], [0.6, 'rgba(255,255,255,.18)'], [1, 'rgba(255,255,255,0)']]);
    smokeT = radialTex([[0, 'rgba(255,255,255,.9)'], [0.55, 'rgba(255,255,255,.45)'], [1, 'rgba(255,255,255,0)']]);
    // all particles render as two batched point clouds (batch.js) instead of 1100 separate sprites
    batches.length = 0; const smokeB = makeSpriteBatch(THREE, scene, 420, smokeT, false), addB = makeSpriteBatch(THREE, scene, 700, glowT, true); smokeB.points.renderOrder = 5; batches.push(smokeB, addB);
    P.add = addB.slots.slice(); P.norm = smokeB.slots.slice(); P.live.length = 0;
    for (let i = 0; i < 40; i++) { const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(13 * 3), 3)); const l = new THREE.Line(g, new THREE.LineBasicMaterial({ color: 0xbfe6ff, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false })); l.visible = false; l.frustumCulled = false; scene.add(l); bolts.push(l); }
  }
  // o: x,y,z, vx,vy,vz, life, s0,s1, c0,c1, g (gravity), drag, a (opacity), ap (fade power), smoke
  function emit(o) {
    if (fxKeep < 1 && Math.random() > fxKeep) return; // cheaper tiers drop a share of the purely cosmetic particles
    const pool = o.smoke ? P.norm : P.add, s = pool.pop(); if (!s) return;
    s.position.set(o.x, o.y, o.z == null ? 0.92 : o.z); s.scale.setScalar(o.s0); s.material.color.setHex(o.c0); s.material.opacity = o.a == null ? 1 : o.a; s.visible = true;
    const r = s.rec || (s.rec = { s, c0: new THREE.Color(), c1: new THREE.Color() }); // reused record: no allocations per particle
    r.pool = pool; r.vx = o.vx || 0; r.vy = o.vy || 0; r.vz = o.vz || 0; r.life = r.max = o.life; r.s0 = o.s0; r.s1 = o.s1 == null ? o.s0 : o.s1; r.c0.setHex(o.c0); r.c1.setHex(o.c1 == null ? o.c0 : o.c1);
    r.g = o.g || 0; r.drag = o.drag == null ? 0.98 : o.drag; r.a = o.a == null ? 1 : o.a; r.ap = o.ap == null ? 1 : o.ap; P.live.push(r);
  }
  function updParticles(dt) {
    for (let i = P.live.length - 1; i >= 0; i--) {
      const p = P.live[i]; p.life -= dt;
      if (p.life <= 0) { p.s.visible = false; p.pool.push(p.s); P.live[i] = P.live[P.live.length - 1]; P.live.pop(); continue; }
      const t = 1 - p.life / p.max, k = Math.pow(p.drag, dt * 60); p.vx *= k; p.vy = p.vy * k - p.g * dt; p.vz *= k;
      p.s.position.x += p.vx * dt; p.s.position.y += p.vy * dt; p.s.position.z = Math.min(1.0, p.s.position.z + p.vz * dt);
      p.s.scale.setScalar(p.s0 + (p.s1 - p.s0) * t); p.s.material.color.copy(p.c0).lerp(p.c1, t); p.s.material.opacity = p.a * Math.pow(1 - t, p.ap);
    }
  }
  const bolts = []; let boltUsed = 0;
  function bolt(a, b, color, amp) {
    if (boltUsed >= bolts.length) return; const L = bolts[boltUsed++], pos = L.geometry.attributes.position, n = 12, dx = b.x - a.x, dy = b.y - a.y, len = Math.hypot(dx, dy) || 1, px = -dy / len, py = dx / len;
    for (let i = 0; i <= n; i++) { const t = i / n, env = Math.sin(t * PI), off = (i === 0 || i === n) ? 0 : (Math.random() - 0.5) * 2 * amp * env; pos.setXYZ(i, a.x + dx * t + px * off, a.y + dy * t + py * off, 0.95); }
    pos.needsUpdate = true; L.material.color.setHex(color); L.material.opacity = 0.65 + Math.random() * 0.35; L.visible = true;
  }
  function ring(p, maxR, color, dur) {
    const m = new THREE.Mesh(new THREE.RingGeometry(0.84, 1, 56), new THREE.MeshBasicMaterial({ color, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide }));
    m.position.set(p.x, p.y, 0.95); track(m); let t = 0;
    addFx((dt) => { t += dt / dur; const e = 1 - Math.pow(1 - Math.min(1, t), 3); m.scale.setScalar(Math.max(0.01, maxR * e)); m.material.opacity = Math.max(0, 1 - t); if (t >= 1) { scene.remove(m); m.geometry.dispose(); m.material.dispose(); return false; } return true; });
  }
  const effects = []; const addFx = (u) => effects.push(u);
  const decals = [];
  function decalTex(kind) {
    const c = document.createElement('canvas'); c.width = c.height = 128; const g = c.getContext('2d');
    if (kind === 'hole') { const gr = g.createRadialGradient(64, 64, 4, 64, 64, 60); gr.addColorStop(0, 'rgba(10,6,4,1)'); gr.addColorStop(0.35, 'rgba(25,14,8,.95)'); gr.addColorStop(0.55, 'rgba(60,34,16,.5)'); gr.addColorStop(1, 'rgba(60,34,16,0)'); g.fillStyle = gr; g.fillRect(0, 0, 128, 128); g.strokeStyle = 'rgba(30,16,8,.6)'; g.lineWidth = 2; for (let i = 0; i < 7; i++) { const a = Math.random() * 6.28; g.beginPath(); g.moveTo(64 + Math.cos(a) * 14, 64 + Math.sin(a) * 14); g.lineTo(64 + Math.cos(a) * rnd(26, 58), 64 + Math.sin(a) * rnd(26, 58)); g.stroke(); } }
    else { const gr = g.createRadialGradient(64, 64, 6, 64, 64, 62); gr.addColorStop(0, 'rgba(8,5,3,.6)'); gr.addColorStop(0.5, 'rgba(25,14,8,.35)'); gr.addColorStop(1, 'rgba(25,14,8,0)'); g.fillStyle = gr; g.fillRect(0, 0, 128, 128); for (let i = 0; i < 14; i++) { g.fillStyle = 'rgba(15,8,4,.5)'; g.beginPath(); g.arc(rnd(20, 108), rnd(20, 108), rnd(2, 6), 0, 6.28); g.fill(); } }
    return new THREE.CanvasTexture(c);
  }
  const decalTexs = {};
  function decal(x, y, size, kind) {
    if (!decalTexs[kind]) decalTexs[kind] = decalTex(kind);
    const m = new THREE.Mesh(new THREE.PlaneGeometry(size, size), new THREE.MeshBasicMaterial({ map: decalTexs[kind], transparent: true, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -2 }));
    m.position.set(x, y, -RD / 2 + 0.012); m.rotation.z = Math.random() * 6.28; scene.add(m); decals.push({ m, t: 0, life: kind === 'hole' ? 12 : 14 });
    if (decals.length > 46) { const o = decals.shift(); scene.remove(o.m); o.m.geometry.dispose(); o.m.material.dispose(); }
  }
  function updDecals(dt) { for (let i = decals.length - 1; i >= 0; i--) { const d = decals[i]; d.t += dt; if (d.t > d.life - 2) d.m.material.opacity = Math.max(0, (d.life - d.t) / 2); if (d.t >= d.life) { scene.remove(d.m); d.m.geometry.dispose(); d.m.material.dispose(); decals.splice(i, 1); } } }
  function shake(a) { shakeAmp = Math.max(shakeAmp, a); }
  function flash(a, col) { const f = document.getElementById('flash'); if (!f) return; f.style.background = col || '#fff'; f.style.transition = 'none'; f.style.opacity = a; requestAnimationFrame(() => { f.style.transition = 'opacity .35s ease-out'; f.style.opacity = 0; }); }

  /* ---- damage numbers + HUD ---- */
  function popup(text, p, mag) {
    const el = document.createElement('div'), fx = document.getElementById('fx'); if (!fx || fx.children.length > 16) return;
    const v = V3(p.x, p.y, p.z || 0).project(camera), w = host.clientWidth, h = host.clientHeight;
    el.className = 'pop'; el.textContent = text; el.style.left = clamp((v.x * 0.5 + 0.5) * w, 40, w - 40) + 'px'; el.style.top = clamp((-v.y * 0.5 + 0.5) * h, 40, h - 20) + 'px';
    el.style.fontSize = 'calc(var(--u) * ' + (5 + Math.min(6, mag / 14)).toFixed(1) + ')'; el.style.color = mag >= 70 ? '#ff4040' : mag >= 28 ? '#ffb02e' : '#ffffff';
    fx.appendChild(el);
    if (el.animate) el.animate([{ transform: 'translate(-50%,-50%) scale(.5)', opacity: 0 }, { transform: 'translate(-50%,-95%) scale(1.15)', opacity: 1, offset: 0.18 }, { transform: 'translate(-50%,-230%) scale(1)', opacity: 0 }], { duration: 950, easing: 'ease-out' }).onfinish = () => el.remove(); else setTimeout(() => el.remove(), 900);
  }
  function dmgHud() { if (typeof coins !== 'undefined') { const dd = totalDmg - lastDmgC; lastDmgC = totalDmg; if (dd > 0) addCoins(dd * 0.08); } const b = document.getElementById('dmgv'); if (!b) return; b.textContent = totalDmg.toLocaleString('en-US'); b.classList.add('bump'); clearTimeout(dmgHud.t); dmgHud.t = setTimeout(() => b.classList.remove('bump'), 110); }
  function setFace(h) {
    if (!doll) return; const f = doll.parts.head.group.userData.face; if (!f) return; const R = f.R;
    f.mouth.rotation.z = h ? 0 : PI; f.mouth.position.y = h ? -R * 0.22 : -R * 0.12; f.mouth.scale.set(h ? 0.75 : 1, h ? 1.5 : 1, 1);
    f.eyes.forEach((e, i) => { const s = i ? 1 : -1; e.scale.set(h ? 1.35 : 1, h ? 1.55 : 1.15, 0.7); }); f.pups.forEach((p) => p.scale.setScalar(h ? 0.55 : 1));
    f.brows.forEach((b) => { b.rotation.z = b.userData.s * (h ? 0.3 : -0.22); b.position.y = R * (h ? 0.62 : 0.52); });
  }
  /* ---- health, blood, tearing, death, x-ray ---- */
  const MAXHP = 700; let hp = MAXHP, dead = false, deadT = 0, kos = 0, slow = 0, onFire = 0, fireAcc = 0, flail = 0, hpShown = -1;
  const stumps = [], NOBLOOD = { burn: 1, shock: 1, hole: 1, bleed: 1, freeze: 1, acid: 1, sting: 1, laser: 1 };
  const SEV = { handL: 28, handR: 28, farmL: 60, farmR: 60, uarmL: 80, uarmR: 80, footL: 45, footR: 45, shinL: 70, shinR: 70, thighL: 85, thighR: 85, head: 170, chest: 360 };
  const SEVMUL = { laser: 2.5, slash: 2.2, saw: 1.9, blast: 2.2, smash: 1.5, crush: 1.7, bullet: 1.15 };
  const LABEL = { handL: 'HAND OFF!', handR: 'HAND OFF!', farmL: 'ARM SNAPPED!', farmR: 'ARM SNAPPED!', uarmL: 'ARM RIPPED OFF!', uarmR: 'ARM RIPPED OFF!', footL: 'FOOT OFF!', footR: 'FOOT OFF!', shinL: 'LEG SNAPPED!', shinR: 'LEG SNAPPED!', thighL: 'LEG TORN OFF!', thighR: 'LEG TORN OFF!', head: 'DECAPITATED!', chest: 'SPLIT IN HALF!' };
  function hpBar() {
    const v = Math.max(0, Math.round(hp)); if (v === hpShown) return; hpShown = v; const f = document.getElementById('hpf'); if (!f) return;
    f.style.width = (v / MAXHP * 100) + '%'; f.style.background = v < MAXHP * 0.3 ? '#ff3b30' : v < MAXHP * 0.6 ? '#ffb02e' : '#3ddc57';
  }
  function popupT(text, p, color, size) {
    const fx = document.getElementById('fx'); if (!fx || fx.children.length > 22) return; const el = document.createElement('div'), v = V3(p.x, p.y, 0).project(camera), w = host.clientWidth, h = host.clientHeight;
    el.className = 'pop'; el.textContent = text; el.style.left = clamp((v.x * 0.5 + 0.5) * w, 90, w - 90) + 'px'; const nowT = performance.now(); popupT.r = (popupT.r || []).filter((x) => nowT - x < 700); const kk = popupT.r.length; if (kk > 3) return; popupT.r.push(nowT); el.style.top = (clamp((-v.y * 0.5 + 0.5) * h, 80, h - 20) - kk * 50) + 'px'; el.style.fontSize = 'calc(var(--u) * ' + size + ')'; el.style.color = color; el.style.whiteSpace = 'nowrap';
    fx.appendChild(el); if (el.animate) el.animate([{ transform: 'translate(-50%,-50%) scale(.3) rotate(-6deg)', opacity: 0 }, { transform: 'translate(-50%,-90%) scale(1.25) rotate(3deg)', opacity: 1, offset: 0.16 }, { transform: 'translate(-50%,-130%) scale(1) rotate(0)', opacity: 1, offset: 0.7 }, { transform: 'translate(-50%,-190%) scale(1)', opacity: 0 }], { duration: 1300, easing: 'ease-out' }).onfinish = () => el.remove(); else setTimeout(() => el.remove(), 1200);
  }
  /* sounds for the body */
  let owT = 0;
  function yelp() { if (!AC) return; const t = AC.currentTime, o = AC.createOscillator(), g = AC.createGain(), f0 = rnd(520, 780); o.type = 'triangle'; o.frequency.setValueAtTime(f0, t); o.frequency.exponentialRampToValueAtTime(f0 * 1.4, t + 0.07); o.frequency.exponentialRampToValueAtTime(f0 * 0.5, t + 0.3); g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.2, t + 0.015); g.gain.exponentialRampToValueAtTime(0.0001, t + 0.32); o.connect(g); g.connect(AC.destination); o.start(t); o.stop(t + 0.35); }
  function scream() { if (!AC) return; const t = AC.currentTime, o = AC.createOscillator(), l = AC.createOscillator(), lg = AC.createGain(), g = AC.createGain(), f = AC.createBiquadFilter(); o.type = 'sawtooth'; l.frequency.value = 9; lg.gain.value = 40; l.connect(lg); lg.connect(o.frequency); o.frequency.setValueAtTime(980, t); o.frequency.exponentialRampToValueAtTime(260, t + 1.1); f.type = 'lowpass'; f.frequency.value = 2400; g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.28, t + 0.03); g.gain.exponentialRampToValueAtTime(0.0001, t + 1.15); o.connect(f); f.connect(g); g.connect(AC.destination); o.start(t); l.start(t); o.stop(t + 1.2); l.stop(t + 1.2); }
  /* blood */
  let dropT = null; const BD = { pool: [], live: [] }, bloodTexs = [], bdecals = []; let bdI = 0;
  function bloodTex() {
    const c = document.createElement('canvas'); c.width = c.height = 128; const g = c.getContext('2d'); g.translate(64, 64); g.fillStyle = 'rgba(125,8,10,.95)'; g.beginPath();
    for (let i = 0; i < 16; i++) { const a = (i / 16) * 6.283, r = rnd(14, 27); i ? g.lineTo(Math.cos(a) * r, Math.sin(a) * r) : g.moveTo(Math.cos(a) * r, Math.sin(a) * r); } g.closePath(); g.fill();
    g.fillStyle = 'rgba(80,4,6,.7)'; g.beginPath(); g.arc(rnd(-4, 4), rnd(-4, 4), rnd(8, 14), 0, 6.283); g.fill();
    for (let i = 0; i < 8; i++) { const a = Math.random() * 6.283, len = rnd(28, 60), w = rnd(2, 5); g.strokeStyle = 'rgba(125,8,10,.92)'; g.lineWidth = w; g.lineCap = 'round'; g.beginPath(); g.moveTo(Math.cos(a) * 16, Math.sin(a) * 16); g.lineTo(Math.cos(a) * len, Math.sin(a) * len); g.stroke(); g.fillStyle = 'rgba(125,8,10,.92)'; g.beginPath(); g.arc(Math.cos(a) * len, Math.sin(a) * len, w * 0.9, 0, 6.283); g.fill(); }
    for (let i = 0; i < 10; i++) { const a = Math.random() * 6.283, d = rnd(30, 60); g.fillStyle = 'rgba(140,10,12,.9)'; g.beginPath(); g.arc(Math.cos(a) * d, Math.sin(a) * d, rnd(1.5, 4.5), 0, 6.283); g.fill(); }
    return new THREE.CanvasTexture(c);
  }
  function initGore() {
    const c = document.createElement('canvas'); c.width = c.height = 64; const g = c.getContext('2d'), gr = g.createRadialGradient(32, 32, 0, 32, 32, 32); gr.addColorStop(0, '#fff'); gr.addColorStop(0.72, '#fff'); gr.addColorStop(1, 'rgba(255,255,255,0)'); g.fillStyle = gr; g.fillRect(0, 0, 64, 64); dropT = new THREE.CanvasTexture(c);
    const dropB = makeSpriteBatch(THREE, scene, 340, dropT, false); batches.push(dropB); BD.pool = dropB.slots.slice(); BD.live.length = 0;
    for (let i = 0; i < 4; i++) bloodTexs.push(bloodTex());
    for (let i = 0; i < 130; i++) { const m = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial({ map: bloodTexs[i % 4], transparent: true, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -3 })); m.visible = false; scene.add(m); bdecals.push(m); }
    // bullet streaks + casings
    const sc = document.createElement('canvas'); sc.width = 128; sc.height = 32; const sg = sc.getContext('2d'), lg = sg.createLinearGradient(0, 0, 128, 0); lg.addColorStop(0, 'rgba(255,180,60,0)'); lg.addColorStop(0.7, 'rgba(255,230,150,.85)'); lg.addColorStop(1, 'rgba(255,255,255,1)'); sg.fillStyle = lg; sg.fillRect(0, 0, 128, 32);
    sg.globalCompositeOperation = 'destination-in'; const vg = sg.createLinearGradient(0, 0, 0, 32); vg.addColorStop(0, 'rgba(0,0,0,0)'); vg.addColorStop(0.5, 'rgba(0,0,0,1)'); vg.addColorStop(1, 'rgba(0,0,0,0)'); sg.fillStyle = vg; sg.fillRect(0, 0, 128, 32);
    streakMat = new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(sc), transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide }); streakGeo = new THREE.PlaneGeometry(1, 1);
  }
  let streakMat = null, streakGeo = null;
  function drop(x, y, vx, vy, size) {
    if (fxKeep < 1 && Math.random() > fxKeep + 0.15) return; const s = BD.pool.pop(); if (!s) return; s.position.set(x, y, rnd(-0.35, 0.7)); s.scale.setScalar(size); s.material.color.setHex([0xa30d0d, 0xc11414, 0x8b0a0a, 0xd01a1a][(Math.random() * 4) | 0]); s.material.opacity = 1; s.visible = true;
    BD.live.push({ s, vx, vy, vz: rnd(-3.2, 0.8), life: rnd(0.8, 1.8), size });
  }
  function bloodDecal(kind, a, b, c, size) {
    const m = bdecals[bdI++ % Math.min(decalCap, bdecals.length)]; m.visible = true; m.material.opacity = 0.88; m.scale.set(size, size, 1); const sp = Math.random() * 6.283;
    if (kind === 'floor') { m.position.set(a, 0.014 + (bdI % 5) * 0.0006, c); m.rotation.set(-PI / 2, 0, sp); }
    else if (kind === 'back') { m.position.set(a, b, -RD / 2 + 0.014 + (bdI % 5) * 0.0006); m.rotation.set(0, 0, sp); }
    else { const L = kind === 'left'; m.position.set(L ? -RW / 2 + 0.014 : RW / 2 - 0.014, b, c); m.rotation.set(0, L ? PI / 2 : -PI / 2, sp); }
  }
  function clearBlood() { for (const m of bdecals) m.visible = false; for (const d of BD.live.splice(0)) { d.s.visible = false; BD.pool.push(d.s); } }
  function updBlood(dt) {
    for (let i = BD.live.length - 1; i >= 0; i--) {
      const d = BD.live[i], s = d.s; d.life -= dt; d.vy -= 24 * dt; s.position.x += d.vx * dt; s.position.y += d.vy * dt; s.position.z += d.vz * dt; const p = s.position; let kill = d.life <= 0;
      if (p.y <= 0.03 && d.vy < 0) { if (Math.random() < 0.55) bloodDecal('floor', p.x, 0, clamp(p.z, -RD / 2 + 0.2, RD / 2 - 0.1), d.size * rnd(2.4, 5)); kill = true; }
      else if (p.x < -RW / 2 + 0.03 || p.x > RW / 2 - 0.03) { if (Math.random() < 0.6) bloodDecal(p.x < 0 ? 'left' : 'right', 0, p.y, clamp(p.z, -RD / 2 + 0.2, RD / 2 - 0.2), d.size * rnd(2.4, 5)); kill = true; }
      else if (p.z < -RD / 2 + 0.03) { if (Math.random() < 0.65) bloodDecal('back', p.x, p.y, 0, d.size * rnd(2.6, 6)); kill = true; }
      else if (p.z > RD / 2 - 0.05) d.vz = -Math.abs(d.vz);
      if (kill) { s.visible = false; BD.pool.push(s); BD.live.splice(i, 1); }
    }
  }
  function bloodBurst(p, n, ux, uy, spd, sz) {
    const base = ux == null ? 0 : Math.atan2(uy, ux);
    for (let i = 0; i < n; i++) { const a = ux == null ? rnd(0, 6.283) : base + rnd(-0.9, 0.9), s = rnd(0.25, 1) * spd; drop(p.x, p.y, Math.cos(a) * s, Math.sin(a) * s + rnd(0, 3), rnd(0.07, 0.15) * sz); }
    for (let i = 0; i < Math.min(5, 1 + n / 6); i++) { const a = ux == null ? rnd(0, 6.283) : base + rnd(-0.7, 0.7); emit({ x: p.x, y: p.y, vx: Math.cos(a) * rnd(1, spd * 0.4), vy: Math.sin(a) * rnd(1, spd * 0.4), life: rnd(0.35, 0.7), s0: 0.12 * sz, s1: 0.5 * sz, c0: 0x7a0a0a, c1: 0x420505, a: 0.55, smoke: true, drag: 0.9 }); }
    if (n >= 8) { const k = (n / 8) | 0; for (let i = 0; i < Math.min(3, k); i++) bloodDecal('back', p.x + rnd(-0.8, 0.8), p.y + rnd(-0.6, 0.8), 0, rnd(0.45, 0.95) * sz); }
  }
  function bloodAt(p, amt, dx, dy) { const n = Math.min(18, 2 + ((amt * 0.45) | 0)); bloodBurst(p, n, dx, dy, 5 + Math.min(7, amt * 0.15), 0.8 + Math.min(0.6, amt / 60)); if (amt > 12 && AC && Math.random() < 0.5) sNoise(0.1, 900, 300, 0.12); }
  /* tearing */
  function addCap(part, pivot) {
    const S = cfg().scale, g = new THREE.Group(), red = new THREE.Mesh(new THREE.SphereGeometry(0.115 * S, 12, 9), new THREE.MeshLambertMaterial({ color: 0xa80f12, emissive: 0x2a0000 })), bone = new THREE.Mesh(new THREE.SphereGeometry(0.052 * S, 8, 6), new THREE.MeshLambertMaterial({ color: 0xf1ead8 }));
    red.scale.z = 0.9; bone.position.z = 0.04 * S; g.add(red); g.add(bone); g.position.set(pivot.x, pivot.y, pivot.z); part.group.add(g);
  }
  function sever(j, dx, dy, silent) {
    if (!doll || j.cut) return; j.cut = true; try { world.removeConstraint(j.c); } catch (e) {} const A = doll.parts[j.a], B = doll.parts[j.b]; if (!A || !B) return; B.cut = true; B.dmg = 0;
    const wp = new CANNON.Vec3(); A.body.pointToWorldFrame(j.c.pivotA, wp); const p = V3(wp.x, wp.y, 0.3); addCap(A, j.c.pivotA); addCap(B, j.c.pivotB);
    let ux = B.body.position.x - A.body.position.x, uy = B.body.position.y - A.body.position.y; const ul = Math.hypot(ux, uy) || 1; ux /= ul; uy /= ul; if (dx != null) { ux = ux * 0.5 + dx * 0.8; uy = uy * 0.5 + dy * 0.8; }
    B.body.velocity.x += ux * 9 + rnd(-2, 2); B.body.velocity.y += uy * 9 + 5; B.body.angularVelocity.z += rnd(-16, 16); A.body.velocity.x -= ux * 2; stumps.push({ j, t: 8, s: 0, acc: 0 });
    bloodBurst(p, 30, ux, uy, 12, 1.25); for (let i = 0; i < 3; i++) bloodDecal('back', p.x + rnd(-1, 1), p.y + rnd(-1, 1), 0, rnd(0.6, 1.2));
    if (!silent) { sfx.snap(); shake(0.3); haptic('thud'); popupT(LABEL[B.name] || 'TORN OFF!', p, '#ffd23f', 7.5); if (!dead) { hp -= 25; totalDmg += 25; dmgHud(); hpBar(); } }
  }
  function woundAt(part, to, dx, dy) {
    bloodBurst(V3(to.x, to.y, 0.5), 9, -dx, -dy, 7, 1.0); bloodBurst(V3(to.x, to.y, 0.5), 7, dx, dy, 9, 0.9);
    const w = part.wounds || (part.wounds = []); if (w.length > 5) w.shift(); w.push({ l: part.body.pointToLocalFrame(new CANNON.Vec3(to.x, to.y, to.z || 0)), t: 2.4, a: 0 });
  }
  function tear(part, dx, dy) { const j = doll.joints.find((q) => q.b === part.name && !q.cut); if (j) sever(j, dx, dy); }
  function hurt(part, amt, pt, quiet, kind, dx, dy) {
    let a = (part.fr || 0) + amt; amt = Math.floor(a); part.fr = a - amt; if (amt <= 0 || grace > 0) return 0; const p = pt || part.body.position, wasDead = dead;
    if (!dead) { totalDmg += amt; hp -= amt; mood = Math.max(mood, 0.95); dmgHud(); hpBar(); if (!quiet) popup('-' + amt, p, amt); if (amt >= 6 && performance.now() - owT > 450) { owT = performance.now(); yelp(); } }
    if (frozenT > 0 && kind !== 'freeze' && kind !== 'bleed' && amt >= 3) shatterIce(dx, dy);
    if (!NOBLOOD[kind]) bloodAt(p, amt, dx, dy);
    const lim = SEV[part.name]; if (lim && !part.cut && kind !== 'burn' && kind !== 'shock' && kind !== 'bleed' && kind !== 'freeze' && kind !== 'acid' && kind !== 'sting') { part.dmg = (part.dmg || 0) + amt * (SEVMUL[kind] || 1); if (part.dmg > lim) tear(part, dx, dy); }
    if (!dead && hp <= 0) die(kind); return wasDead ? 0 : amt;
  }
  function die(kind) {
    if (dead || !doll) return; dead = true; deadT = 0; kos++; hp = 0; hpBar(); const k = document.getElementById('kos'); if (k) k.textContent = 'KOs ' + kos; mood = 999;
    const c = doll.parts.chest.body.position, p = V3(c.x, c.y, 0); popupT('K.O.!', p, '#ff3b30', 12); addCoins(50); popupT('+50 COINS', V3(p.x, p.y - 1.0, 0), '#ffd23f', 7); flash(0.55, '#ff2a1a'); shake(0.9); slow = 0.6; scream(); sfx.thud(); haptic('thud'); bloodBurst(p, 34, null, null, 11, 1.4);
    if (kind === 'blast' || kind === 'crush' || (kind === 'saw' && Math.random() < 0.6)) { for (const j of doll.joints) if (!j.cut && Math.random() < 0.85) sever(j, null, null, true); popupT('GIBBED!', V3(p.x, p.y + 1.1, 0), '#ffd23f', 8.5); sfx.snap(); }
    if (kind === 'acid') { for (const q of doll.list) q.melt = true; popupT('DISSOLVED!', V3(p.x, p.y + 1.1, 0), '#9cff3a', 9); sfx.pop && sfx.pop(); }
    if (kind === 'burn') { onFire = Math.max(onFire, 3); for (const q of doll.list) { q.burn = 1; setTint(q, 1, 0); } popupT('ROASTED!', V3(p.x, p.y + 1.1, 0), '#ff9a2a', 8.5); }
  }
  function respawnDoll() { if (doll) for (const q of doll.list) { puff(q.body.position, 0xd8d8d8, 3); sparks(q.body.position, 2, 0xffffff, 0xffd34a, 4, 0.08); } sfx.whoosh && sfx.whoosh(); resetDoll(); }
  /* x-ray skeleton for the taser */
  function buildBones(q) {
    const S = cfg().scale, sh = q.body.shapes[0], g = new THREE.Group(), name = q.name; g.visible = false;
    const mat = (c) => new THREE.MeshBasicMaterial({ color: c || 0xeaf8ff, transparent: true, opacity: 0, depthTest: false, depthWrite: false });
    const add = (geo, x, y, z, c) => { const m = new THREE.Mesh(geo, mat(c)); m.position.set(x, y, z); m.userData.bone = 1; m.renderOrder = 6; g.add(m); return m; };
    const B = (w, h, d) => new THREE.BoxGeometry(w, h, d), Cy = (r, h) => new THREE.CylinderGeometry(r, r, h, 8), Sp = (r) => new THREE.SphereGeometry(r, 12, 9);
    if (name === 'head') { const r = sh.radius; const sk = add(Sp(r * 0.88), 0, r * 0.08, r * 0.1); sk.scale.set(0.95, 1.05, 0.9); add(Sp(r * 0.22), -r * 0.34, r * 0.1, r * 0.78, 0x06243a); add(Sp(r * 0.22), r * 0.34, r * 0.1, r * 0.78, 0x06243a); add(B(r * 0.1, r * 0.2, r * 0.05), 0, -r * 0.15, r * 0.9, 0x06243a); add(B(r * 0.62, r * 0.2, r * 0.1), 0, -r * 0.5, r * 0.68); for (let i = -2; i <= 2; i++) add(B(r * 0.025, r * 0.2, r * 0.12), i * r * 0.12, -r * 0.5, r * 0.7, 0x06243a); }
    else if (name === 'chest') { const h = sh.halfExtents; add(Cy(0.04 * S, h.y * 2.1), 0, 0, -0.02 * S); add(B(0.05 * S, h.y * 1.4, 0.05 * S), 0, 0.02 * S, 0.1 * S); add(B(h.x * 2.2, 0.05 * S, 0.06 * S), 0, h.y * 0.92, 0.04 * S); for (let k = 0; k < 5; k++) { const yy = h.y * (0.62 - 0.33 * k), w = h.x * (1.75 - Math.abs(k - 1.5) * 0.08); add(B(w * 1.0, 0.04 * S, 0.06 * S), 0, yy, 0.06 * S); add(Sp(0.032 * S), -w / 2, yy, 0.06 * S); add(Sp(0.032 * S), w / 2, yy, 0.06 * S); } }
    else if (name === 'pelvis') { const h = sh.halfExtents; add(B(h.x * 1.8, 0.11 * S, 0.1 * S), 0, h.y * 0.35, 0.02 * S); add(Sp(0.1 * S), -h.x * 0.65, -h.y * 0.25, 0.02 * S); add(Sp(0.1 * S), h.x * 0.65, -h.y * 0.25, 0.02 * S); add(B(0.1 * S, h.y * 1.1, 0.07 * S), 0, 0, 0); }
    else if (name.indexOf('hand') === 0) { const r = sh.radius; add(Sp(r * 0.55), 0, 0, 0); for (let i = -1; i <= 1; i++) add(Cy(0.016 * S, r * 0.9), i * r * 0.3, -r * 0.7, 0); }
    else if (name.indexOf('foot') === 0) { const h = sh.halfExtents; add(B(h.x * 1.1, h.y * 0.9, h.z * 1.7), 0, 0, 0); add(B(h.x * 1.5, h.y * 0.6, 0.04 * S), 0, 0, h.z * 0.95); }
    else { const h = sh.halfExtents, len = h.y * 2 * 0.95; add(Cy(0.034 * S, len), 0, 0, 0); add(Sp(0.068 * S), 0, len / 2, 0); add(Sp(0.068 * S), 0, -len / 2, 0); add(Sp(0.05 * S), 0.04 * S, len / 2, 0); add(Sp(0.05 * S), -0.04 * S, -len / 2, 0); }
    q.group.add(g); q.bones = g;
  }
  function updXray(q, dt, tm) {
    const target = ((q.zap || 0) > 0 || q.melt) ? 1 : 0; q.zap = Math.max(0, (q.zap || 0) - dt); const x0 = q.xr || 0; if (!target && x0 === 0) return; q.xr = x0 + (target - x0) * Math.min(1, dt * (target ? 16 : 6)); if (q.xr < 0.01) q.xr = 0;
    const x = q.xr, fl = 0.78 + 0.22 * Math.sin(tm * 60 + q.body.id * 1.7); q.bones.visible = x > 0;
    q.bones.traverse((m) => { if (m.isMesh) { if (m.userData.c0 == null) m.userData.c0 = m.material.color.getHex(); if (q.char) m.material.color.setHex(0x6a5d54).lerp(CHAR, 0.2).offsetHSL(0, 0, 0.04 * Math.sin(tm * 8 + q.body.id)); m.material.opacity = x * fl; } });
    for (const m of ownMats(q)) { m.material.transparent = true; m.material.opacity = 1 - (q.melt ? 0.97 : 0.76) * x; m.material.depthWrite = x < 0.05; }
  }
  /* per-frame gore: blood, stumps, fire, x-ray, death timer */
  function updateGore(dt) {
    updBlood(dt); updPins(dt); const tm = performance.now() / 1000;
    for (let i = casings.length - 1; i >= 0; i--) { const c = casings[i]; c.t += dt; c.vy -= 22 * dt; c.m.position.x += c.vx * dt; c.m.position.y += c.vy * dt; c.m.rotation.z += c.w * dt; if (c.m.position.y < 0.05 && c.vy < 0) { c.m.position.y = 0.05; c.vy *= -0.35; c.vx *= 0.6; c.w *= 0.5; } if (c.t > 3) { scene.remove(c.m); casings.splice(i, 1); } }
    if (!doll) return;
    for (let i = stumps.length - 1; i >= 0; i--) {
      const s = stumps[i], j = s.j, A = doll.parts[j.a], B = doll.parts[j.b]; s.t -= dt; s.s += dt; if (s.t <= 0 || !A || !B) { stumps.splice(i, 1); continue; }
      const pa = new CANNON.Vec3(), pb = new CANNON.Vec3(); A.body.pointToWorldFrame(j.c.pivotA, pa); B.body.pointToWorldFrame(j.c.pivotB, pb); let ux = B.body.position.x - A.body.position.x, uy = B.body.position.y - A.body.position.y; const ul = Math.hypot(ux, uy) || 1; ux /= ul; uy /= ul;
      const pulse = s.s < 1.6 ? 0.55 + 0.45 * Math.sin(s.s * 14) : 0.2; s.acc += dt * (s.s < 1.6 ? 70 : 10) * pulse; const sp = s.s < 1.6 ? 5.5 * pulse + 2 : 1.4;
      while (s.acc >= 1) { s.acc -= 1; drop(pa.x, pa.y, (ux * 0.5 + rnd(-0.5, 0.5)) * sp, rnd(0.4, 1.2) * sp, rnd(0.07, 0.13)); drop(pb.x, pb.y, (-ux * 0.5 + rnd(-0.5, 0.5)) * sp, rnd(0.4, 1.2) * sp, rnd(0.07, 0.13)); }
      if (!dead) { hp -= dt * 2.4; hpBar(); if (hp <= 0) die('bleed'); }
    }
    if (onFire > 0) {
      onFire -= dt; fireAcc += dt; flail -= dt;
      for (const q of doll.list) { q.flame = Math.max(q.flame || 0, 0.4); q.burn = Math.min(1, (q.burn || 0) + dt * 0.22); }
      if (flail <= 0 && !dead) { flail = rnd(0.1, 0.26); for (let k = 0; k < 3; k++) { const q = doll.list[(Math.random() * doll.list.length) | 0], b = q.body; b.velocity.x += rnd(-6, 6); b.velocity.y += rnd(1, 7); b.angularVelocity.z += rnd(-12, 12); } }
      if (fireAcc > 0.5) { fireAcc = 0; if (!dead) hurt(doll.list[(Math.random() * doll.list.length) | 0], 9, null, false, 'burn'); }
    }
    for (const q of doll.list) if (q.wounds) for (let i = q.wounds.length - 1; i >= 0; i--) { const w = q.wounds[i]; w.t -= dt; if (w.t <= 0) { q.wounds.splice(i, 1); continue; } w.a += dt * 38 * (w.t / 2.4 + 0.2); const wp = new CANNON.Vec3(); q.body.pointToWorldFrame(w.l, wp); while (w.a >= 1) { w.a -= 1; drop(wp.x, wp.y, rnd(-1.6, 1.6), rnd(0.5, 3.2), rnd(0.06, 0.11)); } }
    for (const q of doll.list) {
      if ((q.burn || 0) >= 0.9 && !q.melt && (onFire > 0 || (q.flame || 0) > 0)) { q.ash = (q.ash || 0) + dt * rnd(0.6, 1.2); const b = q.body.position; if (Math.random() < dt * 20) emit({ x: b.x + rnd(-0.2, 0.2), y: b.y + rnd(-0.1, 0.3), vx: rnd(-0.5, 0.5), vy: rnd(1, 2.5), life: rnd(0.6, 1.1), s0: 0.1, s1: 0.03, c0: 0xffb040, c1: 0x401a08, g: -2, a: 0.9 });
        if (q.ash > 1.5) { q.melt = true; q.char = true; q.flame = 0; const bp = q.body.position, pt = V3(bp.x, bp.y, 0); puff(pt, 0x2a2624, 6); for (let i = 0; i < 10; i++) emit({ x: bp.x, y: bp.y, vx: rnd(-2.5, 2.5), vy: rnd(0.5, 4), life: rnd(0.5, 1.1), s0: 0.1, s1: 0.03, c0: 0xffc060, c1: 0x301008, g: 4, a: 0.9 }); doll.nBone = (doll.nBone || 0) + 1; if (doll.nBone === 4) { popupT('BURNED TO THE BONE!', V3(pt.x, pt.y + 1.0, 0), '#ff9a2a', 9); sfx.crack && sfx.crack(); shake(0.4); } } }
    }
    for (const q of doll.list) { if (Math.abs((q.burn || 0) - (q.bs || 0)) > 0.03 || Math.abs((q.ice || 0) - (q.is || 0)) > 0.04 || Math.abs((q.acid || 0) - (q.as || 0)) > 0.03 || Math.abs((q.sting || 0) - (q.ss || 0)) > 0.03) { q.bs = q.burn || 0; q.is = q.ice || 0; q.as = q.acid || 0; q.ss = q.sting || 0; setTint(q, q.burn || 0, q.shock || 0); } updXray(q, dt, tm); }
    { let sIce = 0; for (const q of doll.list) { if (q.ice > 0) { if (frozenT <= 0) q.ice = Math.max(0, q.ice - dt * 0.1); sIce += q.ice; } }
      if (!dead && frozenT <= 0 && (sIce / doll.list.length > 0.55 || (doll.parts.chest.ice || 0) >= 0.98)) { frozenT = 0.65; for (const q of doll.list) q.ice = 1; const c = doll.parts.chest.body.position; popupT('FROZEN SOLID!', V3(c.x, c.y + 0.6, 0), '#7fd8ff', 8.5); sfx.crack(); sfx.crack(); haptic('thud'); flash(0.25, '#cfeeff'); }
      if (frozenT > 0) { frozenT -= dt; if (frozenT <= 0) { frozenT = 0.001; shatterIce(); } } }
    if (dead) { deadT += dt; if (deadT > (doll.list.some((q) => q.melt) ? 4.4 : 2.6)) respawnDoll(); }
  }
  /* bullets that fly out of the barrel, and shell casings */
  const casings = [];
  function bulletFx(from, to, big, onHit, speed) {
    const dx = to.x - from.x, dy = to.y - from.y, L = Math.hypot(dx, dy) || 0.01, ux = dx / L, uy = dy / L, ang = Math.atan2(dy, dx), len = big ? 1.5 : 1.2, m = new THREE.Mesh(streakGeo, streakMat); m.rotation.z = ang; m.renderOrder = 9; track(m); let t = 0, hit = false;
    addFx((dt) => { t += dt; const hd = speed * t, h2 = Math.min(L, hd), tl = Math.max(0, hd - len); if (hd >= L && !hit) { hit = true; onHit(); } if (tl >= L) { scene.remove(m); return false; } const c = (h2 + tl) / 2, w = Math.max(0.01, h2 - tl); m.position.set(from.x + ux * c, from.y + uy * c, 0.96); m.scale.set(w, big ? 0.16 : 0.11, 1); return true; });
  }
  function casing(shell) {
    if (casings.length > 26) { const o = casings.shift(); scene.remove(o.m); } const m = new THREE.Mesh(new THREE.BoxGeometry(shell ? 0.13 : 0.075, shell ? 0.06 : 0.036, 0.04), new THREE.MeshBasicMaterial({ color: shell ? 0xd43a2d : 0xe9b94a }));
    const g = gunMeshes[gunId], px = g ? g.position.x : gun.muz.x, py = g ? g.position.y : gun.muz.y; m.position.set(px, py + 0.15, 0.95); scene.add(m); casings.push({ m, vx: -gun.dir.x * rnd(0.5, 2.5) + rnd(-1.2, 1.2), vy: rnd(3.5, 6.5), w: rnd(-25, 25), t: 0 });
  }

  const CHAR = new THREE.Color(0x15110f);
  function ownMats(part) { if (part._own) return part._own; part._own = []; part.group.traverse((m) => { if (m.isMesh && !m.userData.bone) { m.material = m.material.clone(); m.userData.base = m.material.color.clone(); part._own.push(m); } }); return part._own; }
  const ICEC = new THREE.Color(0x9fdcff);
  function setTint(part, burn, shock) { part.burn = burn; part.shock = shock; const ice = part.ice || 0; for (const m of ownMats(part)) { m.material.color.copy(m.userData.base).lerp(CHAR, burn * 0.9).lerp(ICEC, ice * 0.8).lerp(ACIDC, (part.acid || 0) * 0.85).lerp(STINGC, (part.sting || 0) * 0.6); m.material.emissive.setRGB(shock * 0.3 + ice * 0.04, shock * 0.62 + ice * 0.24 + (part.acid || 0) * 0.3, shock + ice * 0.4); } }

  /* ---- aiming helpers ---- */
  const zPlane = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0), ptr = { down: false, x: 0, y: 0, id: -1 };
  function aim(cx, cy) {
    rayFrom(cx, cy); const hit = doll ? ray.intersectObjects(hitMeshes, false)[0] : null, p = V3(0, RH / 2, 0);
    if (hit) p.copy(hit.point); else if (!ray.ray.intersectPlane(zPlane, p)) p.set(0, RH / 2, 0);
    p.x = clamp(p.x, -RW / 2 + 0.15, RW / 2 - 0.15); p.y = clamp(p.y, 0.15, RH - 0.15); if (!hit) p.z = 0;
    return { p, hit, part: hit ? doll.parts[hit.object.userData.part] : null };
  }
  function nearPart(p, r) { let best = null, bd = r; if (!doll) return null; for (const q of doll.list) { const d = Math.hypot(q.body.position.x - p.x, q.body.position.y - p.y); if (d < bd) { bd = d; best = q; } } return best; }
  function pushAt(part, vx, vy, pt) { const b = part.body, m = b.mass; b.applyImpulse(new CANNON.Vec3(vx * m, vy * m, 0), new CANNON.Vec3(pt.x - b.position.x, pt.y - b.position.y, clamp(pt.z - b.position.z, -0.2, 0.2))); }
  function sparks(p, n, c0, c1, spd, size) { for (let i = 0; i < n; i++) { const a = Math.random() * 6.28, s = rnd(0.35, 1) * spd; emit({ x: p.x, y: p.y, vx: Math.cos(a) * s, vy: Math.sin(a) * s + 1.5, life: rnd(0.25, 0.6), s0: size, s1: size * 0.2, c0, c1, g: 9, drag: 0.95 }); } }
  function puff(p, color, n) { for (let i = 0; i < n; i++) emit({ x: p.x + rnd(-0.1, 0.1), y: p.y + rnd(-0.1, 0.1), vx: rnd(-1.8, 1.8), vy: rnd(-0.5, 2), life: rnd(0.4, 0.8), s0: 0.16, s1: 0.5, c0: color, c1: color, g: -0.4, drag: 0.93, a: 0.7, smoke: true }); }

  /* ---- 2D guns (picture planes that sit beside the target and point at it) ---- */
  const gunMeshes = {}; let gunId = null; const gun = { vis: 0, kick: 0, side: 1, muz: V3(0, 0, 0), dir: V3(1, 0, 0), target: V3(0, 0, 0) };
  function gunMesh(id) {
    if (gunMeshes[id]) return gunMeshes[id]; const G = GUNS[id], u = assetUrl(G.asset); if (!u) return null;
    const t = new THREE.TextureLoader().setCrossOrigin('anonymous').load(u); t.anisotropy = 8; t.minFilter = THREE.LinearFilter;
    const m = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial({ map: t, transparent: true, depthWrite: false, side: THREE.DoubleSide })); m.visible = false; m.renderOrder = 8; m.userData.asp = assetAsp(G.asset, 1.5); scene.add(m); return (gunMeshes[id] = m);
  }
  function placeGun(id, target, dt) {
    const m = gunMesh(id); if (!m) { gun.muz.set(target.x + (target.x > 0 ? 1.2 : -1.2), target.y, 0.95); gun.dir.set(target.x > 0 ? -1 : 1, 0, 0); return; }
    const G = GUNS[id], L = G.L, h = L / m.userData.asp; if (Math.abs(target.x) > 0.5) gun.side = target.x > 0 ? 1 : -1;
    const half = L * 0.5, gx = clamp(target.x + gun.side * (half + 0.95), -RW / 2 + half * 0.85, RW / 2 - half * 0.85), gy = clamp(target.y + 0.05, h * 0.5, RH - h * 0.5);
    let dx = target.x - gx, dy = target.y - gy; const dl = Math.hypot(dx, dy) || 1; dx /= dl; dy /= dl; gun.dir.set(dx, dy, 0);
    const k = gun.kick; m.position.set(gx - dx * k, gy - dy * k, 0.97); m.scale.set(gun.side > 0 ? -L : L, h, 1); m.rotation.z = (gun.side > 0 ? Math.atan2(-dy, -dx) : Math.atan2(dy, dx)) + (G.rot ? (gun.side > 0 ? G.rot : -G.rot) : 0);
    m.updateMatrixWorld(true); gun.muz.set(G.mx, G.my, 0); m.localToWorld(gun.muz); gun.target.copy(target);
    m.material.opacity = clamp(gun.vis * 8, 0, 1); m.visible = gun.vis > 0;
  }
  function hideGuns() { for (const k in gunMeshes) gunMeshes[k].visible = false; }
  function tracer(a, b, color) { let t = 0; addFx((dt) => { t += dt; if (t > 0.07) return false; bolt(a, b, color || 0xfff2b0, 0.02); return true; }); }

  /* ---- explosions, blows ---- */
  function boomFx(p, R, col0, col1) {
    emit({ x: p.x, y: p.y, life: 0.28, s0: R * 1.6, s1: R * 3.3, c0: 0xfff6d0, c1: col0, a: 1, ap: 1.4 });
    for (let i = 0; i < 34; i++) { const a = Math.random() * 6.28, s = rnd(2, 11) * R * 0.45; emit({ x: p.x, y: p.y, vx: Math.cos(a) * s, vy: Math.sin(a) * s, life: rnd(0.35, 0.8), s0: rnd(0.4, 0.9) * R * 0.45, s1: R * 0.1, c0: 0xffe28a, c1: col1, drag: 0.9, g: -1 }); }
    for (let i = 0; i < 16; i++) { const a = Math.random() * 6.28, s = rnd(1, 5); emit({ x: p.x + Math.cos(a) * 0.2, y: p.y + Math.sin(a) * 0.2, vx: Math.cos(a) * s, vy: Math.sin(a) * s + 1.5, life: rnd(0.9, 1.7), s0: R * 0.35, s1: R * 0.95, c0: 0x4a4540, c1: 0x1e1b19, g: -0.8, drag: 0.94, a: 0.8, smoke: true }); }
    sparks(p, 26, 0xffffff, 0xffa030, 15 * R * 0.4, 0.1); ring(p, R * 1.25, col0, 0.42); ring(p, R * 0.8, 0xffffff, 0.28);
  }
  function explode(p, R, power, dmgBase, opt) {
    opt = opt || {}; let sum = 0;
    if (doll) for (const part of doll.list) {
      const b = part.body, dx = b.position.x - p.x, dy = b.position.y - p.y, d = Math.hypot(dx, dy) + 0.05;
      if (d < R) { const f = Math.pow(1 - d / R, 1.1), ux = dx / d, uy = dy / d + 0.3; b.velocity.x += ux * power * f; b.velocity.y += uy * power * f; b.angularVelocity.x += rnd(-1, 1) * f * 6; b.angularVelocity.z += (ux > 0 ? -1 : 1) * f * rnd(4, 11); sum += hurt(part, dmgBase * f * 0.55, null, true, 'blast', ux, uy); if (opt.burn) { part.flame = Math.max(part.flame || 0, 1.6 * f + 0.2); part.burn = Math.min(0.8, (part.burn || 0) + f * 0.6); } }
    }
    if (opt.burn && sum > 0) onFire = Math.max(onFire, 4.5);
    for (const t of things) { if (t.kind === 'mine') { if (Math.hypot(t.body.position.x - p.x, t.body.position.y - p.y) < R) t.trig = true; } else if ((t.kind === 'dyn' || t.kind === 'gren') && t.fuse > 0.2) { const d = Math.hypot(t.body.position.x - p.x, t.body.position.y - p.y); if (d < R) t.fuse = 0.08 + d * 0.05; } }
    boomFx(p, opt.size || R * 0.55, opt.c0 || 0xffb14a, opt.c1 || 0xff3a10);
    shake(opt.shake || 0.5); flash(opt.flash == null ? 0.38 : opt.flash, opt.fcol); sfx.boom(opt.vol || 1); haptic('thud'); decal(p.x, clamp(p.y, 0.3, RH - 0.3), R * 0.8, 'scorch');
    if (sum > 0) popup('-' + sum, V3(p.x, p.y + 0.3, 0), sum);
  }
  function blow(p, dx, dy, R, power, dmgBase) {
    let sum = 0; if (!doll) return 0;
    for (const part of doll.list) { const b = part.body, d = Math.hypot(b.position.x - p.x, b.position.y - p.y); if (d < R) { const f = Math.pow(1 - d / R, 1.3); b.velocity.x += dx * power * f; b.velocity.y += dy * power * f; b.angularVelocity.z += (dx > 0 ? -1 : 1) * f * rnd(5, 12); sum += hurt(part, dmgBase * f * 0.7, null, true, 'smash', dx, dy); } }
    if (sum > 0) popup('-' + sum, V3(p.x, p.y + 0.2, 0), sum); return sum;
  }

  /* ---- physical props: dynamite, anvil, saw, rocket ---- */
  const things = [], propMat = new CANNON.Material('prop'), sawMat = new CANNON.Material('saw');
  function initProps() {
    world.addContactMaterial(new CANNON.ContactMaterial(propMat, wallMat, { friction: 0.45, restitution: 0.25 }));
    world.addContactMaterial(new CANNON.ContactMaterial(propMat, dollMat, { friction: 0.4, restitution: 0.15 }));
    world.addContactMaterial(new CANNON.ContactMaterial(sawMat, wallMat, { friction: 0.01, restitution: 0.9 }));
    world.addContactMaterial(new CANNON.ContactMaterial(sawMat, dollMat, { friction: 0.1, restitution: 0.25 }));
  }
  function disposeObj(o) { o.traverse((m) => { if (m.isMesh) { m.geometry.dispose(); const ms = Array.isArray(m.material) ? m.material : [m.material]; ms.forEach((x) => x.dispose()); } }); }
  function addThing(t) { things.push(t); world.addBody(t.body); scene.add(t.mesh); }
  function dropThing(t) { world.removeBody(t.body); scene.remove(t.mesh); disposeObj(t.mesh); if (t.extra) { scene.remove(t.extra); disposeObj(t.extra); } }
  function phong(c, sh) { return new THREE.MeshPhongMaterial({ color: c, shininess: sh || 60, specular: 0x666666 }); }
  function clearThings() { for (const t of things) dropThing(t); things.length = 0; for (const e of rockets.splice(0)) { scene.remove(e.g); disposeObj(e.g); } holes.forEach((h) => { scene.remove(h.g); disposeObj(h.g); }); holes.length = 0; }

  function spawnDynamite(p) {
    const g = new THREE.Group(), red = new THREE.MeshLambertMaterial({ color: 0xd9352c }), cap = new THREE.MeshLambertMaterial({ color: 0x8c1d19 });
    [[0, 0.1, 0], [0, -0.07, 0.11], [0, -0.07, -0.11]].forEach((q) => { const c = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.12, 0.95, 16), red); c.rotation.z = PI / 2; c.position.set(q[0], q[1], q[2]); g.add(c); [-1, 1].forEach((s) => { const e = new THREE.Mesh(new THREE.CylinderGeometry(0.1, 0.1, 0.02, 14), cap); e.rotation.z = PI / 2; e.position.set(s * 0.48, q[1], q[2]); g.add(e); }); });
    [-0.22, 0.22].forEach((x) => { const r = new THREE.Mesh(new THREE.TorusGeometry(0.2, 0.025, 8, 24), new THREE.MeshLambertMaterial({ color: 0xc9a56a })); r.rotation.y = PI / 2; r.position.set(x, 0, 0); g.add(r); });
    const fz = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, 0.36, 6), new THREE.MeshLambertMaterial({ color: 0x2b2118 })); fz.position.set(0.2, 0.3, 0); fz.rotation.z = -0.5; g.add(fz);
    g.traverse((m) => { if (m.isMesh) m.castShadow = true; });
    const body = new CANNON.Body({ mass: 1.4, material: propMat, linearDamping: 0.08, angularDamping: 0.3 }); body.addShape(new CANNON.Box(new CANNON.Vec3(0.5, 0.2, 0.2)));
    body.position.set(p.x, p.y, 0); body.velocity.set(rnd(-1.5, 1.5), 3, 0); body.angularVelocity.set(0, 0, rnd(-6, 6)); body.collisionFilterGroup = 1; body.collisionFilterMask = 3;
    const t = { kind: 'dyn', body, mesh: g, fuse: 2.4, tick: 0, age: 0 };
    t.update = (dt) => {
      t.fuse -= dt; t.age += dt; const tip = V3(0.34, 0.46, 0); g.updateMatrixWorld(true); g.localToWorld(tip);
      emit({ x: tip.x, y: tip.y, vx: rnd(-1.5, 1.5), vy: rnd(1, 3.5), life: 0.28, s0: 0.2, s1: 0.04, c0: 0xffe08a, c1: 0xff5a14 }); emit({ x: tip.x, y: tip.y, life: 0.08, s0: 0.45, s1: 0.2, c0: 0xffffff, c1: 0xffd070, a: 0.9 });
      t.tick -= dt; if (t.tick <= 0) { t.tick = t.fuse < 0.8 ? 0.1 : 0.32; sfx.tick(); }
      const on = t.fuse < 0.9 && Math.sin(t.age * 40) > 0; red.emissive.setRGB(on ? 0.55 : 0, on ? 0.08 : 0, 0);
      if (t.fuse <= 0) { explode(V3(body.position.x, body.position.y, 0), 3.4, 24, 85, { burn: true }); return false; } return true;
    };
    addThing(t); sfx.tick(); haptic('tap');
  }
  function spawnAnvil(p) {
    const g = new THREE.Group(), dark = phong(0x2c3038, 70), lite = phong(0x6a7280, 110);
    const add = (geo, mat, x, y, z) => { const m = new THREE.Mesh(geo, mat); m.position.set(x, y, z); m.castShadow = true; g.add(m); return m; };
    add(roundBox(1.1, 0.2, 0.78, 0.05, 3), dark, 0, -0.27, 0); add(roundBox(0.6, 0.34, 0.5, 0.05, 3), dark, 0, -0.04, 0); add(roundBox(1.2, 0.2, 0.8, 0.06, 3), dark, 0, 0.2, 0); add(roundBox(1.18, 0.06, 0.76, 0.03, 3), lite, 0, 0.32, 0);
    const horn = add(new THREE.ConeGeometry(0.36, 0.7, 14), dark, 0.9, 0.2, 0); horn.rotation.z = -PI / 2; horn.scale.z = 0.95;
    const body = new CANNON.Body({ mass: 90, material: propMat, linearDamping: 0.01 }); body.addShape(new CANNON.Box(new CANNON.Vec3(0.6, 0.38, 0.4)));
    body.position.set(clamp(p.x, -RW / 2 + 0.8, RW / 2 - 0.8), RH - 0.6, 0); body.velocity.set(0, -14, 0); body.fixedRotation = true; body.updateMassProperties(); body.collisionFilterGroup = 1; body.collisionFilterMask = 3;
    const t = { kind: 'anvil', body, mesh: g, hit: false, landed: false, rest: 0, ghost: false };
    body.addEventListener('collide', (ev) => {
      const o = ev.body, vy = -body.velocity.y, spd = Math.abs(ev.contact.getImpactVelocityAlongNormal());
      if (o && o.partRef && !t.hit && spd > 6) { t.hit = true; t.crush = { x: body.position.x, y: body.position.y - 0.3, v: spd }; }
      else if (o && o.isWall && !t.landed && spd > 6) { t.landed = true; t.land = { x: body.position.x, v: spd }; }
    });
    t.update = (dt) => {
      if (t.crush) { const c = t.crush; t.crush = null; const pt = V3(c.x, c.y, 0); let sum = 0;
        for (const part of doll.list) { const b = part.body, dx = b.position.x - c.x, ady = Math.abs(b.position.y - c.y); if (Math.abs(dx) < 1.3 && ady < 1.6) { const f = 1 - Math.abs(dx) / 1.4; b.velocity.y = Math.min(b.velocity.y, -9 * f - 2); b.velocity.x += (dx >= 0 ? 1 : -1) * 6 * (1 - f * 0.4); sum += hurt(part, 80 * f + 10, null, true, 'crush', 0, -1); } }
        if (sum) popup('-' + sum, V3(c.x, c.y + 0.6, 0), sum); sparks(pt, 22, 0xffffff, 0xffb040, 11, 0.12); puff(pt, 0xd8cdb8, 12); ring(pt, 1.7, 0xfff0c0, 0.35); shake(0.55); sfx.clank(); sfx.thud(); haptic('thud'); flash(0.2); t.ghost = true; }
      if (t.ghost && body.collisionFilterMask !== 2) body.collisionFilterMask = 2;
      if (t.land) { const l = t.land; t.land = null; const pt = V3(l.x, 0.15, 0); puff(pt, 0xd8cdb8, 14); ring(pt, 2.3, 0xffe9b8, 0.4); blow(pt, 0, 0.6, 2.5, 5, 9); shake(0.4); sfx.thud(); sfx.clank(); haptic('thud'); t.rest = 0.001; }
      if (t.rest > 0) { t.rest += dt; if (t.rest > 2.2) { const k = 1 - (t.rest - 2.2) / 0.3; g.scale.setScalar(Math.max(0.01, k)); if (k <= 0) return false; } }
      return true;
    };
    addThing(t); sfx.whoosh && sfx.whoosh();
  }
  function spawnSaw(p) {
    const g = new THREE.Group(), sh = new THREE.Shape(), N = 22; for (let i = 0; i < N * 2; i++) { const a = (i / (N * 2)) * PI * 2, r = i % 2 ? 0.5 : 0.66; const x = Math.cos(a) * r, y = Math.sin(a) * r; if (i) sh.lineTo(x, y); else sh.moveTo(x, y); } sh.closePath();
    const disc = new THREE.Mesh(new THREE.ExtrudeGeometry(sh, { depth: 0.09, bevelEnabled: false }), phong(0xc7d0dc, 120)); disc.position.z = -0.045; g.add(disc);
    const hub = new THREE.Mesh(new THREE.CylinderGeometry(0.17, 0.17, 0.16, 18), phong(0xf08a1c, 80)); hub.rotation.x = PI / 2; g.add(hub);
    for (let i = 0; i < 6; i++) { const a = (i / 6) * PI * 2, b = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, 0.12, 8), phong(0x555a64, 40)); b.rotation.x = PI / 2; b.position.set(Math.cos(a) * 0.32, Math.sin(a) * 0.32, 0.02); g.add(b); }
    g.traverse((m) => { if (m.isMesh) m.castShadow = true; });
    const dir = p.x > 0 ? -1 : 1, body = new CANNON.Body({ mass: 8, material: sawMat, linearDamping: 0.0, angularDamping: 0.2 }); body.addShape(new CANNON.Sphere(0.55));
    body.position.set(p.x, Math.max(p.y, 0.8), 0); body.velocity.set(dir * 19, 4, 0); body.collisionFilterGroup = 1; body.collisionFilterMask = 3; body.allowSleep = false;
    const t = { kind: 'saw', body, mesh: g, life: 6, dir, last: new Map(), tsc: 0 };
    body.addEventListener('collide', (ev) => {
      const o = ev.body, now = performance.now(), cp = V3(body.position.x + ev.contact.ri.x, body.position.y + ev.contact.ri.y, 0);
      if (o && o.partRef) { const lt = t.last.get(o.partRef) || 0; if (now - lt < 110) return; t.last.set(o.partRef, now); hurt(o.partRef, rnd(10, 17), cp, false, 'saw', Math.sign(body.velocity.x), 0.2); sparks(cp, 9, 0xffffff, 0xff9a2a, 8, 0.09); puff(cp, 0xf1e2c4, 3); if (now - t.tsc > 90) { t.tsc = now; sfx.screech(); haptic({ intensity: 0.5, sharpness: 0.9 }); } shake(0.12); }
      else if (o && o.isWall && now - t.tsc > 130) { t.tsc = now; sparks(cp, 5, 0xffffff, 0xffb040, 6, 0.07); }
    });
    t.update = (dt) => {
      t.life -= dt; disc.rotation.z -= dir * 34 * dt; g.rotation.z = 0;
      const v = body.velocity; if (Math.abs(v.x) < 15) v.x = (v.x >= 0 ? 1 : -1) * 15; if (Math.abs(v.x) > 30) v.x *= 0.97; v.z = 0; body.position.z = 0;
      if (Math.random() < 0.6 && body.position.y < 0.9) emit({ x: body.position.x, y: 0.15, vx: rnd(-2, 2), vy: rnd(1, 3), life: 0.25, s0: 0.08, s1: 0.02, c0: 0xffffff, c1: 0xff9a2a, g: 8 });
      if (t.life < 0.4) g.scale.setScalar(Math.max(0.01, t.life / 0.4)); return t.life > 0;
    };
    addThing(t); sfx.screech(); haptic('tap');
  }
  const rockets = [];
  function fireRocket(from, to) {
    const g = new THREE.Group(), body = new THREE.Mesh(new THREE.CylinderGeometry(0.13, 0.13, 0.7, 14), phong(0xe8e8ea, 60)), nose = new THREE.Mesh(new THREE.ConeGeometry(0.13, 0.32, 14), phong(0xd8262c, 80)); nose.position.y = 0.51; body.add(nose);
    for (let i = 0; i < 4; i++) { const f = new THREE.Mesh(new THREE.BoxGeometry(0.02, 0.26, 0.26), phong(0xd8262c, 30)); f.position.y = -0.3; f.rotation.y = (i * PI) / 4; body.add(f); }
    g.add(body); const dx = to.x - from.x, dy = to.y - from.y, L = Math.hypot(dx, dy) || 1, ang = Math.atan2(dy, dx); g.rotation.z = ang - PI / 2; g.position.set(from.x, from.y, 0.5); scene.add(g);
    rockets.push({ g, x: from.x, y: from.y, dx: dx / L, dy: dy / L, tx: to.x, ty: to.y, t: 0 }); sfx.launch(); haptic('thud'); shake(0.2);
    for (let i = 0; i < 10; i++) emit({ x: from.x, y: from.y, vx: -dx / L * rnd(2, 6) + rnd(-1, 1), vy: -dy / L * rnd(2, 6) + rnd(-1, 1), life: rnd(0.3, 0.6), s0: 0.2, s1: 0.5, c0: 0xffd070, c1: 0x555555, drag: 0.9 });
  }
  function updRockets(dt) {
    for (let i = rockets.length - 1; i >= 0; i--) {
      const r = rockets[i]; r.t += dt; const sp = 27 * dt; r.x += r.dx * sp; r.y += r.dy * sp; r.g.position.set(r.x, r.y, 0.5);
      emit({ x: r.x - r.dx * 0.45, y: r.y - r.dy * 0.45, vx: rnd(-0.6, 0.6), vy: rnd(-0.6, 0.6), life: 0.22, s0: 0.3, s1: 0.06, c0: 0xffe9a0, c1: 0xff5a10 });
      emit({ x: r.x - r.dx * 0.55, y: r.y - r.dy * 0.55, vx: rnd(-0.4, 0.4), vy: rnd(-0.2, 0.6), life: 0.8, s0: 0.18, s1: 0.6, c0: 0x9a9a9a, c1: 0x555555, a: 0.6, smoke: true });
      let boom = r.t > 2 || Math.hypot(r.tx - r.x, r.ty - r.y) < sp + 0.1 || (r.x * r.dx > 0 && Math.abs(r.x) > RW / 2 - 0.1) || r.y < 0.3 || r.y > RH - 0.3;
      if (!boom && doll) for (const q of doll.list) { if (Math.hypot(q.body.position.x - r.x, q.body.position.y - r.y) < 0.5) { boom = true; break; } }
      if (boom) { scene.remove(r.g); disposeObj(r.g); rockets.splice(i, 1); explode(V3(r.x, r.y, 0), 3.2, 30, 92, { size: 2.3, shake: 0.7, vol: 1.2, burn: true }); }
    }
  }
  const holes = [];
  function openHole(p) {
    for (const h of holes.splice(0)) { scene.remove(h.g); disposeObj(h.g); }
    const g = new THREE.Group(), core = new THREE.Mesh(new THREE.SphereGeometry(1, 28, 20), new THREE.MeshBasicMaterial({ color: 0x050008 })), rings = [];
    g.add(core); [[1.0, 0xb44cff], [1.5, 0xff3cc8], [2.1, 0x6a5cff]].forEach((q, i) => { const r = new THREE.Mesh(new THREE.TorusGeometry(q[0], 0.07 + i * 0.015, 10, 64), new THREE.MeshBasicMaterial({ color: q[1], transparent: true, opacity: 0.85, blending: THREE.AdditiveBlending, depthWrite: false })); r.rotation.x = 1.05; g.add(r); rings.push(r); });
    const glow = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowT, color: 0x9a3cff, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, opacity: 0.9 })); g.add(glow);
    g.position.set(clamp(p.x, -RW / 2 + 1.7, RW / 2 - 1.7), clamp(p.y, 1.4, RH - 1.4), 0.5); scene.add(g); const h = { g, core, rings, glow, t: 0, dur: 3.4, x: g.position.x, y: g.position.y, dmgT: 0 }; holes.push(h);
    sfx.hole(); haptic('tap');
  }
  function updHoles(dt) {
    for (let i = holes.length - 1; i >= 0; i--) {
      const h = holes[i]; h.t += dt; const k = Math.min(1, h.t / 0.35), end = h.dur - h.t; const s = (0.25 + 0.4 * k) * (end < 0.25 ? Math.max(0.01, end / 0.25) : 1); h.core.scale.setScalar(s);
      h.rings.forEach((r, j) => { r.rotation.z += dt * (6 - j * 1.6) * (j % 2 ? -1 : 1); r.scale.setScalar(k * (end < 0.25 ? Math.max(0.01, end / 0.25) : 1) * (0.9 + 0.1 * Math.sin(h.t * 9 + j))); });
      h.glow.scale.setScalar(k * 3.6 * (0.9 + 0.1 * Math.sin(h.t * 11))); h.g.position.y = h.y + Math.sin(h.t * 3) * 0.06;
      for (let n = 0; n < 3; n++) { const a = Math.random() * 6.28, r = rnd(1.6, 3.1); emit({ x: h.x + Math.cos(a) * r, y: h.y + Math.sin(a) * r, vx: -Math.cos(a) * 5 - Math.sin(a) * 4, vy: -Math.sin(a) * 5 + Math.cos(a) * 4, life: 0.5, s0: 0.14, s1: 0.03, c0: 0xd9a6ff, c1: 0x6a3cff, drag: 0.97 }); }
      h.dmgT -= dt; if (h.dmgT <= 0 && doll) { h.dmgT = 0.22; let sum = 0; for (const q of doll.list) { if (Math.hypot(q.body.position.x - h.x, q.body.position.y - h.y) < 1.5) sum += hurt(q, 3, null, true, 'hole'); } if (sum) popup('-' + sum, V3(h.x, h.y + 0.8, 0), sum); }
      if (h.t >= h.dur) { scene.remove(h.g); disposeObj(h.g); holes.splice(i, 1); explode(V3(h.x, h.y, 0), 4.2, 20, 55, { c0: 0xc67bff, c1: 0x5a2cff, size: 2.0, shake: 0.55, fcol: '#d9b3ff', flash: 0.3 }); }
    }
  }
  function holePull(h) {
    if (!doll) return;
    for (const part of doll.list) { const b = part.body, dx = h.x - b.position.x, dy = h.y - b.position.y, d = Math.hypot(dx, dy) + 0.001, R = 4.6; if (d < R) { const f = Math.pow(1 - d / R, 0.8), m = b.mass, ux = dx / d, uy = dy / d; b.force.x += ux * m * (46 * f + 4) - uy * m * 16 * f; b.force.y += uy * m * (46 * f + 30 * f) + ux * m * 16 * f + m * 24 * f * 0.9; b.velocity.scale(1 - 0.012 * f, b.velocity); } }
  }

  /* ================= 10 more ways: katana, chainsaw, grenade, landmine, freeze ray, wrecking ball, lightning, guillotine, meteor, crossbow ================= */
  let lnT = null, lnW = null, lnB = null; const pins = [];
  function initWays2() {
    const c = document.createElement('canvas'); c.width = 8; c.height = 32; const g = c.getContext('2d'), gr = g.createLinearGradient(0, 0, 0, 32); gr.addColorStop(0, 'rgba(255,255,255,0)'); gr.addColorStop(0.5, 'rgba(255,255,255,1)'); gr.addColorStop(1, 'rgba(255,255,255,0)'); g.fillStyle = gr; g.fillRect(0, 0, 8, 32); lnT = new THREE.CanvasTexture(c);
    lnW = new THREE.MeshBasicMaterial({ map: lnT, color: 0xffffff, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide });
    lnB = new THREE.MeshBasicMaterial({ map: lnT, color: 0x6aa8ff, transparent: true, opacity: 0.7, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide });
  }
  function segMesh(a, b, w, mat, z) { const m = new THREE.Mesh(streakGeo, mat), dx = b.x - a.x, dy = b.y - a.y, L = Math.hypot(dx, dy) || 0.01; m.position.set((a.x + b.x) / 2, (a.y + b.y) / 2, z || 0.97); m.rotation.z = Math.atan2(dy, dx); m.scale.set(L + w * 0.6, w, 1); m.renderOrder = 9; track(m); return m; }
  const lnGeo = () => streakGeo;
  function distSeg(px, py, a, b) { const dx = b.x - a.x, dy = b.y - a.y, l2 = dx * dx + dy * dy || 1e-6; let t = ((px - a.x) * dx + (py - a.y) * dy) / l2; t = clamp(t, 0, 1); return Math.hypot(px - (a.x + dx * t), py - (a.y + dy * t)); }
  function jag(a, b, n, amp) { const pts = [V3(a.x, a.y, 0)], dx = b.x - a.x, dy = b.y - a.y, L = Math.hypot(dx, dy) || 1, px = -dy / L, py = dx / L; for (let i = 1; i < n; i++) { const t = i / n, o = (Math.random() - 0.5) * 2 * amp; pts.push(V3(a.x + dx * t + px * o, a.y + dy * t + py * o, 0)); } pts.push(V3(b.x, b.y, 0)); return pts; }
  function sfxPlus() {
    sfx.slice = () => { sNoise(0.14, 9000, 2500, 0.35, 'highpass'); sTone('sine', 2800, 1900, 0.22, 0.07); };
    sfx.crack = () => { sNoise(0.18, 7000, 3000, 0.3, 'highpass'); sTone('triangle', 1400, 700, 0.15, 0.12); };
    sfx.shatter = () => { sNoise(0.5, 9000, 1500, 0.55, 'highpass'); sTone('triangle', 2200, 500, 0.4, 0.2); setTimeout(() => sNoise(0.3, 7000, 1200, 0.3, 'highpass'), 70); };
    sfx.thunder = () => { sNoise(0.12, 9000, 3000, 0.7, 'highpass'); setTimeout(() => { sNoise(1.3, 1600, 60, 0.95); sTone('sine', 70, 28, 1.1, 0.8); }, 60); };
    sfx.rumble = () => { sNoise(0.6, 300, 1600, 0.35, 'bandpass', 0.8); sTone('sawtooth', 60, 140, 0.55, 0.18); };
    sfx.beep = () => sTone('square', 1250, 1250, 0.05, 0.09);
    sfx.thwip = () => { sNoise(0.14, 2500, 700, 0.35, 'bandpass', 1.2); sTone('triangle', 520, 140, 0.16, 0.22); };
    sfx.chop = () => { sTone('sine', 140, 40, 0.16, 0.6); sNoise(0.18, 3500, 600, 0.5, 'highpass'); };
  }
  /* --- katana: swipe --- */
  const kat = { prev: null, ang: 0, vis: 0 };
  function slash(a, b) {
    const L = Math.hypot(b.x - a.x, b.y - a.y); if (L < 0.1) return; const ux = (b.x - a.x) / L, uy = (b.y - a.y) / L, m = segMesh(a, b, 0.22, lnW), m2 = segMesh(a, b, 0.55, lnB); let t = 0;
    addFx((dt) => { t += dt; const k = 1 - t / 0.17; m.scale.y = 0.22 * Math.max(0, k); m2.scale.y = 0.55 * Math.max(0, k); if (k <= 0) { scene.remove(m); scene.remove(m2); return false; } return true; });
    let hit = 0, sum = 0; if (!doll) return; const now = performance.now();
    for (const j of doll.joints) { if (j.cut) continue; const pw = new CANNON.Vec3(); doll.parts[j.a].body.pointToWorldFrame(j.c.pivotA, pw); if (distSeg(pw.x, pw.y, a, b) < 0.26 && L > 0.3) { sever(j, ux, uy); hit++; } }
    for (const q of doll.list) { const bp = q.body.position; if (distSeg(bp.x, bp.y, a, b) < 0.34 && now - (q.sl || 0) > 120) { q.sl = now; const pt = V3(bp.x, bp.y, 0); sum += hurt(q, 14 + L * 5, pt, true, 'slash', ux, uy); pushAt(q, ux * 4, uy * 4 + 1, pt); sparks(pt, 5, 0xffffff, 0xcfe8ff, 7, 0.07); woundAt(q, pt, ux, uy); hit++; } }
    if (hit) { sfx.slice(); shake(0.16); haptic({ intensity: 0.7, sharpness: 0.9 }); if (sum) popup('-' + sum, V3(b.x, b.y + 0.3, 0), sum); } else if (L > 0.5) sfx.slice();
  }
  function katanaStart(p) { kat.prev = p.clone(); kat.vis = 0.4; }
  function katanaMove(x, y) { const p = aim(x, y).p; if (!kat.prev) { kat.prev = p.clone(); return; } if (Math.hypot(p.x - kat.prev.x, p.y - kat.prev.y) > 0.3) { kat.ang = Math.atan2(p.y - kat.prev.y, p.x - kat.prev.x); slash(kat.prev, p); kat.prev = p.clone(); kat.vis = 0.4; } kat.cur = p; }
  function placeKatana() {
    const m = gunMesh('katana'); if (!m) return; const L = 1.9, h = L / m.userData.asp, p = kat.cur || kat.prev; if (!p || kat.vis <= 0) { m.visible = false; return; }
    m.visible = true; m.material.opacity = clamp(kat.vis * 4, 0, 1); m.scale.set(L, h, 1); m.rotation.z = kat.ang + 0.75 * PI; m.position.set(p.x - Math.cos(kat.ang) * 0.45, p.y - Math.sin(kat.ang) * 0.45, 0.98);
  }
  /* --- chainsaw: hold --- */
  let csT = 0, csPop = 0;
  function holdChainsaw(dt) {
    gunId = 'chainsaw'; gun.vis = Math.max(gun.vis, 0.2); const A = aim(ptr.x, ptr.y); gun.kick = Math.random() * 0.09; placeGun('chainsaw', A.p); const m = gun.muz, d = gun.dir;
    if (!loops.chainsaw) loopStart('chainsaw'); hapStart(0.55, 0.7); csT -= dt; csPop += dt; let hit = 0, sum = 0;
    if (doll) for (const q of doll.list) { const b = q.body; if (Math.hypot(b.position.x - m.x, b.position.y - m.y) < 0.62) { hit++; if (csT <= 0) { sum += hurt(q, 12, V3(m.x, m.y, 0.3), true, 'saw', d.x, d.y); pushAt(q, d.x * 2.2, d.y * 2.2 + 0.3, V3(m.x, m.y, 0.3)); } } }
    if (hit) { for (let i = 0; i < 2; i++) { drop(m.x, m.y, d.x * rnd(2, 9) + rnd(-3, 3), d.y * rnd(1, 7) + rnd(0, 4), rnd(0.1, 0.2)); } if (Math.random() < 0.5) emit({ x: m.x, y: m.y, vx: rnd(-4, 4), vy: rnd(0, 5), life: 0.3, s0: 0.1, s1: 0.03, c0: 0xffffff, c1: 0xffa030, g: 9 }); shake(0.07); }
    if (csT <= 0) { csT = 0.09; if (hit) { bloodBurst(V3(m.x, m.y, 0.4), 7, d.x, d.y, 8, 1.0); if (Math.random() < 0.4) sfx.screech(); haptic({ intensity: 0.5, sharpness: 0.7 }); } }
    if (sum && csPop > 0.35) { csPop = 0; popup('-' + Math.round(sum * 1.5), V3(m.x, m.y + 0.3, 0), sum * 2); }
    emit({ x: m.x - d.x * 0.5, y: m.y - d.y * 0.5, vx: rnd(-1, 1), vy: rnd(0.5, 1.5), life: 0.5, s0: 0.1, s1: 0.4, c0: 0x777777, c1: 0x444444, a: 0.3, smoke: true });
  }
  /* --- grenade --- */
  function shrapnel(p, n) {
    for (let i = 0; i < n; i++) {
      const a = (i / n) * 6.283 + rnd(-0.2, 0.2), dx = Math.cos(a), dy = Math.sin(a); let best = null, bt = 7;
      if (doll) for (const q of doll.list) { const rx = q.body.position.x - p.x, ry = q.body.position.y - p.y, t = rx * dx + ry * dy; if (t < 0.2 || t > bt) continue; if (Math.abs(rx * dy - ry * dx) < 0.32) { bt = t; best = q; } }
      let tw = 7; if (dx > 0.01) tw = Math.min(tw, (RW / 2 - p.x) / dx); else if (dx < -0.01) tw = Math.min(tw, (-RW / 2 - p.x) / dx); if (dy > 0.01) tw = Math.min(tw, (RH - p.y) / dy); else if (dy < -0.01) tw = Math.min(tw, (0 - p.y) / dy);
      const L = best ? bt : Math.max(0.5, tw), to = V3(p.x + dx * L, p.y + dy * L, 0);
      bulletFx(V3(p.x, p.y, 0), to, false, () => { if (best && doll && doll.list.indexOf(best) >= 0) { hurt(best, 9, to, true, 'bullet', dx, dy); woundAt(best, to, dx, dy); sparks(to, 2, 0xffffff, 0xffa030, 4, 0.06); } else if (!best) decal(to.x, to.y, 0.22, 'hole'); }, 55 + rnd(0, 25));
    }
  }
  function spawnGrenade(p) {
    const g = new THREE.Group(), gm = phong(0x4c7a2e, 40), dk = phong(0x2f4d1c, 20), st = phong(0xbfc6cf, 120);
    const body = new THREE.Mesh(new THREE.SphereGeometry(0.22, 16, 12), gm); body.scale.y = 1.15; g.add(body); for (const y of [-0.1, 0.02, 0.14]) { const r = new THREE.Mesh(new THREE.TorusGeometry(0.205 - Math.abs(y) * 0.3, 0.018, 6, 20), dk); r.rotation.x = PI / 2; r.position.y = y; g.add(r); }
    const top = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.09, 0.1, 10), st); top.position.y = 0.3; g.add(top); const lev = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.3, 0.06), st); lev.position.set(0.1, 0.18, 0); g.add(lev); const rg = new THREE.Mesh(new THREE.TorusGeometry(0.07, 0.016, 6, 14), st); rg.position.set(0.22, 0.34, 0); g.add(rg);
    g.traverse((m) => { if (m.isMesh) m.castShadow = true; });
    const sx = p.x > 0 ? -(RW / 2 - 0.4) : RW / 2 - 0.4, body2 = new CANNON.Body({ mass: 0.8, material: propMat, linearDamping: 0.05, angularDamping: 0.2 }); body2.addShape(new CANNON.Sphere(0.22));
    body2.position.set(sx, clamp(p.y + 0.7, 1, RH - 1), 0); body2.velocity.set(clamp((p.x - sx) * 2.1, -17, 17), 7, 0); body2.angularVelocity.set(0, 0, rnd(-15, 15)); body2.collisionFilterGroup = 1; body2.collisionFilterMask = 3;
    const t = { kind: 'gren', body: body2, mesh: g, fuse: 2.3, tick: 0, age: 0 };
    t.update = (dt) => {
      t.fuse -= dt; t.age += dt; t.tick -= dt; if (t.tick <= 0) { t.tick = t.fuse < 0.8 ? 0.1 : 0.4; sfx.beep(); }
      const on = t.fuse < 1 && Math.sin(t.age * 36) > 0; gm.emissive.setRGB(on ? 0.5 : 0, on ? 0.12 : 0, 0);
      if (t.fuse <= 0) { const q = V3(body2.position.x, body2.position.y, 0); explode(q, 3.0, 20, 70, { burn: true, size: 1.9 }); shrapnel(q, 22); return false; } return true;
    };
    addThing(t); sfx.whoosh(); haptic('tap');
  }
  /* --- landmine --- */
  function spawnMine(p) {
    const x = clamp(p.x, -RW / 2 + 0.6, RW / 2 - 0.6), g = new THREE.Group(), base = new THREE.Mesh(new THREE.CylinderGeometry(0.46, 0.5, 0.14, 24), phong(0x434d2c, 30)); g.add(base);
    const dome = new THREE.Mesh(new THREE.SphereGeometry(0.34, 16, 8, 0, PI * 2, 0, PI / 2), phong(0x2e3520, 30)); dome.scale.y = 0.45; dome.position.y = 0.07; g.add(dome); const bm = new THREE.MeshLambertMaterial({ color: 0xd8221f, emissive: 0x000000 }), btn = new THREE.Mesh(new THREE.CylinderGeometry(0.17, 0.2, 0.09, 16), bm); btn.position.y = 0.2; g.add(btn);
    const lights = []; for (let i = 0; i < 4; i++) { const a = (i / 4) * PI * 2 + 0.4, l = new THREE.Mesh(new THREE.SphereGeometry(0.035, 8, 6), new THREE.MeshBasicMaterial({ color: 0x552200 })); l.position.set(Math.cos(a) * 0.37, 0.11, Math.sin(a) * 0.37); g.add(l); lights.push(l); }
    const body = new CANNON.Body({ mass: 0, material: propMat }); body.addShape(new CANNON.Sphere(0.05)); body.position.set(x, 0.07, 0.3); body.collisionFilterGroup = 2; body.collisionFilterMask = 0;
    const t = { kind: 'mine', body, mesh: g, age: 0, trig: false };
    t.update = (dt) => {
      t.age += dt; const armed = t.age > 0.9, on = Math.sin(t.age * (armed ? 6 : 14)) > 0; bm.emissive.setRGB(on ? 0.7 : 0.05, 0, 0); lights.forEach((l, i) => l.material.color.setHex(on && (i % 2 === (t.age * 3 | 0) % 2) ? 0xffcc00 : 0x442200));
      if (armed && doll && !t.trig) for (const q of doll.list) { const bp = q.body.position; if (bp.y < 1.0 && Math.abs(bp.x - x) < 0.65) { t.trig = true; break; } }
      if (t.trig) { sfx.beep(); const q = V3(x, 0.25, 0); explode(q, 3.2, 28, 100, { burn: true, size: 2.3, shake: 0.8 }); if (doll) for (const d of doll.list) { const dd = Math.hypot(d.body.position.x - x, d.body.position.y); if (dd < 2.2) { d.body.velocity.y += 16 * (1 - dd / 2.4); d.body.angularVelocity.z += rnd(-8, 8); } } shrapnel(q, 10); return false; } return true;
    };
    addThing(t); sfx.beep(); haptic('tap'); puff(V3(x, 0.15, 0), 0xd8cdb8, 4);
  }
  /* --- freeze ray: hold --- */
  let frozenT = 0, frT = 0;
  function holdFreeze(dt) {
    gunId = 'freeze'; gun.vis = Math.max(gun.vis, 0.2); const A = aim(ptr.x, ptr.y); placeGun('freeze', A.p); const m = gun.muz, d = gun.dir; if (!loops.freeze) loopStart('freeze'); hapStart(0.3, 0.6);
    for (let i = 0; i < 6; i++) { const sp = rnd(-0.07, 0.07), ca = Math.cos(sp), sa = Math.sin(sp), vx = d.x * ca - d.y * sa, vy = d.x * sa + d.y * ca, s = rnd(13, 22); emit({ x: m.x, y: m.y, vx: vx * s, vy: vy * s, life: rnd(0.3, 0.5), s0: 0.18, s1: rnd(0.5, 0.9), c0: 0xf0fdff, c1: 0x3ab0ff, drag: 0.97, a: 0.85 }); }
    if (Math.random() < 0.6) emit({ x: m.x + d.x * rnd(1, 5), y: m.y + d.y * rnd(1, 5), vx: rnd(-1, 1), vy: rnd(-2, 0.5), life: 0.7, s0: 0.1, s1: 0.03, c0: 0xffffff, c1: 0x9fe0ff, g: 2 });
    const reach = Math.min(8, Math.hypot(A.p.x - m.x, A.p.y - m.y) + 2); frT += dt; let any = 0;
    if (doll) for (const q of doll.list) { const b = q.body, rx = b.position.x - m.x, ry = b.position.y - m.y, tp = rx * d.x + ry * d.y; if (tp < 0 || tp > reach) continue; if (Math.abs(rx * d.y - ry * d.x) < 0.6) { q.ice = Math.min(1, (q.ice || 0) + dt * 1.0); any++; hurt(q, dt * 5, null, true, 'freeze'); if (Math.random() < 0.3) emit({ x: b.position.x + rnd(-0.2, 0.2), y: b.position.y + rnd(-0.2, 0.2), vx: rnd(-1, 1), vy: rnd(0, 2), life: 0.45, s0: 0.09, s1: 0.02, c0: 0xffffff, c1: 0x8fe0ff }); } }
    if (any && frT > 0.5) { frT = 0; sfx.crack(); }
  }
  function shatterIce(dx, dy) {
    if (!doll || frozenT <= 0) return; frozenT = 0; const c = doll.parts.chest.body.position, p = V3(c.x, c.y, 0);
    for (const j of doll.joints) if (!j.cut) sever(j, dx == null ? null : dx, dy == null ? null : dy, true);
    for (const q of doll.list) { const b = q.body; b.velocity.x += rnd(-9, 9); b.velocity.y += rnd(2, 11); b.angularVelocity.z += rnd(-14, 14); q.ice = 0; setTint(q, q.burn || 0, 0); for (let i = 0; i < 5; i++) emit({ x: b.position.x, y: b.position.y, vx: rnd(-8, 8), vy: rnd(-2, 9), life: rnd(0.4, 0.9), s0: rnd(0.12, 0.28), s1: 0.04, c0: 0xf4feff, c1: 0x5ac0ff, g: 14, drag: 0.97 }); }
    for (let i = 0; i < 26; i++) emit({ x: p.x, y: p.y, vx: rnd(-6, 6), vy: rnd(-1, 8), life: rnd(0.7, 1.4), s0: rnd(0.15, 0.3), s1: 0.1, c0: 0xc6efff, c1: 0xa0d8f5, g: 16, drag: 0.98, a: 0.9, smoke: true });
    ring(p, 3, 0xbfeaff, 0.4); ring(p, 4.6, 0x8fd8ff, 0.55); sfx.shatter(); sfx.shatter(); flash(0.5, '#cfeeff'); shake(0.9); haptic('thud'); popupT('SHATTERED!', V3(p.x, p.y + 0.8, 0), '#9fe6ff', 10); bloodBurst(p, 24, null, null, 9, 1.2);
    iceShards(p); if (!dead) die('shatter');
  }
  let shardGeo = null, shardMat = null;
  function iceShards(p) {
    if (!shardGeo) { shardGeo = new THREE.TetrahedronGeometry(0.2); shardMat = new THREE.MeshPhongMaterial({ color: 0xbfeaff, emissive: 0x2a6a9a, specular: 0xffffff, shininess: 120, transparent: true, opacity: 0.88, flatShading: true }); }
    for (let i = 0; i < 34; i++) {
      const m = new THREE.Mesh(shardGeo, shardMat), sc = rnd(0.5, 1.7); m.scale.set(sc, sc * rnd(0.6, 1.5), sc * rnd(0.6, 1.2)); m.position.set(p.x + rnd(-0.5, 0.5), p.y + rnd(-0.9, 0.9), rnd(0.2, 1)); m.renderOrder = 5; scene.add(m);
      let vx = rnd(-9, 9), vy = rnd(0, 11), vz = rnd(-2, 2), t = 0; const sx = rnd(-9, 9), sy = rnd(-9, 9), life = rnd(1.4, 2.6);
      addFx((dt) => { t += dt; vy -= 26 * dt; m.position.x += vx * dt; m.position.y += vy * dt; m.position.z += vz * dt; m.rotation.x += sx * dt; m.rotation.y += sy * dt;
        if (m.position.y < 0.12) { m.position.y = 0.12; vy = -vy * 0.35; vx *= 0.7; vz *= 0.7; if (Math.abs(vy) > 2 && Math.random() < 0.4) emit({ x: m.position.x, y: 0.15, vx: rnd(-2, 2), vy: rnd(1, 3), life: 0.4, s0: 0.1, s1: 0.02, c0: 0xffffff, c1: 0x9fe0ff }); }
        if (Math.abs(m.position.x) > RW / 2 - 0.1) vx = -vx * 0.5;
        if (t > life - 0.4) { m.scale.multiplyScalar(Math.max(0.01, 1 - dt * 3)); } if (t > life) { scene.remove(m); return false; } return true; });
    }
  }
  /* --- wrecking ball --- */
  function spawnBall(p) {
    const x = clamp(p.x, -RW / 2 + 1, RW / 2 - 1), g = new THREE.Group(), ballM = phong(0x2a2e36, 90), ball = new THREE.Mesh(new THREE.SphereGeometry(0.82, 28, 20), ballM); g.add(ball);
    const lug = new THREE.Mesh(new THREE.TorusGeometry(0.2, 0.06, 8, 16), phong(0x80868f, 90)); lug.position.y = 0.88; g.add(lug); const hl = new THREE.Mesh(new THREE.SphereGeometry(0.18, 10, 8), new THREE.MeshBasicMaterial({ color: 0x7e8794, transparent: true, opacity: 0.45 })); hl.position.set(-0.3, 0.3, 0.7); g.add(hl); ball.castShadow = true;
    const ex = new THREE.Group(), links = [], PITCH = 0.148, lkGeo = new THREE.TorusGeometry(0.072, 0.03, 10, 22), lkMat = new THREE.MeshPhongMaterial({ color: 0x8b929e, shininess: 140, specular: 0xdfe6f0 }), lkMat2 = new THREE.MeshPhongMaterial({ color: 0x6c727d, shininess: 120, specular: 0xbfc8d4 });
    for (let i = 0; i < 90; i++) { const lg = new THREE.Group(), m = new THREE.Mesh(lkGeo, i % 2 ? lkMat2 : lkMat); m.scale.set(1, 1.6, 1); m.rotation.y = i % 2 ? PI / 2 : 0; m.castShadow = true; lg.add(m); ex.add(lg); links.push(lg); } scene.add(ex);
    const swv = new THREE.Mesh(new THREE.CylinderGeometry(0.09, 0.11, 0.16, 14), phong(0x4a4f58, 120)); swv.position.y = 0.98; g.add(swv); const swr = new THREE.Mesh(new THREE.TorusGeometry(0.09, 0.03, 8, 16), phong(0x9aa1ac, 130)); swr.position.y = 1.12; g.add(swr);
    const bolt = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, 0.1, 10), phong(0x5a606a, 80)); bolt.position.y = 0.84; g.add(bolt);
    const plate = new THREE.Mesh(new THREE.BoxGeometry(0.7, 0.14, 0.3), phong(0x3e434b, 60)); plate.position.set(x, RH + 0.12, 0.1); ex.add(plate);
    for (const rr of [-0.25, 0.25]) { const rv = new THREE.Mesh(new THREE.SphereGeometry(0.05, 8, 6), phong(0x9aa1ac, 120)); rv.position.set(x + rr, RH + 0.08, 0.26); ex.add(rv); }
    const body = new CANNON.Body({ mass: 140, material: propMat, linearDamping: 0.01, angularDamping: 0.3 }); body.addShape(new CANNON.Sphere(0.82)); body.position.set(x, RH - 0.3, 0); body.velocity.set(0, -22, 0); body.collisionFilterGroup = 1; body.collisionFilterMask = 2;
    const t = { kind: 'ball', body, mesh: g, extra: ex, age: 0, landed: false, sl: new Map(), ax: x };
    body.addEventListener('collide', (ev) => { if (ev.body && ev.body.isWall && !t.landed && Math.abs(ev.contact.getImpactVelocityAlongNormal()) > 6) { t.landed = true; t.land = body.position.x; body.velocity.x = (body.position.x > 0 ? -1 : 1) * 7; } });
    t.update = (dt) => {
      t.age += dt; const bp = body.position, top = V3(t.ax, RH + 0.4, 0), dx = bp.x - top.x, dy = bp.y + 0.8 - top.y;
      const lug0 = V3(bp.x, bp.y + 1.1, 0.1), ux = top.x - lug0.x, uy = top.y - lug0.y, ul = Math.hypot(ux, uy) || 1, nx = ux / ul, ny = uy / ul, ang = Math.atan2(uy, ux) - PI / 2, cnt = Math.min(links.length, Math.ceil(ul / PITCH) + 1);
      links.forEach((l, i) => { l.visible = i < cnt; if (i < cnt) { l.position.set(lug0.x + nx * (i + 0.5) * PITCH, lug0.y + ny * (i + 0.5) * PITCH, 0.1); l.rotation.z = ang; } }); ex.visible = true; g.rotation.z = Math.atan2(-nx, ny) * 0.0;
      if (t.land != null) { const l = t.land; t.land = null; const pt = V3(l, 0.1, 0); puff(pt, 0xd8cdb8, 12); ring(pt, 2.6, 0xffe9b8, 0.4); shake(0.6); sfx.thud(); sfx.clank(); haptic('thud'); blow(pt, 0, 0.8, 2.6, 6, 16); }
      if (doll) { const now = performance.now(); let sum = 0; for (const q of doll.list) { const b = q.body, rx = b.position.x - bp.x, ry = b.position.y - bp.y, d = Math.hypot(rx, ry); if (d < 1.15) { b.velocity.x += (rx / (d || 1)) * 10 * dt * 60 * 0.1; b.velocity.y += (ry / (d || 1)) * 6 * dt * 60 * 0.1 - (body.velocity.y < -8 ? 8 : 0) * dt * 6; if (now - (t.sl.get(q) || 0) > 150) { t.sl.set(q, now); const pt = V3(b.position.x, b.position.y, 0); sum += hurt(q, body.velocity.y < -6 ? 80 : 30, pt, true, 'crush', rx / (d || 1), 0.3); pushAt(q, rx / (d || 1) * 7, 3, pt); sparks(pt, 5, 0xffffff, 0xffb040, 8, 0.1); } } }
        if (sum) { popup('-' + sum, V3(bp.x, bp.y + 1, 0), sum); shake(0.5); sfx.thud(); sfx.chop(); haptic('thud'); } }
      if (t.age > 3.4) { const k = Math.max(0, 1 - (t.age - 3.4) / 0.3); g.scale.setScalar(Math.max(0.01, k)); ex.visible = k > 0.2; if (k <= 0) return false; } return true;
    };
    addThing(t); sfx.whoosh(); sfx.rumble();
  }
  /* --- lightning strike --- */
  function doLightning(A) {
    const p = A.p.clone(), top = V3(p.x + rnd(-1, 1), RH + 0.3, 0); let ph = 0, t = 0, meshes = [];
    const draw = () => { for (const m of meshes) scene.remove(m); meshes = []; const pts = jag(top, p, 16, 0.55); for (let i = 0; i < pts.length - 1; i++) { meshes.push(segMesh(pts[i], pts[i + 1], 0.9, lnB, 0.97), segMesh(pts[i], pts[i + 1], 0.34, lnW, 0.98)); }
      for (let b = 0; b < 3; b++) { const k = (Math.random() * (pts.length - 3) | 0) + 1, s = pts[k], e = V3(s.x + rnd(-1.4, 1.4), s.y - rnd(0.5, 1.5), 0), bp = jag(s, e, 4, 0.25); for (let i = 0; i < bp.length - 1; i++) meshes.push(segMesh(bp[i], bp[i + 1], 0.2, lnW, 0.98)); } };
    draw(); explode(p, 2.6, 18, 70, { burn: true, size: 1.5, c0: 0xcfe8ff, c1: 0x6aa8ff, fcol: '#eaf4ff', flash: 0.85, shake: 0.9, vol: 0.8 }); sfx.thunder();
    if (doll) for (const q of doll.list) { const d = Math.hypot(q.body.position.x - p.x, q.body.position.y - p.y); if (d < 3) { q.zap = 0.5; setTint(q, Math.min(1, (q.burn || 0) + 0.5), 0.9); hurt(q, 14 * (1 - d / 3.2), null, true, 'shock'); q.burn = Math.min(1, (q.burn || 0) + 0.45); } }
    for (let i = 0; i < 24; i++) emit({ x: p.x + rnd(-0.4, 0.4), y: p.y + rnd(-0.4, 0.4), vx: rnd(-9, 9), vy: rnd(-2, 9), life: rnd(0.25, 0.6), s0: 0.14, s1: 0.03, c0: 0xffffff, c1: 0x6aa8ff, g: 10 });
    for (let i = 0; i < 12; i++) emit({ x: top.x + (p.x - top.x) * (i / 12), y: top.y + (p.y - top.y) * (i / 12), life: 0.22, s0: 0.9, s1: 0.4, c0: 0xcfe8ff, c1: 0x4a80ff, a: 0.6 });
    addFx((dt) => { t += dt; ph += dt; if (ph > 0.07 && t < 0.28) { ph = 0; draw(); } if (t > 0.3) { for (const m of meshes) scene.remove(m); return false; } return true; });
  }
  /* --- guillotine --- */
  function doGuillotine(A) {
    const x = clamp(A.p.x, -RW / 2 + 1, RW / 2 - 1), g = new THREE.Group(), wood = phong(0x9a5a22, 20), dark = phong(0x6c3a14, 10), steel = phong(0xc9d2de, 130);
    const post = (px) => { const m = new THREE.Mesh(roundBox(0.24, RH - 0.1, 0.36, 0.04, 2), wood); m.position.set(px, (RH - 0.1) / 2, 0.15); g.add(m); }; post(x - 0.95); post(x + 0.95);
    const beam = new THREE.Mesh(roundBox(2.3, 0.3, 0.38, 0.05, 2), dark); beam.position.set(x, RH - 0.25, 0.15); g.add(beam); const stock = new THREE.Mesh(roundBox(2.3, 0.26, 0.5, 0.05, 2), dark); stock.position.set(x, 0.12, 0.2); g.add(stock);
    const sh = new THREE.Shape(); sh.moveTo(-0.85, 0.3); sh.lineTo(0.85, 0.3); sh.lineTo(0.85, -0.18); sh.lineTo(-0.85, -0.34); sh.closePath(); const blade = new THREE.Mesh(new THREE.ExtrudeGeometry(sh, { depth: 0.1, bevelEnabled: false }), steel); blade.position.z = 0.12; const bg = new THREE.Group(); bg.add(blade); g.add(bg);
    g.traverse((m) => { if (m.isMesh) m.castShadow = true; }); g.scale.set(1, 0.01, 1); g.position.y = RH; track(g); bg.position.set(x, RH - 0.8, 0);
    let t = 0, prev = RH - 1.1, phase = 0; const done = new Set(); sfx.whoosh();
    addFx((dt) => {
      t += dt;
      if (phase === 0) { const k = Math.min(1, t / 0.14); g.scale.y = Math.max(0.01, k); g.position.y = RH * (1 - k); if (k >= 1) { phase = 1; t = 0; } return true; }
      if (phase === 1) { const k = Math.min(1, t / 0.3), e = k * k * k, by = RH - 0.8 + (0.4 - (RH - 0.8)) * e, bottom = by - 0.32; bg.position.y = by;
        if (doll) { for (const j of doll.joints) { if (j.cut || done.has(j)) continue; const pw = new CANNON.Vec3(); doll.parts[j.a].body.pointToWorldFrame(j.c.pivotA, pw); if (Math.abs(pw.x - x) < 0.85 && pw.y <= prev && pw.y > bottom - 0.3) { done.add(j); sever(j, 0, -1); } }
          for (const q of doll.list) { const bp = q.body.position; if (Math.abs(bp.x - x) < 0.85 && bp.y <= prev && bp.y > bottom - 0.2 && !q.gl) { q.gl = 1; hurt(q, 30, V3(bp.x, bp.y, 0), true, 'saw', 0, -1); bloodBurst(V3(bp.x, bp.y, 0.4), 12, 0, 1, 7, 1.1); } } }
        prev = bottom; if (k >= 1) { phase = 2; t = 0; shake(0.7); sfx.chop(); sfx.clank(); haptic('thud'); const pt = V3(x, 0.1, 0); puff(pt, 0xd8cdb8, 8); ring(pt, 2, 0xffe9b8, 0.3); sparks(pt, 14, 0xffffff, 0xffb040, 10, 0.1); if (doll) for (const q of doll.list) q.gl = 0; } return true; }
      if (t > 0.7) { const k = 1 - (t - 0.7) / 0.25; g.scale.set(1, Math.max(0.01, 1), 1); g.traverse((m) => { if (m.isMesh) { m.material.transparent = true; m.material.opacity = Math.max(0, k); } }); if (k <= 0) { scene.remove(g); disposeObj(g); return false; } } return true;
    });
  }
  /* --- meteor --- */
  function doMeteor(A) {
    const T = A.p.clone(), side = T.x > 0 ? -1 : 1, S = V3(T.x + side * (RW * 0.8), RH + 3, 0), dir = V3(T.x - S.x, T.y - S.y, 0), L = Math.hypot(dir.x, dir.y), ux = dir.x / L, uy = dir.y / L;
    const g = new THREE.Group(), rock = new THREE.Mesh(new THREE.IcosahedronGeometry(0.55, 1), new THREE.MeshPhongMaterial({ color: 0x3c2a22, emissive: 0xff5a14, emissiveIntensity: 0.55, flatShading: true })); g.add(rock);
    const gl = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowT, color: 0xff7a22, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending })); gl.scale.setScalar(2.6); g.add(gl); g.position.set(S.x, S.y, 0.6); track(g);
    ring(V3(T.x, T.y, 0), 1.8, 0xff4a1a, 0.6); ring(V3(T.x, T.y, 0), 0.9, 0xffa030, 0.6); sfx.rumble(); let t = 0; const dur = 0.62;
    addFx((dt) => { t += dt; const k = Math.min(1, t / dur), x = S.x + dir.x * k, y = S.y + dir.y * k; g.position.set(x, y, 0.6); rock.rotation.x += dt * 6; rock.rotation.y += dt * 4;
      for (let i = 0; i < 4; i++) { emit({ x: x - ux * rnd(0, 0.8), y: y - uy * rnd(0, 0.8), vx: rnd(-1, 1), vy: rnd(-1, 1), life: rnd(0.3, 0.6), s0: 0.5, s1: 0.1, c0: 0xffe28a, c1: 0xff3a08 }); } emit({ x: x - ux * 0.6, y: y - uy * 0.6, vx: rnd(-0.5, 0.5), vy: rnd(0, 1), life: 0.9, s0: 0.3, s1: 1.0, c0: 0x6a6460, c1: 0x2a2624, a: 0.6, smoke: true });
      if (k >= 1) { scene.remove(g); disposeObj(g); explode(V3(T.x, T.y, 0), 4.3, 40, 135, { burn: true, size: 3.6, shake: 1.2, vol: 1.7, flash: 0.7, fcol: '#ffe0b0' }); for (let i = 0; i < 18; i++) { const a = rnd(0, PI), s = rnd(4, 13); emit({ x: T.x, y: T.y, vx: Math.cos(a) * s * (Math.random() < 0.5 ? -1 : 1), vy: Math.sin(a) * s, life: rnd(0.8, 1.6), s0: rnd(0.15, 0.32), s1: 0.1, c0: 0x4a3a30, c1: 0x2a201a, g: 15, drag: 0.98, a: 1, smoke: true }); } popupT('METEOR!', V3(T.x, T.y + 1.4, 0), '#ff9a2a', 9); return false; } return true; });
  }
  /* --- crossbow: arrows that nail the ragdoll to the wall --- */
  function doCrossbow(A) {
    cd = 0.65; gunId = 'crossbow'; gun.vis = 1.2; gun.kick = 0.45; placeGun('crossbow', A.p); const from = gun.muz.clone(), part = A.part; sfx.thwip(); haptic('thud'); shake(0.15);
    let dx = A.p.x - from.x, dy = A.p.y - from.y; const L0 = Math.hypot(dx, dy) || 1; dx /= L0; dy /= L0;
    // end of the arrow's line: first wall it reaches
    let tw = 20; if (dx > 0.001) tw = Math.min(tw, (RW / 2 - 0.05 - from.x) / dx); else if (dx < -0.001) tw = Math.min(tw, (-RW / 2 + 0.05 - from.x) / dx); if (dy > 0.001) tw = Math.min(tw, (RH - 0.1 - from.y) / dy); else if (dy < -0.001) tw = Math.min(tw, (0.1 - from.y) / dy);
    const end = V3(from.x + dx * tw, from.y + dy * tw, 0), ang = Math.atan2(dy, dx), g = new THREE.Group(), steel = phong(0xcdd5df, 120), wood = phong(0x8a5a2a, 10);
    const shaft = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 1.1, 8), wood); g.add(shaft); const hd = new THREE.Mesh(new THREE.ConeGeometry(0.08, 0.22, 8), steel); hd.position.y = 0.66; g.add(hd); for (const s of [-1, 1]) { const f = new THREE.Mesh(new THREE.BoxGeometry(0.01, 0.2, 0.14), phong(0xd8262c, 10)); f.position.set(0, -0.45, s * 0.07); g.add(f); } g.rotation.z = ang - PI / 2; g.position.set(from.x, from.y, 0.9); track(g);
    const speed = 60; let t = 0, hit = false, stuck = false; const tgt = part && doll ? V3(A.p.x, A.p.y, 0) : end, Lh = Math.hypot(tgt.x - from.x, tgt.y - from.y);
    addFx((dt) => {
      t += dt; const d = speed * t;
      if (!hit) { const hd2 = Math.min(d, Lh); g.position.set(from.x + dx * (hd2 - 0.4), from.y + dy * (hd2 - 0.4), 0.9); emit({ x: g.position.x, y: g.position.y, life: 0.16, s0: 0.16, s1: 0.03, c0: 0xffffff, c1: 0xffe9a0, a: 0.75 }); emit({ x: g.position.x - dx * 0.5, y: g.position.y - dy * 0.5, life: 0.3, s0: 0.2, s1: 0.02, c0: 0xcfeaff, c1: 0x6ab8ff, a: 0.5 }); if (d >= Lh) { hit = true; if (part && doll && doll.list.indexOf(part) >= 0) { const head = part.name === 'head'; hurt(part, head ? 420 : 55, tgt, false, 'bullet', dx, dy); if (head) popupT('HEADSHOT!', V3(tgt.x, tgt.y + 0.9, 0), '#ff3b30', 10); woundAt(part, tgt, dx, dy); bloodBurst(V3(tgt.x, tgt.y, 0.5), 22, dx, dy, 11, 1.3); bloodBurst(V3(tgt.x, tgt.y, 0.5), 10, -dx, -dy, 6, 1.0); pushAt(part, dx * 16, dy * 16 + 2, tgt); sfx.chop(); sfx.thud(); shake(0.45); flash(0.12, '#ffffff'); slow = Math.max(slow, 0.18); ring(V3(tgt.x, tgt.y, 0.5), 1.6, 0xffe9b8, 0.3);
              const anc = new CANNON.Body({ mass: 0, type: CANNON.Body.STATIC }); anc.position.set(end.x, end.y, 0); anc.collisionFilterGroup = 8; anc.collisionFilterMask = 0; world.addBody(anc); const lp = part.body.pointToLocalFrame(new CANNON.Vec3(tgt.x, tgt.y, 0)); const con = new CANNON.PointToPointConstraint(anc, new CANNON.Vec3(0, 0, 0), part.body, lp, 900 * (part.body.mass + 3)); world.addConstraint(con); pins.push({ anc, con, t: 12 });
              g.position.set(end.x - dx * 0.45, end.y - dy * 0.45, 0.9); stuck = true; t = 0; sparks(V3(end.x, end.y, 0), 10, 0xffffff, 0xffd34a, 7, 0.08); puff(V3(end.x, end.y, 0.3), 0xcdb38a, 6); for (let i = 0; i < 3; i++) bloodDecal('back', end.x + rnd(-0.5, 0.5), end.y + rnd(-0.5, 0.5), 0, rnd(0.5, 1.1)); decal(end.x, end.y, 0.28, 'hole'); sfx.thud(); haptic('thud'); } else { decal(end.x, end.y, 0.3, 'hole'); g.position.set(end.x - dx * 0.4, end.y - dy * 0.4, 0.9); stuck = true; t = 0; sfx.thud(); } } return true; }
      if (stuck && t < 0.9) { g.rotation.z = ang - PI / 2 + Math.sin(t * 42) * 0.09 * Math.exp(-t * 4.5); }
      if (stuck && t > 11.5) { const k = Math.max(0, 1 - (t - 11.5) / 0.4); g.scale.setScalar(Math.max(0.01, k)); if (k <= 0) { scene.remove(g); disposeObj(g); return false; } } return true;
    });
  }
  function updPins(dt) { for (let i = pins.length - 1; i >= 0; i--) { const p = pins[i]; p.t -= dt; if (p.t <= 0) { try { world.removeConstraint(p.con); world.removeBody(p.anc); } catch (e) {} pins.splice(i, 1); } } }
  function clearPins() { for (const p of pins.splice(0)) { try { world.removeConstraint(p.con); world.removeBody(p.anc); } catch (e) {} } }

  let fxObjs = []; function track(o) { scene.add(o); fxObjs.push(o); if (fxObjs.length > 300) fxObjs = fxObjs.filter((x) => x.parent); return o; }
  const HOLD = { pistol: 1, taser: 1, flame: 1, chainsaw: 1, freeze: 1, minigun: 1 };
  /* ======================= ways, batch 3 ======================= */
  let lnR = null, lnRW = null, waspTex = null, mgT = 0, buzz = null;
  const mag = { on: false, x: 0, y: 0 };
  function initWays3() {
    lnR = new THREE.MeshBasicMaterial({ map: lnT, color: 0xff2418, transparent: true, opacity: 0.9, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide });
    lnRW = new THREE.MeshBasicMaterial({ map: lnT, color: 0xffe6e0, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide });
    const c = document.createElement('canvas'); c.width = 64; c.height = 64; const g = c.getContext('2d');
    g.fillStyle = 'rgba(225,242,255,.8)'; g.strokeStyle = 'rgba(40,60,90,.9)'; g.lineWidth = 1.6; g.beginPath(); g.ellipse(22, 22, 9, 17, -0.6, 0, 6.28); g.fill(); g.stroke(); g.beginPath(); g.ellipse(42, 22, 9, 17, 0.6, 0, 6.28); g.fill(); g.stroke();
    g.fillStyle = '#f6c51c'; g.strokeStyle = '#1e1606'; g.lineWidth = 3; g.beginPath(); g.ellipse(32, 40, 12, 17, 0, 0, 6.28); g.fill(); g.stroke();
    g.save(); g.beginPath(); g.ellipse(32, 40, 12, 17, 0, 0, 6.28); g.clip(); g.fillStyle = '#1e1606'; g.fillRect(16, 33, 32, 5); g.fillRect(16, 43, 32, 5); g.restore();
    g.fillStyle = '#1e1606'; g.beginPath(); g.arc(32, 22, 8, 0, 6.28); g.fill(); g.fillStyle = '#ff3b30'; g.beginPath(); g.arc(28.5, 21, 2.3, 0, 6.28); g.arc(35.5, 21, 2.3, 0, 6.28); g.fill();
    g.fillStyle = '#1e1606'; g.beginPath(); g.moveTo(32, 58); g.lineTo(29, 51); g.lineTo(35, 51); g.fill();
    waspTex = new THREE.CanvasTexture(c);
    Object.assign(sfx, {
      mg() { sNoise(0.07, 4200, 500, 0.3); sTone('square', 170, 60, 0.06, 0.12); },
      laser() { sTone('sawtooth', 1800, 300, 0.5, 0.14); sNoise(0.5, 9000, 2000, 0.25, 'highpass'); sTone('sine', 90, 50, 0.5, 0.4); },
      sizzle() { sNoise(0.11, 8000, 3500, 0.16, 'highpass'); },
      whistle() { sTone('sine', 2400, 600, 0.8, 0.12); sNoise(0.8, 3000, 800, 0.1, 'bandpass', 2); },
      cannon() { sNoise(0.7, 2200, 80, 0.9); sTone('sine', 80, 26, 0.7, 0.9); sTone('sawtooth', 160, 40, 0.3, 0.3); },
      jet() { sNoise(1.3, 600, 2600, 0.35, 'bandpass', 0.6); sTone('sawtooth', 120, 260, 1.2, 0.1); },
      magnet() { sTone('sine', 70, 140, 1.0, 0.4); sNoise(1.0, 400, 3000, 0.2, 'bandpass', 1.2); },
      slam() { sTone('sine', 80, 25, 0.5, 0.9); sNoise(0.3, 1800, 150, 0.7); sTone('square', 300, 90, 0.2, 0.3); }
    });
  }
  function buzzStart() {
    if (!AC || buzz) return; const o = AC.createOscillator(), l = AC.createOscillator(), lg = AC.createGain(), g = AC.createGain(); o.type = 'sawtooth'; o.frequency.value = 185; l.frequency.value = 47; lg.gain.value = 45; l.connect(lg); lg.connect(o.frequency);
    g.gain.value = 0.0001; g.gain.exponentialRampToValueAtTime(0.085, AC.currentTime + 0.3); o.connect(g); g.connect(AC.destination); o.start(); l.start(); buzz = { o, l, g };
  }
  function buzzStop() { if (!buzz) return; const b = buzz; buzz = null; try { b.g.gain.cancelScheduledValues(AC.currentTime); b.g.gain.setValueAtTime(b.g.gain.value, AC.currentTime); b.g.gain.exponentialRampToValueAtTime(0.0001, AC.currentTime + 0.25); setTimeout(() => { try { b.o.stop(); b.l.stop(); } catch (e) {} }, 320); } catch (e) {} }
  function pinPart(part, pt, secs, str) {
    const anc = new CANNON.Body({ mass: 0, type: CANNON.Body.STATIC }); anc.position.set(pt.x, pt.y, 0); anc.collisionFilterGroup = 8; anc.collisionFilterMask = 0; world.addBody(anc);
    const lp = part.body.pointToLocalFrame(new CANNON.Vec3(pt.x, pt.y, 0)), con = new CANNON.PointToPointConstraint(anc, new CANNON.Vec3(0, 0, 0), part.body, lp, (str || 900) * (part.body.mass + 3)); world.addConstraint(con); pins.push({ anc, con, t: secs });
  }
  const jointOf = (part) => doll.joints.find((q) => q.b === part.name && !q.cut);

  /* --- minigun: hold, spins up --- */
  function holdMinigun(dt) {
    gunId = 'minigun'; gun.vis = Math.max(gun.vis, 0.25); const A = aim(ptr.x, ptr.y); placeGun('minigun', A.p);
    if (mgT === 0) { sTone('sawtooth', 70, 360, 0.7, 0.12); } mgT = Math.min(1, mgT + dt / 0.85); hapStart(0.35 + 0.4 * mgT, 0.9);
    if (cd <= 0) {
      cd = 0.16 - 0.125 * mgT; gun.kick = rnd(0.05, 0.14); const m = gun.muz, d = gun.dir; emit({ x: m.x, y: m.y, life: 0.05, s0: 0.7 + 0.5 * mgT, s1: 0.9, c0: 0xffffff, c1: 0xffb040 });
      casing(false); if (mgT > 0.5) casing(false); bulletShot(10 + 10 * mgT, 3.5, rnd(9, 15), false, 80); if (mgT > 0.5) bulletShot(14 + 10 * mgT, 3.5, rnd(9, 15), false, 80);
      sfx.mg(); shake(0.04 + 0.06 * mgT);
      if (Math.random() < 0.3) emit({ x: m.x + d.x * 0.3, y: m.y + d.y * 0.3, vx: d.x * 2, vy: 1 + d.y * 2, life: 0.8, s0: 0.12, s1: 0.5, c0: 0x9a9a9a, c1: 0x555555, a: 0.4, smoke: true, g: -0.6 });
    }
  }

  /* --- laser grid --- */
  function doLaserGrid(A) {
    const W = 2.7, H = 2.2, step = 0.62, cx = clamp(A.p.x, -RW / 2 + W * 0.5, RW / 2 - W * 0.5), cy = clamp(A.p.y, 1.5, RH - 1.2), nV = Math.floor(2 * W / step) + 1, nH = Math.floor(2 * H / step) + 1, ms = [], mats = [lnR.clone(), lnRW.clone()];
    const put = () => { const t0 = ms.length; for (let i = 0; i < nV; i++) { const x = cx - W + i * step; ms.push([segMesh(V3(x, cy - H, 0), V3(x, cy + H, 0), 0.06, mats[0], 0.96), segMesh(V3(x, cy - H, 0), V3(x, cy + H, 0), 0.02, mats[1], 0.97), 0, i]); } for (let i = 0; i < nH; i++) { const y = cy - H + i * step; ms.push([segMesh(V3(cx - W, y, 0), V3(cx + W, y, 0), 0.06, mats[0], 0.96), segMesh(V3(cx - W, y, 0), V3(cx + W, y, 0), 0.02, mats[1], 0.97), 1, i]); } };
    put(); let t = 0, fired = false, cuts = 0, hurtT = 0; sfx.whoosh(); const corners = [V3(cx - W, cy - H, 0), V3(cx + W, cy - H, 0), V3(cx - W, cy + H, 0), V3(cx + W, cy + H, 0)];
    addFx((dt) => {
      t += dt; const warn = t < 0.55, fire = !warn && t < 1.05; let ox = 0, oy = 0;
      if (fire && !fired) { fired = true; sfx.laser(); shake(0.55); flash(0.28, '#ff3020'); haptic('thud'); popupT('LASER GRID!', V3(cx, cy + H * 0.6, 0), '#ff5a4a', 9); }
      if (fire) { ox = Math.sin((t - 0.55) * 46) * 0.2; oy = Math.cos((t - 0.55) * 38) * 0.2; }
      const th = warn ? 0.025 : fire ? 0.16 : 0, fl = warn ? (Math.random() < 0.55 ? 1 : 0.25) : 1; mats[0].opacity = 0.9 * fl; mats[1].opacity = fl;
      for (const m of ms) { const [a, b, o, i] = m, k = th; if (o === 0) { a.position.x = cx - W + i * step + ox; b.position.x = a.position.x; } else { a.position.y = cy - H + i * step + oy; b.position.y = a.position.y; } a.scale.y = k * 1.4; b.scale.y = k * 0.45; a.visible = b.visible = k > 0; }
      for (const c of corners) emit({ x: c.x, y: c.y, life: 0.12, s0: warn ? 0.35 : 0.8, s1: 0.2, c0: 0xff5040, c1: 0xff2010, a: 0.8 });
      if (fire && doll) {
        hurtT -= dt; const inB = (x, y) => Math.abs(x - cx) < W && Math.abs(y - cy) < H, nd = (v, o) => { const m = (((v - o) % step) + step) % step; return Math.min(m, step - m); };
        for (const j of doll.joints) { if (j.cut) continue; const pw = new CANNON.Vec3(); doll.parts[j.a].body.pointToWorldFrame(j.c.pivotA, pw); if (!inB(pw.x, pw.y)) continue; const dX = nd(pw.x, cx - W + ox), dY = nd(pw.y, cy - H + oy); if (Math.min(dX, dY) < 0.1) { sever(j, rnd(-1, 1), rnd(0, 1)); cuts++; sparks(V3(pw.x, pw.y, 0), 8, 0xffffff, 0xff4030, 8, 0.07); if (cuts === 4) popupT('DICED!', V3(cx, cy - 0.4, 0), '#ffd23f', 10); } }
        if (hurtT <= 0) { hurtT = 0.07; let sum = 0; for (const q of doll.list) { const b = q.body.position; if (!inB(b.x, b.y)) continue; const dX = nd(b.x, cx - W + ox), dY = nd(b.y, cy - H + oy); if (Math.min(dX, dY) < 0.16) { sum += hurt(q, 12, V3(b.x, b.y, 0), true, 'laser', rnd(-1, 1), 0.3); q.burn = Math.min(1, (q.burn || 0) + 0.04); setTint(q, q.burn, q.shock || 0); sparks(V3(b.x, b.y, 0), 3, 0xffffff, 0xff3a20, 6, 0.06); puff(V3(b.x, b.y, 0), 0x6a5a50, 1); } } if (sum) popup('-' + sum, V3(cx, cy + 0.2, 0), sum); }
      }
      if (t > 1.1) { for (const m of ms) { scene.remove(m[0]); scene.remove(m[1]); } return false; } return true;
    });
  }

  /* --- acid --- */
  const ACIDC = new THREE.Color(0x72e21e), STINGC = new THREE.Color(0xb23d5a);
  function doAcid(A) {
    const px = clamp(A.p.x, -RW / 2 + 1.3, RW / 2 - 1.3), g = new THREE.Group(), steel = phong(0x5f6f88, 90);
    const body = new THREE.Mesh(new THREE.CylinderGeometry(0.44, 0.34, 0.66, 24, 1, true), steel); g.add(body); const bot = new THREE.Mesh(new THREE.CircleGeometry(0.34, 24), steel); bot.rotation.x = PI / 2; bot.position.y = -0.33; g.add(bot);
    const rim = new THREE.Mesh(new THREE.TorusGeometry(0.44, 0.04, 8, 28), phong(0x9aa8bd, 110)); rim.rotation.x = PI / 2; rim.position.y = 0.33; g.add(rim);
    const liq = new THREE.Mesh(new THREE.CircleGeometry(0.42, 24), new THREE.MeshBasicMaterial({ color: 0x8aff2a })); liq.rotation.x = -PI / 2; liq.position.y = 0.27; g.add(liq);
    const st = new THREE.Mesh(new THREE.CircleGeometry(0.17, 20), new THREE.MeshBasicMaterial({ color: 0xffd400 })); st.position.set(0, 0, 0.42); g.add(st); const sk = new THREE.Mesh(new THREE.CircleGeometry(0.07, 14), new THREE.MeshBasicMaterial({ color: 0x1a1a1a })); sk.position.set(0, 0.01, 0.43); g.add(sk);
    g.traverse((m) => { if (m.isMesh) m.castShadow = true; }); track(g);
    const strM = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial({ color: 0x69e61c, transparent: true, opacity: 0.85, depthWrite: false })); strM.renderOrder = 7; track(strM);
    const pool = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial({ map: glowT, color: 0x5ee014, transparent: true, opacity: 0.8, depthWrite: false })); pool.position.set(px, 0.14, 0.4); pool.scale.set(0.01, 0.01, 1); track(pool);
    let t = 0, ps = 0; const d0 = doll; sfx.whoosh();
    addFx((dt) => {
      t += dt; const ang = t < 0.5 ? (t / 0.5) * 1.95 : t < 3.1 ? 1.95 : Math.max(0, 1.95 - (t - 3.1) * 4), sx = -0.44 * Math.cos(ang) - 0.31 * Math.sin(ang) * 0 - Math.sin(ang) * 0.33, sy = -0.44 * Math.sin(ang) + 0.33 * Math.cos(ang);
      const by = RH - 1.2 - (t > 3.1 ? (t - 3.1) * 8 : 0), bx = px - (-0.44 * Math.cos(ang) - Math.sin(ang) * 0.33); g.position.set(bx, by, 0.5); g.rotation.z = ang; const spX = bx + sx, spY = by + sy;
      let floorY = 0.12, pouring = t > 0.35 && t < 3.0 && doll === d0;
      if (pouring && doll) { let top = -1; for (const q of doll.list) { const b = q.body.position; if (Math.abs(b.x - spX) < 0.5 && b.y < spY) top = Math.max(top, b.y + 0.18); } if (top > 0) floorY = top; }
      if (pouring) {
        strM.visible = true; strM.position.set(spX, (spY + floorY) / 2, 0.45); strM.scale.set(0.24 + Math.sin(t * 30) * 0.03, spY - floorY, 1);
        for (let i = 0; i < 5; i++) emit({ x: spX + rnd(-0.1, 0.1), y: spY, vx: rnd(-0.4, 0.4), vy: -rnd(1, 3), life: 0.5, s0: 0.2, s1: 0.08, c0: 0xd4ff66, c1: 0x38a010, g: 14, a: 0.9 });
        for (let i = 0; i < 4; i++) emit({ x: spX + rnd(-0.3, 0.3), y: floorY + 0.05, vx: rnd(-3, 3), vy: rnd(1, 4.5), life: rnd(0.3, 0.6), s0: 0.14, s1: 0.04, c0: 0xc8ff5a, c1: 0x3aa812, g: 14, a: 0.9 });
        if (doll) for (const q of doll.list) { const b = q.body.position; if (Math.abs(b.x - spX) < 0.52 && b.y < spY) { q.acid = Math.min(1, (q.acid || 0) + dt * 0.55); } }
        const pw = Math.min(2.4, t * 1.3); pool.scale.set(pw, 0.24, 1); sfx.sizzle && Math.random() < 0.3 && sfx.sizzle();
      } else strM.visible = false;
      if (t > 3.1) { pool.material.opacity = Math.max(0, 0.8 - (t - 3.1) * 0.15); } if (t > 3.6) g.scale.setScalar(Math.max(0.01, 1 - (t - 3.6) * 4));
      if (t > 9) { scene.remove(pool); scene.remove(g); scene.remove(strM); return false; } return true;
    });
  }
  let acT = 0, acFl = 0, acPop = 0;
  function updAcid(dt) {
    if (!doll) return; let any = 0, sum = 0; acT += dt; acFl -= dt; acPop += dt;
    for (const j of doll.joints) { const A = doll.parts[j.a], B = doll.parts[j.b]; if (!A || !B || j.cut) continue; if ((A.acid || 0) > 0.5) B.acid = Math.min(1, (B.acid || 0) + dt * 0.12 * A.acid); if ((B.acid || 0) > 0.5) A.acid = Math.min(1, (A.acid || 0) + dt * 0.12 * B.acid); }
    for (const q of doll.list) {
      const a = q.acid || 0; if (a <= 0) continue; any++; const b = q.body.position;
      if (!dead) sum += hurt(q, dt * (6 + 24 * a), null, true, 'acid'); if (a > 0.7) q.zap = 0.25; if (a >= 1 && !q.melt) { q.melt = true; puff(b, 0x6ab02a, 5); sfx.pop && sfx.pop(); }
      if (Math.random() < dt * 14 * a) emit({ x: b.x + rnd(-0.2, 0.2), y: b.y + rnd(-0.15, 0.25), vx: rnd(-0.4, 0.4), vy: rnd(0.6, 1.8), life: rnd(0.5, 0.9), s0: rnd(0.08, 0.18), s1: 0.03, c0: 0xd4ff6a, c1: 0x3aa810, a: 0.9 });
      if (Math.random() < dt * 6 * a) emit({ x: b.x, y: b.y + 0.2, vx: rnd(-0.3, 0.3), vy: rnd(0.8, 1.6), life: 1.0, s0: 0.2, s1: 0.8, c0: 0x6ab02a, c1: 0x2a4a10, a: 0.45, smoke: true, g: -0.6 });
      if (Math.random() < dt * 5 * a) emit({ x: b.x + rnd(-0.1, 0.1), y: b.y - 0.15, vx: rnd(-0.2, 0.2), vy: -rnd(0.2, 1), life: 0.7, s0: 0.1, s1: 0.05, c0: 0xb6ff4a, c1: 0x3aa810, g: 12, a: 0.9 });
    }
    if (any && !dead && acFl <= 0) { acFl = rnd(0.12, 0.28); for (let k = 0; k < 2; k++) { const q = doll.list[(Math.random() * doll.list.length) | 0], bb = q.body; bb.velocity.x += rnd(-4, 4); bb.velocity.y += rnd(0.5, 5); bb.angularVelocity.z += rnd(-9, 9); } }
    if (any && Math.random() < dt * 7) sfx.sizzle();
    if (any && acPop > 0.7 && sum) { acPop = 0; const c = doll.parts.chest.body.position; popup('-' + Math.max(1, Math.round(sum * 3)), V3(c.x, c.y + 0.7, 0), 9); }
  }

  /* --- bear trap --- */
  function spawnBeartrap(p) {
    const x = clamp(p.x, -RW / 2 + 1, RW / 2 - 1), g = new THREE.Group(), rust = phong(0x8a4a26, 40), steel = phong(0xb6bec9, 110), dark = phong(0x4a2a16, 20);
    const plate = new THREE.Mesh(roundBox(0.55, 0.08, 0.6, 0.03, 2), dark); plate.position.y = 0.04; g.add(plate); const trg = new THREE.Mesh(new THREE.CylinderGeometry(0.17, 0.17, 0.05, 20), rust); trg.position.y = 0.11; g.add(trg);
    const mkJaw = (s) => { const j = new THREE.Group(), bar = new THREE.Mesh(roundBox(0.62, 0.07, 0.4, 0.03, 2), rust); bar.position.x = s * 0.36; j.add(bar); for (let i = 0; i < 5; i++) { const t = new THREE.Mesh(new THREE.ConeGeometry(0.065, 0.24, 8), steel); t.position.set(s * (0.15 + i * 0.12), 0.15, 0.06); j.add(t); const t2 = t.clone(); t2.position.z = -0.08; j.add(t2); } j.position.set(s * 0.14, 0.1, 0); return j; };
    const jl = mkJaw(-1), jr = mkJaw(1); g.add(jl, jr); const open = 0.2; jl.rotation.z = -open; jr.rotation.z = open; g.position.set(x, 0, 0.5); g.scale.setScalar(1.5); g.traverse((m) => { if (m.isMesh) m.castShadow = true; }); track(g);
    let t = 0, state = 0, closeT = 0; puff(V3(x, 0.15, 0), 0xd8cdb8, 4); sfx.clank(); haptic('tap');
    addFx((dt) => {
      t += dt; const d0 = doll;
      if (state === 0) { if (t > 0.5 && doll) { let hit = null, bd = 9; for (const q of doll.list) { const b = q.body.position, dx = Math.abs(b.x - x); if (b.y < 0.8 && dx < 0.62 && dx < bd) { bd = dx; hit = q; } } if (hit) { state = 1; closeT = 0; snapTrap(hit, x); } } if (t > 25) { scene.remove(g); disposeObj(g); return false; } }
      else if (state === 1) { closeT += dt; const k = Math.min(1, closeT / 0.07), e = k * k; jl.rotation.z = -open - (1.45 - open) * e; jr.rotation.z = open + (1.45 - open) * e; if (closeT > 11) state = 2; }
      else { g.scale.setScalar(Math.max(0.01, g.scale.x - dt * 3)); if (g.scale.x <= 0.02) { scene.remove(g); disposeObj(g); return false; } }
      return true;
    });
  }
  function snapTrap(part, x) {
    const pt = V3(x, 0.4, 0), dx = 0, dy = 1; sfx.snap(); sfx.clank(); sfx.crack(); shake(0.7); haptic('thud'); flash(0.18, '#ffffff');
    hurt(part, 95, pt, false, 'crush', dx, dy); woundAt(part, pt, dx, dy); bloodBurst(V3(x, 0.45, 0.5), 30, 0, 1, 9, 1.3); sparks(pt, 12, 0xffffff, 0xffd34a, 9, 0.08); popupT('BEAR TRAP!', V3(x, 1.2, 0), '#ffd23f', 9);
    const j = jointOf(part); if (j && Math.random() < 0.75) { tear(part, 0, 1); } pinPart(part, pt, 9, 1400); part.body.velocity.set(0, 0, 0);
    if (doll) for (const q of doll.list) if (q !== part) { q.body.velocity.y += rnd(1, 4); q.body.angularVelocity.z += rnd(-4, 4); }
  }

  /* --- nuke --- */
  function doNuke(A) {
    const x = clamp(A.p.x, -RW / 2 + 1.5, RW / 2 - 1.5), g = new THREE.Group(), olive = phong(0x586c2a, 70);
    const body = new THREE.Mesh(new THREE.SphereGeometry(0.42, 20, 16), olive); body.scale.set(1, 1.55, 1); g.add(body); for (let i = 0; i < 4; i++) { const f = new THREE.Mesh(new THREE.BoxGeometry(0.03, 0.4, 0.4), phong(0xc23a2a, 30)); f.position.y = 0.58; f.rotation.y = i * PI / 4; g.add(f); }
    const dsc = new THREE.Mesh(new THREE.CircleGeometry(0.2, 20), new THREE.MeshBasicMaterial({ color: 0xffd21a })); dsc.position.set(0, -0.05, 0.42); g.add(dsc); g.traverse((m) => { if (m.isMesh) m.castShadow = true; }); g.position.set(x, RH + 1.4, 0.4); g.rotation.z = rnd(-0.1, 0.1); track(g);
    let t = 0; const T = 0.85; sfx.whistle(); const bx = x;
    addFx((dt) => {
      t += dt; const k = Math.min(1, t / T), y = RH + 1.4 + (0.55 - RH - 1.4) * k * k; g.position.y = y; emit({ x: bx, y: y + 0.9, life: 0.4, s0: 0.3, s1: 0.8, c0: 0xcfcfcf, c1: 0x707070, a: 0.5, smoke: true });
      if (k >= 1) { scene.remove(g); disposeObj(g); nukeBlast(bx); return false; } return true;
    });
  }
  function nukeBlast(x) {
    const p = V3(x, 0.6, 0); flash(1, '#ffffff'); setTimeout(() => flash(0.55, '#ff9a40'), 260); shake(2.2); haptic('thud');
    explode(p, 14, 52, 1100, { burn: true, size: 7, shake: 2.2, vol: 2.8, flash: 1, fcol: '#ffffff', c0: 0xfff0c0, c1: 0xff5a10 });
    if (doll) { for (const j of doll.joints) if (!j.cut) sever(j, rnd(-1, 1), rnd(0, 1), true); if (!dead) die('blast'); popupT('VAPORIZED!', V3(x, 3, 0), '#ffe04a', 12); }
    ring(p, 14, 0xfff0c0, 0.7); ring(p, 10, 0xffa040, 0.55); ring(p, 6, 0xffffff, 0.4); sfx.boom(2.4); sfx.rumble && sfx.rumble(); decal(x, 0.5, 10, 'scorch');
    emit({ x, y: 1.0, life: 0.7, s0: 4, s1: 15, c0: 0xffffff, c1: 0xffa030, a: 1, ap: 1.4 });
    for (let i = 0; i < 26; i++) { const s = (Math.random() < 0.5 ? -1 : 1) * rnd(7, 24); emit({ x: x + rnd(-1, 1), y: rnd(0.2, 0.9), vx: s, vy: rnd(0, 1.5), life: rnd(1.0, 1.9), s0: 0.9, s1: 2.6, c0: 0xcdb08a, c1: 0x6a5a48, a: 0.7, smoke: true, drag: 0.96 }); }
    let t = 0, tick = 0; const top = Math.min(RH - 1.0, 8.5);
    addFx((dt) => {
      t += dt; tick -= dt; if (tick <= 0 && t < 3.4) { tick = 0.05; const rise = top * (1 - Math.exp(-t * 1.55));
        for (let i = 0; i < 2; i++) emit({ x: x + rnd(-0.5, 0.5), y: 0.6 + rise * rnd(0.1, 0.95), vx: rnd(-0.5, 0.5), vy: rnd(0.5, 1.5), life: 1.5, s0: 1.0, s1: 1.8, c0: t < 1 ? 0xff9a3a : 0x6a5a50, c1: 0x2e2824, a: 0.8, smoke: true, drag: 0.96 });
        for (let i = 0; i < 3; i++) { const a = rnd(0.1, 3.04), s = rnd(2.2, 4.8) * Math.min(1, t * 1.2); emit({ x: x + Math.cos(a) * 0.7, y: 0.6 + rise + Math.sin(a) * 0.5, vx: Math.cos(a) * s, vy: Math.sin(a) * s * 0.35 - 0.2, life: 1.6, s0: 1.1, s1: 2.3, c0: t < 1.1 ? 0xffb050 : 0x7a6a60, c1: 0x2e2824, a: 0.85, smoke: true, drag: 0.95 }); }
        emit({ x: x + rnd(-0.4, 0.4), y: 0.6 + rise + rnd(-0.4, 0.5), life: 0.5, s0: 1.8, s1: 3.2, c0: 0xffcf6a, c1: 0xff4a10, a: 0.7 }); }
      return t < 3.5;
    });
  }

  /* --- giant magnet --- */
  function doMagnet(A) {
    const mx = clamp(A.p.x, -RW / 2 + 1.4, RW / 2 - 1.4), g = new THREE.Group(), red = phong(0xe02a1c, 80), silver = phong(0xd5dce6, 120);
    const arc = new THREE.Mesh(new THREE.TorusGeometry(0.62, 0.22, 14, 28, PI), red); g.add(arc); for (const s of [-1, 1]) { const l = new THREE.Mesh(new THREE.CylinderGeometry(0.22, 0.22, 0.6, 16), red); l.position.set(s * 0.62, -0.3, 0); g.add(l); const tp = new THREE.Mesh(new THREE.CylinderGeometry(0.235, 0.235, 0.3, 16), silver); tp.position.set(s * 0.62, -0.75, 0); g.add(tp); }
    g.traverse((m) => { if (m.isMesh) m.castShadow = true; }); g.position.set(mx, RH + 1.5, 0.5); track(g);
    const hy = RH - 1.6, poleY = hy - 0.95; let t = 0, rel = false, slamT = 0; sfx.magnet(); const d0 = doll;
    addFx((dt) => {
      t += dt; const kIn = Math.min(1, t / 0.4); if (!rel) g.position.y = RH + 1.5 + (hy - RH - 1.5) * (1 - Math.pow(1 - kIn, 3));
      if (t <= 0.3) { /* descending */ } else if (t < 3.0 && doll === d0) { mag.on = true; mag.x = mx; mag.y = poleY - 0.25; const tips = [V3(mx - 0.62, poleY - 0.2, 0), V3(mx + 0.62, poleY - 0.2, 0)];
        for (const q of doll.list) { const b = q.body.position, dx = b.x - mx, dy = b.y - poleY, d = Math.hypot(dx, dy); if (d < 4.5 && Math.random() < 0.5) bolt(tips[dx < 0 ? 0 : 1], V3(b.x, b.y, 0), 0x9fd8ff, 0.25); if (d < 1.4) { hurt(q, dt * 14, null, true, 'crush'); q.zap = 0.15; if (Math.random() < 0.3) sparks(V3(b.x, b.y, 0), 2, 0xffffff, 0x59b2ff, 5, 0.06); } }
        if (Math.random() < 0.1) popupT('MAGNETIZED!', V3(mx, poleY - 0.8, 0), '#7fd8ff', 8); shake(0.08); hapStart(0.4, 0.5);
        emit({ x: mx + rnd(-0.7, 0.7), y: poleY - 0.2, life: 0.2, s0: 0.4, s1: 0.1, c0: 0xffffff, c1: 0x4aa8ff, a: 0.8 }); }
      else if (!rel) { rel = true; mag.on = false; hapStop(); if (doll === d0 && doll) { for (const q of doll.list) { q.body.velocity.set(rnd(-1, 1), -24, 0); } slamT = 1.2; sfx.whoosh(); } }
      if (rel) { g.position.y += dt * 14; if (slamT > 0 && doll === d0 && doll) { slamT -= dt; const c = doll.parts.chest.body; if (c.position.y < 0.9) { slamT = 0; let s = 0; for (const q of doll.list) s += hurt(q, 95, V3(q.body.position.x, q.body.position.y, 0), true, 'crush', 0, -1); const cp = V3(c.position.x, 0.3, 0); sfx.slam(); shake(1.1); flash(0.3, '#ffffff'); ring(cp, 3, 0xffe9b8, 0.35); puff(cp, 0xd8cdb8, 12); bloodBurst(cp, 30, 0, 1, 10, 1.3); decal(cp.x, 0.3, 2, 'scorch'); popupT('SLAMMED!', V3(cp.x, 1.2, 0), '#ffd23f', 10); if (s) popup('-' + s, V3(cp.x, 1.8, 0), s); } } if (g.position.y > RH + 3) { scene.remove(g); disposeObj(g); return false; } }
      return true;
    });
  }
  function magnetStep(h) {
    if (!doll) { mag.on = false; return; } const gv = cfg().gravity;
    for (const q of doll.list) { const b = q.body, dx = mag.x - b.position.x, dy = mag.y - b.position.y, d = Math.hypot(dx, dy) + 0.25, f = b.mass * (34 + 55 / d); b.force.x += dx / d * f; b.force.y += dy / d * f + b.mass * gv; b.velocity.scale(1 - 0.03, b.velocity); b.angularVelocity.scale(0.97, b.angularVelocity); }
  }

  /* --- cannon --- */
  function doCannon(A) {
    cd = 1.1; gunId = 'cannon'; gun.vis = 1.5; gun.kick = 0.9; placeGun('cannon', A.p); const from = gun.muz.clone(), part = A.part;
    let dx = A.p.x - from.x, dy = A.p.y - from.y; const L0 = Math.hypot(dx, dy) || 1; dx /= L0; dy /= L0;
    emit({ x: from.x, y: from.y, life: 0.12, s0: 2.2, s1: 3.2, c0: 0xffffff, c1: 0xff9a30 }); for (let i = 0; i < 14; i++) emit({ x: from.x + dx * 0.3, y: from.y + dy * 0.3, vx: dx * rnd(2, 9) + rnd(-1.5, 1.5), vy: dy * rnd(2, 9) + rnd(-1, 2.5), life: rnd(0.9, 1.7), s0: 0.4, s1: 1.4, c0: 0x4a4540, c1: 0x1e1b19, a: 0.8, smoke: true, g: -0.5, drag: 0.95 });
    sparks(from, 14, 0xffffff, 0xff9a30, 12, 0.1); sfx.cannon(); shake(0.6); haptic('thud'); flash(0.15, '#ffd9a0');
    let tw = 30; if (dx > 0.001) tw = Math.min(tw, (RW / 2 - 0.05 - from.x) / dx); else if (dx < -0.001) tw = Math.min(tw, (-RW / 2 + 0.05 - from.x) / dx); if (dy > 0.001) tw = Math.min(tw, (RH - 0.1 - from.y) / dy); else if (dy < -0.001) tw = Math.min(tw, (0.1 - from.y) / dy);
    let best = null, bt = tw; if (doll) for (const q of doll.list) { const rx = q.body.position.x - from.x, ry = q.body.position.y - from.y, tp = rx * dx + ry * dy; if (tp > 0.3 && tp < bt && Math.abs(rx * dy - ry * dx) < 0.5) { bt = tp; best = q; } }
    const ball = new THREE.Mesh(new THREE.SphereGeometry(0.24, 18, 14), phong(0x23262c, 120)); ball.position.set(from.x, from.y, 0.9); ball.castShadow = true; track(ball); const end = V3(from.x + dx * tw, from.y + dy * tw, 0), hitP = best ? V3(from.x + dx * bt, from.y + dy * bt, 0) : null; let t = 0, hitDone = false;
    addFx((dt) => {
      t += dt; const d = 62 * t; ball.position.set(from.x + dx * d, from.y + dy * d, 0.9); emit({ x: ball.position.x, y: ball.position.y, life: 0.3, s0: 0.3, s1: 0.1, c0: 0xcccccc, c1: 0x555555, a: 0.5, smoke: true });
      if (best && !hitDone && d >= bt) { hitDone = true; explode(hitP, 3.2, 26, 150, { size: 2.2, shake: 0.8, vol: 1.1 }); if (doll && doll.list.indexOf(best) >= 0) { hurt(best, 160, hitP, false, 'blast', dx, dy); if (jointOf(best)) tear(best, dx, dy); pushAt(best, dx * 30, dy * 30 + 4, hitP); bloodBurst(V3(hitP.x, hitP.y, 0.5), 30, dx, dy, 13, 1.4); popupT('CANNONBALL!', V3(hitP.x, hitP.y + 1.0, 0), '#ff9a2a', 10); } slow = Math.max(slow, 0.25); }
      if (d >= tw) { scene.remove(ball); disposeObj(ball); const e = end; decal(e.x, e.y, 0.9, 'hole'); decal(e.x, e.y, 1.4, 'scorch'); puff(e, 0xb59a74, 10); sparks(e, 14, 0xffffff, 0xffb040, 9, 0.09); sfx.thud(); shake(0.4); for (let i = 0; i < 6; i++) emit({ x: e.x, y: e.y, vx: rnd(-6, 6), vy: rnd(0, 7), life: 0.8, s0: 0.12, s1: 0.06, c0: 0xb98a52, c1: 0x6a4a2a, g: 16 }); return false; } return true;
    });
  }

  /* --- wasp swarm --- */
  function doWasps(A) {
    const p = A.p.clone(), nest = new THREE.Mesh(new THREE.IcosahedronGeometry(0.42, 1), new THREE.MeshPhongMaterial({ color: 0xb59058, flatShading: true, shininess: 10 })); nest.scale.set(1, 1.25, 1); nest.position.set(p.x, RH + 0.6, 0.5); track(nest);
    let t = 0, burst = false, ws = [], bt = 0, stingPop = 0, flailT = 0, ptT = 0; const d0 = doll;
    addFx((dt) => {
      t += dt;
      if (!burst) { const k = Math.min(1, t / 0.55); nest.position.y = RH + 0.6 + (p.y - RH - 0.6) * k * k; nest.rotation.z += dt * 4; if (k >= 1) { burst = true; scene.remove(nest); nest.geometry.dispose(); bt = 0; buzzStart(); sfx.pop(); puff(p, 0xb59058, 8); popupT('WASPS!', V3(p.x, p.y + 0.8, 0), '#ffd23f', 9);
          for (let i = 0; i < 32; i++) { const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: waspTex, transparent: true, depthWrite: false })); s.scale.set(0.5, 0.5, 1); s.position.set(p.x + rnd(-0.3, 0.3), p.y + rnd(-0.3, 0.3), 0.97); s.renderOrder = 8; track(s); ws.push({ s, vx: rnd(-4, 4), vy: rnd(-2, 5), part: null, ang: rnd(0, 6.28), r: rnd(0.25, 0.7), spd: rnd(4, 9) * (Math.random() < 0.5 ? -1 : 1), ph: rnd(0, 6.28), st: rnd(0.2, 0.9), re: 0 }); } } return true; }
      bt += dt; const alive = bt < 8.5 && doll === d0 && doll; flailT -= dt; stingPop -= dt;
      for (const w of ws) {
        const s = w.s; w.ph += dt * 60; s.scale.x = 0.52 * (0.78 + 0.3 * Math.sin(w.ph)); if (!alive) { w.vy += 14 * dt; s.position.x += w.vx * dt * 2; s.position.y += w.vy * dt * 2; s.material.opacity = Math.max(0, s.material.opacity - dt * 1.6); continue; }
        w.re -= dt; if (!w.part || w.re <= 0) { w.part = doll.list[(Math.random() * doll.list.length) | 0]; w.re = rnd(0.8, 2.2); } w.ang += w.spd * dt;
        const b = w.part.body.position, tx = b.x + Math.cos(w.ang) * w.r, ty = b.y + Math.sin(w.ang * 1.3) * w.r * 0.8, ox = s.position.x, oy = s.position.y; s.position.x += (tx - ox) * Math.min(1, dt * 9) + rnd(-0.03, 0.03); s.position.y += (ty - oy) * Math.min(1, dt * 9) + rnd(-0.03, 0.03);
        const vx = s.position.x - ox, vy = s.position.y - oy; s.material.rotation = Math.atan2(vy, vx) - PI / 2 + PI; w.st -= dt;
        if (w.st <= 0 && Math.hypot(s.position.x - b.x, s.position.y - b.y) < 0.5) { w.st = rnd(0.5, 1.0); const pt = V3(b.x + rnd(-0.1, 0.1), b.y + rnd(-0.1, 0.1), 0); hurt(w.part, 1.6, pt, true, 'sting', 0, 0); w.part.sting = Math.min(1, (w.part.sting || 0) + 0.05); drop(pt.x, pt.y, rnd(-0.6, 0.6), rnd(0.2, 1.2), 0.06); emit({ x: pt.x, y: pt.y, life: 0.2, s0: 0.14, s1: 0.04, c0: 0xff6a5a, c1: 0xaa1a10, a: 0.9 }); if (stingPop <= 0) { stingPop = 0.5; popupT(Math.random() < 0.5 ? 'STUNG!' : 'OUCH!', pt, '#ffd23f', 6.5); } }
      }
      if (alive && flailT <= 0 && !dead) { flailT = rnd(0.1, 0.22); for (let k = 0; k < 2; k++) { const q = doll.list[(Math.random() * doll.list.length) | 0], bb = q.body; bb.velocity.x += rnd(-4, 4); bb.velocity.y += rnd(0.5, 5); bb.angularVelocity.z += rnd(-9, 9); } mood = Math.max(mood, 0.95); }
      if (!alive && bt > 0.01 && buzz) buzzStop(); if (bt > 10.3 || (!alive && ws.length && ws[0].s.material.opacity <= 0)) { for (const w of ws) scene.remove(w.s); buzzStop(); return false; } return true;
    });
  }

  /* --- airstrike --- */
  function makeBomb(scale) {
    const g = new THREE.Group(), pts = [[0, 0.62], [0.07, 0.56], [0.13, 0.42], [0.16, 0.2], [0.165, -0.1], [0.15, -0.3], [0.1, -0.5], [0.06, -0.62], [0, -0.62]].map((p) => new THREE.Vector2(p[0], p[1]));
    const body = new THREE.Mesh(new THREE.LatheGeometry(pts, 20), new THREE.MeshPhongMaterial({ color: 0x55672b, shininess: 90, specular: 0x99aa77 })); g.add(body);
    const band = new THREE.Mesh(new THREE.CylinderGeometry(0.17, 0.17, 0.05, 20), phong(0xf2c21b, 40)); band.position.y = 0.1; g.add(band); const band2 = band.clone(); band2.position.y = -0.02; g.add(band2);
    const nose = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.05, 0.1, 10), phong(0x9aa0aa, 120)); nose.position.y = 0.62; g.add(nose);
    for (let i = 0; i < 4; i++) { const f = new THREE.Mesh(new THREE.BoxGeometry(0.02, 0.3, 0.26), phong(0x3a4a1e, 30)); f.position.set(0, -0.5, 0); f.rotation.y = i * PI / 2; f.children.length; const hold = new THREE.Group(); hold.rotation.y = i * PI / 2; f.rotation.y = 0; f.position.set(0, -0.48, 0.14); hold.add(f); g.add(hold); }
    const ring = new THREE.Mesh(new THREE.TorusGeometry(0.19, 0.012, 6, 18), phong(0x222222, 10)); ring.rotation.x = PI / 2; ring.position.y = -0.58; g.add(ring);
    g.scale.setScalar(scale || 1); g.traverse((m) => { if (m.isMesh) m.castShadow = true; }); return g;
  }
  function makeJet() {
    const g = new THREE.Group(), hull = new THREE.MeshPhongMaterial({ color: 0x6b7a92, shininess: 110, specular: 0xbcc8dc }), dark = phong(0x2c3442, 60), accent = phong(0xd8262c, 40);
    const fp = [[-1.62, 0.12], [-1.55, 0.2], [-1.2, 0.27], [-0.6, 0.31], [0.2, 0.3], [0.8, 0.24], [1.25, 0.14], [1.7, 0.03], [1.78, 0]].map((p) => new THREE.Vector2(p[1], p[0]));
    const fus = new THREE.Mesh(new THREE.LatheGeometry(fp, 28), hull); fus.rotation.z = -PI / 2; fus.scale.set(1, 1, 0.9); g.add(fus);
    const can = new THREE.Mesh(new THREE.SphereGeometry(0.5, 20, 14), new THREE.MeshPhongMaterial({ color: 0x1a3a5e, shininess: 160, specular: 0xffffff, emissive: 0x0a1a2e })); can.scale.set(0.62, 0.2, 0.2); can.position.set(0.55, 0.27, 0); g.add(can);
    const wsh = new THREE.Shape(); wsh.moveTo(0.7, 0); wsh.lineTo(-0.85, 1.35); wsh.lineTo(-1.2, 1.35); wsh.lineTo(-1.1, 0); wsh.closePath();
    for (const sd of [1, -1]) { const w = new THREE.Mesh(new THREE.ExtrudeGeometry(wsh, { depth: 0.05, bevelEnabled: false }), hull); w.rotation.x = -PI / 2 * sd; w.scale.z = 1; if (sd < 0) { w.scale.y = 1; } w.position.set(0, -0.03, 0); g.add(w);
      const tip = new THREE.Mesh(new THREE.BoxGeometry(0.34, 0.06, 0.05), accent); tip.position.set(-1.0, 0, sd * 1.33); g.add(tip);
      const msl = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, 0.75, 10), phong(0xdfe3ea, 80)); msl.rotation.z = PI / 2; msl.position.set(-0.45, -0.1, sd * 0.95); g.add(msl); const mn = new THREE.Mesh(new THREE.ConeGeometry(0.05, 0.16, 10), accent); mn.rotation.z = -PI / 2; mn.position.set(-0.04, -0.1, sd * 0.95); g.add(mn); }
    const tsh = new THREE.Shape(); tsh.moveTo(-0.95, 0); tsh.lineTo(-1.45, 0.95); tsh.lineTo(-1.68, 0.95); tsh.lineTo(-1.62, 0); tsh.closePath(); const fin = new THREE.Mesh(new THREE.ExtrudeGeometry(tsh, { depth: 0.04, bevelEnabled: false }), hull); fin.position.set(0, 0.2, -0.02); g.add(fin);
    const stripe = new THREE.Mesh(new THREE.BoxGeometry(0.2, 0.3, 0.045), accent); stripe.position.set(-1.55, 0.7, 0.0); g.add(stripe);
    const hsh = new THREE.Shape(); hsh.moveTo(-1.1, 0); hsh.lineTo(-1.55, 0.6); hsh.lineTo(-1.75, 0.6); hsh.lineTo(-1.7, 0); hsh.closePath(); for (const sd of [1, -1]) { const h = new THREE.Mesh(new THREE.ExtrudeGeometry(hsh, { depth: 0.04, bevelEnabled: false }), hull); h.rotation.x = -PI / 2 * sd; h.position.set(0, 0.02, 0); g.add(h); }
    const noz = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.17, 0.26, 20, 1, true), dark); noz.rotation.z = PI / 2; noz.position.set(-1.7, 0, 0); g.add(noz);
    const intake = new THREE.Mesh(new THREE.BoxGeometry(0.55, 0.12, 0.34), dark); intake.position.set(0.5, -0.2, 0); g.add(intake);
    const flame = new THREE.Mesh(new THREE.ConeGeometry(0.17, 1.2, 14), new THREE.MeshBasicMaterial({ color: 0xffa040, transparent: true, opacity: 0.85, blending: THREE.AdditiveBlending, depthWrite: false })); flame.rotation.z = PI / 2; flame.position.set(-2.3, 0, 0); g.add(flame); g.userData.flame = flame;
    const core = new THREE.Mesh(new THREE.ConeGeometry(0.09, 0.8, 12), new THREE.MeshBasicMaterial({ color: 0xfff4c0, transparent: true, opacity: 0.95, blending: THREE.AdditiveBlending, depthWrite: false })); core.rotation.z = PI / 2; core.position.set(-2.1, 0, 0); g.add(core); g.userData.core = core;
    g.userData.carried = []; for (const [bx, bz] of [[-0.2, 0.55], [-0.2, -0.55], [-0.6, 0.55], [-0.6, -0.55]]) { const b = makeBomb(0.5); b.rotation.z = PI / 2; b.position.set(bx, -0.28, bz); g.add(b); g.userData.carried.push(b); }
    g.traverse((m) => { if (m.isMesh) m.castShadow = true; }); return g;
  }
  function doAirstrike(A) {
    const cx = clamp(A.p.x, -RW / 2 + 0.5, RW / 2 - 0.5), dir = cx > 0 ? -1 : 1, x0 = dir > 0 ? -RW / 2 - 2.6 : RW / 2 + 2.6, jy = RH - 1.5, NB = 8, gap = 1.0;
    const bc = new THREE.Group(), bb = new THREE.Mesh(new THREE.BoxGeometry(0.3, 0.18, 0.2), phong(0x3a3f2a, 40)); bb.position.y = 0.09; bc.add(bb); const ant = new THREE.Mesh(new THREE.CylinderGeometry(0.01, 0.01, 0.4, 6), phong(0x222222, 10)); ant.position.set(0.1, 0.38, 0); bc.add(ant); const lamp = new THREE.Mesh(new THREE.SphereGeometry(0.05, 10, 8), new THREE.MeshBasicMaterial({ color: 0xff2a1a })); lamp.position.set(-0.08, 0.2, 0.11); bc.add(lamp); bc.position.set(cx, 0.02, 0.6); track(bc);
    const jet = makeJet(); jet.scale.setScalar(1.05); jet.rotation.x = 0.9; if (dir < 0) { jet.rotation.y = PI; } jet.position.set(x0, jy, 0.2); jet.visible = false; track(jet);
    let t = 0, jetS = 0, dropped = 0, jt = 0; const bombs = [], seq = []; for (let i = 0; i < NB; i++) seq.push(clamp(cx + (i - (NB - 1) / 2) * gap * dir, -RW / 2 + 0.5, RW / 2 - 0.5));
    sfx.beep && sfx.beep(); popupT('AIRSTRIKE INBOUND!', V3(cx, 2.6, 0), '#ff5a4a', 8.5);
    addFx((dt) => {
      t += dt; lamp.visible = Math.sin(t * 20) > 0; if (t < 1.1 || (jetS === 1)) { for (let i = 0; i < 2; i++) emit({ x: cx + rnd(-0.08, 0.08), y: 0.25, vx: rnd(-0.3, 0.3), vy: rnd(1.5, 3), life: 1.8, s0: 0.25, s1: 1.1, c0: 0xff5a3a, c1: 0x8a1a14, a: 0.6, smoke: true, g: -0.3 }); }
      if (t > 1.0 && jetS === 0) { jetS = 1; jet.visible = true; sfx.jet(); jt = 0; }
      if (jetS === 1) {
        jt += dt; const sp = 15, jx = x0 + dir * sp * jt, bob = Math.sin(jt * 5) * 0.06; jet.position.set(jx, jy + bob, 0.2); jet.rotation.z = dir * Math.sin(jt * 3) * 0.03; const fl = jet.userData.flame, co = jet.userData.core; fl.scale.set(0.85 + Math.random() * 0.3, 1, 1); co.scale.set(0.8 + Math.random() * 0.4, 1, 1);
        const tx = jx - dir * 2.0; emit({ x: tx, y: jy, life: 0.9, s0: 0.35, s1: 1.1, c0: 0xe4e4e4, c1: 0x8f8f8f, a: 0.5, smoke: true, vx: -dir * 1.2 }); emit({ x: tx + dir * 0.3, y: jy, life: 0.1, s0: 0.5, s1: 0.2, c0: 0xffd070, c1: 0xff5a10, a: 0.8 });
        for (const sd of [-1, 1]) emit({ x: jx - dir * 1.2, y: jy + sd * 0.55 * Math.cos(0.9) + 0.0, life: 0.6, s0: 0.1, s1: 0.2, c0: 0xffffff, c1: 0xdde8f5, a: 0.35, smoke: true });
        if (Math.abs(jx - cx) < 0.9 && !doAirstrike.sh) { doAirstrike.sh = 1; shake(0.5); } if (Math.abs(jx - cx) > 2) doAirstrike.sh = 0;
        while (dropped < NB && ((dir > 0 && jx >= seq[dropped]) || (dir < 0 && jx <= seq[dropped]))) {
          const bx = seq[dropped], b = makeBomb(1.0); b.position.set(bx, jy - 0.3, 0.5); b.rotation.z = dir * PI / 2 - dir * 0.2; b.rotation.z += PI; track(b); bombs.push({ b, x: bx, y: jy - 0.3, v: 0, tilt: 1.2 * dir }); const car = jet.userData.carried[dropped >> 1]; if (car && dropped % 2 === 1) car.visible = false;
          dropped++; }
        if (jx > RW / 2 + 3.5 || jx < -RW / 2 - 3.5) { scene.remove(jet); jetS = 2; } }
      for (let i = bombs.length - 1; i >= 0; i--) { const q = bombs[i]; q.v += 30 * dt; q.y -= q.v * dt; q.b.position.y = q.y; q.tilt *= Math.pow(0.04, dt); q.b.rotation.z = PI + q.tilt * 0.6; q.b.rotation.y += dt * 3;
        emit({ x: q.x, y: q.y + 0.7, life: 0.25, s0: 0.22, s1: 0.06, c0: 0xffffff, c1: 0xffa040, a: 0.5 }); emit({ x: q.x, y: q.y + 1.1, life: 0.5, s0: 0.12, s1: 0.3, c0: 0xdddddd, c1: 0x888888, a: 0.35, smoke: true });
        if (q.y < 0.65) { scene.remove(q.b); disposeObj(q.b); explode(V3(q.x, 0.4, 0), 2.7, 24, 100, { burn: true, size: 2.1, shake: 0.7, vol: 1.1 }); bombs.splice(i, 1); } }
      if (dropped >= NB && bombs.length === 0 && jetS === 2) { scene.remove(bc); return false; } return true;
    });
  }

  /* --- spike crusher --- */
  function doCrusher(A) {
    const x = clamp(A.p.x, -RW / 2 + 1.5, RW / 2 - 1.5), W = 2.6, g = new THREE.Group(), steel = phong(0x69727e, 70), brt = phong(0xdfe6ef, 130), dark = phong(0x3a4048, 40);
    const blk = new THREE.Mesh(roundBox(W, 0.6, 0.9, 0.07, 3), steel); blk.position.y = 0; g.add(blk); const pst = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.3, 12, 16), dark); pst.position.y = 6.3; g.add(pst);
    const spikes = []; for (let i = 0; i < 9; i++) { const s = new THREE.Mesh(new THREE.ConeGeometry(0.13, 0.95, 10), brt.clone()); s.rotation.x = PI; s.position.set(-W / 2 + 0.2 + i * (W - 0.4) / 8, -0.77, 0); g.add(s); spikes.push(s); }
    for (let i = 0; i < 6; i++) { const rv = new THREE.Mesh(new THREE.SphereGeometry(0.05, 8, 6), brt); rv.position.set(-W / 2 + 0.3 + i * (W - 0.6) / 5, 0.12, 0.46); g.add(rv); }
    g.traverse((m) => { if (m.isMesh) m.castShadow = true; }); const tipOff = 1.25, topY = RH + 1.3, botY = 0.1 + tipOff; g.position.set(x, topY, 0.5); track(g);
    const mk = new THREE.Mesh(new THREE.PlaneGeometry(W, 0.2), new THREE.MeshBasicMaterial({ color: 0xff2a1a, transparent: true, opacity: 0, depthWrite: false })); mk.position.set(x, 0.12, 0.4); track(mk);
    let t = 0, st = 0, prevTip = topY - tipOff; const hit = new Set(), d0 = doll; sfx.whoosh(); popupT('CRUSH!', V3(x, 3, 0), '#ff7a3a', 8);
    addFx((dt) => {
      t += dt; if (st === 0) { mk.material.opacity = (Math.random() < 0.6 ? 0.55 : 0.15) * Math.min(1, t * 3); if (Math.random() < 0.5) emit({ x: x + rnd(-W / 2, W / 2), y: RH - 0.2, vx: rnd(-0.4, 0.4), vy: -rnd(1, 3), life: 0.8, s0: 0.1, s1: 0.2, c0: 0xcdb08a, c1: 0x8a7050, a: 0.6, smoke: true, g: 5 }); g.position.x = x + Math.sin(t * 60) * 0.02; if (t > 0.6) { st = 1; t = 0; mk.visible = false; } return true; }
      if (st === 1) { const k = Math.min(1, t / 0.15), e = k * k * k; g.position.y = topY + (botY - topY) * e; const tip = g.position.y - tipOff;
        if (doll && doll === d0) for (const q of doll.list) { const b = q.body.position; if (hit.has(q) || Math.abs(b.x - x) > W / 2 + 0.05) continue; if (b.y <= prevTip + 0.45 && b.y >= tip - 0.55) { hit.add(q); const pt = V3(b.x, Math.max(0.2, b.y), 0); hurt(q, 120, pt, false, 'crush', 0, -1); woundAt(q, pt, 0, -1); bloodBurst(V3(b.x, b.y, 0.5), 22, 0, -1, 9, 1.3); pushAt(q, 0, -14, pt); pinPart(q, pt, 2.2, 1600); sparks(pt, 6, 0xffffff, 0xffd34a, 7, 0.07); if (jointOf(q) && Math.random() < 0.35) tear(q, 0, -1); } }
        prevTip = tip; if (k >= 1) { st = 2; t = 0; sfx.slam(); shake(1.3); flash(0.3, '#ffffff'); haptic('thud'); const cp = V3(x, 0.2, 0); puff(cp, 0xd8cdb8, 14); sparks(cp, 18, 0xffffff, 0xffb040, 10, 0.09); ring(cp, 3.2, 0xffe9b8, 0.35); decal(x, 0.3, 2, 'scorch');
          if (hit.size) { for (const s of spikes) s.material.color.setHex(0xa01818); popupT(hit.size > 2 ? 'IMPALED!' : 'SKEWERED!', V3(x, 2.6, 0), '#ffd23f', 10); if (hit.size >= 4 && doll && !dead) die('crush'); } else popupT('MISSED!', V3(x, 2.2, 0), '#ffffff', 7); }
        return true; }
      if (st === 2) { if (hit.size && Math.random() < dt * 20) { const sp = spikes[(Math.random() * spikes.length) | 0]; drop(x + sp.position.x, 0.5 + rnd(0, 0.4), rnd(-0.3, 0.3), -rnd(0, 1), 0.08); } if (t > 1.3) { st = 3; t = 0; } return true; }
      g.position.y += dt * 11; if (g.position.y > topY + 0.2) { scene.remove(g); scene.remove(mk); disposeObj(g); return false; } return true;
    });
  }

  /* ---- ways 32-40: glove, piano, tornado, sniper, fireworks, UFO, shuriken, car, lava ---- */
  function sfx4() {
    Object.assign(sfx, {
      boing() { sTone('sine', 180, 520, 0.18, 0.3); sTone('triangle', 520, 260, 0.25, 0.18); },
      chord() { [262, 330, 392, 523].forEach((f, i) => setTimeout(() => sTone('triangle', f * (0.98 + Math.random() * 0.04), f * 0.5, 0.9, 0.16), i * 18)); sNoise(0.4, 1800, 100, 0.6); sTone('sine', 70, 30, 0.6, 0.8); },
      wind() { sNoise(1.6, 300, 900, 0.32, 'bandpass', 0.9); },
      snipe() { sNoise(0.5, 6000, 300, 0.9); sTone('square', 260, 40, 0.35, 0.35); sTone('sine', 70, 25, 0.5, 0.7); },
      crackle() { for (let i = 0; i < 6; i++) setTimeout(() => sNoise(0.05, 7000, 3000, 0.25, 'highpass'), 40 + i * 55 + Math.random() * 30); },
      ufo() { sTone('sine', 300, 900, 0.7, 0.14); setTimeout(() => sTone('sine', 900, 300, 0.7, 0.14), 700); },
      honk() { sTone('square', 420, 410, 0.16, 0.12); setTimeout(() => sTone('square', 420, 410, 0.22, 0.12), 210); }
    });
  }
  const sideOf = (x) => (x > 0 ? 1 : -1); // travel direction: tools come in from the wall farther from the target
  const fade = (g, k) => g.traverse((m) => { if (m.isMesh) { m.material.transparent = true; m.material.opacity = Math.max(0, k); } });
  const kill = (g) => { scene.remove(g); disposeObj(g); };
  function partsNear(x, y, rx, ry) { return doll ? doll.list.filter((q) => Math.abs(q.body.position.x - x) < rx && Math.abs(q.body.position.y - y) < ry) : []; }

  /* --- boxing glove on a spring --- */
  function doGlove(A) {
    const p = A.p.clone(), s = sideOf(p.x), wallX = s > 0 ? -RW / 2 : RW / 2, g = new THREE.Group(), red = phong(0xe0262a, 90), spring = phong(0xb8c0cc, 120);
    const fist = new THREE.Mesh(new THREE.SphereGeometry(0.5, 20, 16), red); fist.scale.set(1.15, 0.95, 0.95); g.add(fist);
    const thumb = new THREE.Mesh(new THREE.SphereGeometry(0.2, 12, 10), red); thumb.position.set(-s * 0.05, 0.42, 0.15); g.add(thumb);
    const cuff = new THREE.Mesh(new THREE.CylinderGeometry(0.34, 0.38, 0.32, 16), phong(0xffffff, 40)); cuff.rotation.z = PI / 2; cuff.position.x = -s * 0.6; g.add(cuff);
    const coil = new THREE.Group(), N = 10; for (let i = 0; i < N; i++) { const r = new THREE.Mesh(new THREE.TorusGeometry(0.16, 0.04, 6, 14), spring); r.rotation.y = PI / 2 + 0.3; coil.add(r); } track(coil); track(g);
    let t = 0, hit = false; sfx.boing();
    addFx((dt) => {
      t += dt; const out = t < 0.12 ? (t / 0.12) ** 2 : t < 0.35 ? 1 : Math.max(0, 1 - (t - 0.35) / 0.2), gx = wallX + (p.x - s * 0.55 - wallX) * out;
      g.position.set(gx, p.y, 0.95); coil.children.forEach((r, i) => r.position.set(wallX + (gx - s * 0.75 - wallX) * (i / (N - 1)), p.y, 0.95));
      if (!hit && t >= 0.12) { hit = true; const sum = blow(p, s, 0.45, 1.5, 30, 36); sparks(p, 12, 0xffffff, 0xffd34a, 9, 0.12); ring(p, 1.1, 0xffffff, 0.22); popupT('POW!', V3(p.x, p.y + 0.9, 0), '#ffd23f', 9); shake(sum ? 0.4 : 0.15); sfx.smash(); haptic('thud'); }
      if (t > 0.6) { kill(g); kill(coil); return false; } return true;
    });
  }

  /* --- grand piano dropped from the ceiling --- */
  function spawnPiano(p) {
    const g = new THREE.Group(), blk = phong(0x15161a, 140), wht = phong(0xf4f4f0, 40);
    const add = (geo, mat, x, y, z) => { const m = new THREE.Mesh(geo, mat); m.position.set(x, y, z); m.castShadow = true; g.add(m); return m; };
    add(roundBox(2.1, 0.55, 1.0, 0.1, 3), blk, 0, 0.1, 0); const lid = add(roundBox(2.0, 0.06, 0.96, 0.03, 2), blk, -0.15, 0.62, 0); lid.rotation.z = 0.35;
    add(roundBox(1.5, 0.1, 0.3, 0.02, 2), wht, 0.1, -0.05, 0.42); for (let i = 0; i < 9; i++) add(new THREE.BoxGeometry(0.07, 0.06, 0.18), blk, -0.55 + i * 0.15, 0.02, 0.48);
    for (const lx of [-0.85, 0.85]) add(new THREE.CylinderGeometry(0.07, 0.05, 0.5, 10), blk, lx, -0.42, 0);
    const body = new CANNON.Body({ mass: 220, material: propMat, linearDamping: 0.01 }); body.addShape(new CANNON.Box(new CANNON.Vec3(1.05, 0.55, 0.5)));
    body.position.set(clamp(p.x, -RW / 2 + 1.15, RW / 2 - 1.15), RH - 0.7, 0); body.velocity.set(0, -16, 0); body.fixedRotation = true; body.updateMassProperties(); body.collisionFilterGroup = 1; body.collisionFilterMask = 3;
    const t = { kind: 'piano', body, mesh: g, hit: false, landed: false, rest: 0, ghost: false };
    body.addEventListener('collide', (ev) => { const o = ev.body, spd = Math.abs(ev.contact.getImpactVelocityAlongNormal()); if (o && o.partRef && !t.hit && spd > 5) { t.hit = true; t.crush = { x: body.position.x, y: body.position.y - 0.4 }; } else if (o && o.isWall && !t.landed && spd > 5) { t.landed = true; t.land = body.position.x; } });
    t.update = (dt) => {
      if (t.crush && doll) { const c = t.crush; t.crush = null; const pt = V3(c.x, c.y, 0); let sum = 0;
        for (const part of doll.list) { const b = part.body, dx = b.position.x - c.x; if (Math.abs(dx) < 1.6 && Math.abs(b.position.y - c.y) < 1.8) { const f = 1 - Math.abs(dx) / 1.7; b.velocity.y = Math.min(b.velocity.y, -10 * f - 2); b.velocity.x += (dx >= 0 ? 1 : -1) * 5; sum += hurt(part, 70 * f + 10, null, true, 'crush', 0, -1); } }
        if (sum) popup('-' + sum, V3(c.x, c.y + 0.7, 0), sum); popupT('PLONK!', V3(c.x, c.y + 1.6, 0), '#ffffff', 9); sparks(pt, 20, 0xffffff, 0xffb040, 11, 0.12); puff(pt, 0xd8cdb8, 14); shake(0.7); sfx.chord(); haptic('thud'); flash(0.2); t.ghost = true; }
      if (t.ghost && body.collisionFilterMask !== 2) body.collisionFilterMask = 2;
      if (t.land != null) { const x = t.land; t.land = null; const pt = V3(x, 0.15, 0); puff(pt, 0xd8cdb8, 16); ring(pt, 2.6, 0xffe9b8, 0.4); blow(pt, 0, 0.7, 2.8, 6, 12); shake(0.5); if (!t.hit) sfx.chord(); else sfx.thud(); haptic('thud'); t.rest = 0.001;
        for (let i = 0; i < 6; i++) emit({ x: x + rnd(-1, 1), y: 0.5, vx: rnd(-5, 5), vy: rnd(3, 8), life: 1, s0: 0.12, s1: 0.1, c0: i % 2 ? 0xffffff : 0x15161a, c1: 0x777777, g: 16 }); }
      if (t.rest > 0) { t.rest += dt; if (t.rest > 2.2) { const k = 1 - (t.rest - 2.2) / 0.3; g.scale.setScalar(Math.max(0.01, k)); if (k <= 0) return false; } }
      return true;
    };
    addThing(t); sfx.whoosh();
  }

  /* --- tornado: a funnel that sucks the doll up and spins him --- */
  function doTornado(A) {
    let x = A.p.x; const g = new THREE.Group(), H = RH - 0.4, rings = [];
    for (let i = 0; i < 9; i++) { const k = i / 8, m = new THREE.Mesh(new THREE.TorusGeometry(0.35 + k * 1.1, 0.1 + k * 0.08, 6, 24), new THREE.MeshBasicMaterial({ color: i % 2 ? 0x8a96a6 : 0xb7c0cc, transparent: true, opacity: 0.0, depthWrite: false })); m.rotation.x = PI / 2 - 0.25; m.position.y = 0.2 + k * H; g.add(m); rings.push(m); }
    g.position.z = 0.4; track(g); let t = 0, tick = 0; const D = 4.2; sfx.wind(); setTimeout(() => sfx.wind && sfx.wind(), 1500); popupT('TORNADO!', V3(x, 3, 0), '#cfe0ff', 9);
    addFx((dt) => {
      t += dt; const op = Math.min(1, t / 0.4) * Math.min(1, (D - t) / 0.5);
      if (doll) { const c = doll.parts.chest.body.position.x; x += clamp(c - x, -1, 1) * dt * 0.8; } x = clamp(x, -RW / 2 + 0.8, RW / 2 - 0.8); g.position.x = x;
      rings.forEach((r, i) => { r.rotation.z += dt * (8 + i); r.position.x = Math.sin(t * 3 + i * 0.7) * 0.15 * i; r.material.opacity = 0.55 * op; });
      if (Math.random() < 0.7) { const a = rnd(0, 6.28), y = rnd(0.1, H); emit({ x: x + Math.cos(a) * (0.3 + y * 0.15), y, vx: -Math.sin(a) * 6, vy: rnd(1, 3), life: 0.5, s0: 0.12, s1: 0.04, c0: 0xc9b089, c1: 0x7a6a50, a: 0.8, drag: 0.95 }); }
      if (t < D - 0.5 && Math.random() < 0.08) haptic({ intensity: 0.3, sharpness: 0.2 });
      tick += dt; const hitNow = tick > 0.3; if (hitNow) tick = 0; let sum = 0;
      if (doll && t < D - 0.3) for (const q of doll.list) { const b = q.body, dx = b.position.x - x, ad = Math.abs(dx); if (ad < 1.9) { const f = 1 - ad / 2; b.velocity.y += (cfg().gravity * 1.25 + 6) * f * dt; b.velocity.x += (-dx * 9 + (b.position.y % 2 > 1 ? 7 : -7)) * f * dt; b.angularVelocity.y += 14 * f * dt; b.angularVelocity.z += 10 * f * dt; if (b.position.y > H - 0.6) b.velocity.y = Math.min(b.velocity.y, 0); if (hitNow) sum += hurt(q, 2 * f, null, true, 'smash'); } }
      if (sum) popup('-' + sum, V3(x, 3.5, 0), sum);
      if (t >= D - 0.3 && !g.userData.fling) { g.userData.fling = true; if (doll) for (const q of doll.list) if (Math.abs(q.body.position.x - x) < 2) { q.body.velocity.x += rnd(-14, 14); q.body.velocity.y -= 4; } }
      if (t > D) { kill(g); return false; } return true;
    });
  }

  /* --- sniper: one big shot, slow motion, limbs come off --- */
  function doSniper(A) {
    cd = 1.1; gunId = 'sniper'; gun.vis = 1.3; gun.kick = 0.7; placeGun('sniper', A.p); muzzleFlash(true); const from = gun.muz.clone(); sfx.snipe(); shake(0.35); haptic('thud');
    let dx = A.p.x - from.x, dy = A.p.y - from.y; const L = Math.hypot(dx, dy) || 1; dx /= L; dy /= L;
    let best = null, bt = 30; if (doll) for (const q of doll.list) { const rx = q.body.position.x - from.x, ry = q.body.position.y - from.y, tp = rx * dx + ry * dy; if (tp > 0.2 && tp < bt && Math.abs(rx * dy - ry * dx) < 0.32) { bt = tp; best = q; } }
    if (A.part) { best = A.part; bt = L; }
    const end = best ? V3(from.x + dx * bt, from.y + dy * bt, 0) : A.p.clone(); tracer(from, end, 0xfff6c0); tracer(from, end, 0xffffff);
    if (best) { const head = best.name === 'head'; hurt(best, head ? 220 : 95, end, false, 'bullet', dx, dy); if (jointOf(best) && (head || Math.random() < 0.8)) tear(best, dx, dy); pushAt(best, dx * 26, dy * 26 + 3, end); bloodBurst(V3(end.x, end.y, 0.5), 26, dx, dy, 14, 1.3); slow = Math.max(slow, 0.45); if (head) popupT('HEADSHOT!', V3(end.x, end.y + 1, 0), '#ff3b30', 10); }
    else { decal(end.x, end.y, 0.4, 'hole'); puff(end, 0xb59a74, 6); sparks(end, 8, 0xffffff, 0xffb040, 7, 0.08); }
  }

  /* --- fireworks: rockets that burst into colour around the target --- */
  const FW = [[0xff3b6a, 0xffd0e0], [0x3bd1ff, 0xd0f4ff], [0xffd23f, 0xfff4c0], [0x7aff5a, 0xe0ffd0], [0xc76bff, 0xf0d8ff]];
  function doFireworks(A) {
    const p = A.p.clone(); sfx.launch(); popupT('FIREWORKS!', V3(p.x, Math.min(RH - 0.8, p.y + 1.6), 0), '#ffd23f', 8);
    for (let i = 0; i < 5; i++) {
      const sx = clamp(p.x + rnd(-1.8, 1.8), -RW / 2 + 0.3, RW / 2 - 0.3), T = V3(clamp(p.x + rnd(-1, 1), -RW / 2 + 0.3, RW / 2 - 0.3), clamp(p.y + rnd(-0.8, 1.2), 0.6, RH - 0.5), 0), col = FW[i], delay = i * 0.16, dur = 0.45 + Math.random() * 0.15; let t = -delay;
      addFx((dt) => { t += dt; if (t < 0) return true; const k = Math.min(1, t / dur), x = sx + (T.x - sx) * k + Math.sin(k * 14) * 0.08, y = 0.1 + (T.y - 0.1) * k;
        emit({ x, y, vx: rnd(-0.6, 0.6), vy: -2, life: 0.35, s0: 0.22, s1: 0.04, c0: 0xffffff, c1: col[0] });
        if (k >= 1) { explode(T, 1.7, 11, 28, { burn: true, size: 0.9, c0: col[0], c1: col[0], flash: 0.12, fcol: '#' + col[1].toString(16).padStart(6, '0'), shake: 0.25, vol: 0.45 }); for (let j = 0; j < 26; j++) { const a = (j / 26) * 6.28, s = rnd(5, 8); emit({ x: T.x, y: T.y, vx: Math.cos(a) * s, vy: Math.sin(a) * s, life: rnd(0.6, 1), s0: 0.16, s1: 0.03, c0: col[1], c1: col[0], g: 4, drag: 0.94 }); } sfx.crackle(); return false; } return true; });
    }
  }

  /* --- UFO: tractor beam lifts him up, zaps him, then drops him --- */
  function doUFO(A) {
    const g = new THREE.Group(), disc = new THREE.Mesh(new THREE.SphereGeometry(1, 28, 12), phong(0xb9c2cf, 140)); disc.scale.set(1.25, 0.28, 1.25); g.add(disc);
    const dome = new THREE.Mesh(new THREE.SphereGeometry(0.5, 20, 12, 0, 6.28, 0, PI / 2), new THREE.MeshPhongMaterial({ color: 0x7affb0, transparent: true, opacity: 0.75, shininess: 160 })); dome.position.y = 0.18; g.add(dome);
    const lights = []; for (let i = 0; i < 8; i++) { const a = (i / 8) * 6.28, l = new THREE.Mesh(new THREE.SphereGeometry(0.08, 8, 6), new THREE.MeshBasicMaterial({ color: 0xffe04a })); l.position.set(Math.cos(a) * 1.15, 0, Math.sin(a) * 1.15); g.add(l); lights.push(l); }
    const beam = new THREE.Mesh(new THREE.CylinderGeometry(0.45, 1.5, 1, 24, 1, true), new THREE.MeshBasicMaterial({ color: 0x6aff9a, transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide })); g.add(beam);
    const s = sideOf(A.p.x), Y = RH - 0.9; let x = s > 0 ? -RW / 2 - 2 : RW / 2 + 2, t = 0, ph = 0, zap = 0; g.position.set(x, Y, 0.3); track(g); sfx.ufo(); const tx0 = A.p.x;
    addFx((dt) => {
      t += dt; const tgt = doll ? doll.parts.chest.body.position.x : tx0; lights.forEach((l, i) => l.material.color.setHex(((i + (t * 12 | 0)) % 2) ? 0xffe04a : 0xff4a4a)); disc.rotation.y += dt * 3;
      if (ph === 0) { x += (clamp(tgt, -RW / 2 + 1.3, RW / 2 - 1.3) - x) * Math.min(1, dt * 4); if (t > 0.8) { ph = 1; t = 0; popupT('ABDUCTED!', V3(x, Y - 1.4, 0), '#7affb0', 8); hapStart(0.3, 0.6); } }
      else if (ph === 1) { x += clamp(tgt - x, -1, 1) * dt * 1.2; x = clamp(x, -RW / 2 + 1.3, RW / 2 - 1.3); beam.material.opacity = 0.35 + 0.1 * Math.sin(t * 20); beam.scale.y = Y; beam.position.y = -Y / 2;
        if (doll) for (const q of doll.list) { const b = q.body, dx = b.position.x - x; if (Math.abs(dx) < 1.4) { b.velocity.y += (cfg().gravity + 10 + (Y - 1.6 - b.position.y) * 3) * dt; b.velocity.x -= dx * 6 * dt; b.velocity.scale(1 - 1.5 * dt, b.velocity); b.angularVelocity.z += 3 * dt; } }
        if (Math.random() < 0.6) emit({ x: x + rnd(-1.2, 1.2), y: rnd(0.2, Y - 0.6), vy: rnd(1, 3), life: 0.6, s0: 0.1, s1: 0.03, c0: 0xd0ffe0, c1: 0x3aff7a, a: 0.8 });
        zap -= dt; if (t > 1.6 && zap <= 0 && doll) { zap = 0.22; const q = doll.list[(Math.random() * doll.list.length) | 0], bp = V3(q.body.position.x, q.body.position.y, 0); bolt(V3(x, Y - 0.25, 0.3), bp, 0x7affb0, 0.12); sparks(bp, 4, 0xffffff, 0x3aff7a, 6, 0.08); hurt(q, 9, bp, false, 'shock'); q.zap = 0.3; sfx.sizzle(); haptic({ intensity: 0.5, sharpness: 0.8 }); }
        if (t > 3.2) { ph = 2; t = 0; beam.material.opacity = 0; hapStop(); if (doll) for (const q of doll.list) if (Math.abs(q.body.position.x - x) < 1.6) q.body.velocity.y = -16; sfx.whoosh(); } }
      else { x += dt * 9 * -s; g.position.y = Y + t * 3; if (t > 1.2) { kill(g); return false; } }
      g.position.x = x; return true;
    });
  }

  /* --- shuriken: three spinning stars that slice through and stick in the wall --- */
  let starGeo = null;
  function doShuriken(A) {
    if (!starGeo) { const sh = new THREE.Shape(); for (let i = 0; i < 8; i++) { const a = (i / 8) * 6.28, r = i % 2 ? 0.1 : 0.34; i ? sh.lineTo(Math.cos(a) * r, Math.sin(a) * r) : sh.moveTo(r, 0); } sh.closePath(); starGeo = new THREE.ExtrudeGeometry(sh, { depth: 0.04, bevelEnabled: false }); }
    const p = A.p.clone(), s = sideOf(p.x), from = V3(s > 0 ? -RW / 2 + 0.2 : RW / 2 - 0.2, clamp(p.y + 1.2, 0.5, RH - 0.5), 0); sfx.thwip(); haptic('tick');
    for (let i = -1; i <= 1; i++) {
      let dx = p.x - from.x, dy = p.y + i * 0.55 - from.y; const L = Math.hypot(dx, dy) || 1; dx /= L; dy /= L;
      let tw = 30; if (dx > 0.001) tw = Math.min(tw, (RW / 2 - 0.1 - from.x) / dx); else if (dx < -0.001) tw = Math.min(tw, (-RW / 2 + 0.1 - from.x) / dx); if (dy > 0.001) tw = Math.min(tw, (RH - 0.15 - from.y) / dy); else if (dy < -0.001) tw = Math.min(tw, (0.12 - from.y) / dy);
      const m = new THREE.Mesh(starGeo, phong(0x9aa4b2, 160)); m.position.copy(from); m.position.z = 0.9; track(m); let t = -(i + 1) * 0.06, stuck = 0; const hit = new Set();
      addFx((dt) => { t += dt; if (t < 0) return true;
        if (!stuck) { const d = Math.min(tw, 24 * t), x = from.x + dx * d, y = from.y + dy * d; m.position.set(x, y, 0.9); m.rotation.z -= dt * 30 * s;
          if (doll) for (const q of doll.list) { if (hit.has(q)) continue; const b = q.body.position; if (Math.hypot(b.x - x, b.y - y) < 0.42) { hit.add(q); const pt = V3(x, y, 0); hurt(q, 16, pt, false, 'slash', dx, dy); woundAt(q, pt, dx, dy); pushAt(q, dx * 5, dy * 5, pt); sfx.slice(); } }
          if (d >= tw) { stuck = 0.001; sfx.clank(); sparks(m.position, 5, 0xffffff, 0xffd34a, 5, 0.06); } }
        else { stuck += dt; if (stuck > 2) { m.scale.setScalar(Math.max(0.01, 1 - (stuck - 2) / 0.3)); if (stuck > 2.3) { kill(m); return false; } } } return true; });
    }
  }

  /* --- car: drives in along the floor and rams him --- */
  function doCar(A) {
    const s = sideOf(A.p.x), g = new THREE.Group(), red = phong(0xe02a2a, 120), dark = phong(0x1c1d22, 30), glass = new THREE.MeshPhongMaterial({ color: 0x9fd6ff, shininess: 180, transparent: true, opacity: 0.85 });
    const add = (geo, mat, x, y, z) => { const m = new THREE.Mesh(geo, mat); m.position.set(x, y, z); m.castShadow = true; g.add(m); return m; };
    add(roundBox(2.4, 0.55, 1.1, 0.16, 3), red, 0, 0.55, 0); add(roundBox(1.3, 0.5, 1.0, 0.16, 3), red, -0.2, 1.0, 0); add(roundBox(1.1, 0.36, 1.02, 0.1, 2), glass, -0.2, 1.02, 0.01);
    add(roundBox(0.12, 0.14, 0.9, 0.04, 2), phong(0xfff3a0, 60), 1.2, 0.62, 0); const wheels = [];
    for (const wx of [-0.75, 0.75]) for (const wz of [-0.5, 0.5]) { const w = add(new THREE.CylinderGeometry(0.3, 0.3, 0.2, 16), dark, wx, 0.3, wz); w.rotation.x = PI / 2; wheels.push(w); }
    g.scale.x = s; let x = -s * (RW / 2 + 2); g.position.set(x, 0, 0); track(g); sfx.honk(); sfx.rumble(); hapStart(0.35, 0.3); let t = 0; const hit = new Set(), spd = 17;
    addFx((dt) => { t += dt; x += s * spd * dt; g.position.x = x; for (const w of wheels) w.rotation.y += dt * 40; if (Math.random() < 0.6) emit({ x: x - s * 1.3, y: 0.2, vx: -s * 2, vy: rnd(0.3, 1.2), life: 0.7, s0: 0.15, s1: 0.5, c0: 0x8a8580, c1: 0x4a4540, a: 0.6, smoke: true });
      if (doll) { let sum = 0; for (const q of doll.list) { if (hit.has(q)) continue; const b = q.body.position; if (Math.abs(b.x - (x + s * 0.6)) < 1.0 && b.y < 1.5) { hit.add(q); const pt = V3(b.x, b.y, 0); sum += hurt(q, 25, pt, true, 'crush', s, 0.5); q.body.velocity.x = s * spd * 1.25 + rnd(-2, 2); q.body.velocity.y = rnd(9, 14); q.body.angularVelocity.z += -s * rnd(8, 14); } }
        if (sum) { popup('-' + sum, V3(x + s * 1.2, 1.8, 0), sum); if (!g.userData.p) { g.userData.p = 1; popupT('VROOM!', V3(x + s, 2.6, 0), '#ffd23f', 9); } shake(0.6); sfx.thud(); sfx.smash(); haptic('thud'); } }
      if (Math.abs(x) > RW / 2 + 2.5 && t > 0.3) { kill(g); hapStop(); return false; } return true; });
  }

  /* --- lava geyser: the floor cracks, then erupts --- */
  function doLava(A) {
    const x = clamp(A.p.x, -RW / 2 + 0.6, RW / 2 - 0.6); decal(x, 0.25, 1.2, 'scorch'); sfx.rumble(); let t = 0, tick = 0; const D = 2.3;
    addFx((dt) => { t += dt;
      if (t < 0.5) { shake(0.12); if (Math.random() < 0.5) emit({ x: x + rnd(-0.6, 0.6), y: 0.1, vy: rnd(1, 3), vx: rnd(-1, 1), life: 0.5, s0: 0.12, s1: 0.04, c0: 0xffa030, c1: 0x9a2a08, g: 8 }); return true; }
      if (!tick) { tick = 0.001; popupT('LAVA!', V3(x, 3, 0), '#ff7a22', 9); sfx.boom(0.6); hapStart(0.55, 0.3); }
      for (let i = 0; i < 6; i++) emit({ x: x + rnd(-0.3, 0.3), y: 0.1, vx: rnd(-1.2, 1.2), vy: rnd(10, 16), life: rnd(0.5, 0.9), s0: rnd(0.35, 0.6), s1: 0.1, c0: 0xffe070, c1: 0xff2a08, g: 14, drag: 0.98, a: 0.95 });
      if (Math.random() < 0.3) emit({ x: x + rnd(-0.3, 0.3), y: rnd(2, 5), vx: rnd(-0.5, 0.5), vy: rnd(1, 2), life: 1, s0: 0.4, s1: 1.2, c0: 0x4a4540, c1: 0x1e1b19, a: 0.5, smoke: true, g: -1 });
      tick += dt; let sum = 0; const hitNow = tick > 0.25; if (hitNow) tick = 0.001;
      if (doll && t < D) for (const q of doll.list) { const b = q.body, dx = b.position.x - x; if (Math.abs(dx) < 0.85 && b.position.y < 6) { b.velocity.y += 70 * dt; b.velocity.x += (dx > 0 ? 1 : -1) * 4 * dt; q.flame = Math.max(q.flame || 0, 2.4); q.burn = Math.min(1, (q.burn || 0) + dt * 0.8); setTint(q, q.burn, 0); if (hitNow) sum += hurt(q, 9, null, true, 'burn'); } }
      if (sum) { popup('-' + sum, V3(x, 2.5, 0), sum); onFire = Math.max(onFire, 4); }
      if (t > D) { hapStop(); return false; } return true; });
  }

  /* ---- using a tool ---- */
  function useStart(x, y) {
    ptr.down = true; ptr.x = x; ptr.y = y; if (grace > 0) grace = 0; const A = aim(x, y);
    switch (tool) {
      case 'hammer': if (cd <= 0) doHammer(A.p); break;
      case 'shotgun': if (cd <= 0) doShotgun(A); break;
      case 'dynamite': if (cd <= 0) { cd = 0.28; spawnDynamite(A.p); } break;
      case 'rocket': if (cd <= 0) doRocket(A); break;
      case 'anvil': if (cd <= 0) { cd = 0.5; spawnAnvil(A.p); } break;
      case 'saw': if (cd <= 0) { cd = 0.5; spawnSaw(A.p); } break;
      case 'hole': if (cd <= 0) { cd = 1.0; openHole(A.p); } break;
      case 'katana': katanaStart(A.p); break;
      case 'grenade': if (cd <= 0) { cd = 0.4; spawnGrenade(A.p); } break;
      case 'mine': if (cd <= 0) { cd = 0.4; spawnMine(A.p); } break;
      case 'ball': if (cd <= 0) { cd = 1.2; spawnBall(A.p); } break;
      case 'lightning': if (cd <= 0) { cd = 0.7; doLightning(A); } break;
      case 'guillotine': if (cd <= 0) { cd = 1.1; doGuillotine(A); } break;
      case 'meteor': if (cd <= 0) { cd = 1.4; doMeteor(A); } break;
      case 'crossbow': if (cd <= 0) doCrossbow(A); break;
      case 'lasergrid': if (cd <= 0) { cd = 1.3; doLaserGrid(A); } break;
      case 'acid': if (cd <= 0) { cd = 1.5; doAcid(A); } break;
      case 'beartrap': if (cd <= 0) { cd = 0.5; spawnBeartrap(A.p); } break;
      case 'nuke': if (cd <= 0) { cd = 2.2; doNuke(A); } break;
      case 'magnet': if (cd <= 0) { cd = 3.4; doMagnet(A); } break;
      case 'cannon': if (cd <= 0) doCannon(A); break;
      case 'wasps': if (cd <= 0) { cd = 1.0; doWasps(A); } break;
      case 'airstrike': if (cd <= 0) { cd = 3.0; doAirstrike(A); } break;
      case 'crusher': if (cd <= 0) { cd = 2.2; doCrusher(A); } break;
      case 'glove': if (cd <= 0) { cd = 0.45; doGlove(A); } break;
      case 'piano': if (cd <= 0) { cd = 1.0; spawnPiano(A.p); } break;
      case 'tornado': if (cd <= 0) { cd = 4.4; doTornado(A); } break;
      case 'sniper': if (cd <= 0) doSniper(A); break;
      case 'fireworks': if (cd <= 0) { cd = 1.3; doFireworks(A); } break;
      case 'ufo': if (cd <= 0) { cd = 5.4; doUFO(A); } break;
      case 'shuriken': if (cd <= 0) { cd = 0.5; doShuriken(A); } break;
      case 'car': if (cd <= 0) { cd = 1.4; doCar(A); } break;
      case 'lava': if (cd <= 0) { cd = 2.6; doLava(A); } break;
      case 'pistol': case 'taser': case 'flame': case 'chainsaw': case 'freeze': case 'minigun': gunId = tool; gun.vis = 0.3; gun.kick = 0; break;
    }
  }
  function useMove(x, y) { ptr.x = x; ptr.y = y; if (tool === 'katana' && ptr.down) katanaMove(x, y); }
  function endUse() { if (ptr.down) { ptr.down = false; } loopStop('taser'); loopStop('flame'); loopStop('chainsaw'); loopStop('freeze'); hapStop(); tzOn = false; mgT = 0; kat.prev = null; kat.cur = null; }

  function doHammer(p) {
    cd = 0.42; const side = p.x > 0 ? 1 : -1, L = 1.65, g = new THREE.Group();
    const wood = phong(0xa86a2c, 20), steel = phong(0xb3bdcc, 110), dark = phong(0x3c2210, 10), hand = new THREE.Mesh(new THREE.CylinderGeometry(0.075, 0.09, 1.5, 14), wood); hand.position.y = 0.72; g.add(hand);
    for (let i = 0; i < 4; i++) { const r = new THREE.Mesh(new THREE.TorusGeometry(0.088, 0.02, 6, 16), dark); r.rotation.x = PI / 2; r.position.y = 0.1 + i * 0.12; g.add(r); }
    const cap = new THREE.Mesh(new THREE.SphereGeometry(0.1, 12, 8), dark); g.add(cap);
    const head = new THREE.Mesh(roundBox(1.0, 0.6, 0.62, 0.09, 4), steel); head.position.y = L; g.add(head);
    [-1, 1].forEach((s) => { const b = new THREE.Mesh(roundBox(0.1, 0.64, 0.66, 0.04, 2), phong(0x6c7686, 90)); b.position.set(s * 0.36, L, 0); g.add(b); });
    g.traverse((m) => { if (m.isMesh) m.castShadow = true; }); track(g);
    const phi0 = side > 0 ? 0.2 : PI - 0.2, phi1 = side > 0 ? 2.5 : PI - 2.5, px = p.x - L * Math.cos(phi1), py = p.y - L * Math.sin(phi1); let t = 0, hit = false;
    addFx((dt) => {
      t += dt; const k = Math.min(1, t / 0.24), e = k * k * k, phi = phi0 + (phi1 - phi0) * e;
      g.rotation.z = phi - PI / 2; g.position.set(px, py, 1.15);
      if (t < 0.24 && t > 0.08) emit({ x: px + L * Math.cos(phi), y: py + L * Math.sin(phi), life: 0.18, s0: 0.35, s1: 0.1, c0: 0xffffff, c1: 0xffe9a0, a: 0.6 });
      if (!hit && t >= 0.24) { hit = true; smash(p, side); }
      if (t > 0.38) g.scale.setScalar(Math.max(0.01, 1 - (t - 0.38) / 0.16));
      if (t > 0.56) { scene.remove(g); disposeObj(g); return false; } return true;
    });
  }
  function smash(p, side) {
    const sum = blow(p, -side * 0.95, 0.25, 1.5, 17, 38); sparks(p, 12, 0xffffff, 0xffd34a, 9, 0.13); ring(p, 1.0, 0xffffff, 0.22);
    emit({ x: p.x, y: p.y, life: 0.18, s0: 1.0, s1: 1.8, c0: 0xffffff, c1: 0xffd34a }); puff(p, 0xf3e4c5, 6); shake(sum ? 0.3 : 0.15); sfx.smash(); haptic('thud');
    if (!sum && p.y < 0.6) puff(p, 0xd8cdb8, 5);
  }
  function bulletShot(spread, power, dmg, mark, speed) {
    const A = aim(ptr.x + rnd(-spread, spread), ptr.y + rnd(-spread, spread)), to = A.p.clone(), from = gun.muz.clone(), part = A.part;
    let dx = to.x - from.x, dy = to.y - from.y; const L = Math.hypot(dx, dy) || 1; dx /= L; dy /= L;
    bulletFx(from, to, !!mark, () => {
      if (part && doll && doll.list.indexOf(part) >= 0) { pushAt(part, dx * power, dy * power + 0.4, to); hurt(part, dmg, to, !!mark, 'bullet', dx, dy); woundAt(part, to, dx, dy); sparks(to, 4, 0xffffff, 0xffd34a, 5, 0.07); puff(to, 0xf6e7c8, 2); }
      else { decal(to.x, to.y, 0.34, 'hole'); sparks(to, 3, 0xffffff, 0xffa030, 4, 0.06); puff(to, 0xb59a74, 2); }
    }, speed || 58);
    return A;
  }
  function muzzleFlash(big) {
    const m = gun.muz, d = gun.dir; emit({ x: m.x, y: m.y, life: 0.07, s0: big ? 1.4 : 0.8, s1: big ? 2.2 : 1.2, c0: 0xffffff, c1: 0xffc14a });
    for (let i = 0; i < (big ? 10 : 5); i++) emit({ x: m.x, y: m.y, vx: d.x * rnd(5, 14) + rnd(-2, 2), vy: d.y * rnd(5, 14) + rnd(-2, 2), life: 0.16, s0: 0.14, s1: 0.03, c0: 0xffffff, c1: 0xffa030 });
    const f = new THREE.Mesh(streakGeo, streakMat); f.renderOrder = 9; f.rotation.z = Math.atan2(d.y, d.x); const L = big ? 2.4 : 1.5; f.position.set(m.x + d.x * L * 0.4, m.y + d.y * L * 0.4, 0.98); f.scale.set(L, big ? 0.9 : 0.55, 1); track(f); let t = 0; addFx((dt) => { t += dt; if (t > 0.055) { scene.remove(f); return false; } return true; });
    emit({ x: m.x + d.x * 0.3, y: m.y + d.y * 0.3, vx: d.x * 1.5, vy: d.y * 1.5 + 0.8, life: 0.7, s0: 0.12, s1: 0.5, c0: 0xaaaaaa, c1: 0x777777, a: 0.4, smoke: true, g: -0.5 });
  }
  function doPistol() {
    cd = 0.14; gun.vis = 0.5; gun.kick = 0.24; const A = aim(ptr.x, ptr.y); placeGun('pistol', A.p); muzzleFlash(false); casing(false); bulletShot(7, 6, rnd(10, 17), false, 62);
    sfx.shot(); haptic({ intensity: 0.45, sharpness: 0.9 }); shake(0.06);
  }
  function doShotgun(A) {
    cd = 0.7; gunId = 'shotgun'; gun.vis = 1.1; gun.kick = 0.55; placeGun('shotgun', A.p); muzzleFlash(true); casing(true);
    for (let i = 0; i < 9; i++) bulletShot(46, 6, rnd(9, 16), i % 2 ? 0xffe2a0 : 0xffffff, 44 + rnd(0, 14));
    sfx.shotgun(); haptic('thud'); shake(0.32);
  }
  function popupBlast() { }
  function doRocket(A) { cd = 1.0; gunId = 'rocket'; gun.vis = 1.2; gun.kick = 0.6; placeGun('rocket', A.p); muzzleFlash(true); fireRocket(gun.muz.clone(), A.p.clone()); }

  /* ---- continuous tools: taser and flamethrower ---- */
  let tzOn = false, tzT = 0, tzDmg = 0, tzPop = 0, flT = 0;
  function holdTool(dt) {
    if (tool === 'minigun') { holdMinigun(dt); return; } if (tool === 'chainsaw') { holdChainsaw(dt); return; } if (tool === 'freeze') { holdFreeze(dt); return; }
    if (tool === 'pistol') { if (cd <= 0) doPistol(); gun.vis = Math.max(gun.vis, 0.2); return; }
    if (tool === 'taser') {
      gunId = 'taser'; gun.vis = Math.max(gun.vis, 0.2); const A = aim(ptr.x, ptr.y); placeGun('taser', A.p); const m = gun.muz; let tp = A.p, part = A.part || nearPart(A.p, 0.9);
      if (!tzOn) { tzOn = true; loopStart('taser'); }
      hapStart(part ? 0.6 : 0.25, 0.9); tzT += dt; const to = part ? V3(part.body.position.x, part.body.position.y, 0) : tp, tgt = (A.part && A.hit) ? A.p : to;
      bolt(m, tgt, 0xffffff, 0.14); bolt(m, tgt, 0x9fd8ff, 0.3); bolt(m, tgt, 0x4aa8ff, 0.5);
      emit({ x: m.x, y: m.y, life: 0.08, s0: 0.7, s1: 0.4, c0: 0xffffff, c1: 0x6ab8ff, a: 0.9 });
      if (part && doll) {
        for (const q of doll.list) { const b = q.body, k = q === part ? 1 : 0.55; b.velocity.x += rnd(-1, 1) * 3.2 * k; b.velocity.y += rnd(-0.6, 1.4) * 2.4 * k * (dt * 60); b.angularVelocity.z += rnd(-1, 1) * 4 * k; q.zap = 0.3; setTint(q, q.burn || 0, 0.55 + 0.45 * Math.sin(tzT * 50 + q.body.id)); }
        for (let i = 0; i < 3; i++) { const q = doll.list[(Math.random() * doll.list.length) | 0]; if (Math.random() < 0.6) bolt(tgt, V3(q.body.position.x, q.body.position.y, 0), 0xa9dcff, 0.18); }
        sparks(tgt, 2, 0xffffff, 0x59b2ff, 6, 0.08); tzDmg += dt * 22; tzPop += dt; const whole = Math.floor(tzDmg); if (whole > 0) { tzDmg -= whole; hurt(part, whole, null, true, 'shock'); }
        if (tzPop > 0.35) { tzPop = 0; popup('-' + Math.round(22 * 0.35), tgt, 8); }
      } else { sparks(tgt, 1, 0xffffff, 0x59b2ff, 4, 0.06); }
      return;
    }
    if (tool === 'flame') {
      gunId = 'flame'; gun.vis = Math.max(gun.vis, 0.2); const A = aim(ptr.x, ptr.y); placeGun('flame', A.p); const m = gun.muz, d = gun.dir;
      if (!loops.flame) { loopStart('flame'); } hapStart(0.32, 0.2);
      for (let i = 0; i < 7; i++) { const sp = rnd(-0.16, 0.16), ca = Math.cos(sp), sa = Math.sin(sp), vx = (d.x * ca - d.y * sa), vy = (d.x * sa + d.y * ca), s = rnd(11, 18); emit({ x: m.x, y: m.y, vx: vx * s, vy: vy * s + 0.5, life: rnd(0.35, 0.65), s0: 0.22, s1: rnd(0.9, 1.5), c0: 0xfff0a0, c1: 0xff3a08, drag: 0.93, g: -2.5, a: 0.85, ap: 1.2 }); }
      if (Math.random() < 0.4) emit({ x: m.x + d.x * 3, y: m.y + d.y * 3, vx: d.x * 6, vy: d.y * 6 + 2, life: 0.9, s0: 0.3, s1: 1.1, c0: 0x3c3733, c1: 0x1a1816, g: -1.5, drag: 0.95, a: 0.5, smoke: true });
      const reach = Math.min(7, Math.hypot(A.p.x - m.x, A.p.y - m.y) + 1.6); flT += dt; let sum = 0, nb = 0;
      if (doll) for (const q of doll.list) {
        const b = q.body, rx = b.position.x - m.x, ry = b.position.y - m.y, tproj = rx * d.x + ry * d.y; if (tproj < 0 || tproj > reach) continue; const dist = Math.abs(rx * d.y - ry * d.x);
        if (dist < 0.62) { b.velocity.x += d.x * 9 * dt; b.velocity.y += d.y * 9 * dt; q.flame = Math.max(q.flame || 0, 2.6); q.burn = Math.min(1, (q.burn || 0) + dt * 0.55); setTint(q, q.burn, 0); sum += hurt(q, dt * 22, null, true, 'burn'); nb++; }
      }
      if (nb) onFire = Math.max(onFire, 4.5);
      if (sum && flT > 0.4) { flT = 0; popup('-' + Math.max(1, Math.round(13 * 0.4 * 3)), V3(A.p.x, A.p.y, 0), 12); }
      return;
    }
  }

  function updateWays(dt) {
    cd = Math.max(0, cd - dt); grace = Math.max(0, grace - dt); boltUsed = 0;
    if (ptr.down && HOLD[tool]) holdTool(dt);
    else if (tool === 'taser' || tool === 'flame') { loopStop(tool); }
    gun.vis = Math.max(0, gun.vis - dt); gun.kick *= Math.pow(0.0004, dt);
    if (gunId && !(ptr.down && HOLD[tool]) && gun.vis > 0) placeGun(gunId, gun.target, dt);
    if (gun.vis <= 0) hideGuns();
    for (const k in gunMeshes) if (k !== gunId) gunMeshes[k].visible = false;
    for (let i = bolts.length - 1; i >= boltUsed; i--) bolts[i].visible = false;
    if (tool === 'katana') { kat.vis = Math.max(0, kat.vis - dt); if (ptr.down) placeKatana(); else if (gunMeshes.katana) gunMeshes.katana.visible = false; } else if (gunMeshes.katana) gunMeshes.katana.visible = false;
    for (let i = effects.length - 1; i >= 0; i--) if (!effects[i](dt)) effects.splice(i, 1);
    for (let i = things.length - 1; i >= 0; i--) { const t = things[i]; t.mesh.position.copy(t.body.position); if (t.kind !== 'saw' || true) t.mesh.quaternion.copy(t.body.quaternion); if (t.kind === 'saw') t.mesh.quaternion.set(0, 0, 0, 1); if (!t.update(dt)) { dropThing(t); things.splice(i, 1); } }
    updRockets(dt); updHoles(dt); updAcid(dt);
    if (doll) for (const q of doll.list) {
      if (q.flame > 0) { q.flame -= dt; const b = q.body, n = (dt * 60 * 0.9) | 0 || (Math.random() < 0.9 ? 1 : 0); for (let i = 0; i < n; i++) { emit({ x: b.position.x + rnd(-0.12, 0.12), y: b.position.y + rnd(-0.1, 0.2), vx: rnd(-0.6, 0.6), vy: rnd(1.5, 3.2), life: rnd(0.3, 0.55), s0: 0.22, s1: 0.06, c0: 0xffd45a, c1: 0xff3a08, g: -1, a: 0.85 }); } if (Math.random() < 0.3) emit({ x: b.position.x, y: b.position.y + 0.2, vy: rnd(1, 2.4), vx: rnd(-0.4, 0.4), life: 0.8, s0: 0.2, s1: 0.8, c0: 0x4a4540, c1: 0x1c1a18, g: -1, a: 0.5, smoke: true }); if (Math.random() < 0.05) hurt(q, 1, null, true); }
      if (q.shock > 0 && !(tzOn && ptr.down)) { q.shock = Math.max(0, q.shock - dt * 6); setTint(q, q.burn || 0, q.shock); }
    }
    updateGore(dt); updParticles(dt); updDecals(dt);
    if (mood > 0) { mood -= dt; const h = mood > 0; if (h !== faceHurt) { faceHurt = h; setFace(h); } }
    shakeAmp *= Math.pow(0.002, dt); if (shakeAmp < 0.004) shakeAmp = 0;
  }
  function waysStep(h) { if (mag.on) magnetStep(h); for (const x of holes) holePull(x); if (doll) for (const q of doll.list) { if (q.ice > 0) { const b = q.body; b.velocity.scale(1 - 0.05 * q.ice, b.velocity); b.angularVelocity.scale(1 - 0.05 * q.ice, b.angularVelocity); if (frozenT > 0) { b.force.y += b.mass * cfg().gravity; b.velocity.scale(0.92, b.velocity); b.angularVelocity.scale(0.9, b.angularVelocity); } } } }
  function clearWays() { clearThings(); effects.length = 0; endUse(); hideGuns(); mood = 0; faceHurt = false; grace = 1.6; hp = MAXHP; dead = false; deadT = 0; stumps.length = 0; onFire = 0; slow = 0; hpShown = -1; hpBar(); frozenT = 0; mag.on = false; buzzStop(); clearPins(); for (const o of fxObjs.splice(0)) scene.remove(o); for (const c of casings.splice(0)) scene.remove(c.m); }

  /* ------------------------------------------------------------------ 6. input + loop */
  let orbitId = -1, orbitLast = null, acc = 0, last = 0, running = false;
  function bindInput() {
    const el = renderer.domElement;
    el.addEventListener('pointerdown', (e) => {
      if (hold.on || orbitId >= 0 || ptr.id >= 0) return; audioInit();
      try { el.setPointerCapture(e.pointerId); } catch (x) {}
      if (tool === 'hand') { if (grab(e.clientX, e.clientY)) { hold.id = e.pointerId; } }
      else { ptr.id = e.pointerId; useStart(e.clientX, e.clientY); }
      e.preventDefault();
    });
    el.addEventListener('pointermove', (e) => {
      if (e.pointerId === hold.id) moveHold(e.clientX, e.clientY);
      if (e.pointerId === ptr.id) useMove(e.clientX, e.clientY);
    });
    const up = (e) => { if (e.pointerId === ptr.id) { ptr.id = -1; endUse(); } if (e.pointerId === hold.id) { release(); hold.id = -1; } if (e.pointerId === orbitId) { orbitId = -1; orbitLast = null; } };
    el.addEventListener('pointerup', up); el.addEventListener('pointercancel', up);
    document.getElementById('btnReset').addEventListener('click', () => { audioInit(); haptic('tick'); clearBlood(); resetDoll(); });
  }

  function frame(t) {
    requestAnimationFrame(frame);
    const raw = t - last; watchQuality(raw); let dt = Math.min(0.11, Math.max(0.0001, raw / 1000)); last = t; if (slow > 0) { slow -= dt; dt *= 0.3; }
    if (mode === 'play') {
      acc += dt; let n = 0;
      while (acc >= FIX && n < MAXSUB) { driveHold(); waysStep(FIX); world.step(FIX); acc -= FIX; n++; }
      if (acc > FIX) acc = 0;
      safety(); sync(); updateWays(dt);
      if (hold.on && hold.dot) { hold.part.body.pointToWorldFrame(hold.local, wv); hold.dot.position.set(wv.x, wv.y, wv.z); }
    }
    placeCamera(); const vh = renderer.domElement.height; for (const b of batches) b.flush(vh); renderer.render(scene, camera);
  }

  // anything that somehow escapes the room (or turns to NaN) gets the doll rebuilt
  function safety() {
    if (!doll) return;
    for (const p of doll.list) { const q = p.body.position; if (!(q.x === q.x) || Math.abs(q.x) > RW || q.y < -2 || q.y > RH + 2 || Math.abs(q.z) > RD) { resetDoll(); return; } }
  }

  function applyConfig() {
    world.gravity.set(0, -cfg().gravity, 0); dollWallContact.restitution = cfg().bounce;
  }

  function run(m) {
    mode = m || window.mode || 'play';
    initWorld(); initScene(); initFx(); initGore(); initWays2(); sfxPlus(); initWays3(); sfx4(); initProps(); resetDoll(); if (m !== 'edit' && (m || window.mode || 'play') === 'play') { buildPanel(); setTool('hand'); loadShop(); }
    try {
      lib.showGameParameters({
        name: '40 Ways to Kill the Ragdoll',
        params: {
          'Gravity': { key: 'gravity', type: 'slider', min: 6, max: 45, step: 1, onChange: (v) => { window.gameConfig.gravity = v; applyConfig(); } },
          'Wall bounce': { key: 'bounce', type: 'slider', min: 0, max: 0.8, step: 0.05, onChange: (v) => { window.gameConfig.bounce = v; applyConfig(); } },
          'Ragdoll size': { key: 'scale', type: 'slider', min: 0.5, max: 1, step: 0.02, onChange: (v) => { window.gameConfig.scale = v; resetDoll(); } },
          'Grab strength': { key: 'grab', type: 'slider', min: 0.4, max: 2, step: 0.1, onChange: (v) => { window.gameConfig.grab = v; } },
          'Unlock all ways (testing)': { key: 'unlockAll', type: 'checkbox', onChange: (v) => { window.gameConfig.unlockAll = !!v; refreshPanel(); } }
        }
      });
    } catch (e) {}
    if (mode === 'play') bindInput(); else { document.getElementById('hint').classList.add('off'); document.getElementById('btnReset').style.display = 'none'; const pn = document.getElementById('panel'); if (pn) pn.style.display = 'none'; }
    window.__rag = { addCoins: (n) => addCoins(n), world, get doll() { return doll; }, cam, camera, grab, moveHold, release, hold, resetDoll, setTool, useStart, useMove, endUse, ptr, TOOLS, get dmg() { return totalDmg; }, things, holes, rockets, P, step: (n) => { for (let i = 0; i < n; i++) { driveHold(); waysStep(FIX); world.step(FIX); } sync(); updateWays(n * FIX); }, render: () => { placeCamera(); renderer.render(scene, camera); }, ROOM: [RW, RH, RD], scene, gunMeshes, gun };
    window.__quality = (force) => { if (force != null) { autoQ = null; applyQuality(force); } return { tier: TIERS[qTier].name, fps: autoQ && autoQ.lastFps }; };
    if (!running) { running = true; requestAnimationFrame(frame); }
    preloadImages(['wood_back', ...TOOLS.map((t) => t.asset)].map(assetUrl), setLoaderProgress).then(() => hideLoader());
  }
  window.run = run;
})();
