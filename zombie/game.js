/* 50 Ways to Kill a Zombie — a cartoon physics sandbox (Three.js r128 + Cannon.js 0.6.2).
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

  /* ruined zombie room: cracked stained plaster, boarded window, blood smears, rotten plank floor (all painted on canvases) */
  const texCache = {};
  function boxTex(kind) {
    if (texCache[kind]) return texCache[kind];
    let sd = kind.length * 977 + 13; const rnd = () => { sd = (sd * 16807) % 2147483647; return sd / 2147483647; };
    const W = 512, H = 1024, c = document.createElement('canvas'); c.width = W; c.height = H; const g = c.getContext('2d');
    const base = { back: '#59614f', floor: '#3a2e21', ceil: '#2c2f28', side: '#3e4339' }[kind];
    g.fillStyle = base; g.fillRect(0, 0, W, H);
    const blot = (n, rmin, rmax, col, al) => { for (let i = 0; i < n; i++) { const x = rnd() * W, y = rnd() * H, r = rmin + rnd() * (rmax - rmin), rg = g.createRadialGradient(x, y, 0, x, y, r); rg.addColorStop(0, col.replace('A', al)); rg.addColorStop(1, col.replace('A', 0)); g.fillStyle = rg; g.fillRect(x - r, y - r, r * 2, r * 2); } };
    const crack = (x, y, len, col) => { g.strokeStyle = col; g.lineWidth = 1.5 + rnd() * 1.5; g.beginPath(); g.moveTo(x, y); let a = rnd() * 6.28; for (let i = 0; i < 9; i++) { a += (rnd() - 0.5) * 1.1; x += Math.cos(a) * len / 9; y += Math.sin(a) * len / 9; g.lineTo(x, y); if (rnd() < 0.3) { const bx = x, by = y, ba = a + (rnd() - 0.5) * 2; g.moveTo(bx, by); g.lineTo(bx + Math.cos(ba) * len / 6, by + Math.sin(ba) * len / 6); g.moveTo(x, y); } } g.stroke(); };
    const smear = (x, y, w, h, col) => { g.fillStyle = col; g.beginPath(); g.moveTo(x, y); g.bezierCurveTo(x + w, y + h * 0.1, x + w * 1.2, y + h * 0.6, x + w * 0.3, y + h); g.bezierCurveTo(x - w * 0.5, y + h * 0.7, x - w * 0.6, y + h * 0.2, x, y); g.fill(); };
    const drip = (x, y, len, col) => { g.fillStyle = col; g.fillRect(x - 2, y, 4, len); g.beginPath(); g.arc(x, y + len, 4, 0, 6.3); g.fill(); };
    if (kind === 'back') {
      // faded wallpaper stripes, peeling in places
      for (let x = 0; x < W; x += 64) { g.fillStyle = (x / 64) % 2 ? 'rgba(80,100,70,.28)' : 'rgba(30,40,25,.18)'; g.fillRect(x, 0, 64, H); }
      blot(26, 40, 120, 'rgba(25,30,18,A)', 0.4); blot(10, 50, 130, 'rgba(110,90,40,A)', 0.22);
      for (let i = 0; i < 7; i++) { const x = rnd() * W * 0.9, y = rnd() * H * 0.7, w = 30 + rnd() * 60, h = 60 + rnd() * 140; g.fillStyle = 'rgba(46,44,36,.9)'; g.fillRect(x, y, w, h); g.fillStyle = 'rgba(20,20,16,.35)'; g.fillRect(x, y + h - 6, w, 6); g.fillStyle = 'rgba(110,130,95,.5)'; g.beginPath(); g.moveTo(x, y); g.lineTo(x + w * 0.5, y + 18); g.lineTo(x + w, y); g.fill(); }
      for (let i = 0; i < 5; i++) crack(rnd() * W, rnd() * H * 0.8, 120 + rnd() * 160, 'rgba(15,16,12,.75)');
      // boarded window top-left with moonlight
      g.fillStyle = '#0c1118'; g.fillRect(34, 60, 120, 170); const mg = g.createLinearGradient(34, 60, 154, 230); mg.addColorStop(0, 'rgba(140,170,210,.55)'); mg.addColorStop(1, 'rgba(60,80,110,.05)'); g.fillStyle = mg; g.fillRect(34, 60, 120, 170);
      for (const [y, a] of [[84, -0.06], [140, 0.05], [196, -0.04]]) { g.save(); g.translate(94, y); g.rotate(a); g.fillStyle = '#5a4630'; g.fillRect(-92, -14, 184, 28); g.fillStyle = 'rgba(0,0,0,.35)'; g.fillRect(-92, 8, 184, 6); g.fillStyle = '#9a9a9a'; g.fillRect(-80, -2, 4, 4); g.fillRect(74, -2, 4, 4); g.restore(); }
      g.strokeStyle = '#241a10'; g.lineWidth = 8; g.strokeRect(34, 60, 120, 170);
      // blood: handprint-ish smears, drips and scratches near the edges
      smear(436, 180, 38, 120, 'rgba(100,12,16,.8)'); smear(60, 560, 30, 90, 'rgba(90,10,14,.75)'); smear(452, 640, 34, 110, 'rgba(110,14,18,.7)');
      for (const [x, y, l] of [[440, 290, 80], [452, 300, 40], [470, 296, 110], [64, 640, 70], [78, 650, 36], [462, 740, 90]]) drip(x, y, l, 'rgba(100,12,16,.8)');
      g.strokeStyle = 'rgba(14,10,8,.6)'; g.lineWidth = 3; for (let k = 0; k < 4; k++) { g.beginPath(); g.moveTo(380 + k * 14, 380); g.lineTo(372 + k * 14, 520); g.stroke(); }
      // sickly green glow behind the zombie, dark toward the edges
      const rg = g.createRadialGradient(W / 2, H * 0.5, 20, W / 2, H * 0.5, H * 0.62); rg.addColorStop(0, 'rgba(160,200,110,.32)'); rg.addColorStop(.5, 'rgba(90,120,60,.08)'); rg.addColorStop(1, 'rgba(0,0,0,.5)'); g.fillStyle = rg; g.fillRect(0, 0, W, H);
      // baseboard
      g.fillStyle = '#231a12'; g.fillRect(0, H - 54, W, 54); g.fillStyle = 'rgba(0,0,0,.4)'; g.fillRect(0, H - 54, W, 5);
    } else if (kind === 'floor') {
      // rotten planks running left-right, seams, grime and blood pools
      for (let y = 0, i = 0; y < H; y += 128, i++) { g.fillStyle = i % 2 ? '#40331f' : '#34291a'; g.fillRect(0, y, W, 128); g.fillStyle = 'rgba(0,0,0,.55)'; g.fillRect(0, y, W, 4); for (let k = 0; k < 14; k++) { g.fillStyle = 'rgba(0,0,0,.16)'; g.fillRect(rnd() * W, y + 8 + rnd() * 110, 40 + rnd() * 160, 2); } const sx = (i * 173) % W; g.fillStyle = 'rgba(0,0,0,.6)'; g.fillRect(sx, y, 4, 128); }
      blot(18, 30, 100, 'rgba(10,8,4,A)', 0.5); blot(5, 40, 90, 'rgba(95,10,14,A)', 0.6); blot(3, 20, 60, 'rgba(60,70,30,A)', 0.4);
      const lg = g.createLinearGradient(0, H, 0, 0); lg.addColorStop(0, 'rgba(0,0,0,.45)'); lg.addColorStop(1, 'rgba(0,0,0,0)'); g.fillStyle = lg; g.fillRect(0, 0, W, H);
    } else if (kind === 'ceil') {
      for (let x = 0; x < W; x += 128) { g.fillStyle = 'rgba(30,22,14,.9)'; g.fillRect(x, 0, 26, H); }
      blot(14, 40, 120, 'rgba(70,60,20,A)', 0.4); blot(10, 40, 110, 'rgba(8,10,6,A)', 0.5);
    } else {
      blot(24, 40, 120, 'rgba(15,18,10,A)', 0.45); blot(6, 40, 100, 'rgba(100,80,30,A)', 0.2);
      for (let i = 0; i < 4; i++) crack(rnd() * W, rnd() * H, 150 + rnd() * 160, 'rgba(10,12,8,.7)');
      smear(120, 260, 36, 100, 'rgba(90,10,14,.6)'); drip(130, 330, 70, 'rgba(90,10,14,.6)');
      const dg = g.createLinearGradient(0, 0, W, 0); dg.addColorStop(0, 'rgba(0,0,0,.5)'); dg.addColorStop(1, 'rgba(0,0,0,0)'); g.fillStyle = dg; g.fillRect(0, 0, W, H);
    }
    // film grain
    for (let i = 0; i < 900; i++) { g.fillStyle = rnd() < 0.5 ? 'rgba(0,0,0,.08)' : 'rgba(255,255,255,.035)'; g.fillRect(rnd() * W, rnd() * H, 2 + rnd() * 4, 1 + rnd() * 2); }
    const t = new THREE.CanvasTexture(c); t.anisotropy = 4; texCache[kind] = t; return t;
  }

  let roomObjs = [], woodImg = null;
  // real wood-plank picture for the back panel (generated asset); the canvas cardboard stays as the fallback
  function loadWood() {
    return; const a = window.lib && lib.getAsset && lib.getAsset('wood_back'); if (!a || !a.url) return;
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
    roomObjs = []; walls.length = 0; disposeSet();
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
    applyWood(); buildSet();
  }
  /* ---- 3D set dressing: real geometry in front of the painted back wall (visual only, no physics) ---- */
  let setG = null, bulbMat = null, bulbGlow = null; const setTex = {};
  function woodTexS() {
    if (setTex.wood) return setTex.wood;
    const c = document.createElement('canvas'); c.width = c.height = 128; const g = c.getContext('2d'); g.fillStyle = '#6b5236'; g.fillRect(0, 0, 128, 128);
    let sd = 91; const r = () => { sd = (sd * 16807) % 2147483647; return sd / 2147483647; };
    for (let i = 0; i < 9; i++) { const y = i * 14.2; g.fillStyle = i % 2 ? '#5d4630' : '#74593a'; g.fillRect(0, y, 128, 14); g.fillStyle = 'rgba(0,0,0,.35)'; g.fillRect(0, y + 13, 128, 1.5); }
    for (let i = 0; i < 90; i++) { g.strokeStyle = 'rgba(30,20,10,' + (0.12 + r() * 0.2) + ')'; g.lineWidth = 1; const y = r() * 128, x = r() * 128; g.beginPath(); g.moveTo(x, y); g.lineTo(x + 20 + r() * 50, y + (r() - 0.5) * 3); g.stroke(); }
    for (let i = 0; i < 5; i++) { g.fillStyle = 'rgba(20,12,6,.5)'; g.beginPath(); g.ellipse(r() * 128, r() * 128, 3 + r() * 3, 2, 0, 0, 6.3); g.fill(); }
    const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.anisotropy = 4; return (setTex.wood = t);
  }
  function glowTexS() {
    if (setTex.glow) return setTex.glow;
    const c = document.createElement('canvas'); c.width = c.height = 128; const g = c.getContext('2d'), gr = g.createRadialGradient(64, 64, 0, 64, 64, 64); gr.addColorStop(0, 'rgba(255,240,180,1)'); gr.addColorStop(0.25, 'rgba(255,220,130,.5)'); gr.addColorStop(1, 'rgba(255,200,100,0)'); g.fillStyle = gr; g.fillRect(0, 0, 128, 128);
    return (setTex.glow = new THREE.CanvasTexture(c));
  }
  function webTexS() {
    if (setTex.web) return setTex.web;
    const c = document.createElement('canvas'); c.width = c.height = 128; const g = c.getContext('2d'); g.strokeStyle = 'rgba(225,230,215,.8)'; g.lineWidth = 1.1;
    for (let i = 0; i <= 6; i++) { const a = (i / 6) * PI / 2; g.beginPath(); g.moveTo(0, 0); g.lineTo(Math.cos(a) * 180, Math.sin(a) * 180); g.stroke(); }
    for (let k = 1; k <= 6; k++) { const R = k * 21; g.beginPath(); for (let i = 0; i <= 6; i++) { const a = (i / 6) * PI / 2, rr = R * (i % 1 === 0 && i > 0 && i < 6 ? 0.93 : 1); const x = Math.cos(a) * rr, y = Math.sin(a) * rr; i ? g.lineTo(x, y) : g.moveTo(x, y); } g.stroke(); }
    return (setTex.web = new THREE.CanvasTexture(c));
  }
  function disposeSet() { if (!setG) return; scene.remove(setG); setG.traverse((m) => { if (m.isMesh) { m.geometry.dispose(); const a = Array.isArray(m.material) ? m.material : [m.material]; a.forEach((x) => x.dispose()); } }); setG = null; }
  function buildSet() {
    disposeSet(); const G = new THREE.Group(); setG = G; scene.add(G); const zb = -RD / 2;
    const M = (col, rough, metal, ex) => new THREE.MeshStandardMaterial(Object.assign({ color: col, roughness: rough == null ? 0.8 : rough, metalness: metal || 0, envMapIntensity: metal ? 0.9 : 0.3 }, ex || {}));
    const P = (geo, mat, x, y, z, rx, ry, rz, noShadow) => { const m = new THREE.Mesh(geo, mat); m.position.set(x, y, z); if (rx || ry || rz) m.rotation.set(rx || 0, ry || 0, rz || 0); m.castShadow = !noShadow; m.receiveShadow = true; G.add(m); return m; };
    const wood = M(0xffffff, 0.85, 0, { map: woodTexS() }), woodD = M(0x3a2a1a, 0.9), steel = M(0x6b727a, 0.42, 0.85), rust = M(0x6a3a28, 0.7, 0.4), dark = M(0x1d1f1a, 0.8);
    // skirting board and crown moulding give the flat wall a real edge to catch light
    P(roundBox(RW, 0.34, 0.12, 0.04, 2), M(0x2c2319, 0.9), 0, 0.17, zb + 0.06); P(roundBox(RW, 0.07, 0.15, 0.025, 2), M(0x3d3022, 0.9), 0, 0.38, zb + 0.07);
    P(roundBox(RW, 0.22, 0.16, 0.04, 2), M(0x221b13, 0.9), 0, RH - 0.11, zb + 0.08); P(roundBox(RW, 0.06, 0.12, 0.02, 2), M(0x3d3022, 0.9), 0, RH - 0.27, zb + 0.06);
    // boarded window (matches the painted one, now with real frame and planks) + a cold light shaft
    const wx = (94 / 512 - 0.5) * RW, wy = RH * (1 - 145 / 1024), ww = 0.234 * RW, wh = 0.166 * RH;
    for (const [dx, dy, w, h] of [[0, wh / 2 + 0.04, ww + 0.2, 0.1], [0, -wh / 2 - 0.04, ww + 0.2, 0.1], [-ww / 2 - 0.04, 0, 0.1, wh], [ww / 2 + 0.04, 0, 0.1, wh]]) P(roundBox(w, h, 0.14, 0.03, 2), woodD, wx + dx, wy + dy, zb + 0.08);
    for (const [dy, a, len] of [[0.45, -0.06, 1.62], [0.036, 0.05, 1.58], [-0.4, -0.04, 1.64]]) { const b = P(roundBox(len, 0.2, 0.05, 0.015, 2), wood, wx, wy + dy, zb + 0.16, 0, 0, -a); for (const s of [-1, 1]) P(new THREE.CylinderGeometry(0.028, 0.028, 0.03, 8), steel, wx + s * (ww / 2 - 0.05), wy + dy, zb + 0.2, PI / 2, 0, 0, true); }
    { const gm = new THREE.BufferGeometry(), v = [wx - ww / 2, wy - wh / 2, 0, wx + ww / 2, wy - wh / 2, 0, wx + ww / 2 + 3.4, 0.05, 0, wx - ww / 2 + 1.2, 0.05, 0], cc = [0.11, 0.15, 0.21, 0.11, 0.15, 0.21, 0, 0, 0, 0, 0, 0];
      gm.setAttribute('position', new THREE.Float32BufferAttribute(v, 3)); gm.setAttribute('color', new THREE.Float32BufferAttribute(cc, 3)); gm.setIndex([0, 1, 2, 0, 2, 3]);
      const sh = new THREE.Mesh(gm, new THREE.MeshBasicMaterial({ vertexColors: true, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide })); sh.position.z = zb + 0.22; sh.renderOrder = 2; G.add(sh); }
    // ceiling lamp: cord, tin shade, glowing bulb (flickers with the room light)
    const lamp = new THREE.Group(); lamp.position.set(RW * 0.2, RH - 0.2, zb + 0.55); G.add(lamp);
    { const cord = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, 1.5, 6), dark); cord.position.y = -0.75; lamp.add(cord); const sh = new THREE.Mesh(new THREE.ConeGeometry(0.34, 0.3, 18, 1, true), M(0x2f3a30, 0.5, 0.6, { side: THREE.DoubleSide })); sh.position.y = -1.62; sh.castShadow = false; lamp.add(sh);
      const cap = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, 0.12, 10), steel); cap.position.y = -1.44; lamp.add(cap);
      bulbMat = new THREE.MeshBasicMaterial({ color: 0xfff1b0 }); const bu = new THREE.Mesh(new THREE.SphereGeometry(0.1, 12, 10), bulbMat); bu.position.y = -1.7; lamp.add(bu);
      bulbGlow = new THREE.Mesh(new THREE.PlaneGeometry(1.7, 1.7), new THREE.MeshBasicMaterial({ map: glowTexS(), transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, opacity: 0.55 })); bulbGlow.position.set(0, -1.7, 0.15); bulbGlow.renderOrder = 3; lamp.add(bulbGlow); }
    // pipes: a horizontal run under the ceiling and a vertical drop on the right, with flanges, a valve and a slow drip
    { const h = P(new THREE.CylinderGeometry(0.085, 0.085, RW, 14), steel, 0, RH - 0.6, zb + 0.14, 0, 0, PI / 2); for (const fx of [-0.42, -0.12, 0.38].map((k) => k * RW)) P(new THREE.CylinderGeometry(0.125, 0.125, 0.07, 14), rust, fx, RH - 0.6, zb + 0.14, 0, 0, PI / 2);
      const vx = RW / 2 - 0.32, vp = P(new THREE.CylinderGeometry(0.07, 0.07, RH - 1.0, 12), steel, vx, (RH - 0.6 + 0.4) / 2, zb + 0.14); P(new THREE.SphereGeometry(0.11, 12, 10), steel, vx, RH - 0.6, zb + 0.14);
      for (const fy of [1.2, 3.4, 5.2]) P(new THREE.CylinderGeometry(0.105, 0.105, 0.06, 12), rust, vx, fy, zb + 0.14);
      const val = new THREE.Group(); val.position.set(vx, 3.0, zb + 0.28); G.add(val); const wh2 = new THREE.Mesh(new THREE.TorusGeometry(0.16, 0.025, 8, 18), M(0x8a2a22, 0.6, 0.3)); val.add(wh2); for (let i = 0; i < 3; i++) { const sp = new THREE.Mesh(new THREE.BoxGeometry(0.32, 0.03, 0.03), M(0x8a2a22, 0.6, 0.3)); sp.rotation.z = i * PI / 3; val.add(sp); } P(new THREE.CylinderGeometry(0.03, 0.03, 0.16, 8), steel, vx, 3.0, zb + 0.2, PI / 2, 0, 0);
      var drip = new THREE.Mesh(new THREE.SphereGeometry(0.035, 8, 6), new THREE.MeshBasicMaterial({ color: 0x8aa890 })); drip.position.set(-0.6 * RW * 0.5, RH - 0.7, zb + 0.2); G.add(drip); }
    // crate stack, a lone crate and a rusty barrel
    const crate = (s, x, y, z, ry) => { const c = new THREE.Group(); c.position.set(x, y, z); c.rotation.y = ry || 0; G.add(c); const add = (geo, mat, px, py, pz) => { const m = new THREE.Mesh(geo, mat); m.position.set(px, py, pz); m.castShadow = true; m.receiveShadow = true; c.add(m); }; add(roundBox(s, s, s, 0.03, 2), wood, 0, 0, 0);
      for (const sy of [-1, 1]) add(roundBox(s + 0.04, 0.09, s + 0.04, 0.02, 2), woodD, 0, sy * (s / 2 - 0.05), 0); for (const sx of [-1, 1]) for (const sz of [-1, 1]) add(roundBox(0.09, s + 0.04, 0.09, 0.02, 2), woodD, sx * (s / 2 - 0.02), 0, sz * (s / 2 - 0.02)); const dg = new THREE.Mesh(new THREE.BoxGeometry(0.07, s * 1.2, 0.03), woodD); dg.rotation.z = 0.78; dg.position.z = s / 2 + 0.005; c.add(dg); return c; };
    // (crates and barrel removed: they covered the character)
    // wall shelf with a skull, a jar and bottles
    { const sx = RW / 2 - 1.5, sy = 4.35, sz = zb + 0.22; P(roundBox(1.5, 0.08, 0.42, 0.025, 2), wood, sx, sy, sz); for (const k of [-0.5, 0.5]) P(roundBox(0.07, 0.3, 0.3, 0.02, 2), woodD, sx + k, sy - 0.18, sz - 0.04);
      P(new THREE.SphereGeometry(0.17, 14, 12), M(0xdcd5b4, 0.7), sx - 0.38, sy + 0.2, sz); P(roundBox(0.18, 0.08, 0.14, 0.03, 2), M(0xcfc8a8, 0.7), sx - 0.38, sy + 0.07, sz + 0.05); for (const e of [-1, 1]) P(new THREE.SphereGeometry(0.04, 8, 6), dark, sx - 0.38 + e * 0.06, sy + 0.21, sz + 0.14, 0, 0, 0, true);
      P(new THREE.CylinderGeometry(0.13, 0.13, 0.34, 14), M(0xa8d8c0, 0.1, 0, { transparent: true, opacity: 0.5 }), sx + 0.1, sy + 0.21, sz, 0, 0, 0, true); P(new THREE.CylinderGeometry(0.105, 0.105, 0.2, 14), new THREE.MeshBasicMaterial({ color: 0x6aff4a }), sx + 0.1, sy + 0.14, sz, 0, 0, 0, true);
      for (const [k, c, hh] of [[0.45, 0x7a4a1a, 0.34], [0.62, 0x2a5a2a, 0.26]]) { P(new THREE.CylinderGeometry(0.06, 0.07, hh, 10), M(c, 0.2, 0, { transparent: true, opacity: 0.85 }), sx + k, sy + hh / 2 + 0.04, sz, 0, 0, 0, true); P(new THREE.CylinderGeometry(0.025, 0.03, 0.12, 8), M(c, 0.3), sx + k, sy + hh + 0.1, sz, 0, 0, 0, true); } }
    // hanging chain with hook, sways a little
    const chain = new THREE.Group(); chain.position.set(RW * 0.36, RH - 0.25, zb + 0.5); G.add(chain);
    for (let i = 0; i < 9; i++) { const l = new THREE.Mesh(new THREE.TorusGeometry(0.06, 0.016, 6, 12), steel); l.scale.y = 1.5; l.position.y = -0.12 - i * 0.14; l.rotation.y = i % 2 ? 0 : PI / 2; l.castShadow = true; chain.add(l); }
    { const hk = new THREE.Mesh(new THREE.TorusGeometry(0.11, 0.03, 8, 14, 4.4), steel); hk.position.y = -1.5; hk.rotation.z = 0.6; hk.castShadow = true; chain.add(hk); }
    // cobweb in the top-right corner, rubble and bones on the floor
    { const wm = new THREE.Mesh(new THREE.PlaneGeometry(1.1, 1.1), new THREE.MeshBasicMaterial({ map: webTexS(), transparent: true, opacity: 0.7, depthWrite: false, side: THREE.DoubleSide })); wm.rotation.z = PI; wm.position.set(RW / 2 - 0.55, RH - 0.55, zb + 0.04); G.add(wm); const wl = wm.clone(); wl.rotation.z = -PI / 2; wl.scale.set(0.8, 0.8, 1); wl.position.set(-RW / 2 + 0.45, RH - 0.45, zb + 0.04); G.add(wl); }
    { let sd = 5; const r = () => { sd = (sd * 16807) % 2147483647; return sd / 2147483647; };
      for (let i = 0; i < 14; i++) { const x = (r() - 0.5) * RW * 0.9, big = r() * 0.16 + 0.05; P(new THREE.IcosahedronGeometry(big, 0), M(i % 3 ? 0x5a574e : 0x7a6f5a, 0.95, 0, { flatShading: true }), x, big * 0.55, zb + 0.15 + r() * 0.5, r() * 3, r() * 3, r() * 3); }
      for (let i = 0; i < 4; i++) { const x = (r() - 0.5) * RW * 0.7, z = zb + 0.7 + r() * 0.3, a = (r() - 0.5) * 0.8; P(new THREE.CylinderGeometry(0.025, 0.025, 0.3, 6), M(0xe6dfc4, 0.7), x, 0.03, z, 0, a, PI / 2, true); for (const e of [-1, 1]) P(new THREE.SphereGeometry(0.045, 8, 6), M(0xe6dfc4, 0.7), x + Math.cos(a) * 0.15 * e, 0.03, z - Math.sin(a) * 0.15 * e, 0, 0, 0, true); } }
    let t = 0; addFx((dt) => { if (setG !== G) return false; t += dt; lamp.rotation.z = Math.sin(t * 0.9) * 0.045; chain.rotation.z = Math.sin(t * 0.7 + 1) * 0.06; if (drip) { const k = (t * 0.8) % 1; drip.position.y = RH - 0.7 - k * k * (RH - 0.75); drip.visible = k < 0.97; } return true; });
  }
  function setBulb(level) { if (!bulbMat) return; const k = clamp(level, 0.2, 1); bulbMat.color.setRGB(1 * k, 0.945 * k, 0.69 * k); if (bulbGlow) bulbGlow.material.opacity = 0.55 * k; }

  function initWorld() {
    world = new CANNON.World(); world.gravity.set(0, -cfg().gravity, 0);
    world.broadphase = new CANNON.NaiveBroadphase(); world.solver.iterations = 22; world.solver.tolerance = 0.0005; world.allowSleep = false;
    dollWallContact = new CANNON.ContactMaterial(dollMat, wallMat, { friction: 0.55, restitution: cfg().bounce, contactEquationStiffness: 2e7, contactEquationRelaxation: 3, frictionEquationStiffness: 1e7 });
    dollDollContact = new CANNON.ContactMaterial(dollMat, dollMat, { friction: 0.25, restitution: 0.05, contactEquationStiffness: 1e7, contactEquationRelaxation: 3 });
    world.addContactMaterial(dollWallContact); world.addContactMaterial(dollDollContact);
  }

  let hemi = null;
  function zombieUI() {
    const st = document.createElement('style'); st.textContent = `html,body{background:#10130d!important}#panel{background:linear-gradient(#34382d,#14170f)!important;border-top:calc(var(--u)*1.2) solid #07090a!important}.cell{background:linear-gradient(#5c6450,#343a2d)!important;border-color:#0b0d08!important}.cell i{color:#d9e4c2!important}.cell.locked{background:linear-gradient(#3a3d33,#22251d)!important}.cell.locked i{color:#9aa08a!important}.cell.on{background:linear-gradient(#d8f09a,#8fc23c)!important;border-color:#f2ffd0!important;box-shadow:0 0 0 calc(var(--u)*.9) #6bb01f,0 0 calc(var(--u)*4) #9be03a!important}.cell.on i{color:#1c2a08!important}#loader{background:radial-gradient(circle at 50% 40%,#2c3a22,#151b10 70%,#080b06)!important}#vig{position:absolute;left:0;right:0;top:0;bottom:calc(var(--u)*46);pointer-events:none;background:radial-gradient(ellipse at 50% 48%,rgba(0,0,0,0) 45%,rgba(4,10,2,.55) 78%,rgba(0,0,0,.9) 100%),radial-gradient(circle at 0 100%,rgba(120,190,70,.22),rgba(0,0,0,0) 38%),radial-gradient(circle at 100% 100%,rgba(120,190,70,.18),rgba(0,0,0,0) 34%);box-shadow:inset 0 0 calc(var(--u)*9) calc(var(--u)*2) rgba(0,0,0,.85)}#vig svg{position:absolute;left:0;top:0;width:100%;height:100%}`;
    document.head.appendChild(st);
    const ui = document.getElementById('ui'), pan = document.getElementById('panel'); if (!ui || document.getElementById('vig')) return;
    const v = document.createElement('div'); v.id = 'vig';
    // barbed wire strung along the top edge and down both sides
    let w = '<svg viewBox="0 0 360 640" preserveAspectRatio="none"><g stroke="#6b6f66" stroke-width="1.4" fill="none" opacity=".85"><path d="M0 8 Q90 20 180 8 T360 10"/><path d="M0 10 Q90 -2 180 12 T360 8"/>';
    for (let i = 0; i < 12; i++) { const x = 14 + i * 30, y = 11 + (i % 2 ? 2 : -1); w += '<path d="M' + (x - 4) + ' ' + (y - 4) + 'L' + (x + 4) + ' ' + (y + 4) + 'M' + (x + 4) + ' ' + (y - 4) + 'L' + (x - 4) + ' ' + (y + 4) + '"/>'; }
    w += '</g></svg>'; v.innerHTML = w; ui.insertBefore(v, ui.firstChild);
  }
  // procedural studio environment (soft boxes on a dark green dome) baked once with PMREM: gives metal and glossy props something to reflect
  function buildEnv() {
    try {
      const es = new THREE.Scene(), dome = new THREE.Mesh(new THREE.SphereGeometry(30, 24, 16), new THREE.MeshBasicMaterial({ side: THREE.BackSide, vertexColors: true })), pa = dome.geometry.attributes.position, cols = new Float32Array(pa.count * 3), top = new THREE.Color(0x56685a), bot = new THREE.Color(0x0c110b), c = new THREE.Color();
      for (let i = 0; i < pa.count; i++) { c.copy(bot).lerp(top, clamp((pa.getY(i) / 30 + 0.55) / 1.3, 0, 1)); cols[i * 3] = c.r; cols[i * 3 + 1] = c.g; cols[i * 3 + 2] = c.b; }
      dome.geometry.setAttribute('color', new THREE.BufferAttribute(cols, 3)); es.add(dome);
      const box = (w, h, col, x, y, z, rx, ry) => { const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ color: new THREE.Color(col).multiplyScalar(5), side: THREE.DoubleSide })); m.position.set(x, y, z); m.rotation.set(rx || 0, ry || 0, 0); es.add(m); };
      box(14, 6, 0xffffff, 0, 16, 8, PI / 2.4, 0); box(3, 16, 0xcfe8ff, -14, 3, 6, 0, PI / 2.4); box(3, 12, 0xffd6a0, 15, 2, 5, 0, -PI / 2.4); box(10, 2, 0xbfffd8, 0, -2, 14, 0, 0); box(12, 3, 0x9affc8, 0, 6, -16, 0, 0);
      const pm = new THREE.PMREMGenerator(renderer); pm.compileCubemapShader && pm.compileCubemapShader(); const rt = pm.fromScene(es, 0.04); scene.environment = rt.texture; pm.dispose();
    } catch (e) { try { console.warn('env map unavailable', e); } catch (x) {} }
  }
  function initScene() {
    zombieUI();
    host = document.getElementById('gl');
    qTier = guessTier(); autoQ = new AutoQuality(qTier);
    renderer = new THREE.WebGLRenderer({ antialias: qTier >= 2, powerPreference: 'high-performance', precision: qTier === 0 ? 'mediump' : 'highp' });
    renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap; renderer.setClearColor(0x10130d);
    renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 0.92;
    host.appendChild(renderer.domElement);
    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(22, 9 / 16, 0.5, 160);
    hemi = new THREE.HemisphereLight(0xcfe6bd, 0x30332a, 0.78); scene.add(hemi);
    sun = new THREE.DirectionalLight(0xe6f0d8, 0.5); sun.position.set(2, 9, 12); sun.castShadow = true;
    sun.shadow.mapSize.set(1024, 1024); const sc = sun.shadow.camera; sc.left = -5; sc.right = 5; sc.top = 6; sc.bottom = -6; sc.near = 1; sc.far = 30; sun.shadow.bias = -0.0008;
    scene.add(sun);
    // flickering overhead bulb: now and then the light stutters
    setInterval(() => { if (!hemi) return; const r = Math.random(); hemi.intensity = r < 0.06 ? 0.4 : r < 0.12 ? 0.62 : 0.78; sun.intensity = r < 0.06 ? 0.3 : 0.5; setBulb(r < 0.06 ? 0.35 : r < 0.12 ? 0.65 : 1); }, 130);
    // cool back-lights: they catch the bevelled edges so every prop and the zombie get a clean rim against the dark room
    const rimA = new THREE.DirectionalLight(0x8affd0, 0.5); rimA.position.set(-5, 4, -7); scene.add(rimA); const rimB = new THREE.DirectionalLight(0xffb070, 0.3); rimB.position.set(6, 3, -6); scene.add(rimB);
    buildEnv();
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
  /* ---- zombie look: sickly green skin, torn office clothes, exposed ribs and bone, glowing mismatched eyes ---- */
  const ZC = { skin: 0x9db87a, skinD: 0x7f9c60, skinDD: 0x587345, bone: 0xece4c8, blood: 0x7a1014, bloodD: 0x4a0a0e, flesh: 0x5e2a2e, tooth: 0xd9d3a4, tooth2: 0xbdb583, gum: 0x4a1d20, hair: 0x2e2a22, shirt: 0x5d7090, shirtD: 0x3f4d66, shirtL: 0x7388a8, tie: 0x8a2330, pants: 0x4e4239, pantsD: 0x362d26, shoe: 0x2b2622, sole: 0x4d4239, belt: 0x1c1815, buckle: 0xc9b44a, nail: 0xcdbf82, dark: 0x14170f, tongue: 0x9a4a5e };
  const COL = { skin: ZC.skin, shirt: ZC.shirt, pants: ZC.pants, shoe: ZC.shoe };
  const UG = { s: new THREE.SphereGeometry(1, 10, 8), b: new THREE.BoxGeometry(1, 1, 1), c: new THREE.CylinderGeometry(1, 1, 1, 8), k: new THREE.ConeGeometry(1, 1, 8) };
  const Z3 = new THREE.Vector3(0, 0, 1), Y3 = new THREE.Vector3(0, 1, 0);
  const qTo = (axis, n) => new THREE.Quaternion().setFromUnitVectors(axis, n.clone().normalize());
  const qRot = (ax, a) => new THREE.Quaternion().setFromAxisAngle(ax, a);
  let zseed = 7; const zr = () => { zseed = (zseed * 16807) % 2147483647; return zseed / 2147483647; };
  // one item = a unit shape (s sphere, b box, c cylinder, k cone) placed in the part's frame; everything is merged into one vertex-coloured mesh
  function zi(g, p, s, col, q, rot) { return { g, p, s, col, q: q || (rot ? new THREE.Quaternion().setFromEuler(new THREE.Euler(rot[0] || 0, rot[1] || 0, rot[2] || 0)) : null) }; }
  // flattened patch lying on a sphere of radius R: n = direction from the centre, ang = spin about it
  function zsurf(R, n, ang, off, s, col, push) {
    const nn = new THREE.Vector3(n[0], n[1], n[2]).normalize(), q = qTo(Z3, nn).multiply(qRot(Z3, ang || 0));
    const p = nn.clone().multiplyScalar(R * (push == null ? 0.97 : push)).add(new THREE.Vector3(off ? off[0] * R : 0, off ? off[1] * R : 0, off ? off[2] * R : 0).applyQuaternion(q));
    return zi('s', [p.x, p.y, p.z], [s[0] * R, s[1] * R, s[2] * R], col, q);
  }
  function zmerge(items, S) {
    const pos = [], nor = [], colr = [], idx = [], m = new THREE.Matrix4(), nm = new THREE.Matrix3(), c = new THREE.Color(), v = new THREE.Vector3(), one = new THREE.Quaternion();
    let off = 0;
    for (const it of items) {
      const g = UG[it.g], P = g.attributes.position, N = g.attributes.normal;
      m.compose(new THREE.Vector3(it.p[0] * S, it.p[1] * S, it.p[2] * S), it.q || one, new THREE.Vector3(it.s[0] * S, it.s[1] * S, it.s[2] * S)); nm.getNormalMatrix(m); c.setHex(it.col);
      for (let i = 0; i < P.count; i++) { v.fromBufferAttribute(P, i).applyMatrix4(m); pos.push(v.x, v.y, v.z); v.fromBufferAttribute(N, i).applyMatrix3(nm).normalize(); nor.push(v.x, v.y, v.z); colr.push(c.r, c.g, c.b); }
      if (g.index) for (let i = 0; i < g.index.count; i++) idx.push(g.index.getX(i) + off); else for (let i = 0; i < P.count; i++) idx.push(i + off);
      off += P.count;
    }
    const geo = new THREE.BufferGeometry(); geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); geo.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3)); geo.setAttribute('color', new THREE.Float32BufferAttribute(colr, 3)); geo.setIndex(idx);
    return new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: 0xffffff, vertexColors: true, roughness: 0.7, metalness: 0, envMapIntensity: 0.16 }));
  }
  // rotated strip helper: a torn cloth tatter hanging around a limb
  function ztat(list, r, y, n, w, h, col, spread) {
    for (let k = 0; k < n; k++) { const a = (k / n) * 6.2832 + (spread || 0), hh = h * (0.7 + zr() * 0.6); list.push(zi('b', [Math.sin(a) * r, y - hh / 2, Math.cos(a) * r], [w, hh, 0.024], col, null, [0, a, (zr() - 0.5) * 0.35])); }
  }
  function zbone(list, n, p, len) { // a broken bone sticking out of a wound at p along direction n
    const nn = new THREE.Vector3(n[0], n[1], n[2]).normalize(), q = qTo(Y3, nn), q2 = qTo(Z3, nn);
    list.push(zi('s', p, [0.07, 0.08, 0.03], ZC.blood, q2)); list.push(zi('s', p, [0.045, 0.055, 0.04], ZC.flesh, q2));
    const c = new THREE.Vector3(p[0], p[1], p[2]).addScaledVector(nn, len / 2);
    list.push(zi('c', [c.x, c.y, c.z], [0.02, len, 0.02], ZC.bone, q));
    const t = new THREE.Vector3(p[0], p[1], p[2]).addScaledVector(nn, len);
    list.push(zi('s', [t.x, t.y, t.z], [0.032, 0.032, 0.032], ZC.bone)); list.push(zi('s', [t.x + nn.y * 0.02, t.y - nn.x * 0.02, t.z], [0.022, 0.022, 0.022], ZC.bone));
  }
  function zombieDeco(name, S) {
    const L = [];
    if (name === 'pelvis') {
      L.push(zi('b', [0, 0.1, 0], [0.63, 0.05, 0.37], ZC.belt)); L.push(zi('b', [0, 0.1, 0.185], [0.085, 0.06, 0.02], ZC.buckle)); L.push(zi('b', [0, 0.1, 0.197], [0.045, 0.03, 0.01], ZC.belt));
      L.push(zi('s', [-0.2, -0.02, 0.165], [0.09, 0.1, 0.02], ZC.bloodD, qTo(Z3, new THREE.Vector3(-0.2, 0, 1)))); L.push(zi('s', [-0.2, -0.02, 0.17], [0.065, 0.075, 0.02], ZC.skinD, qTo(Z3, new THREE.Vector3(-0.2, 0, 1))));
      ztat(L, 0.17, -0.12, 0, 0, 0, 0);
      for (let i = 0; i < 5; i++) L.push(zi('b', [-0.24 + i * 0.12, -0.17, 0.16], [0.08, 0.07 + zr() * 0.05, 0.03], ZC.pants, null, [0, 0, (zr() - 0.5) * 0.4]));
    } else if (name === 'chest') {
      L.push(zi('c', [0, 0.38, -0.01], [0.115, 0.11, 0.115], ZC.skinD)); L.push(zi('c', [0, 0.35, 0], [0.2, 0.045, 0.17], ZC.shirtL)); L.push(zi('c', [0, 0.325, 0], [0.215, 0.03, 0.185], ZC.shirtD));
      for (const s of [-1, 1]) { L.push(zi('s', [s * 0.27, 0.28, 0], [0.17, 0.09, 0.17], ZC.shirt, null, [0, 0, -s * 0.35])); L.push(zi('s', [s * 0.345, 0.2, 0], [0.09, 0.14, 0.15], ZC.shirtD)); }
      for (let i = 0; i < 7; i++) { const h = 0.07 + zr() * 0.1; L.push(zi('b', [-0.3 + i * 0.1, -0.3 - h / 2 + 0.02, 0.17], [0.085, h, 0.03], i % 2 ? ZC.shirtD : ZC.shirt, null, [0, 0, (zr() - 0.5) * 0.3])); L.push(zi('b', [-0.3 + i * 0.1, -0.3 - h / 2 + 0.02, -0.17], [0.085, h, 0.03], i % 2 ? ZC.shirt : ZC.shirtD, null, [0, 0, (zr() - 0.5) * 0.3])); }
      // torn open: exposed ribcage on the right side of the chest
      L.push(zi('b', [0.16, 0.0, 0.192], [0.24, 0.32, 0.02], ZC.flesh));
      for (let k = 0; k < 4; k++) { L.push(zi('b', [0.16, 0.1 - k * 0.075, 0.206], [0.21, 0.03, 0.036], ZC.bone)); L.push(zi('s', [0.265, 0.1 - k * 0.075, 0.206], [0.022, 0.022, 0.022], ZC.bone)); L.push(zi('s', [0.055, 0.1 - k * 0.075, 0.206], [0.022, 0.022, 0.022], ZC.bone)); }
      L.push(zi('b', [0.16, 0.0, 0.2], [0.025, 0.3, 0.02], ZC.tooth2));
      L.push(zi('b', [0.14, 0.18, 0.2], [0.09, 0.07, 0.03], ZC.shirt, null, [0, 0, 0.55])); L.push(zi('b', [0.24, 0.17, 0.2], [0.08, 0.07, 0.03], ZC.shirtD, null, [0, 0, -0.5]));
      L.push(zi('b', [0.12, -0.18, 0.2], [0.09, 0.07, 0.03], ZC.shirtD, null, [0, 0, -0.5])); L.push(zi('b', [0.25, -0.17, 0.2], [0.08, 0.08, 0.03], ZC.shirt, null, [0, 0, 0.6]));
      L.push(zi('b', [0.04, 0.0, 0.2], [0.05, 0.1, 0.03], ZC.shirt, null, [0, 0, 0.3])); L.push(zi('b', [0.29, 0.02, 0.2], [0.05, 0.1, 0.03], ZC.shirtD, null, [0, 0, -0.3]));
      // blood stains and a torn necktie
      L.push(zi('b', [-0.22, 0.1, 0.193], [0.11, 0.09, 0.02], ZC.bloodD, null, [0, 0, 0.3])); L.push(zi('b', [-0.14, -0.1, 0.193], [0.08, 0.12, 0.02], ZC.blood, null, [0, 0, -0.2])); L.push(zi('b', [-0.24, -0.15, 0.193], [0.05, 0.05, 0.02], ZC.bloodD));
      L.push(zi('b', [-0.1, 0.26, 0.2], [0.075, 0.06, 0.04], ZC.tie)); L.push(zi('b', [-0.09, 0.1, 0.198], [0.08, 0.27, 0.025], ZC.tie, null, [0, 0, 0.07])); L.push(zi('b', [-0.085, -0.04, 0.2], [0.045, 0.06, 0.02], ZC.shirtD, null, [0, 0, 0.5]));
      L.push(zi('b', [-0.14, 0.29, 0.185], [0.11, 0.05, 0.04], ZC.shirtL, null, [0, 0, 0.5])); L.push(zi('b', [0.04, 0.29, 0.185], [0.11, 0.05, 0.04], ZC.shirtL, null, [0, 0, -0.5]));
      L.push(zi('b', [-0.1, 0.12, -0.192], [0.2, 0.24, 0.02], ZC.skinD)); L.push(zi('b', [-0.1, 0.12, -0.185], [0.25, 0.29, 0.016], ZC.bloodD));
    } else if (name === 'uarmL' || name === 'uarmR') {
      ztat(L, 0.1, -0.2, 5, 0.055, 0.1, ZC.shirt, name === 'uarmL' ? 0.2 : 0.7);
      L.push(zi('s', [0, 0.12, 0.085], [0.05, 0.07, 0.02], ZC.bloodD)); if (name === 'uarmR') L.push(zi('b', [0.0, -0.05, 0.1], [0.07, 0.05, 0.02], ZC.skinD, null, [0, 0, 0.6]));
    } else if (name === 'farmL' || name === 'farmR') {
      ztat(L, 0.095, 0.24, 4, 0.05, 0.1, ZC.shirtD, name === 'farmL' ? 0.5 : 0.1);
      L.push(zi('s', [0, 0.02, 0.082], [0.05, 0.07, 0.02], ZC.skinDD)); for (let i = 0; i < 3; i++) L.push(zi('b', [-0.02 + i * 0.025, -0.08, 0.087], [0.012, 0.09, 0.01], ZC.bloodD, null, [0, 0, 0.5]));
      if (name === 'farmR') zbone(L, [0.8, 0, 0.6], [0.07, -0.07, 0.05], 0.15);
    } else if (name === 'handL' || name === 'handR') {
      for (let i = 0; i < 4; i++) L.push(zi('k', [-0.065 + i * 0.043, -0.15, 0.05], [0.02, 0.11, 0.02], ZC.nail, null, [Math.PI, 0, 0]));
      L.push(zi('k', [name === 'handL' ? 0.1 : -0.1, -0.06, 0.04], [0.02, 0.09, 0.02], ZC.nail, null, [Math.PI, 0, name === 'handL' ? -0.9 : 0.9])); L.push(zi('s', [0, 0.04, 0.09], [0.05, 0.04, 0.02], ZC.skinDD));
    } else if (name === 'thighL') {
      L.push(zi('s', [0.03, 0.05, 0.11], [0.09, 0.11, 0.015], ZC.bloodD)); L.push(zi('s', [0.03, 0.05, 0.116], [0.065, 0.085, 0.015], ZC.skinD)); L.push(zi('b', [-0.04, -0.12, 0.118], [0.06, 0.1, 0.012], ZC.pantsD));
    } else if (name === 'thighR') {
      L.push(zi('b', [-0.03, -0.08, 0.118], [0.08, 0.12, 0.012], ZC.bloodD, null, [0, 0, 0.3])); L.push(zi('s', [0.04, 0.12, 0.11], [0.05, 0.06, 0.015], ZC.skinDD));
    } else if (name === 'shinL') {
      L.push(zi('c', [0, -0.15, 0], [0.104, 0.22, 0.104], ZC.skin)); ztat(L, 0.1, -0.05, 6, 0.05, 0.09, ZC.pants, 0.3); L.push(zi('s', [0.04, -0.1, 0.09], [0.04, 0.06, 0.015], ZC.skinDD)); L.push(zi('b', [0, -0.18, 0.1], [0.012, 0.1, 0.01], ZC.bloodD, null, [0, 0, 0.4]));
    } else if (name === 'shinR') {
      L.push(zi('b', [0.03, 0.1, 0.1], [0.07, 0.1, 0.012], ZC.pantsD)); zbone(L, [0.2, 0, 1], [-0.02, -0.04, 0.085], 0.14); ztat(L, 0.1, -0.2, 6, 0.045, 0.07, ZC.pants, 0.6);
    } else if (name === 'footL') {
      for (let i = 0; i < 5; i++) L.push(zi('s', [-0.08 + i * 0.04, -0.015, 0.2], [0.03, 0.03, 0.04], i === 2 ? ZC.skinD : ZC.skin)); L.push(zi('s', [0, 0.03, 0.0], [0.06, 0.03, 0.08], ZC.skinDD));
    } else if (name === 'footR') {
      L.push(zi('b', [0, -0.07, 0.01], [0.225, 0.035, 0.41], ZC.sole)); L.push(zi('s', [0.04, 0.0, 0.205], [0.045, 0.04, 0.045], ZC.skin)); L.push(zi('s', [-0.03, -0.005, 0.21], [0.04, 0.035, 0.04], ZC.skinD)); L.push(zi('b', [0, 0.065, -0.05], [0.2, 0.025, 0.06], ZC.pantsD));
    } else if (name === 'head') {
      const R = 0.4;
      for (const s of [-1, 1]) { L.push(zi('s', [s * 0.4 * R, 0.2 * R, 0.8 * R], [0.31 * R, 0.34 * R, 0.17 * R], ZC.dark)); }
      for (const s of [-1, 1]) L.push(zi('s', [s * 0.07 * R, -0.1 * R, 0.985 * R], [0.045 * R, 0.06 * R, 0.03 * R], ZC.dark));
      L.push(zsurf(R, [-0.62, -0.28, 0.72], 0.3, null, [0.2, 0.15, 0.05], ZC.skinD)); L.push(zsurf(R, [0.6, -0.3, 0.72], -0.3, null, [0.2, 0.15, 0.05], ZC.skinDD)); L.push(zsurf(R, [0.25, 0.62, 0.72], 0.4, null, [0.17, 0.1, 0.04], ZC.skinDD)); L.push(zsurf(R, [0.0, -0.8, 0.5], 0.0, null, [0.2, 0.1, 0.05], ZC.skinD));
      L.push(zi('s', [0, -0.03 * R, 0.97 * R], [0.13 * R, 0.19 * R, 0.16 * R], ZC.skinD, qRot(new THREE.Vector3(1, 0, 0), -0.35))); L.push(zi('s', [0.02 * R, -0.17 * R, 1.03 * R], [0.1 * R, 0.07 * R, 0.07 * R], ZC.skinDD));
      L.push(zi('s', [0, -0.8 * R, 0.55 * R], [0.34 * R, 0.24 * R, 0.3 * R], ZC.skin)); for (const s of [-1, 1]) L.push(zi('s', [s * 0.52 * R, -0.18 * R, 0.78 * R], [0.2 * R, 0.14 * R, 0.14 * R], ZC.skinD));
      L.push(zi('s', [0, 0.46 * R, 0.86 * R], [0.62 * R, 0.09 * R, 0.14 * R], ZC.skinD));
      // hair cap and tufts at the back, bald in front
      L.push(zi('s', [0, 0.1 * R, -0.18 * R], [1.04 * R, 1.0 * R, 1.0 * R], ZC.hair));
      for (let i = 0; i < 14; i++) { const th = zr() * 6.28, ph = 0.25 + zr() * 1.0, d = new THREE.Vector3(Math.cos(ph) * Math.sin(th), Math.sin(ph), Math.cos(ph) * Math.cos(th) - 0.3); if (d.z > 0.35) continue; d.normalize(); const len = (0.16 + zr() * 0.2) * R * 1.4, pp = d.clone().multiplyScalar(R * 1.0 + len * 0.35); L.push(zi('k', [pp.x, pp.y, pp.z], [0.075 * R, len, 0.075 * R], ZC.hair, qTo(Y3, d.clone().add(new THREE.Vector3(zr() * 0.4 - 0.2, zr() * 0.2, zr() * 0.4 - 0.2))))); }
      // exposed skull patch on the right side, torn ear and the stitched scar on the left
      L.push(zsurf(R, [0.9, 0.55, 0.0], 0.4, null, [0.34, 0.3, 0.1], ZC.bloodD, 0.93)); L.push(zsurf(R, [0.9, 0.55, 0.0], 0.4, null, [0.28, 0.24, 0.12], ZC.bone, 0.94)); L.push(zsurf(R, [0.9, 0.6, 0.0], 0.9, [0.02, 0.05, 0], [0.2, 0.014, 0.12], ZC.flesh, 0.99)); L.push(zsurf(R, [0.9, 0.5, 0.0], 0.2, [-0.03, -0.05, 0], [0.12, 0.014, 0.12], ZC.flesh, 0.99));
      L.push(zi('s', [1.0 * R, 0.0, -0.05 * R], [0.12 * R, 0.21 * R, 0.17 * R], ZC.skin)); L.push(zi('s', [-0.97 * R, 0.0, -0.05 * R], [0.08 * R, 0.13 * R, 0.11 * R], ZC.skinD));
      const nS = [-0.55, 0.45, 0.7]; L.push(zsurf(R, nS, 0.5, null, [0.5, 0.035, 0.03], ZC.dark, 1.0)); for (let k = -2; k <= 2; k++) L.push(zsurf(R, nS, 0.5, [k * 0.17, 0, 0], [0.028, 0.14, 0.03], ZC.dark, 1.0));
    }
    return L;
  }

  const mats = {}; const matFor = (c) => mats[c] || (mats[c] = new THREE.MeshStandardMaterial({ color: c, roughness: 0.72, metalness: 0, envMapIntensity: 0.16 }));

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

  // wounds (blood, flesh, bone) are hidden at the start and show up part by part as the zombie takes damage (value = share of health below which the part is wounded)
  const WOUND_COL = new Set([ZC.bone, ZC.blood, ZC.bloodD, ZC.flesh, ZC.tooth2]);
  const WOUND_AT = { chest: 0.92, uarmR: 0.86, pelvis: 0.8, thighL: 0.74, uarmL: 0.7, head: 0.62, farmL: 0.58, thighR: 0.52, farmR: 0.45, shinL: 0.4, shinR: 0.32, footL: 0.25, footR: 0.2 };
  function updateWounds() { if (!doll) return; const r = hp / MAXHP; for (const p of doll.list) p.group.traverse((m) => { if (m.userData.wound != null) m.visible = r < m.userData.wound; }); }
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
      { const dl = zombieDeco(name, S); if (dl.length) {
        const base = dl.filter((i) => !WOUND_COL.has(i.col)), wd = dl.filter((i) => WOUND_COL.has(i.col));
        if (base.length) group.add(zmerge(base, S));
        if (wd.length) { const wm = zmerge(wd, S); wm.userData.wound = WOUND_AT[name] == null ? 0.6 : WOUND_AT[name]; wm.userData.bone = 0; wm.visible = hp / MAXHP < wm.userData.wound; group.add(wm); }
      } }
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
      add('foot' + n, 'box', [0.11, 0.07, 0.2], 0.8, [s * 0.17, 0.07, 0.09], s < 0 ? COL.skin : COL.shoe, { r: 0.06 });
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
    const F = { R, eyes: [], pups: [], brows: [], mouth: null }, M = (c, e) => new THREE.MeshStandardMaterial({ color: c, emissive: e || 0, roughness: 0.55, metalness: 0, envMapIntensity: 0.2 });
    [[-1, 0.2, 0.87, 0.2, 0xe9f06a, 0x8a9a14, 1.0], [1, 0.14, 0.88, 0.15, 0xe6efe0, 0x2a3026, 0.95]].forEach(([s, y, z, r, c, e, k]) => {
      const eye = new THREE.Mesh(new THREE.SphereGeometry(r * R, 14, 10), M(c, e)); eye.position.set(s * R * 0.4, y * R, z * R); eye.userData.b = [1, 1.1, 0.6]; eye.scale.set(1, 1.1, 0.6); eye.userData.bone = 1; group.add(eye); F.eyes.push(eye);
      const p = new THREE.Mesh(new THREE.SphereGeometry(R * (s < 0 ? 0.065 : 0.045), 8, 6), M(0x0d0f0a)); p.position.set(s * R * 0.4 + s * R * 0.015, y * R - R * 0.01, z * R + r * R * 0.5); p.userData.bone = 1; group.add(p); F.pups.push(p);
      const b = new THREE.Mesh(new THREE.BoxGeometry(R * 0.42, R * 0.09, R * 0.07), M(0x4a5f36)); b.position.set(s * R * 0.42, R * 0.52, R * 0.82); b.rotation.z = -s * 0.22; b.userData.s = s; group.add(b); F.brows.push(b);
    });
    const mg = new THREE.Group(), L = [];
    L.push(zi('s', [0, 0, 0], [0.37 * R, 0.17 * R, 0.12 * R], ZC.gum)); L.push(zi('s', [0, 0, -0.01 * R], [0.34 * R, 0.14 * R, 0.12 * R], ZC.dark));
    for (let i = -3; i <= 2; i++) L.push(zi('b', [(i + 0.5) * 0.1 * R, 0.075 * R, 0.1 * R], [0.088 * R, (0.1 + (i === 0 ? 0.04 : 0)) * R, 0.05 * R], i === -1 ? ZC.tooth2 : ZC.tooth));
    for (let i = -2; i <= 2; i++) if (i !== 1) L.push(zi('b', [i * 0.095 * R, -0.075 * R, 0.1 * R], [0.08 * R, (0.07 + (i % 2 ? 0.04 : 0)) * R, 0.05 * R], i === 0 ? ZC.tooth2 : ZC.tooth));
    L.push(zi('s', [0.09 * R, -0.15 * R, 0.1 * R], [0.1 * R, 0.07 * R, 0.05 * R], ZC.tongue));
    const mm = zmerge(L, 1); mm.userData.deco = 1; mg.add(mm); mg.position.set(0, -0.4 * R, 0.86 * R); group.add(mg); F.mouth = mg;
    group.userData.face = F;
  }

  function removeDoll() {
    if (!doll) return;
    for (const j of doll.joints) world.removeConstraint(j.c);
    for (const p of doll.list) { world.removeBody(p.body); scene.remove(p.group); p.group.traverse((m) => { if (m.isMesh) { m.geometry.dispose(); const i = hitMeshes.indexOf(m); if (i >= 0) hitMeshes.splice(i, 1); } }); }
    doll = null;
  }
  function resetDoll() {
    release(); clearWays(); removeDoll(); doll = buildDoll(0.03); for (const q of doll.list) buildBones(q);
    standRest = doll.list.map((q) => ({ q, p: q.body.position.clone(), r: q.body.quaternion.clone(), ph: Math.random() * 6 })); standing = mode === 'play'; standT = 0;
    sync();
  }
  /* the zombie only spawns once the loading screen has faded, so the player sees him fall in */
  function introDrop() { if (mode === 'play') resetDoll(); }
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
  function audioInit() { if (AC) { if (AC.state === 'suspended') AC.resume(); return; } try { AC = new (window.AudioContext || window.webkitAudioContext)(); } catch (e) { AC = null; } if (AC) zvLoad(); }
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
    { id: 'hand', name: 'GRAB', asset: 'item_hand', emo: '✋', hint: 'DRAG THE ZOMBIE TO GRAB & FLING IT' },
    { id: 'hammer', name: 'SLEDGE', asset: 'item_hammer', emo: '🔨', hint: 'TAP TO SMASH' },
    { id: 'pistol', name: 'HANDGUN', asset: 'item_pistol', emo: '🔫', hint: 'HOLD TO SHOOT' },
    { id: 'shotgun', name: 'SHOTGUN', asset: 'item_shotgun', emo: '💥', hint: 'TAP TO BLAST' },
    { id: 'dynamite', name: 'DYNAMITE', asset: 'item_dynamite', emo: '🧨', hint: 'TAP TO DROP DYNAMITE' },
    { id: 'rocket', name: 'ROCKET', asset: 'item_rocket', emo: '🚀', hint: 'TAP TO FIRE A ROCKET' },
    { id: 'anvil', name: 'ANVIL', asset: 'item_anvil', emo: '⚓', hint: 'TAP TO DROP AN ANVIL' },
    { id: 'revolver', name: 'SILVER GUN', asset: 'item_revolver', emo: '🔫', hint: 'TAP TO FIRE A SILVER BULLET' },
    { id: 'flame', name: 'BURN IT', asset: 'item_flamethrower', emo: '🔥', hint: 'HOLD TO BURN' },
    { id: 'saw', name: 'BUZZSAW', asset: 'item_saw', emo: '🔄', hint: 'TAP TO THROW A BUZZSAW' },
    { id: 'bat', name: 'NAIL BAT', asset: 'item_bat', emo: '\u26BE', hint: 'TAP TO SWING THE BAT' },
    { id: 'crowbar', name: 'CROWBAR', asset: 'item_crowbar', emo: '\uD83D\uDD27', hint: 'TAP TO HOOK & SLAM HIM' },
    { id: 'shovel', name: 'SHOVEL', asset: 'item_shovel', emo: '\u26CF', hint: 'TAP TO WHACK HIM' },
    { id: 'machete', name: 'MACHETE', asset: 'item_machete', emo: '\uD83D\uDD2A', hint: 'TAP TO CHOP CHOP CHOP' },
    { id: 'axe', name: 'FIRE AXE', asset: 'item_axe', emo: '\uD83E\uDE93', hint: 'TAP TO CHOP' },
    { id: 'katana', name: 'KATANA', asset: 'item_katana', emo: '\uD83D\uDDE1', hint: 'SWIPE TO SLICE' },
    { id: 'grenade', name: 'GRENADE', asset: 'item_grenade', emo: '\uD83D\uDCA3', hint: 'TAP TO THROW A GRENADE' },
    { id: 'mine', name: 'LANDMINE', asset: 'item_landmine', emo: '\uD83D\uDFE2', hint: 'TAP TO PLANT A MINE' },
    { id: 'beartrap', name: 'BEAR TRAP', asset: 'item_beartrap', emo: '\uD83E\uDDB7', hint: 'TAP TO SET A TRAP' },
    { id: 'molotov', name: 'MOLOTOV', asset: 'item_molotov', emo: '\uD83C\uDF7E', hint: 'TAP TO THROW A MOLOTOV' },
    { id: 'holy', name: 'HOLY WATER', asset: 'item_holywater', emo: '\uD83D\uDCA7', hint: 'TAP TO THROW HOLY WATER' },
    { id: 'crossbow', name: 'CROSSBOW', asset: 'item_crossbow', emo: '\uD83C\uDFF9', hint: 'TAP TO NAIL HIM TO THE WALL' },
    { id: 'chainsaw', name: 'CHAINSAW', asset: 'item_chainsaw', emo: '\uD83E\uDE9A', hint: 'HOLD TO SHRED' },
    { id: 'spikepit', name: 'SPIKE PIT', asset: 'item_spikepit', emo: '\uD83D\uDCCC', hint: 'TAP TO RAISE THE SPIKES' },
    { id: 'noose', name: 'NOOSE', asset: 'item_noose', emo: '\uD83E\uDDF5', hint: 'TAP TO HANG HIM' },
    { id: 'hole', name: 'VOID', asset: 'item_blackhole', emo: '🌀', hint: 'TAP TO OPEN A BLACK HOLE' },
    { id: 'acid', name: 'TOXIC ACID', asset: 'item_acid', emo: '\u2623', hint: 'TAP TO POUR ACID' },
    { id: 'zdog', name: 'ZOMBIE DOG', asset: 'item_zdog', emo: '\uD83D\uDC15', hint: 'TAP TO SIC THE DOG' },
    { id: 'barrels', name: 'BARRELS', asset: 'item_barrels', emo: '\uD83D\uDEE2', hint: 'TAP TO DROP EXPLOSIVE BARRELS' },
    { id: 'lightning', name: 'LIGHTNING', asset: 'item_lightning', emo: '\u26C8', hint: 'TAP TO CALL A LIGHTNING STRIKE' },
    { id: 'guillotine', name: 'GUILLOTINE', asset: 'item_guillotine', emo: '\u2702', hint: 'TAP TO DROP THE GUILLOTINE' },
    { id: 'fence', name: 'E-FENCE', asset: 'item_efence', emo: '\u26A1', hint: 'TAP TO DROP A LIVE FENCE' },
    { id: 'brainbait', name: 'BRAIN BAIT', asset: 'item_brainbait', emo: '\uD83E\uDDE0', hint: 'TAP TO LURE THE HORDE' },
    { id: 'mower', name: 'LAWNMOWER', asset: 'item_mower', emo: '\uD83C\uDF31', hint: 'TAP TO RUN HIM OVER' },
    { id: 'grinder', name: 'GRINDER', asset: 'item_grinder', emo: '\u2699', hint: 'TAP TO FEED THE MEAT GRINDER' },
    { id: 'chipper', name: 'WOOD CHIPPER', asset: 'item_chipper', emo: '\u2699', hint: 'TAP TO FEED THE CHIPPER' },
    { id: 'ball', name: 'WRECK BALL', asset: 'item_wreckingball', emo: '\u26AB', hint: 'TAP TO DROP THE WRECKING BALL' },
    { id: 'minigun', name: 'MINIGUN', asset: 'item_minigun', emo: '\uD83D\uDCA5', hint: 'HOLD - IT SPINS UP FAST' },
    { id: 'crusher', name: 'SPIKE CRUSH', asset: 'item_spikecrusher', emo: '\u2B07', hint: 'TAP TO DROP THE SPIKES' },
    { id: 'coffin', name: 'COFFIN DROP', asset: 'item_coffin', emo: '\u26B0', hint: 'TAP TO DROP A COFFIN' },
    { id: 'truck', name: 'GARBAGE TRUCK', asset: 'item_truck', emo: '\uD83D\uDE9B', hint: 'TAP TO RUN HIM OVER' },
    { id: 'graves', name: 'GRAVE HANDS', asset: 'item_graveyard', emo: '\uD83E\uDDDF', hint: 'TAP TO RAISE THE DEAD' },
    { id: 'sniper', name: 'HEADSHOT', asset: 'item_sniper', emo: '\uD83C\uDFAF', hint: 'TAP TO SNIPE - AIM FOR THE HEAD' },
    { id: 'horde', name: 'HORDE', asset: 'item_horde', emo: '\uD83E\uDDDF', hint: 'TAP TO SEND IN THE HORDE' },
    { id: 'burial', name: 'BURIAL', asset: 'item_pit', emo: '\u26B0', hint: 'TAP TO BURY HIM ALIVE' },
    { id: 'skydrop', name: 'SKY DROP', asset: 'item_rooftop', emo: '\u2B07', hint: 'TAP TO LAUNCH & SLAM HIM' },
    { id: 'sunbeam', name: 'SUNLIGHT', asset: 'item_sunbeam', emo: '\u2600', hint: 'TAP TO BURN HIM WITH SUNLIGHT' },
    { id: 'meteor', name: 'APOCALYPSE', asset: 'item_meteor', emo: '\u2604', hint: 'TAP TO CALL A METEOR' },
    { id: 'airstrike', name: 'AIRSTRIKE', asset: 'item_airstrike', emo: '\u2708', hint: 'TAP TO CALL AN AIRSTRIKE' },
    { id: 'nuke', name: 'OUTBREAK', asset: 'item_nuke', emo: '\u2622', hint: 'TAP TO DROP THE OUTBREAK BOMB' }
  ];
  // where the muzzle sits on each 2D gun picture (fractions of its width / height from the centre) and how long it is drawn
  const GUNS = { revolver: { asset: 'item_revolver', L: 1.5, mx: 0.5, my: 0.22 }, sniper: { asset: 'item_sniper', L: 2.4, mx: 0.48, my: 0.06 }, pistol: { asset: 'item_pistol', L: 1.4, mx: 0.49, my: 0.31 }, shotgun: { asset: 'item_shotgun', L: 2.1, mx: 0.5, my: 0.37 }, rocket: { asset: 'item_rocket', L: 2.2, mx: 0.5, my: 0.06 }, taser: { asset: 'item_taser', L: 1.1, mx: 0.5, my: 0.2 }, chainsaw: { asset: 'item_chainsaw', L: 2.3, mx: 0.5, my: -0.25 }, freeze: { asset: 'item_freezeray', L: 1.8, mx: 0.5, my: 0.12 }, crossbow: { asset: 'item_crossbow', L: 2.0, mx: 0.5, my: 0.03 }, minigun: { asset: 'item_minigun', L: 2.4, mx: 0.475, my: -0.057 }, cannon: { asset: 'item_cannon', L: 2.5, mx: 0.475, my: 0.2486, rot: 0.35 }, katana: { asset: 'item_katana', L: 1.9, mx: 0, my: 0 }, flame: { asset: 'item_flamethrower', L: 1.9, mx: 0.5, my: 0.2 } };

  let tool = 'hand', totalDmg = 0, mood = 0, grace = 0, cd = 0, shakeAmp = 0, faceHurt = 0, faceKind = 1;
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
  const FREE = ['hand', 'pistol', 'shotgun', 'bat', 'shovel', 'machete', 'axe', 'molotov', 'holy', 'crossbow', 'chainsaw', 'sniper', 'flame', 'dynamite', 'barrels', 'crowbar', 'zdog', 'mower', 'brainbait', 'noose', 'spikepit', 'fence', 'hammer', 'revolver', 'grenade'];
  const BUY_ORDER = ['anvil', 'rocket', 'saw', 'katana', 'mine', 'beartrap', 'hole', 'acid', 'lightning', 'guillotine', 'grinder', 'chipper', 'ball', 'minigun', 'crusher', 'coffin', 'truck', 'graves', 'horde', 'burial', 'skydrop', 'sunbeam', 'meteor', 'airstrike', 'nuke'];
  { const ord = FREE.concat(BUY_ORDER); TOOLS.sort((x, y) => ord.indexOf(x.id) - ord.indexOf(y.id)); }
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
    endUse(); release(); hold.id = -1; ptr.id = -1; orbitId = -1; orbitLast = null; tool = id;
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
    // 0 normal, 1 shocked yelp (wide eyes, pinprick pupils), 3 wince (eyes squeezed, teeth bared), 2 dead (eyes rolled, jaw slack)
    f.mouth.scale.set(h === 2 ? 1.1 : h === 3 ? 1.15 : h ? 0.85 : 1, h === 2 ? 2.7 : h === 3 ? 2.2 : h ? 1.9 : 1, 1); f.mouth.position.y = -R * (h === 2 ? 0.5 : h === 3 ? 0.45 : h ? 0.43 : 0.4); f.mouth.rotation.z = h === 3 ? 0.08 : 0;
    f.eyes.forEach((e, k) => { const b = e.userData.b; const sx = h === 2 ? 1.0 : h === 3 ? 1.1 : h ? 1.3 : 1, sy = h === 2 ? 0.45 : h === 3 ? 0.18 : h ? 1.35 : 1; e.scale.set(b[0] * sx, b[1] * sy, b[2]); e.rotation.z = h === 2 ? (k ? 0.35 : -0.3) : 0; });
    f.pups.forEach((p, k) => { p.scale.setScalar(h === 1 ? 0.5 : h === 2 ? 0.7 : h === 3 ? 0.4 : 1); p.visible = h !== 3; });
    f.brows.forEach((b) => { b.rotation.z = b.userData.s * (h === 3 ? 0.55 : h === 2 ? -0.5 : h ? 0.3 : -0.22); b.position.y = R * (h === 3 ? 0.4 : h === 2 ? 0.58 : h ? 0.62 : 0.52); });
  }
  /* ---- health, blood, tearing, death, x-ray ---- */
  let standing = false, standT = 0, standRest = null;
  const MAXHP = 700; let hp = MAXHP, dead = false, deadT = 0, kos = 0, slow = 0, onFire = 0, fireAcc = 0, flail = 0, hpShown = -1;
  const stumps = [], NOBLOOD = { burn: 1, shock: 1, hole: 1, bleed: 1, freeze: 1, acid: 1, sting: 1, laser: 1 };
  const SEV = { handL: 28, handR: 28, farmL: 60, farmR: 60, uarmL: 80, uarmR: 80, footL: 45, footR: 45, shinL: 70, shinR: 70, thighL: 85, thighR: 85, head: 170, chest: 360 };
  const SEVMUL = { laser: 2.5, slash: 2.2, saw: 1.9, blast: 2.2, smash: 1.5, crush: 1.7, bullet: 1.15 };
  const LABEL = { handL: 'HAND OFF!', handR: 'HAND OFF!', farmL: 'ARM SNAPPED!', farmR: 'ARM SNAPPED!', uarmL: 'ARM RIPPED OFF!', uarmR: 'ARM RIPPED OFF!', footL: 'FOOT OFF!', footR: 'FOOT OFF!', shinL: 'LEG SNAPPED!', shinR: 'LEG SNAPPED!', thighL: 'LEG TORN OFF!', thighR: 'LEG TORN OFF!', head: 'DECAPITATED!', chest: 'SPLIT IN HALF!' };
  function hpBar() {
    const v = Math.max(0, Math.round(hp)); if (v === hpShown) return; hpShown = v; updateWounds(); const f = document.getElementById('hpf'); if (!f) return;
    f.style.width = (v / MAXHP * 100) + '%'; f.style.background = v < MAXHP * 0.3 ? '#ff3b30' : v < MAXHP * 0.6 ? '#ffb02e' : '#3ddc57';
  }
  function popupT(text, p, color, size) {
    const fx = document.getElementById('fx'); if (!fx || fx.children.length > 22) return; const el = document.createElement('div'), v = V3(p.x, p.y, 0).project(camera), w = host.clientWidth, h = host.clientHeight;
    el.className = 'pop'; el.textContent = text; el.style.left = clamp((v.x * 0.5 + 0.5) * w, 90, w - 90) + 'px'; const nowT = performance.now(); popupT.r = (popupT.r || []).filter((x) => nowT - x < 700); const kk = popupT.r.length; if (kk > 3) return; popupT.r.push(nowT); el.style.top = (clamp((-v.y * 0.5 + 0.5) * h, 80, h - 20) - kk * 50) + 'px'; el.style.fontSize = 'calc(var(--u) * ' + size + ')'; el.style.color = color; el.style.whiteSpace = 'nowrap';
    fx.appendChild(el); if (el.animate) el.animate([{ transform: 'translate(-50%,-50%) scale(.3) rotate(-6deg)', opacity: 0 }, { transform: 'translate(-50%,-90%) scale(1.25) rotate(3deg)', opacity: 1, offset: 0.16 }, { transform: 'translate(-50%,-130%) scale(1) rotate(0)', opacity: 1, offset: 0.7 }, { transform: 'translate(-50%,-190%) scale(1)', opacity: 0 }], { duration: 1300, easing: 'ease-out' }).onfinish = () => el.remove(); else setTimeout(() => el.remove(), 1200);
  }
  /* sounds for the body */
  let owT = 0;
  /* real zombie voice clips (AI generated): decoded once, played with pitch variation; the synth voice below is the fallback */
  const ZV = {}; let zvCur = null, zvBusy = false;
  function zvLoad() {
    if (zvBusy || !AC) return; zvBusy = true;
    for (const id of ['zgroan1', 'zgroan2', 'zgroan3', 'zdeath']) { const u = assetUrl(id); if (!u) continue; try { fetch(u, { mode: 'cors' }).then((r) => r.arrayBuffer()).then((b) => new Promise((res, rej) => { const p = AC.decodeAudioData(b, res, rej); if (p && p.catch) p.catch(rej); })).then((buf) => { ZV[id] = buf; }).catch(() => {}); } catch (e) {} }
  }
  function zvPlay(id, vol, rate) {
    const b = ZV[id]; if (!AC || !b) return false; const t = AC.currentTime;
    if (zvCur) { try { zvCur.g.gain.cancelScheduledValues(t); zvCur.g.gain.setValueAtTime(zvCur.g.gain.value, t); zvCur.g.gain.linearRampToValueAtTime(0.0001, t + 0.12); zvCur.s.stop(t + 0.14); } catch (e) {} }
    const s = AC.createBufferSource(), g = AC.createGain(); s.buffer = b; s.playbackRate.value = rate; g.gain.value = vol; s.connect(g); g.connect(AC.destination); s.start(t); zvCur = { s, g }; return b.duration / rate;
  }
  /* zombie voice: glottal saw -> two formant filters (vowel glide) + raspy breath noise */
  let groanMouth = 0;
  function zvoice(o) {
    if (!AC) return; const t = AC.currentTime + (o.delay || 0), D = o.dur, out = AC.createGain(); out.gain.setValueAtTime(0.0001, t); out.gain.exponentialRampToValueAtTime(o.vol, t + o.atk); out.gain.setValueAtTime(o.vol, t + o.atk + (o.hold || 0)); out.gain.exponentialRampToValueAtTime(0.0001, t + D); out.connect(AC.destination);
    const src = AC.createOscillator(), src2 = AC.createOscillator(), lfo = AC.createOscillator(), lg = AC.createGain(), mix = AC.createGain(), sg = AC.createGain();
    src.type = 'sawtooth'; src2.type = 'square'; src.frequency.setValueAtTime(o.f0 * (o.rise || 0.9), t); src.frequency.linearRampToValueAtTime(o.f0, t + o.atk * 1.5); src.frequency.exponentialRampToValueAtTime(o.f1, t + D);
    src2.frequency.setValueAtTime(o.f0 * 0.5, t); src2.frequency.exponentialRampToValueAtTime(o.f1 * 0.5, t + D); sg.gain.value = 0.35; src2.connect(sg); sg.connect(mix);
    lfo.frequency.value = o.vib || 6; lg.gain.value = o.vibD || 5; lfo.connect(lg); lg.connect(src.frequency); src.connect(mix);
    const fm = [[o.a1, o.b1, 5, 1], [o.a2, o.b2, 6, 0.7], [o.a3 || 2400, (o.b3 || 1900), 4, 0.25]];
    for (const [fa, fb, q, gn] of fm) { const f = AC.createBiquadFilter(), g = AC.createGain(); f.type = 'bandpass'; f.Q.value = q; f.frequency.setValueAtTime(fa, t); f.frequency.exponentialRampToValueAtTime(fb, t + D); g.gain.value = gn; mix.connect(f); f.connect(g); g.connect(out); }
    if (o.gurg) { const am = AC.createOscillator(), ag = AC.createGain(); am.frequency.value = o.gurg; ag.gain.value = 0.45; am.connect(ag); ag.connect(out.gain); am.start(t); am.stop(t + D + 0.1); }
    const ns = AC.createBufferSource(), nf = AC.createBiquadFilter(), ng = AC.createGain(); ns.buffer = noiseBuf(); ns.loop = true; nf.type = 'bandpass'; nf.frequency.value = o.nz || 700; nf.Q.value = 0.9; ng.gain.setValueAtTime(0.0001, t); ng.gain.exponentialRampToValueAtTime(o.vol * (o.rasp || 0.5), t + o.atk); ng.gain.exponentialRampToValueAtTime(0.0001, t + D); ns.connect(nf); nf.connect(ng); ng.connect(AC.destination); ns.start(t); ns.stop(t + D + 0.05);
    src.start(t); src2.start(t); lfo.start(t); src.stop(t + D + 0.1); src2.stop(t + D + 0.1); lfo.stop(t + D + 0.1);
  }
  function yelp(sev) {
    if (!AC) return; sev = sev || 0; const heavy = sev > 0.5, f0 = rnd(105, 150), v = (Math.random() * 3) | 0;
    const zd = zvPlay('zgroan' + (1 + v), 0.95, heavy ? rnd(0.84, 0.96) : rnd(0.98, 1.14)); if (zd) { groanMouth = Math.min(1.4, zd * 0.7); return; }
    groanMouth = heavy ? 0.7 : 0.5;
    // v0: low "uhhh", v1: pained "aaah", v2: grumbly "ohhh"
    zvoice({ dur: heavy ? 0.75 : 0.55, atk: 0.05, vol: 0.34 + sev * 0.08, f0: f0 * (v === 1 ? 1.25 : 1), f1: f0 * (heavy ? 0.5 : 0.65), rise: v === 1 ? 1.15 : 0.9, vib: 5 + Math.random() * 3, vibD: 4 + sev * 5, a1: v === 1 ? 760 : v === 2 ? 420 : 560, b1: v === 1 ? 520 : v === 2 ? 330 : 380, a2: v === 1 ? 1250 : v === 2 ? 800 : 1000, b2: v === 1 ? 900 : v === 2 ? 650 : 760, nz: 650, rasp: 0.5 });
  }
  function scream() {
    if (!AC) return; const zd = zvPlay('zdeath', 1, 1); if (zd) { groanMouth = Math.min(3.2, zd * 0.8); return; } groanMouth = 2.4; const f0 = rnd(135, 160);
    zvoice({ dur: 1.0, atk: 0.07, hold: 0.12, vol: 0.4, f0: f0 * 1.15, f1: f0 * 0.62, rise: 0.85, vib: 6.5, vibD: 9, a1: 780, b1: 480, a2: 1250, b2: 800, nz: 800, rasp: 0.6 });
    zvoice({ delay: 0.78, dur: 1.15, atk: 0.1, vol: 0.34, f0: f0 * 0.7, f1: f0 * 0.34, rise: 1.0, vib: 4.5, vibD: 6, a1: 520, b1: 230, a2: 900, b2: 450, gurg: 15, nz: 500, rasp: 0.9 });
    zvoice({ delay: 1.7, dur: 0.95, atk: 0.05, vol: 0.22, f0: 70, f1: 38, rise: 1.0, vib: 3, vibD: 3, a1: 300, b1: 160, a2: 600, b2: 300, gurg: 11, nz: 380, rasp: 1.4 });
  }
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
    let a = (part.fr || 0) + amt; amt = Math.floor(a); part.fr = a - amt; if (amt <= 0 || grace > 0) return 0; if (standing) standing = false; const p = pt || part.body.position, wasDead = dead;
    if (!dead) { totalDmg += amt; hp -= amt; mood = Math.max(mood, amt >= 18 ? 1.3 : 0.95); if (amt >= 18) faceKind = 3; else if (mood < 1) faceKind = 1; dmgHud(); hpBar(); if (!quiet) popup('-' + amt, p, amt); if (amt >= 6 && performance.now() - owT > 600) { owT = performance.now(); yelp(Math.min(1, amt / 40)); } }
    if (frozenT > 0 && kind !== 'freeze' && kind !== 'bleed' && amt >= 3) shatterIce(dx, dy);
    if (!NOBLOOD[kind]) bloodAt(p, amt, dx, dy);
    const lim = SEV[part.name]; if (lim && !part.cut && kind !== 'burn' && kind !== 'shock' && kind !== 'bleed' && kind !== 'freeze' && kind !== 'acid' && kind !== 'sting') { part.dmg = (part.dmg || 0) + amt * (SEVMUL[kind] || 1); if (part.dmg > lim) tear(part, dx, dy); }
    if (!dead && hp <= 0) die(kind); return wasDead ? 0 : amt;
  }
  function die(kind) {
    if (dead || !doll) return; standing = false; dead = true; deadT = 0; kos++; hp = 0; hpBar(); const k = document.getElementById('kos'); if (k) k.textContent = 'KOs ' + kos; mood = 999;
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
  function pushAt(part, vx, vy, pt) { if (standing && (Math.abs(vx) + Math.abs(vy)) > 2) standing = false; const b = part.body, m = b.mass; b.applyImpulse(new CANNON.Vec3(vx * m, vy * m, 0), new CANNON.Vec3(pt.x - b.position.x, pt.y - b.position.y, clamp(pt.z - b.position.z, -0.2, 0.2))); }
  function sparks(p, n, c0, c1, spd, size) { for (let i = 0; i < n; i++) { const a = Math.random() * 6.28, s = rnd(0.35, 1) * spd; emit({ x: p.x, y: p.y, vx: Math.cos(a) * s, vy: Math.sin(a) * s + 1.5, life: rnd(0.25, 0.6), s0: size, s1: size * 0.2, c0, c1, g: 9, drag: 0.95 }); } }
  function puff(p, color, n) { for (let i = 0; i < n; i++) emit({ x: p.x + rnd(-0.1, 0.1), y: p.y + rnd(-0.1, 0.1), vx: rnd(-1.8, 1.8), vy: rnd(-0.5, 2), life: rnd(0.4, 0.8), s0: 0.16, s1: 0.5, c0: color, c1: color, g: -0.4, drag: 0.93, a: 0.7, smoke: true }); }

  /* ---- 2D guns (picture planes that sit beside the target and point at it) ---- */
  /* ---- 3D weapons: every gun is built from real geometry (extruded profiles, bevelled boxes, cylinders) instead of a flat picture ---- */
  // Each builder lays the weapon along +x (muzzle on the right), total length about 1 unit, and returns { g, H (height), mx, my (muzzle), update(t) }.
  const G3 = (() => {
    const S = (c, r, m, ex) => new THREE.MeshStandardMaterial(Object.assign({ color: c, roughness: r, metalness: m, envMapIntensity: m > 0.5 ? 1.2 : 0.4 }, ex || {}));
    const mat = { steel: S(0x8a929c, 0.3, 0.95), gun: S(0x30353d, 0.38, 0.85), dark: S(0x16181c, 0.5, 0.5), black: S(0x101114, 0.6, 0.15), silver: S(0xdfe5ec, 0.16, 1.0), brass: S(0xc9a14a, 0.3, 0.9), wood: null, woodD: S(0x4a2f18, 0.6, 0), olive: S(0x56653a, 0.55, 0.25), orange: S(0xe2781c, 0.42, 0.15), red: S(0xc4281f, 0.42, 0.2), rubber: S(0x1d1e20, 0.9, 0) };
    mat.wood = S(0xffffff, 0.55, 0, { map: woodTexS() });
    const lens = new THREE.MeshBasicMaterial({ color: 0x66c8ff });
    const mk = (geo, m, x, y, z, rx, ry, rz) => { const o = new THREE.Mesh(geo, m); o.position.set(x || 0, y || 0, z || 0); if (rx || ry || rz) o.rotation.set(rx || 0, ry || 0, rz || 0); o.castShadow = true; return o; };
    const slab = (pts, d, m, bev) => { const sh = new THREE.Shape(); pts.forEach((p, i) => (i ? sh.lineTo(p[0], p[1]) : sh.moveTo(p[0], p[1]))); const b = bev == null ? 0.008 : bev; const geo = new THREE.ExtrudeGeometry(sh, { depth: d, bevelEnabled: true, bevelThickness: b, bevelSize: b, bevelSegments: 2, curveSegments: 6 }); geo.translate(0, 0, -d / 2); const o = new THREE.Mesh(geo, m); o.castShadow = true; return o; };
    const cylX = (r1, r2, len, m, x, y, z, seg) => { const geo = new THREE.CylinderGeometry(r1, r2, len, seg || 18); geo.rotateZ(-PI / 2); return mk(geo, m, x, y, z); };
    const rb = (w, h, d, r, m, x, y, z, rz) => mk(roundBox(w, h, d, r, 3), m, x, y, z, 0, 0, rz || 0);
    const guard = (x, y, r, m) => { const t = mk(new THREE.TorusGeometry(r, 0.011, 6, 14, PI * 1.05), m, x, y, 0, 0, 0, PI * 1.0); return t; };
    const out = {};
    // handgun
    out.pistol = () => { const g = new THREE.Group(); g.add(rb(0.7, 0.15, 0.1, 0.03, mat.gun, 0.02, 0.1, 0)); for (let i = 0; i < 5; i++) g.add(mk(new THREE.BoxGeometry(0.012, 0.11, 0.104), mat.dark, -0.2 + i * 0.03, 0.1, 0));
      g.add(mk(new THREE.BoxGeometry(0.16, 0.035, 0.102), mat.dark, 0.08, 0.172, 0)); g.add(cylX(0.034, 0.034, 0.1, mat.black, 0.4, 0.1, 0)); g.add(rb(0.03, 0.04, 0.03, 0.01, mat.dark, 0.32, 0.2, 0)); g.add(rb(0.04, 0.035, 0.05, 0.01, mat.dark, -0.3, 0.19, 0));
      g.add(slab([[-0.28, 0.04], [0.3, 0.04], [0.3, -0.03], [0.04, -0.03], [-0.28, -0.03]], 0.085, mat.black)); g.add(slab([[-0.3, 0.0], [-0.08, 0.0], [-0.05, -0.38], [-0.3, -0.38]], 0.09, mat.black, 0.012)); g.add(slab([[-0.285, -0.02], [-0.095, -0.02], [-0.07, -0.34], [-0.285, -0.34]], 0.108, mat.wood, 0.006));
      g.add(guard(0.02, -0.04, 0.055, mat.gun)); g.add(rb(0.015, 0.06, 0.02, 0.005, mat.steel, 0.0, -0.04, 0, -0.25)); g.add(rb(0.05, 0.03, 0.04, 0.01, mat.steel, -0.17, -0.38, 0)); g.add(rb(0.04, 0.05, 0.02, 0.008, mat.steel, -0.36, 0.14, 0, 0.5));
      return { g, H: 0.62, mx: 0.5, my: 0.1 }; };
    // silver revolver
    out.revolver = () => { const g = new THREE.Group(); g.add(cylX(0.038, 0.034, 0.58, mat.silver, 0.2, 0.14, 0)); g.add(rb(0.52, 0.03, 0.045, 0.01, mat.silver, 0.22, 0.19, 0)); g.add(rb(0.34, 0.075, 0.075, 0.025, mat.silver, 0.1, 0.075, 0)); g.add(rb(0.03, 0.045, 0.03, 0.01, mat.silver, 0.45, 0.205, 0));
      g.add(rb(0.34, 0.24, 0.085, 0.04, mat.silver, -0.15, 0.13, 0)); g.add(cylX(0.11, 0.11, 0.22, mat.steel, -0.04, 0.13, 0, 20)); for (let i = 0; i < 6; i++) { const a = i / 6 * PI * 2; g.add(mk(new THREE.BoxGeometry(0.15, 0.03, 0.03), mat.dark, -0.04, 0.13 + Math.sin(a) * 0.105, Math.cos(a) * 0.105)); }
      g.add(cylX(0.113, 0.113, 0.025, mat.silver, -0.15, 0.13, 0, 20)); g.add(cylX(0.113, 0.113, 0.025, mat.silver, 0.07, 0.13, 0, 20)); g.add(slab([[-0.36, 0.28], [-0.3, 0.32], [-0.25, 0.28], [-0.3, 0.2]], 0.03, mat.steel, 0.005));
      g.add(slab([[-0.26, 0.04], [-0.14, 0.04], [-0.12, -0.1], [-0.2, -0.3], [-0.36, -0.32], [-0.4, -0.2]], 0.07, mat.silver, 0.008)); g.add(slab([[-0.255, 0.02], [-0.155, 0.02], [-0.135, -0.1], [-0.205, -0.28], [-0.34, -0.3], [-0.375, -0.2]], 0.098, mat.wood, 0.006)); g.add(guard(-0.04, -0.03, 0.07, mat.silver)); g.add(rb(0.015, 0.06, 0.02, 0.005, mat.steel, -0.04, -0.01, 0, -0.2));
      return { g, H: 0.66, mx: 0.5, my: 0.14 }; };
    // pump shotgun
    out.shotgun = () => { const g = new THREE.Group(); g.add(cylX(0.034, 0.034, 0.66, mat.gun, 0.17, 0.09, 0)); g.add(cylX(0.029, 0.029, 0.5, mat.gun, 0.08, 0.02, 0)); g.add(mk(new THREE.SphereGeometry(0.018, 8, 6), mat.brass, 0.49, 0.13, 0)); g.add(rb(0.34, 0.16, 0.095, 0.03, mat.black, -0.14, 0.05, 0)); g.add(mk(new THREE.BoxGeometry(0.1, 0.03, 0.098), mat.dark, -0.1, 0.11, 0));
      const fo = rb(0.26, 0.085, 0.09, 0.035, mat.wood, 0.15, 0.015, 0); g.add(fo); for (let i = 0; i < 6; i++) g.add(mk(new THREE.BoxGeometry(0.01, 0.07, 0.094), mat.woodD, 0.06 + i * 0.035, 0.015, 0));
      g.add(slab([[-0.3, 0.12], [-0.3, -0.02], [-0.5, -0.16], [-0.5, 0.04]], 0.085, mat.wood, 0.01)); g.add(rb(0.03, 0.17, 0.09, 0.012, mat.rubber, -0.5, -0.06, 0, 0.38)); g.add(slab([[-0.2, -0.02], [-0.12, -0.02], [-0.1, -0.2], [-0.19, -0.2]], 0.08, mat.black, 0.01)); g.add(guard(-0.02, -0.03, 0.05, mat.gun)); g.add(rb(0.012, 0.05, 0.02, 0.005, mat.steel, -0.02, -0.03, 0, -0.2));
      return { g, H: 0.42, mx: 0.5, my: 0.09 }; };
    // sniper rifle with scope and bipod
    out.sniper = () => { const g = new THREE.Group(); g.add(cylX(0.021, 0.026, 0.8, mat.gun, 0.1, 0.07, 0)); g.add(cylX(0.042, 0.042, 0.09, mat.black, 0.47, 0.07, 0)); for (let i = 0; i < 3; i++) g.add(mk(new THREE.BoxGeometry(0.012, 0.09, 0.09), mat.dark, 0.44 + i * 0.025, 0.07, 0));
      g.add(rb(0.38, 0.1, 0.085, 0.03, mat.olive, -0.08, 0.06, 0)); g.add(rb(0.22, 0.05, 0.088, 0.02, mat.black, 0.1, 0.03, 0));
      g.add(cylX(0.044, 0.044, 0.32, mat.black, -0.03, 0.19, 0)); g.add(cylX(0.062, 0.05, 0.07, mat.black, 0.16, 0.19, 0)); g.add(cylX(0.05, 0.062, 0.07, mat.black, -0.22, 0.19, 0)); g.add(cylX(0.052, 0.052, 0.01, lens, 0.2, 0.19, 0)); g.add(cylX(0.04, 0.04, 0.01, lens, -0.26, 0.19, 0));
      for (const x of [-0.12, 0.08]) g.add(rb(0.03, 0.07, 0.04, 0.01, mat.steel, x, 0.125, 0)); g.add(mk(new THREE.CylinderGeometry(0.01, 0.01, 0.06, 6), mat.steel, -0.2, 0.1, 0.055, PI / 2, 0, 0)); g.add(mk(new THREE.SphereGeometry(0.018, 8, 6), mat.steel, -0.2, 0.1, 0.09));
      g.add(slab([[-0.26, 0.11], [-0.26, -0.02], [-0.5, -0.1], [-0.5, 0.07]], 0.08, mat.olive, 0.01)); g.add(slab([[-0.38, 0.1], [-0.26, 0.11], [-0.28, 0.065], [-0.38, 0.065]], 0.09, mat.black, 0.006)); g.add(slab([[-0.17, -0.02], [-0.1, -0.02], [-0.08, -0.17], [-0.15, -0.17]], 0.075, mat.olive, 0.008));
      g.add(rb(0.07, 0.13, 0.06, 0.015, mat.dark, 0.0, -0.06, 0)); g.add(guard(-0.05, -0.03, 0.05, mat.gun));
      for (const s of [-1, 1]) { const leg = mk(new THREE.CylinderGeometry(0.008, 0.008, 0.2, 6), mat.steel, 0.3, -0.07, s * 0.05, 0, 0, 0.25); g.add(leg); g.add(mk(new THREE.SphereGeometry(0.014, 6, 6), mat.steel, 0.32, -0.17, s * 0.05)); }
      return { g, H: 0.44, mx: 0.5, my: 0.07 }; };
    // rocket launcher
    out.rocket = () => { const g = new THREE.Group(); g.add(cylX(0.088, 0.088, 0.9, mat.olive, 0.04, 0.05, 0, 22)); g.add(cylX(0.12, 0.09, 0.1, mat.gun, -0.46, 0.05, 0, 22)); g.add(cylX(0.1, 0.1, 0.04, mat.gun, 0.49, 0.05, 0, 22)); g.add(cylX(0.092, 0.092, 0.06, mat.orange, 0.36, 0.05, 0, 22)); g.add(cylX(0.092, 0.092, 0.03, mat.orange, 0.25, 0.05, 0, 22));
      g.add(mk(new THREE.ConeGeometry(0.07, 0.14, 14).rotateZ(-PI / 2), mat.red, 0.47, 0.05, 0)); for (const x of [-0.3, 0.1]) { const r = mk(new THREE.TorusGeometry(0.092, 0.012, 6, 20), mat.steel, x, 0.05, 0, 0, PI / 2, 0); g.add(r); }
      g.add(slab([[-0.1, -0.02], [0.0, -0.02], [0.02, -0.2], [-0.07, -0.2]], 0.07, mat.black, 0.01)); g.add(slab([[0.2, -0.03], [0.28, -0.03], [0.27, -0.16], [0.2, -0.16]], 0.065, mat.black, 0.01)); g.add(rb(0.07, 0.05, 0.12, 0.015, mat.rubber, -0.27, -0.02, 0)); g.add(rb(0.03, 0.06, 0.012, 0.005, mat.steel, 0.3, 0.17, 0)); g.add(rb(0.02, 0.045, 0.012, 0.005, mat.steel, -0.3, 0.16, 0));
      return { g, H: 0.34, mx: 0.5, my: 0.05 }; };
    // flamethrower
    out.flame = () => { const g = new THREE.Group(); g.add(rb(0.34, 0.15, 0.1, 0.04, mat.red, -0.22, 0.04, 0)); g.add(cylX(0.032, 0.032, 0.58, mat.steel, 0.2, 0.07, 0)); for (const x of [0.0, 0.15, 0.3]) g.add(cylX(0.045, 0.045, 0.03, mat.gun, x, 0.07, 0)); g.add(cylX(0.05, 0.036, 0.07, mat.gun, 0.47, 0.07, 0));
      g.add(cylX(0.1, 0.1, 0.32, mat.orange, -0.24, -0.12, 0, 20)); g.add(mk(new THREE.SphereGeometry(0.1, 14, 10), mat.orange, -0.4, -0.12, 0)); g.add(mk(new THREE.SphereGeometry(0.1, 14, 10), mat.orange, -0.08, -0.12, 0)); g.add(cylX(0.103, 0.103, 0.025, mat.gun, -0.3, -0.12, 0, 20)); g.add(cylX(0.103, 0.103, 0.025, mat.gun, -0.18, -0.12, 0, 20));
      g.add(mk(new THREE.TorusGeometry(0.1, 0.014, 6, 16, PI), mat.rubber, -0.05, -0.0, 0, 0, 0, PI / 2 + 0.2)); g.add(slab([[-0.1, -0.02], [-0.03, -0.02], [-0.02, -0.2], [-0.1, -0.2]], 0.075, mat.black, 0.01)); g.add(slab([[0.14, 0.0], [0.2, 0.0], [0.2, -0.15], [0.13, -0.15]], 0.065, mat.black, 0.01)); g.add(guard(-0.05, -0.03, 0.045, mat.gun));
      g.add(mk(new THREE.ConeGeometry(0.018, 0.05, 8).rotateZ(-PI / 2), new THREE.MeshBasicMaterial({ color: 0x5ab4ff }), 0.5, 0.0, 0)); g.add(mk(new THREE.CylinderGeometry(0.006, 0.006, 0.07, 6), mat.steel, 0.46, 0.035, 0));
      return { g, H: 0.42, mx: 0.52, my: 0.07 }; };
    // chainsaw (the chain keeps moving)
    out.chainsaw = () => { const g = new THREE.Group(), bar = new THREE.Group(); g.add(rb(0.42, 0.28, 0.15, 0.06, mat.orange, -0.27, 0.0, 0)); g.add(rb(0.26, 0.09, 0.152, 0.03, mat.black, -0.3, 0.17, 0)); g.add(rb(0.12, 0.1, 0.16, 0.03, mat.dark, -0.38, -0.06, 0));
      g.add(mk(new THREE.TorusGeometry(0.13, 0.024, 8, 18, PI * 1.45), mat.rubber, -0.34, 0.2, 0, 0, 0, 0.1)); g.add(slab([[-0.4, -0.14], [-0.28, -0.14], [-0.24, -0.3], [-0.36, -0.3]], 0.09, mat.rubber, 0.012)); g.add(cylX(0.04, 0.04, 0.04, mat.steel, -0.47, 0.05, 0));
      const BL = 0.62, BC = 0.19, BW = 0.1; g.add(rb(BL, BW, 0.06, 0.05, mat.steel, BC, 0, 0)); g.add(rb(BL - 0.1, BW - 0.04, 0.066, 0.02, mat.gun, BC, 0, 0)); g.add(mk(new THREE.CylinderGeometry(0.03, 0.03, 0.07, 14).rotateX(PI / 2), mat.dark, 0.05, 0, 0));
      const teeth = []; const per = 2 * (BL - BW) + PI * BW, N = 34; for (let i = 0; i < N; i++) { const t = mk(new THREE.BoxGeometry(0.026, 0.02, 0.07), mat.silver, 0, 0, 0); g.add(t); teeth.push(t); }
      const place = (tm) => { for (let i = 0; i < N; i++) { let s = ((i / N + tm) % 1) * per, x, y, a; const straight = BL - BW, arc = PI * BW / 2; if (s < straight) { x = BC - straight / 2 + s; y = BW / 2; a = 0; } else if (s < straight + arc) { const k = (s - straight) / arc * PI; x = BC + straight / 2 + Math.sin(k) * BW / 2; y = Math.cos(k) * BW / 2; a = -k; } else if (s < 2 * straight + arc) { x = BC + straight / 2 - (s - straight - arc); y = -BW / 2; a = PI; } else { const k = (s - 2 * straight - arc) / arc * PI; x = BC - straight / 2 - Math.sin(k) * BW / 2; y = -Math.cos(k) * BW / 2; a = PI - k; } teeth[i].position.set(x, y, 0); teeth[i].rotation.z = a; teeth[i].scale.set(1, (i % 2) ? 1.5 : 0.8, 1); } };
      place(0); g.add(rb(0.05, 0.12, 0.17, 0.02, mat.red, -0.1, 0.1, 0));
      return { g, H: 0.44, mx: 0.5, my: 0.0, update: (t) => place(t * 3.2) }; };
    // crossbow
    out.crossbow = () => { const g = new THREE.Group(); g.add(slab([[-0.5, 0.04], [-0.5, -0.05], [-0.3, -0.07], [-0.12, -0.04], [0.5, -0.02], [0.5, 0.04]], 0.09, mat.wood, 0.012)); g.add(rb(0.84, 0.03, 0.06, 0.01, mat.gun, 0.02, 0.055, 0)); g.add(slab([[-0.26, -0.05], [-0.18, -0.05], [-0.16, -0.22], [-0.25, -0.22]], 0.075, mat.woodD, 0.01));
      const limb = (s) => { const pts = []; for (let i = 0; i <= 10; i++) { const k = i / 10; pts.push(new THREE.Vector3(0.28 + Math.sin(k * 1.0) * 0.07 * 0 + k * k * 0.1, s * (0.03 + k * 0.4), 0)); } const c = new THREE.CatmullRomCurve3(pts); return mk(new THREE.TubeGeometry(c, 16, 0.018, 8, false), mat.dark, 0, 0, 0); };
      g.add(limb(1)); g.add(limb(-1)); g.add(rb(0.07, 0.1, 0.07, 0.02, mat.gun, 0.28, 0.0, 0)); for (const s of [-1, 1]) { g.add(mk(new THREE.SphereGeometry(0.022, 8, 6), mat.steel, 0.38, s * 0.43, 0)); }
      const sg = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0.38, 0.43, 0), new THREE.Vector3(0.05, 0.04, 0), new THREE.Vector3(0.38, -0.43, 0)]); g.add(new THREE.Line(sg, new THREE.LineBasicMaterial({ color: 0xe6e0c8 })));
      g.add(cylX(0.012, 0.012, 0.62, mat.steel, 0.2, 0.09, 0)); g.add(mk(new THREE.ConeGeometry(0.03, 0.09, 8).rotateZ(-PI / 2), mat.steel, 0.54, 0.09, 0)); for (const s of [-1, 1]) g.add(slab([[-0.08, 0.09], [-0.02, 0.09 + s * 0.04], [-0.02, 0.09]], 0.006, mat.red, 0.002));
      return { g, H: 0.92, mx: 0.55, my: 0.09 }; };
    // minigun: the barrel cluster spins
    out.minigun = () => { const g = new THREE.Group(), spin = new THREE.Group(); spin.position.set(0.18, 0, 0); g.add(spin); for (let i = 0; i < 6; i++) { const a = i / 6 * PI * 2; spin.add(cylX(0.028, 0.028, 0.62, mat.gun, 0, Math.sin(a) * 0.07, Math.cos(a) * 0.07, 10)); } spin.add(cylX(0.06, 0.06, 0.3, mat.dark, 0, 0, 0)); for (const x of [-0.25, 0.0, 0.26]) spin.add(mk(new THREE.TorusGeometry(0.09, 0.014, 6, 18), mat.steel, x, 0, 0, 0, PI / 2, 0));
      g.add(cylX(0.13, 0.13, 0.3, mat.gun, -0.2, 0, 0, 20)); for (const x of [-0.3, -0.2, -0.1]) g.add(cylX(0.135, 0.135, 0.02, mat.steel, x, 0, 0, 20)); g.add(rb(0.22, 0.24, 0.2, 0.05, mat.dark, -0.4, 0.0, 0)); g.add(rb(0.3, 0.035, 0.05, 0.015, mat.steel, -0.2, 0.17, 0)); g.add(slab([[-0.22, -0.1], [-0.12, -0.1], [-0.1, -0.28], [-0.2, -0.28]], 0.08, mat.black, 0.01));
      g.add(slab([[0.0, -0.1], [0.08, -0.1], [0.08, -0.25], [0.0, -0.25]], 0.07, mat.black, 0.01)); g.add(rb(0.14, 0.2, 0.14, 0.03, mat.olive, -0.35, -0.2, 0)); for (let i = 0; i < 7; i++) g.add(rb(0.03, 0.02, 0.05, 0.006, mat.brass, -0.28 + i * -0.0, -0.12 + i * -0.005 - 0.0, 0.0 + 0)); g.add(cylX(0.11, 0.09, 0.05, mat.gun, 0.46, 0, 0, 14));
      return { g, H: 0.5, mx: 0.5, my: 0.0, update: (t) => { spin.rotation.x = t * 14; } }; };
    // katana: curved mirror blade, hamon line, wrapped handle
    out.katana = () => { const g = new THREE.Group(); g.add(slab([[-0.12, 0.02], [0.3, 0.024], [0.5, 0.07], [0.46, 0.036], [0.3, -0.012], [-0.12, -0.016]], 0.012, mat.silver, 0.004)); g.add(slab([[-0.1, 0.002], [0.3, 0.004], [0.46, 0.036], [0.3, -0.006], [-0.1, -0.006]], 0.0145, S(0xf4f8ff, 0.1, 1.0), 0.0015));
      g.add(cylX(0.052, 0.052, 0.014, mat.brass, -0.135, 0.0, 0, 20)); g.add(rb(0.3, 0.042, 0.048, 0.016, mat.black, -0.3, 0.0, 0)); for (let i = 0; i < 7; i++) g.add(mk(new THREE.BoxGeometry(0.024, 0.044, 0.05), mat.red, -0.43 + i * 0.042, 0.0, 0, 0, 0, 0.6)); g.add(rb(0.035, 0.05, 0.05, 0.012, mat.brass, -0.46, 0.0, 0));
      return { g, H: 0.16, mx: 0.5, my: 0.05 }; };
    return out;
  })();

  const gunMeshes = {}; let gunId = null; const gun = { vis: 0, kick: 0, side: 1, muz: V3(0, 0, 0), dir: V3(1, 0, 0), target: V3(0, 0, 0) };
  function gunMesh(id) {
    if (gunMeshes[id]) return gunMeshes[id];
    if (G3[id]) { const spec = G3[id](), m = new THREE.Group(), inner = new THREE.Group(); inner.rotation.y = 0.32; inner.add(spec.g); m.add(inner); m.visible = false; m.userData.g3 = spec; m.userData.asp = 1 / spec.H; m.material = { opacity: 1 }; m.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = false; } }); scene.add(m); return (gunMeshes[id] = m); }
    const G = GUNS[id], u = assetUrl(G.asset); if (!u) return null;
    const t = new THREE.TextureLoader().setCrossOrigin('anonymous').load(u); t.anisotropy = 8; t.minFilter = THREE.LinearFilter;
    const m = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial({ map: t, transparent: true, depthWrite: false, side: THREE.DoubleSide })); m.visible = false; m.renderOrder = 8; m.userData.asp = assetAsp(G.asset, 1.5); scene.add(m); return (gunMeshes[id] = m);
  }
  function placeGun(id, target, dt) {
    const m = gunMesh(id); if (!m) { gun.muz.set(target.x + (target.x > 0 ? 1.2 : -1.2), target.y, 0.95); gun.dir.set(target.x > 0 ? -1 : 1, 0, 0); return; }
    const G = GUNS[id], L = G.L, h = L / m.userData.asp; if (Math.abs(target.x) > 0.5) gun.side = target.x > 0 ? 1 : -1;
    const half = L * 0.5, gx = clamp(target.x + gun.side * (half + 0.95), -RW / 2 + half * 0.85, RW / 2 - half * 0.85), gy = clamp(target.y + 0.05, h * 0.5, RH - h * 0.5);
    let dx = target.x - gx, dy = target.y - gy; const dl = Math.hypot(dx, dy) || 1; dx /= dl; dy /= dl; gun.dir.set(dx, dy, 0);
    const k = gun.kick, sp = m.userData.g3, pop = sp ? clamp(gun.vis * 8, 0.02, 1) : 1; m.position.set(gx - dx * k, gy - dy * k, 0.97);
    if (sp) m.scale.set((gun.side > 0 ? -L : L) * pop, L * pop, L * pop); else m.scale.set(gun.side > 0 ? -L : L, h, 1);
    m.rotation.z = (gun.side > 0 ? Math.atan2(-dy, -dx) : Math.atan2(dy, dx)) + (G.rot ? (gun.side > 0 ? G.rot : -G.rot) : 0);
    m.updateMatrixWorld(true); if (sp) { gun.muz.set(sp.mx, sp.my, 0); if (sp.update) sp.update(performance.now() / 1000); } else gun.muz.set(G.mx, G.my, 0); m.localToWorld(gun.muz); gun.target.copy(target);
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
  // props use physically based materials: steel-like greys become metal (they pick up the studio reflections), paint and plastic stay glossy dielectrics
  function pbr(o) {
    const col = new THREE.Color(o.color == null ? 0xffffff : o.color), hsl = {}; col.getHSL(hsl); const sh = o.shininess == null ? 60 : o.shininess, spec = o.specular == null ? 0x666666 : o.specular;
    const metal = sh >= 70 && hsl.s < 0.3 && hsl.l > 0.12 ? 0.85 : (sh >= 90 && (spec & 0xff) > 0x90 && hsl.s < 0.45 ? 0.6 : 0);
    const m = new THREE.MeshStandardMaterial({ color: col, roughness: clamp(1.0 - sh / 175, metal ? 0.28 : 0.3, 0.95), metalness: metal, envMapIntensity: metal ? 1.15 : 0.22 });
    if (o.emissive != null) m.emissive = new THREE.Color(o.emissive); if (o.emissiveIntensity != null) m.emissiveIntensity = o.emissiveIntensity;
    if (o.transparent) { m.transparent = true; m.opacity = o.opacity == null ? 1 : o.opacity; m.roughness = 0.12; m.envMapIntensity = 1.4; }
    if (o.flatShading) m.flatShading = true; if (o.side != null) m.side = o.side; if (o.depthWrite != null) m.depthWrite = o.depthWrite; return m;
  }
  function phong(c, sh) { return pbr({ color: c, shininess: sh || 60 }); }
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
    const g = new THREE.Group(), dark = phong(0x343944, 90), lite = phong(0x8a93a2, 140), D = 0.66;
    const prof = new THREE.Shape(); prof.moveTo(-0.62, -0.5); prof.lineTo(0.62, -0.5); prof.lineTo(0.56, -0.4); prof.lineTo(0.3, -0.34); prof.quadraticCurveTo(0.22, -0.16, 0.34, -0.02); prof.quadraticCurveTo(0.9, -0.06, 1.4, 0.15); prof.quadraticCurveTo(1.1, 0.3, 0.8, 0.3); prof.lineTo(-0.78, 0.3); prof.lineTo(-0.78, 0.1); prof.lineTo(-0.34, 0.06); prof.quadraticCurveTo(-0.22, -0.16, -0.3, -0.34); prof.lineTo(-0.56, -0.4); prof.closePath();
    const body3 = new THREE.Mesh(new THREE.ExtrudeGeometry(prof, { depth: D, bevelEnabled: true, bevelThickness: 0.05, bevelSize: 0.04, bevelSegments: 3, curveSegments: 10 }), dark); body3.position.set(-0.2, 0.05, -D / 2); body3.castShadow = true; g.add(body3);
    const add = (geo, mat, x, y, z) => { const m = new THREE.Mesh(geo, mat); m.position.set(x, y, z); m.castShadow = true; g.add(m); return m; };
    add(roundBox(1.5, 0.06, D - 0.04, 0.025, 3), lite, 0.0, 0.38, 0);
    add(roundBox(0.14, 0.05, 0.14, 0.015, 2), phong(0x0c0d10, 20), -0.45, 0.42, 0);
    add(new THREE.CylinderGeometry(0.06, 0.06, 0.05, 14), phong(0x0c0d10, 20), -0.15, 0.42, 0);
    add(roundBox(0.5, 0.05, D + 0.12, 0.02, 2), lite, -0.1, -0.12, 0);
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
    const g = new THREE.Group(), sh = new THREE.Shape(), N = 24;
    for (let i = 0; i < N; i++) { const a0 = (i / N) * PI * 2, a1 = ((i + 0.55) / N) * PI * 2, a2 = ((i + 1) / N) * PI * 2, R = 0.68, r = 0.56;
      const p0 = [Math.cos(a0) * r, Math.sin(a0) * r], p1 = [Math.cos(a1) * R, Math.sin(a1) * R], p2 = [Math.cos(a2) * r, Math.sin(a2) * r];
      if (i) sh.lineTo(p0[0], p0[1]); else sh.moveTo(p0[0], p0[1]); sh.lineTo(p1[0], p1[1]); sh.lineTo(p2[0], p2[1]); }
    sh.closePath(); const hole = new THREE.Path(); hole.absarc(0, 0, 0.14, 0, PI * 2, true); sh.holes.push(hole);
    const steel = phong(0xd3dae4, 150), disc = new THREE.Mesh(new THREE.ExtrudeGeometry(sh, { depth: 0.05, bevelEnabled: true, bevelThickness: 0.02, bevelSize: 0.015, bevelSegments: 2, curveSegments: 6 }), steel); disc.position.z = -0.025; g.add(disc);
    [0.44, 0.3].forEach((rr, k) => { const rg = new THREE.Mesh(new THREE.TorusGeometry(rr, 0.014, 6, 40), phong(k ? 0x9aa3b0 : 0xe6ecf4, 130)); rg.position.z = 0.04; g.add(rg); const rb2 = rg.clone(); rb2.position.z = -0.04; g.add(rb2); });
    for (let i = 0; i < 5; i++) { const a = (i / 5) * PI * 2 + 0.3, hh = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, 0.14, 12), phong(0x20242c, 40)); hh.rotation.x = PI / 2; hh.position.set(Math.cos(a) * 0.37, Math.sin(a) * 0.37, 0); g.add(hh); }
    const hub = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.2, 0.15, 22), phong(0xf08a1c, 90)); hub.rotation.x = PI / 2; g.add(hub);
    [0.085, -0.085].forEach((z) => { const w = new THREE.Mesh(new THREE.CylinderGeometry(0.13, 0.13, 0.025, 20), phong(0xb9c2cf, 140)); w.rotation.x = PI / 2; w.position.z = z; g.add(w); const bolt = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, 0.04, 6), phong(0x474c57, 80)); bolt.rotation.x = PI / 2; bolt.position.z = z * 1.35; g.add(bolt); });
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
    m.visible = true; m.material.opacity = clamp(kat.vis * 4, 0, 1);
    if (m.userData.g3) { m.scale.setScalar(L * clamp(kat.vis * 6, 0.02, 1)); m.rotation.z = kat.ang; m.position.set(p.x - Math.cos(kat.ang) * 0.35, p.y - Math.sin(kat.ang) * 0.35, 0.98); return; }
    m.scale.set(L, h, 1); m.rotation.z = kat.ang + 0.75 * PI; m.position.set(p.x - Math.cos(kat.ang) * 0.45, p.y - Math.sin(kat.ang) * 0.45, 0.98);
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
    if (!shardGeo) { shardGeo = new THREE.TetrahedronGeometry(0.2); shardMat = pbr({ color: 0xbfeaff, emissive: 0x2a6a9a, specular: 0xffffff, shininess: 120, transparent: true, opacity: 0.88, flatShading: true }); }
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
    const ex = new THREE.Group(), links = [], PITCH = 0.148, lkGeo = new THREE.TorusGeometry(0.072, 0.03, 10, 22), lkMat = pbr({ color: 0x8b929e, shininess: 140, specular: 0xdfe6f0 }), lkMat2 = pbr({ color: 0x6c727d, shininess: 120, specular: 0xbfc8d4 });
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
    const g = new THREE.Group(), rock = new THREE.Mesh(new THREE.IcosahedronGeometry(0.55, 1), pbr({ color: 0x3c2a22, emissive: 0xff5a14, emissiveIntensity: 0.55, flatShading: true })); g.add(rock);
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
    const p = A.p.clone(), nest = new THREE.Mesh(new THREE.IcosahedronGeometry(0.42, 1), pbr({ color: 0xb59058, flatShading: true, shininess: 10 })); nest.scale.set(1, 1.25, 1); nest.position.set(p.x, RH + 0.6, 0.5); track(nest);
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
    const body = new THREE.Mesh(new THREE.LatheGeometry(pts, 20), pbr({ color: 0x55672b, shininess: 90, specular: 0x99aa77 })); g.add(body);
    const band = new THREE.Mesh(new THREE.CylinderGeometry(0.17, 0.17, 0.05, 20), phong(0xf2c21b, 40)); band.position.y = 0.1; g.add(band); const band2 = band.clone(); band2.position.y = -0.02; g.add(band2);
    const nose = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.05, 0.1, 10), phong(0x9aa0aa, 120)); nose.position.y = 0.62; g.add(nose);
    for (let i = 0; i < 4; i++) { const f = new THREE.Mesh(new THREE.BoxGeometry(0.02, 0.3, 0.26), phong(0x3a4a1e, 30)); f.position.set(0, -0.5, 0); f.rotation.y = i * PI / 2; f.children.length; const hold = new THREE.Group(); hold.rotation.y = i * PI / 2; f.rotation.y = 0; f.position.set(0, -0.48, 0.14); hold.add(f); g.add(hold); }
    const ring = new THREE.Mesh(new THREE.TorusGeometry(0.19, 0.012, 6, 18), phong(0x222222, 10)); ring.rotation.x = PI / 2; ring.position.y = -0.58; g.add(ring);
    g.scale.setScalar(scale || 1); g.traverse((m) => { if (m.isMesh) m.castShadow = true; }); return g;
  }
  function makeJet() {
    const g = new THREE.Group(), hull = pbr({ color: 0x6b7a92, shininess: 110, specular: 0xbcc8dc }), dark = phong(0x2c3442, 60), accent = phong(0xd8262c, 40);
    const fp = [[-1.62, 0.12], [-1.55, 0.2], [-1.2, 0.27], [-0.6, 0.31], [0.2, 0.3], [0.8, 0.24], [1.25, 0.14], [1.7, 0.03], [1.78, 0]].map((p) => new THREE.Vector2(p[1], p[0]));
    const fus = new THREE.Mesh(new THREE.LatheGeometry(fp, 28), hull); fus.rotation.z = -PI / 2; fus.scale.set(1, 1, 0.9); g.add(fus);
    const can = new THREE.Mesh(new THREE.SphereGeometry(0.5, 20, 14), pbr({ color: 0x1a3a5e, shininess: 160, specular: 0xffffff, emissive: 0x0a1a2e })); can.scale.set(0.62, 0.2, 0.2); can.position.set(0.55, 0.27, 0); g.add(can);
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
  function spawnPiano(p, coffin) {
    const g = new THREE.Group(), blk = phong(0x15161a, 140), wht = phong(0xf4f4f0, 40);
    const add = (geo, mat, x, y, z) => { const m = new THREE.Mesh(geo, mat); m.position.set(x, y, z); m.castShadow = true; g.add(m); return m; };
    if (coffin) { const wd = phong(0x3a2414, 30), gold = phong(0xd8b640, 120);
      add(roundBox(2.1, 0.55, 1.0, 0.14, 3), wd, 0, 0.1, 0); const lid = add(roundBox(1.9, 0.12, 0.9, 0.05, 2), phong(0x2e1c10, 30), 0, 0.42, 0); lid.rotation.z = 0.0;
      add(new THREE.BoxGeometry(0.1, 0.46, 0.04), gold, 0.35, 0.1, 0.52); add(new THREE.BoxGeometry(0.3, 0.1, 0.04), gold, 0.35, 0.22, 0.52);
      for (const hx of [-0.6, 0, 0.6]) add(new THREE.BoxGeometry(0.22, 0.05, 0.05), phong(0xb8c0cc, 120), hx, 0.0, 0.52); add(new THREE.BoxGeometry(0.05, 0.4, 0.9), phong(0x24160c, 20), 1.05, 0.1, 0);
    } else {
      add(roundBox(2.1, 0.55, 1.0, 0.1, 3), blk, 0, 0.1, 0); const lid = add(roundBox(2.0, 0.06, 0.96, 0.03, 2), blk, -0.15, 0.62, 0); lid.rotation.z = 0.35;
      add(roundBox(1.5, 0.1, 0.3, 0.02, 2), wht, 0.1, -0.05, 0.42); for (let i = 0; i < 9; i++) add(new THREE.BoxGeometry(0.07, 0.06, 0.18), blk, -0.55 + i * 0.15, 0.02, 0.48);
      for (const lx of [-0.85, 0.85]) add(new THREE.CylinderGeometry(0.07, 0.05, 0.5, 10), blk, lx, -0.42, 0);
    }
    const body = new CANNON.Body({ mass: 220, material: propMat, linearDamping: 0.01 }); body.addShape(new CANNON.Box(new CANNON.Vec3(1.05, 0.55, 0.5)));
    body.position.set(clamp(p.x, -RW / 2 + 1.15, RW / 2 - 1.15), RH - 0.7, 0); body.velocity.set(0, -16, 0); body.fixedRotation = true; body.updateMassProperties(); body.collisionFilterGroup = 1; body.collisionFilterMask = 3;
    const t = { kind: 'piano', body, mesh: g, hit: false, landed: false, rest: 0, ghost: false };
    body.addEventListener('collide', (ev) => { const o = ev.body, spd = Math.abs(ev.contact.getImpactVelocityAlongNormal()); if (o && o.partRef && !t.hit && spd > 5) { t.hit = true; t.crush = { x: body.position.x, y: body.position.y - 0.4 }; } else if (o && o.isWall && !t.landed && spd > 5) { t.landed = true; t.land = body.position.x; } });
    t.update = (dt) => {
      if (t.crush && doll) { const c = t.crush; t.crush = null; const pt = V3(c.x, c.y, 0); let sum = 0;
        for (const part of doll.list) { const b = part.body, dx = b.position.x - c.x; if (Math.abs(dx) < 1.6 && Math.abs(b.position.y - c.y) < 1.8) { const f = 1 - Math.abs(dx) / 1.7; b.velocity.y = Math.min(b.velocity.y, -10 * f - 2); b.velocity.x += (dx >= 0 ? 1 : -1) * 5; sum += hurt(part, 70 * f + 10, null, true, 'crush', 0, -1); } }
        if (sum) popup('-' + sum, V3(c.x, c.y + 0.7, 0), sum); popupT(coffin ? 'COFFIN SLAM!' : 'PLONK!', V3(c.x, c.y + 1.6, 0), '#ffffff', 9); sparks(pt, 20, 0xffffff, 0xffb040, 11, 0.12); puff(pt, 0xd8cdb8, 14); shake(0.7); (coffin ? sfx.thud() : sfx.chord()); haptic('thud'); flash(0.2); t.ghost = true; }
      if (t.ghost && body.collisionFilterMask !== 2) body.collisionFilterMask = 2;
      if (t.land != null) { const x = t.land; t.land = null; const pt = V3(x, 0.15, 0); puff(pt, 0xd8cdb8, 16); ring(pt, 2.6, 0xffe9b8, 0.4); blow(pt, 0, 0.7, 2.8, 6, 12); shake(0.5); if (!t.hit && !coffin) sfx.chord(); else sfx.thud(); haptic('thud'); t.rest = 0.001;
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
    const dome = new THREE.Mesh(new THREE.SphereGeometry(0.5, 20, 12, 0, 6.28, 0, PI / 2), pbr({ color: 0x7affb0, transparent: true, opacity: 0.75, shininess: 160 })); dome.position.y = 0.18; g.add(dome);
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
    const s = sideOf(A.p.x), g = new THREE.Group(), red = phong(0xe02a2a, 120), dark = phong(0x1c1d22, 30), glass = pbr({ color: 0x9fd6ff, shininess: 180, transparent: true, opacity: 0.85 });
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

  /* ===================== zombie ways ===================== */
  const nearestPart = (x, y, maxD) => { let best = null, bd = maxD || 9; if (doll) for (const q of doll.list) { const d = Math.hypot(q.body.position.x - x, q.body.position.y - y); if (d < bd) { bd = d; best = q; } } return best; };
  const mkM = (geo, col, sh) => { const m = new THREE.Mesh(geo, phong(col, sh || 30)); m.castShadow = true; return m; };
  const dirtPuff = (p, n) => { for (let i = 0; i < n; i++) emit({ x: p.x + rnd(-0.3, 0.3), y: p.y + rnd(0, 0.2), vx: rnd(-3, 3), vy: rnd(2, 6), life: rnd(0.4, 0.8), s0: 0.16, s1: 0.06, c0: 0x8a6a44, c1: 0x4a3320, g: 14 }); };
  // a swinging hand tool (bat, axe, shovel, machete): build(L) returns a group with its pivot at the origin pointing along +y
  function swingTool(p, L, build, a0, a1, dur, onHit) {
    const side = sideOf(p.x), inner = build(L), g = new THREE.Group(); g.add(inner); if (side > 0) inner.scale.x = -1; g.traverse((m) => { if (m.isMesh) m.castShadow = true; }); track(g);
    const A0 = side > 0 ? a0 : PI - a0, A1 = side > 0 ? a1 : PI - a1, px = p.x - L * Math.cos(A1), py = p.y - L * Math.sin(A1); let t = 0, hit = false;
    addFx((dt) => {
      t += dt; const k = Math.min(1, t / dur), e = k * k * k, phi = A0 + (A1 - A0) * e; g.rotation.z = phi - PI / 2; g.position.set(px, py, 1.15);
      if (t < dur && t > dur * 0.3) emit({ x: px + L * Math.cos(phi), y: py + L * Math.sin(phi), life: 0.18, s0: 0.35, s1: 0.1, c0: 0xffffff, c1: 0xffe9a0, a: 0.5 });
      if (!hit && t >= dur) { hit = true; onHit(p, side); }
      if (t > dur + 0.14) g.scale.setScalar(Math.max(0.01, 1 - (t - dur - 0.14) / 0.16)); if (t > dur + 0.32) { kill(g); return false; } return true;
    });
  }
  // --- baseball bat with nails ---
  function doBat(A) {
    cd = 0.42; const wood = 0xb9854a;
    swingTool(A.p.clone(), 1.9, (L) => { const g = new THREE.Group(); const b = mkM(new THREE.CylinderGeometry(0.17, 0.06, L, 14), wood, 25); b.position.y = L / 2; g.add(b); g.add(mkM(new THREE.SphereGeometry(0.09, 10, 8), 0x6b4524)); const cap = mkM(new THREE.SphereGeometry(0.17, 12, 8), wood, 25); cap.position.y = L; cap.scale.y = 0.5; g.add(cap);
      for (let i = 0; i < 8; i++) { const a = i * 0.8, y = L * (0.62 + (i % 4) * 0.09), n = mkM(new THREE.ConeGeometry(0.03, 0.2, 6), 0xaab0b8, 120); n.position.set(Math.cos(a) * 0.2, y, Math.sin(a) * 0.2); n.rotation.z = -Math.cos(a) * 1.4; n.rotation.x = Math.sin(a) * 1.4; g.add(n); }
      const bl = mkM(new THREE.CylinderGeometry(0.175, 0.15, 0.16, 12), 0x6a0f12); bl.position.y = L * 0.8; g.add(bl); return g; }, 0.5, PI - 0.1, 0.22,
    (p, side) => { const sum = blow(p, -side * 0.95, 0.2, 1.4, 21, 40); sparks(p, 8, 0xffffff, 0xffd34a, 8, 0.1); bloodBurst(V3(p.x, p.y, 0.5), 10, -side, 0.3, 9, 1.0); popupT('BONK!', V3(p.x, p.y + 0.9, 0), '#ffd23f', 9); ring(p, 1.0, 0xffffff, 0.2); shake(sum ? 0.4 : 0.15); sfx.smash(); haptic('thud'); });
  }
  // --- fire axe ---
  function doAxe(A) {
    cd = 0.5;
    swingTool(A.p.clone(), 1.7, (L) => { const g = new THREE.Group(); const h = mkM(new THREE.CylinderGeometry(0.06, 0.07, L, 12), 0xa86a2c, 20); h.position.y = L / 2; g.add(h); const pad = mkM(new THREE.BoxGeometry(0.25, 0.1, 0.14), 0x9a1c1c); pad.position.y = L - 0.05; g.add(pad);
      const sh = new THREE.Shape(); sh.moveTo(0, -0.28); sh.lineTo(0.55, -0.4); sh.lineTo(0.62, 0.4); sh.lineTo(0, 0.28); sh.closePath(); const bl = mkM(new THREE.ExtrudeGeometry(sh, { depth: 0.07, bevelEnabled: false }), 0xc2cad6, 140); bl.position.set(0.05, L - 0.05, -0.035); g.add(bl);
      const sp = mkM(new THREE.ConeGeometry(0.06, 0.35, 8), 0x9a1c1c, 60); sp.rotation.z = PI / 2; sp.position.set(-0.2, L - 0.05, 0); g.add(sp); return g; }, 0.2, 2.5, 0.24,
    (p, side) => { const sum = blow(p, -side * 0.95, 0.35, 1.0, 14, 60); const q = nearestPart(p.x, p.y, 0.7); if (q && doll && jointOf(q) && Math.random() < 0.65) { tear(q, -side, 0.2); popupT('CHOPPED!', V3(p.x, p.y + 1.2, 0), '#ff5a3a', 9); } else popupT('CHOP!', V3(p.x, p.y + 0.9, 0), '#ffd23f', 9); bloodBurst(V3(p.x, p.y, 0.5), 16, -side, 0.4, 11, 1.2); sparks(p, 6, 0xffffff, 0xffd34a, 7, 0.08); shake(sum ? 0.5 : 0.2); sfx.chop && sfx.chop(); sfx.slice(); haptic('thud'); });
  }
  // --- shovel ---
  function doShovel(A) {
    cd = 0.5;
    swingTool(A.p.clone(), 1.8, (L) => { const g = new THREE.Group(); const h = mkM(new THREE.CylinderGeometry(0.05, 0.05, L, 10), 0xa86a2c, 20); h.position.y = L / 2; g.add(h); const gr = mkM(new THREE.TorusGeometry(0.12, 0.04, 6, 12), 0x6b4524); gr.position.y = 0; g.add(gr);
      const bl = mkM(roundBox(0.55, 0.72, 0.06, 0.02, 2), 0x7d8794, 100); bl.position.y = L + 0.2; g.add(bl); const dirt = mkM(new THREE.SphereGeometry(0.16, 8, 6), 0x5a4128); dirt.position.set(0.1, L + 0.1, 0.06); dirt.scale.set(1.2, 0.7, 0.5); g.add(dirt); return g; }, 0.2, 2.5, 0.26,
    (p, side) => { const sum = blow(p, -side * 0.95, 0.4, 1.3, 27, 32); dirtPuff(p, 12); sparks(p, 7, 0xffffff, 0xffd34a, 9, 0.1); ring(p, 1.1, 0xffe9b8, 0.22); popupT('CLANG!', V3(p.x, p.y + 0.9, 0), '#ffd23f', 9); shake(sum ? 0.45 : 0.15); sfx.clank(); sfx.smash(); haptic('thud'); });
  }
  // --- machete: three fast chops ---
  function doMachete(A) {
    cd = 0.75; const p = A.p.clone(), plan = [[0.2, 2.4, 0], [2.7, 0.5, 0.13], [-0.1, 2.0, 0.26]]; let t = 0, n = 0;
    const slash = (a0, a1) => swingTool(p, 1.5, (L) => { const g = new THREE.Group(); const hd = mkM(new THREE.CylinderGeometry(0.05, 0.05, 0.42, 8), 0x1c1c20, 20); hd.position.y = 0.2; g.add(hd); const bl = mkM(new THREE.BoxGeometry(0.2, L - 0.4, 0.04), 0xc8d0da, 150); bl.position.y = 0.42 + (L - 0.4) / 2; g.add(bl); return g; }, a0, a1, 0.11,
      (pp, side) => { let sum = 0; if (doll) for (const q of doll.list) { const b = q.body.position; if (Math.hypot(b.x - pp.x, b.y - pp.y) < 0.85) { const pt = V3(b.x, b.y, 0); sum += hurt(q, 20, pt, true, 'slash', -side, 0.2); woundAt(q, pt, -side, 0.2); pushAt(q, -side * 4, 2, pt); if (jointOf(q) && Math.random() < 0.22) tear(q, -side, 0.2); } }
        if (sum) popup('-' + sum, V3(pp.x, pp.y + 0.8, 0), sum); bloodBurst(V3(pp.x, pp.y, 0.5), 9, -side, 0.3, 10, 1.0); sparks(pp, 5, 0xffffff, 0xff6a5a, 7, 0.06); sfx.slice(); haptic('tick'); shake(0.18); });
    addFx((dt) => { t += dt; while (n < plan.length && t >= plan[n][2]) { slash(plan[n][0], plan[n][1]); n++; } if (n === 1 && t < 0.02) popupT('CHOP CHOP!', V3(p.x, p.y + 1.4, 0), '#ff5a3a', 8.5); return n < plan.length; });
  }
  // --- zombie horde: five shamblers pile onto him and bite ---
  function zFigure(shirt) {
    const g = new THREE.Group(); const body = mkM(roundBox(0.5, 0.72, 0.3, 0.08, 3), shirt, 20); body.position.y = 1.05; g.add(body); const head = mkM(new THREE.SphereGeometry(0.23, 14, 10), 0x9db87a, 15); head.position.set(0, 1.62, 0.02); g.add(head);
    for (const s of [-1, 1]) { const e = new THREE.Mesh(new THREE.SphereGeometry(0.045, 8, 6), new THREE.MeshBasicMaterial({ color: s < 0 ? 0xf0ff4a : 0xe8e8d0 })); e.position.set(s * 0.09, 1.65, 0.21); g.add(e); const arm = mkM(roundBox(0.14, 0.14, 0.62, 0.04, 2), 0x9db87a, 15); arm.position.set(s * 0.33, 1.2, 0.3); arm.userData.arm = 1; g.add(arm); const leg = mkM(roundBox(0.18, 0.62, 0.2, 0.05, 2), 0x4e4239, 15); leg.position.set(s * 0.13, 0.4, 0); leg.userData.leg = s; g.add(leg); }
    const m = mkM(new THREE.BoxGeometry(0.16, 0.06, 0.04), 0x2a0a0c, 5); m.position.set(0, 1.55, 0.24); g.add(m); return g;
  }
  /* ---- better shambling zombie rig: hips / torso / head+jaw / shoulder+elbow arms / hip+knee legs ---- */
  function zWalker(shirt, v) {
    v = v || {}; const g = new THREE.Group(), R = {}, skin = v.skin || 0x9db87a, pants = v.pants || 0x4a4238, bone = 0xd9d0b0;
    const hips = new THREE.Group(); hips.position.y = v.crawl ? 0.5 : 0.96; g.add(hips); R.hips = hips;
    const pel = mkM(roundBox(0.46, 0.2, 0.27, 0.06, 2), pants, 15); hips.add(pel);
    const torso = new THREE.Group(); torso.position.y = 0.06; hips.add(torso); R.torso = torso;
    const body = mkM(roundBox(0.5, 0.62, 0.28, 0.08, 3), shirt, 20); body.position.y = 0.34; torso.add(body);
    const belt = mkM(roundBox(0.52, 0.06, 0.3, 0.02, 2), 0x2a1c12, 40); belt.position.y = 0.04; torso.add(belt);
    for (let i = 0; i < 3; i++) { const rb = mkM(roundBox(0.2 - i * 0.03, 0.025, 0.02, 0.008, 1), bone, 25); rb.position.set(v.ribSide || 0.08, 0.36 + i * 0.07, 0.145); torso.add(rb); }
    const gash = mkM(new THREE.BoxGeometry(0.22, 0.2, 0.02), 0x5a0c10, 8); gash.position.set(v.ribSide || 0.08, 0.4, 0.139); torso.add(gash);
    for (let i = 0; i < 3; i++) { const fl = mkM(new THREE.BoxGeometry(0.1, 0.18 + i * 0.05, 0.02), shirt, 8); fl.position.set(-0.17 + i * 0.17, -0.0, 0.14); fl.rotation.z = (i - 1) * 0.12; torso.add(fl); }
    const tie = v.tie !== false ? mkM(new THREE.BoxGeometry(0.06, 0.34, 0.02), 0x8a1a22, 20) : null; if (tie) { tie.position.set(-0.08, 0.5, 0.146); torso.add(tie); }
    const neck = mkM(new THREE.CylinderGeometry(0.075, 0.09, 0.14, 8), skin, 15); neck.position.y = 0.7; torso.add(neck);
    for (const s of [-1, 1]) { const sh = mkM(new THREE.SphereGeometry(0.1, 10, 8), shirt, 20); sh.position.set(s * 0.29, 0.62, 0); torso.add(sh); }
    const head = new THREE.Group(); head.position.set(0, 0.84, 0.03); torso.add(head); R.head = head;
    const cr = mkM(new THREE.SphereGeometry(0.22, 16, 12), skin, 15); cr.scale.set(1, 1.02, 1.0); cr.position.y = 0.06; head.add(cr);
    const cheek = [-1, 1].map((s) => { const c = mkM(new THREE.SphereGeometry(0.07, 8, 6), skin, 15); c.position.set(s * 0.12, -0.03, 0.15); head.add(c); return c; });
    const brow = mkM(roundBox(0.34, 0.05, 0.1, 0.02, 2), 0x7d9a62, 12); brow.position.set(0, 0.11, 0.17); head.add(brow);
    const nose = mkM(new THREE.ConeGeometry(0.04, 0.08, 6), skin, 15); nose.rotation.x = PI / 2; nose.position.set(0, 0.0, 0.23); head.add(nose);
    for (const s of [-1, 1]) { const sock = mkM(new THREE.SphereGeometry(0.055, 8, 6), 0x1a1c14, 5); sock.position.set(s * 0.085, 0.06, 0.19); sock.scale.z = 0.6; head.add(sock); const e = new THREE.Mesh(new THREE.SphereGeometry(0.036, 8, 6), new THREE.MeshBasicMaterial({ color: s < 0 ? 0xf0ff4a : 0xe8e8d0 })); e.position.set(s * 0.085, 0.06, 0.215); head.add(e); const ear = mkM(new THREE.SphereGeometry(0.05, 8, 6), skin, 15); ear.scale.x = 0.5; ear.position.set(s * 0.22, 0.02, 0); head.add(ear); }
    const jaw = new THREE.Group(); jaw.position.set(0, -0.08, 0.02); head.add(jaw); R.jaw = jaw; const jb = mkM(roundBox(0.24, 0.08, 0.2, 0.03, 2), skin, 12); jb.position.set(0, -0.03, 0.1); jaw.add(jb);
    const mouth = mkM(new THREE.BoxGeometry(0.2, 0.05, 0.08), 0x3a0a0c, 4); mouth.position.set(0, 0.015, 0.2); jaw.add(mouth);
    for (let i = 0; i < 4; i++) { const th = mkM(new THREE.BoxGeometry(0.03, 0.04, 0.02), 0xe8e0c0, 30); th.position.set(-0.075 + i * 0.05, 0.03, 0.215); jaw.add(th); const tu = mkM(new THREE.BoxGeometry(0.03, 0.04, 0.02), 0xe8e0c0, 30); tu.position.set(-0.075 + i * 0.05, -0.045, 0.225); head.add(tu); }
    if (v.brain) { const br = mkM(new THREE.SphereGeometry(0.17, 10, 8), 0xe88aa0, 60); br.scale.set(1, 0.7, 1); br.position.set(0.04, 0.2, 0.0); head.add(br); for (let i = 0; i < 5; i++) { const lump = mkM(new THREE.SphereGeometry(0.06, 7, 5), 0xd8708a, 60); lump.position.set(-0.06 + i * 0.05, 0.25 + (i % 2) * 0.02, (i % 3 - 1) * 0.05); head.add(lump); } cr.position.y = 0.0; }
    else for (let i = 0; i < 7; i++) { const h = mkM(new THREE.ConeGeometry(0.028, 0.14, 5), v.hair || 0x2a2118, 10); const a = i * 0.9; h.position.set(Math.cos(a) * 0.1, 0.24, Math.sin(a) * 0.08 - 0.02); h.rotation.z = -Math.cos(a) * 0.6; h.rotation.x = Math.sin(a) * 0.6; head.add(h); }
    R.arm = []; R.elb = [];
    for (const s of [-1, 1]) {
      const sho = new THREE.Group(); sho.position.set(s * 0.31, 0.6, 0); torso.add(sho); R.arm.push(sho); const stump = v.noArm === s;
      const up = mkM(roundBox(0.15, stump ? 0.16 : 0.3, 0.15, 0.04, 2), shirt, 20); up.position.y = stump ? -0.08 : -0.14; sho.add(up);
      if (stump) { const bl = mkM(new THREE.SphereGeometry(0.075, 8, 6), 0x7a0c10, 10); bl.position.y = -0.17; sho.add(bl); R.elb.push(null); continue; }
      const el = new THREE.Group(); el.position.y = -0.3; sho.add(el); R.elb.push(el);
      const fa = mkM(roundBox(0.12, 0.3, 0.12, 0.035, 2), skin, 12); fa.position.y = -0.15; el.add(fa);
      const hd = mkM(roundBox(0.12, 0.1, 0.05, 0.02, 2), skin, 12); hd.position.y = -0.34; el.add(hd);
      for (let i = 0; i < 3; i++) { const fg = mkM(new THREE.BoxGeometry(0.03, 0.09, 0.03), skin, 12); fg.position.set(-0.04 + i * 0.04, -0.43, 0.0); fg.rotation.x = -0.35; el.add(fg); }
      const wr = mkM(new THREE.BoxGeometry(0.13, 0.03, 0.13), 0xd9d0b0, 20); wr.position.y = -0.04; el.add(wr);
    }
    R.leg = []; R.knee = [];
    for (const s of [-1, 1]) {
      const hp = new THREE.Group(); hp.position.set(s * 0.12, -0.08, 0); hips.add(hp); R.leg.push(hp);
      const th = mkM(roundBox(0.17, 0.42, 0.18, 0.05, 2), pants, 15); th.position.y = -0.2; hp.add(th);
      const kn = new THREE.Group(); kn.position.y = -0.42; hp.add(kn); R.knee.push(kn);
      if (v.crawl && s > 0) { th.scale.y = 0.45; th.position.y = -0.09; const bl = mkM(new THREE.SphereGeometry(0.08, 8, 6), 0x7a0c10, 10); bl.position.y = -0.2; hp.add(bl); kn.visible = false; R.knee[1] = kn; continue; }
      const sh = mkM(roundBox(0.14, 0.4, 0.15, 0.04, 2), pants, 15); sh.position.y = -0.2; kn.add(sh);
      const bare = mkM(roundBox(0.13, 0.16, 0.14, 0.03, 2), skin, 12); bare.position.y = -0.33; kn.add(bare);
      const ft = mkM(roundBox(0.15, 0.08, 0.28, 0.03, 2), 0x2a2420, 25); ft.position.set(0, -0.42, 0.06); kn.add(ft);
    }
    g.userData.rig = R; g.userData.v = v; g.traverse((m) => { if (m.isMesh) m.castShadow = true; }); return g;
  }
  // mode: 'walk' (ph advances), 'reach' (waiting under the bait), 'bite' (feeding); tm = running clock
  function zAnim(g, ph, mode, tm) {
    const R = g.userData.rig, v = g.userData.v, s = Math.sin, run = v.runner ? 1.35 : 1, mx = Math.max;
    if (v.crawl) {
      const bite = mode === 'bite';
      R.hips.position.y = 0.42 + Math.abs(s(ph)) * 0.03; R.torso.rotation.x = 1.2 + (bite ? s(tm * 16) * 0.2 : s(ph * 0.5) * 0.06); R.torso.rotation.z = s(ph) * 0.05;
      R.arm[0].rotation.x = -PI + 0.4 + s(ph) * 0.6; R.arm[1].rotation.x = -PI + 0.4 + s(ph + PI) * 0.6; R.arm[0].rotation.z = 0.2; R.arm[1].rotation.z = -0.2;
      if (R.elb[0]) R.elb[0].rotation.x = -0.3; if (R.elb[1]) R.elb[1].rotation.x = -0.3;
      R.leg[0].rotation.x = 1.3 + s(ph) * 0.2; R.leg[1].rotation.x = 1.3; R.knee[0].rotation.x = 0.2; R.head.rotation.x = -1.0 + (bite ? s(tm * 16) * 0.2 : 0); R.head.rotation.z = s(ph * 0.7) * 0.15; R.jaw.rotation.x = bite ? (0.5 + 0.5 * s(tm * 18)) * 0.75 : 0.25 + 0.15 * s(ph); return;
    }
    if (mode === 'bite') {
      const a = tm * 16; R.hips.position.y = 0.92; R.torso.rotation.x = 0.5 + s(a) * 0.18; R.torso.rotation.z = s(a * 0.5) * 0.06; R.torso.rotation.y = s(a * 0.5) * 0.1;
      R.leg[0].rotation.x = -0.25; R.leg[1].rotation.x = 0.25; R.knee[0].rotation.x = 0.35; R.knee[1].rotation.x = 0.35;
      R.head.rotation.x = 0.35 + s(a) * 0.22; R.head.rotation.z = s(a * 0.7) * 0.2; R.jaw.rotation.x = (0.5 + 0.5 * s(tm * 18 + 1)) * 0.8;
      for (let i = 0; i < 2; i++) { R.arm[i].rotation.x = -1.6 + s(tm * 14 + i * 2) * 0.45; R.arm[i].rotation.z = (i ? -1 : 1) * 0.1; if (R.elb[i]) R.elb[i].rotation.x = -0.7 + s(tm * 14 + i * 2) * 0.4; } return;
    }
    if (mode === 'reach') {
      R.hips.position.y = 0.96; R.torso.rotation.x = -0.05 + s(tm * 2.2) * 0.05; R.torso.rotation.z = s(tm * 1.7) * 0.06; R.torso.rotation.y = 0;
      R.leg[0].rotation.x = s(tm * 3) * 0.1; R.leg[1].rotation.x = -s(tm * 3) * 0.1; R.knee[0].rotation.x = 0.1; R.knee[1].rotation.x = 0.1;
      R.head.rotation.x = -0.45 + s(tm * 3) * 0.08; R.head.rotation.z = s(tm * 2.1) * 0.12; R.jaw.rotation.x = 0.55 + s(tm * 5) * 0.25;
      for (let i = 0; i < 2; i++) { R.arm[i].rotation.x = -2.05 + s(tm * 5 + i * 1.7) * 0.18; R.arm[i].rotation.z = (i ? -1 : 1) * 0.12; if (R.elb[i]) R.elb[i].rotation.x = -0.15 + s(tm * 5 + i) * 0.1; } return;
    }
    const sw = s(ph) * 0.5 * run;
    R.hips.position.y = 0.95 + Math.abs(s(ph)) * 0.05; R.torso.rotation.x = 0.16 + (run - 1) * 0.5 + s(ph * 2) * 0.03; R.torso.rotation.z = s(ph) * 0.07; R.torso.rotation.y = s(ph) * 0.14;
    R.leg[0].rotation.x = sw; R.leg[1].rotation.x = -sw; R.knee[0].rotation.x = 0.1 + mx(0, -sw) * 1.0; R.knee[1].rotation.x = 0.1 + mx(0, sw) * 1.0;
    R.head.rotation.x = -0.12 + s(ph * 2 + 0.5) * 0.08; R.head.rotation.z = 0.12 + s(ph * 0.7 + 1) * 0.22; R.head.rotation.y = s(ph * 0.5) * 0.25; R.jaw.rotation.x = 0.2 + (0.5 + 0.5 * s(ph * 1.3)) * 0.25;
    const base = -1.35 - (run - 1) * 0.3; for (let i = 0; i < 2; i++) { R.arm[i].rotation.x = base + s(ph * 0.8 + i * 2) * 0.12; R.arm[i].rotation.z = (i ? -1 : 1) * 0.08; if (R.elb[i]) R.elb[i].rotation.x = -0.25 + s(ph + i) * 0.1; }
  }
  function doHorde(A) {
    const cols = [0x5d7090, 0x7a4a4a, 0x4a6a4a, 0x6a5a3a, 0x555a70], figs = [], d0 = doll; popupT('BRAAAINS!', V3(A.p.x, Math.min(RH - 1, A.p.y + 1.6), 0), '#9cff3a', 9); sfx.screech && sfx.screech();
    const hv = [{ tie: true }, { brain: true, skin: 0xa8bf86 }, { runner: true, tie: false }, { noArm: -1, skin: 0x92ae74 }, { skin: 0x8fa878, hair: 0x6a6258 }];
    for (let i = 0; i < 5; i++) { const side = i % 2 ? 1 : -1, g = zWalker(cols[i], hv[i]); g.position.set(side * (RW / 2 + 0.8 + (i >> 1) * 1.1), 0, 0.25 + (i % 3) * 0.12); g.rotation.y = -side * PI / 2; g.scale.setScalar(1.08); track(g); figs.push({ g, side, st: 0, bt: 0, tick: rnd(0, 0.3), ph: rnd(0, 6), off: (i - 2) * 0.7, life: 0, v: hv[i] }); }
    addFx((dt) => {
      let alive = 0; const cx = doll && doll === d0 ? doll.parts.chest.body.position.x : A.p.x, cy = doll && doll === d0 ? doll.parts.chest.body.position.y : A.p.y;
      for (const f of figs) {
        f.life += dt; f.ph += dt * (f.v.runner ? 12 : 8.5); const g = f.g; zAnim(g, f.ph, f.st === 1 ? 'bite' : 'walk', f.life + f.ph);
        if (f.st === 0) { const tx = cx + f.off, dx = tx - g.position.x; g.rotation.y = (dx > 0 ? 1 : -1) * PI / 2; g.position.x += clamp(dx, -1, 1) * (f.v.runner ? 7 : 4.6) * dt * (Math.abs(dx) > 0.2 ? 1 : 0); if (Math.abs(dx) < 0.9) { f.st = 1; f.bt = 0; } alive++; }
        else if (f.st === 1) { alive++; f.bt += dt; f.tick -= dt; g.position.x += (cx + f.off * 0.5 - g.position.x) * dt * 3; if (f.tick <= 0 && doll === d0 && doll) { f.tick = 0.3; const q = nearestPart(g.position.x, g.position.y + 1.2, 1.6) || doll.parts.chest, b = q.body.position, pt = V3(b.x, b.y, 0.4); hurt(q, 8, pt, true, 'slash', -f.side, 0.2); bloodBurst(pt, 4, -f.side, 0.5, 6, 0.8); q.body.velocity.x += (g.position.x < b.x ? 1 : -1) * -1.2; q.body.angularVelocity.z += rnd(-3, 3); if (Math.random() < 0.3) popup('-8', pt, 8); sfx.thud && Math.random() < 0.3 && sfx.thud(); haptic({ intensity: 0.25, sharpness: 0.4 }); } if (f.bt > 2.6) f.st = 2; }
        else { g.position.x += f.side * 4 * dt; g.rotation.y = f.side * PI / 2; if (Math.abs(g.position.x) > RW / 2 + 1.5) { g.visible = false; } else alive++; }
        g.position.y = 0;
      }
      if (!alive || figs[0].life > 9) { for (const f of figs) kill(f.g); return false; } return true;
    });
  }
  // --- graveyard hands: rotting hands tear out of the ground, claw at him, clamp on and drag him down into the grave ---
  const ZSKIN = 0x8fae6c, ZDARK = 0x5f7a46, ZNAIL = 0xcdbf82, ZBONE = 0xe8e0c8, ZDIRT = 0x4a3523, ZCLOTH = [0x4a6b8a, 0x6a5a48, 0x58406a];
  function zHand(k) {
    const g = new THREE.Group(), cyl = (r0, r1, h, col, sh) => mkM(new THREE.CylinderGeometry(r0, r1, h, 9), col, sh || 15), hand = new THREE.Group(), fingers = [], fl = [0.17, 0.2, 0.19, 0.15];
    const palm = mkM(roundBox(0.3, 0.26, 0.11, 0.04, 2), ZSKIN, 15); palm.position.y = 0.1; hand.add(palm);
    for (let i = 0; i < 4; i++) { const spot = mkM(new THREE.SphereGeometry(0.035, 6, 5), ZDIRT, 5); spot.position.set(-0.09 + i * 0.06, 0.08 + (i % 2) * 0.07, 0.06); spot.scale.z = 0.4; hand.add(spot); }
    const wound = mkM(new THREE.BoxGeometry(0.1, 0.07, 0.02), 0x7a1c1c, 5); wound.position.set(0.04, 0.12, 0.06); wound.rotation.z = 0.4; hand.add(wound);
    for (let i = 0; i < 4; i++) {
      const L = fl[i], l1 = L * 0.45, l2 = L * 0.33, l3 = L * 0.22, r = 0.034 - i * 0.002, fg = new THREE.Group(); fg.position.set(-0.108 + i * 0.072, 0.22, 0); fg.rotation.z = (i - 1.5) * 0.05; hand.add(fg);
      const a = cyl(r * 0.9, r, l1, ZSKIN); a.position.y = l1 / 2; fg.add(a); const j2 = new THREE.Group(); j2.position.y = l1; fg.add(j2); const b = cyl(r * 0.82, r * 0.9, l2, ZSKIN); b.position.y = l2 / 2; j2.add(b);
      const kn = mkM(new THREE.SphereGeometry(r * 1.05, 6, 5), ZDARK, 5); j2.add(kn); const j3 = new THREE.Group(); j3.position.y = l2; j2.add(j3);
      const bone = (k + i) % 5 === 0; const c = cyl(r * 0.7, r * 0.82, l3, bone ? ZBONE : ZSKIN, bone ? 40 : 15); c.position.y = l3 / 2; j3.add(c); const nail = mkM(new THREE.ConeGeometry(r * 0.7, l3 * 0.8, 5), bone ? ZBONE : ZNAIL, 5); nail.position.set(0, l3 + 0.02, 0.012); j3.add(nail);
      fingers.push({ fg, j2, j3, off: i * 0.9 });
    }
    const th = new THREE.Group(); th.position.set(0.15, 0.06, 0.01); th.rotation.z = -0.95; hand.add(th); const t1 = cyl(0.036, 0.04, 0.12, ZSKIN); t1.position.y = 0.06; th.add(t1); const tj = new THREE.Group(); tj.position.y = 0.12; th.add(tj); const t2 = cyl(0.03, 0.036, 0.1, ZSKIN); t2.position.y = 0.05; tj.add(t2); const tn = mkM(new THREE.ConeGeometry(0.026, 0.08, 5), ZNAIL, 5); tn.position.y = 0.12; tj.add(tn);
    const cuff = cyl(0.135, 0.15, 0.16, ZCLOTH[k % 3], 8); cuff.position.y = -0.06; hand.add(cuff); for (let i = 0; i < 4; i++) { const rag = mkM(new THREE.ConeGeometry(0.035, 0.12, 4), ZCLOTH[k % 3], 5); rag.position.set(-0.1 + i * 0.07, -0.16, 0.1); rag.rotation.z = PI; hand.add(rag); }
    hand.scale.setScalar(1.25); return { hand, fingers, th: tj, thumb: th };
  }
  function doGraveyard(A) {
    if (!doll) return; const cx = clamp(doll.parts.chest.body.position.x, -RW / 2 + 1.5, RW / 2 - 1.5), d0 = doll, hs = [], N = 5, grp = new THREE.Group(); grp.position.z = 0; track(grp);
    popupT('THEY GRAB!', V3(cx, 3.4, 0), '#9cff3a', 9); sfx.rumble(); shake(0.35); hapStart(0.4, 0.5);
    const dirt = (x, y, n, sp) => { for (let i = 0; i < n; i++) emit({ x: x + rnd(-0.3, 0.3), y, vx: rnd(-sp, sp), vy: rnd(1.5, sp * 1.6), life: rnd(0.4, 0.9), s0: rnd(0.08, 0.16), s1: 0.03, c0: Math.random() < 0.5 ? 0x6b4a2b : 0x4a3220, c1: 0x2a1c10, g: 14 }); };
    for (let i = 0; i < N; i++) {
      const hx = clamp(cx + (i - (N - 1) / 2) * 0.62, -RW / 2 + 0.5, RW / 2 - 0.5), z = 0.42 + (i % 2) * 0.22, H = zHand(i), g = new THREE.Group(); g.position.z = z; grp.add(g);
      const up = mkM(new THREE.CylinderGeometry(0.1, 0.125, 1, 9), ZSKIN, 15), fo = mkM(new THREE.CylinderGeometry(0.085, 0.1, 1, 9), ZSKIN, 15), el = mkM(new THREE.SphereGeometry(0.115, 9, 7), ZDARK, 10), sl = mkM(new THREE.CylinderGeometry(0.125, 0.14, 0.5, 9), ZCLOTH[i % 3], 8), bn = mkM(new THREE.CylinderGeometry(0.03, 0.03, 0.3, 6), ZBONE, 40);
      g.add(up, fo, el, sl, bn, H.hand); sl.visible = i % 2 === 0; bn.visible = i % 3 === 1;
      const mound = new THREE.Mesh(new THREE.SphereGeometry(0.62, 14, 7, 0, 6.283, 0, PI / 2), phong(0x5a4128, 8)); mound.scale.set(1.1, 0.34, 0.8); mound.position.set(hx, 0, z); grp.add(mound); mound.scale.setScalar(0.01);
      const clods = []; for (let c = 0; c < 4; c++) { const m = mkM(new THREE.IcosahedronGeometry(rnd(0.07, 0.13), 0), Math.random() < 0.5 ? 0x5a4128 : 0x3a2a1a, 5); m.position.set(hx + rnd(-0.45, 0.45), 0.05, z + rnd(-0.15, 0.25)); m.visible = false; grp.add(m); clods.push(m); }
      hs.push({ i, hx, z, g, H, up, fo, el, sl, bn, mound, clods, delay: i * 0.13, tip: { x: hx, y: 0 }, bend: i % 2 ? 1 : -1, ph: i * 1.7, grip: 0, tgt: null, gt: 0, ms: 0.01 });
    }
    const place = (m, x0, y0, x1, y1) => { m.position.set((x0 + x1) / 2, (y0 + y1) / 2, 0); m.scale.y = Math.max(0.01, Math.hypot(x1 - x0, y1 - y0)); m.rotation.z = Math.atan2(-(x1 - x0), y1 - y0); };
    const L1 = 0.95, L2 = 0.95;
    function pose(h, tx, ty, curl, t) {
      const bx0 = h.hx, by0 = -0.15; let dx = tx - bx0, dy = ty - by0, d = Math.hypot(dx, dy); const mx = L1 + L2 - 0.03; if (d > mx) { dx *= mx / d; dy *= mx / d; d = mx; tx = bx0 + dx; ty = by0 + dy; } d = Math.max(d, 0.4);
      const a = (L1 * L1 - L2 * L2 + d * d) / (2 * d), hh = Math.sqrt(Math.max(0, L1 * L1 - a * a)), ux = dx / d, uy = dy / d, ex = bx0 + ux * a - uy * hh * h.bend, ey = by0 + uy * a + ux * hh * h.bend;
      place(h.up, bx0, by0, ex, ey); place(h.fo, ex, ey, tx, ty); h.el.position.set(ex, ey, 0); const ang = Math.atan2(-(ty - ey), tx - ex); h.H.hand.position.set(tx, ty, 0); h.H.hand.rotation.z = ang + (h.bend > 0 ? 0 : 0);
      place(h.sl, ex + (tx - ex) * 0.1, ey + (ty - ey) * 0.1, ex + (tx - ex) * 0.62, ey + (ty - ey) * 0.62); h.sl.scale.y = 0.55 * Math.hypot(tx - ex, ty - ey); h.bn.position.set(ex, ey, 0); h.bn.rotation.z = ang + 0.5; h.bn.position.x += h.bend * 0.1; h.bn.position.y += 0.05;
      for (const f of h.H.fingers) { const w = Math.sin(t * 7 + f.off + h.ph) * 0.5 + 0.5, c = curl >= 0.95 ? 1.1 : 0.25 + 0.3 * w + curl * 0.9; f.fg.rotation.x = c * 0.55; f.j2.rotation.x = c * 0.95; f.j3.rotation.x = c * 0.8; }
      h.H.thumb.rotation.z = -0.95 + curl * 0.5; h.H.th.rotation.x = 0.2 + curl * 0.6; return { x: tx, y: ty };
    }
    let t = 0, tick = 0, st = 0, over = 0, grpT = 0, snd = 0, pickDone = false;
    for (const h of hs) { h.tip = pose(h, h.hx, 0, 0, 0); }
    addFx((dt) => {
      t += dt; snd -= dt; const gone = doll !== d0 || !doll;
      if (gone && st < 3) { st = 3; over = t; hapStop(); }
      // ---- heave: mounds bulge, hands erupt one by one ----
      for (const h of hs) {
        const tt = t - h.delay; if (tt < 0) continue; if (h.ms < 1) { if (h.ms === 0.01) { dirt(h.hx, 0.1, 10, 4.5); shake(0.2); for (const c of h.clods) { c.visible = true; c.userData.v = { x: rnd(-2, 2), y: rnd(3, 6) }; } sfx.thud && sfx.thud(); } h.ms = Math.min(1, h.ms + dt * 6); h.mound.scale.set(1.1 * h.ms, 0.34 * h.ms, 0.8 * h.ms); }
        for (const c of h.clods) { const v = c.userData.v; if (v && c.visible) { v.y -= 22 * dt; c.position.x += v.x * dt; c.position.y += v.y * dt; c.rotation.x += dt * 8; if (c.position.y < 0.06 && v.y < 0) { c.userData.v = null; c.position.y = 0.06; } } }
      }
      // ---- choose who grabs what (once, after they have risen) ----
      if (!pickDone && t > 1.15 && st === 0) { pickDone = true; st = 1; const used = new Set(); zgroan(0.55, 1.0);
        const cand = doll.list.filter((q) => !q.gone && /^(foot|shin|thigh|pelvis|farm|uarm|chest|hand)/.test(q.name)); const ordered = hs.slice().sort((a, b) => a.hx - b.hx);
        for (const h of ordered) { let best = null, bd = 1e9; for (const q of cand) { if (used.has(q)) continue; const b = q.body.position, d = Math.abs(b.x - h.hx) * 1.0 + Math.max(0, b.y - 1.6) * 1.4 + (/^(foot|shin)/.test(q.name) ? -0.5 : 0); if (d < bd) { bd = d; best = q; } } if (best) { used.add(best); h.tgt = best; } } }
      // ---- hands: reach, clamp, drag ----
      tick += dt; const hit = tick > 0.35; if (hit) tick = 0; let alive = 0, clamped = 0;
      for (const h of hs) {
        const tt = t - h.delay; if (tt < 0) continue; const rise = Math.min(1, tt / 0.55), er = 1 - Math.pow(1 - rise, 3); let tx, ty, curl = 0;
        const q = h.tgt && !h.tgt.gone ? h.tgt : null;
        if (st === 3) { const k = Math.min(1, (t - over) / 0.7); tx = h.hx; ty = Math.max(-0.1, h.tip.y - 2.5 * dt * 2); curl = 0.4; h.tip = pose(h, h.hx + (h.tip.x - h.hx) * (1 - k), h.tip.y * (1 - k * 0.1) - 0.0 - dt * 2.4 * (0.4 + k), 0.4, t); continue; }
        if (q && st >= 1) { const b = q.body.position; tx = b.x; ty = Math.max(0.15, b.y); const dx = tx - h.tip.x, dy = ty - h.tip.y, d = Math.hypot(dx, dy); const sp = Math.min(d, (h.grip ? 14 : 6.5) * dt * (d > 0.3 ? 1 : 3)); if (d > 0.01) { h.tip.x += dx / d * sp; h.tip.y += dy / d * sp; } if (!h.grip && d < 0.34) { standing = false; h.grip = 1; h.gt = 0; sfx.chop && sfx.chop(); haptic({ intensity: 0.35, sharpness: 0.5 }); bloodBurst(V3(b.x, b.y, 0.5), 5, 0, 1, 4, 0.8); mood = Math.max(mood, 0.9); } if (h.grip) { h.gt += dt; tx = b.x; ty = b.y; h.tip.x = b.x + (h.tip.x - b.x) * 0.5; h.tip.y = b.y + (h.tip.y - b.y) * 0.5; curl = Math.min(1, h.gt / 0.25); clamped++; } else curl = 0.15; }
        else { const sway = Math.sin(t * 2.3 + h.ph) * 0.18, reach = (1.45 + Math.sin(t * 3 + h.ph) * 0.2) * er; h.tip.x = h.hx + sway + Math.sin(t * 4 + h.ph) * 0.06 * er; h.tip.y = reach; curl = 0; }
        if (h.grip && h.gt > 0) curl = Math.min(1, h.gt / 0.25);
        h.tip = pose(h, h.tip.x, h.tip.y, curl, t);
        if (q && h.grip) {
          const b = q.body, r = Math.min(1, 9 * dt), pull = Math.min(1, h.gt / 0.4); b.velocity.x += ((h.hx * 0.6 + cx * 0.4 - b.position.x) * 5 - b.velocity.x) * r * 0.5; b.velocity.y += (-3.5 * pull - b.velocity.y * 0.0) * r * 0.6; b.velocity.z += (-b.position.z * 10 - b.velocity.z) * r;
          if (hit) { hurt(q, 7, V3(b.position.x, b.position.y, 0.4), true, 'bleed'); bloodBurst(V3(b.position.x, b.position.y, 0.55), 3, 0, 1, 4, 0.7); }
        }
      }
      // ---- whole body is hauled down once the grips hold ----
      if (st === 1 && doll === d0) {
        if (clamped) grpT += dt; const frac = clamped / N; alive = 0;
        for (const q of doll.list) { if (q.gone) continue; alive++; const b = q.body, dx = b.position.x - cx; b.velocity.z += (-b.position.z * 10 - b.velocity.z) * Math.min(1, 8 * dt);
          if (grpT > 0.5) { const w = Math.min(1, (grpT - 0.5) / 1.2); b.velocity.x += (-dx * 2.5 - b.velocity.x * 0.4) * dt * 4; b.velocity.y -= (10 + 14 * w) * dt * (0.4 + frac); b.angularVelocity.scale(1 - Math.min(1, 3 * dt), b.angularVelocity); }
          if (grpT > 1.7 && b.position.y < 0.62 && Math.abs(dx) < 1.9) { swallow(q); dirt(b.position.x, 0.1, 8, 4); for (let i = 0; i < 3; i++) emit({ x: b.position.x + rnd(-0.3, 0.3), y: 0.15, vx: rnd(-1, 1), vy: rnd(1, 2.5), life: 0.7, s0: 0.12, s1: 0.4, c0: 0x8a6a45, c1: 0x4a3a2a, a: 0.5, smoke: true, g: -0.4 }); sfx.thud && sfx.thud(); shake(0.15); } }
        if (grpT > 0.1 && snd <= 0) { snd = 0.5; sfx.rumble && sfx.rumble(); }
        if (hit) { haptic({ intensity: 0.3, sharpness: 0.3 }); }
        if (alive === 0 || t > 9) { st = 3; over = t; hapStop(); if (!dead) hurt(doll.parts.chest, 9999, V3(cx, 0.8, 0), true, 'bleed'); popupT('DRAGGED DOWN!', V3(cx, 2.6, 0), '#9cff3a', 10); sfx.slam && sfx.slam(); shake(0.7); flash(0.22, '#201208'); for (let i = 0; i < 4; i++) dirt(cx + rnd(-1, 1), 0.1, 10, 5); zgroan(0.9, 0.85); }
      }
      if (st === 3 && t > over + 1.5) { for (const h of hs) { kill(h.g); kill(h.mound); } kill(grp); return false; } return true;
    });
  }
  // --- molotov: a flaming bottle lands and sets him alight ---
  function doMolotov(A) {
    const p = A.p.clone(), s = sideOf(p.x), from = V3(-s * (RW / 2 - 0.3), clamp(p.y + 1.2, 1.5, RH - 1), 0.8), g = new THREE.Group();
    const glass = new THREE.Mesh(new THREE.CylinderGeometry(0.15, 0.2, 0.55, 12), pbr({ color: 0x4fa35a, transparent: true, opacity: 0.85, shininess: 140 })); g.add(glass); const neck = mkM(new THREE.CylinderGeometry(0.06, 0.1, 0.25, 10), 0x4fa35a, 100); neck.position.y = 0.38; g.add(neck);
    const rag = mkM(new THREE.BoxGeometry(0.08, 0.2, 0.04), 0xe8e0c8, 5); rag.position.y = 0.56; g.add(rag); const fl = new THREE.Mesh(new THREE.ConeGeometry(0.1, 0.34, 8), new THREE.MeshBasicMaterial({ color: 0xffa030, transparent: true, opacity: 0.9, blending: THREE.AdditiveBlending })); fl.position.y = 0.78; g.add(fl); track(g); sfx.whoosh(); let t = 0; const T = 0.55;
    addFx((dt) => { t += dt; const k = Math.min(1, t / T), x = from.x + (p.x - from.x) * k, y = from.y + (p.y - from.y) * k + 2.2 * Math.sin(k * PI); g.position.set(x, y, 0.8); g.rotation.z += dt * 12 * -s; emit({ x, y: y + 0.5, vx: rnd(-0.5, 0.5), vy: rnd(0, 1), life: 0.3, s0: 0.2, s1: 0.05, c0: 0xffe070, c1: 0xff3a08, a: 0.9 });
      if (k >= 1) { kill(g); sfx.shatter && sfx.shatter(); explode(p, 2.0, 8, 24, { burn: true, size: 1.1, c0: 0xffb030, c1: 0xff3a08, flash: 0.12, fcol: '#ffb050', shake: 0.3, vol: 0.5 }); decal(p.x, Math.max(0.2, p.y), 1.3, 'scorch'); popupT('BURN!', V3(p.x, p.y + 1.0, 0), '#ff7a22', 9); let ft = 0;
        addFx((dt2) => { ft += dt2; for (let i = 0; i < 3; i++) emit({ x: p.x + rnd(-0.9, 0.9), y: Math.max(0.1, p.y - 0.4) + rnd(0, 0.3), vx: rnd(-0.6, 0.6), vy: rnd(2, 5), life: rnd(0.4, 0.8), s0: rnd(0.3, 0.5), s1: 0.1, c0: 0xffe070, c1: 0xff2a08, g: -2, a: 0.9 });
          if (doll) { let sum = 0; for (const q of doll.list) { const b = q.body.position; if (Math.abs(b.x - p.x) < 1.1 && b.y < p.y + 1.4) { q.flame = Math.max(q.flame || 0, 2.4); q.burn = Math.min(1, (q.burn || 0) + dt2 * 0.3); sum += hurt(q, dt2 * 7, null, true, 'burn'); } } if (sum) onFire = Math.max(onFire, 3); }
          return ft < 3.2; }); return false; }
      return true; });
  }
  // --- holy water: a glowing bottle shatters and the splash burns undead skin ---
  function doHolyWater(A) {
    const x = clamp(A.p.x, -RW / 2 + 0.8, RW / 2 - 0.8), g = new THREE.Group();
    const glass = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.2, 0.5, 14), pbr({ color: 0xcfe8ff, transparent: true, opacity: 0.6, shininess: 200, emissive: 0x88aadd, emissiveIntensity: 0.5 })); g.add(glass); const neck = mkM(new THREE.CylinderGeometry(0.06, 0.1, 0.22, 10), 0xcfe8ff, 100); neck.position.y = 0.36; g.add(neck); const cork = mkM(new THREE.CylinderGeometry(0.07, 0.06, 0.1, 8), 0xa07040, 10); cork.position.y = 0.52; g.add(cork);
    const cr1 = mkM(new THREE.BoxGeometry(0.06, 0.26, 0.02), 0xffd23f, 80); cr1.position.z = 0.2; g.add(cr1); const cr2 = mkM(new THREE.BoxGeometry(0.18, 0.06, 0.02), 0xffd23f, 80); cr2.position.set(0, 0.04, 0.2); g.add(cr2);
    g.position.set(x, RH - 0.4, 0.6); track(g); let vy = 0, t = 0; sfx.whoosh(); const d0 = doll;
    addFx((dt) => { t += dt; vy -= 38 * dt; g.position.y += vy * dt; g.rotation.z += dt * 6; emit({ x: g.position.x, y: g.position.y, life: 0.3, s0: 0.14, s1: 0.04, c0: 0xffffff, c1: 0xffe8a0, a: 0.8 });
      let hitY = 0.15; if (doll) for (const q of doll.list) { const b = q.body.position; if (Math.abs(b.x - g.position.x) < 0.5 && b.y < g.position.y) hitY = Math.max(hitY, b.y + 0.2); }
      if (g.position.y <= hitY) { const sp = V3(g.position.x, hitY, 0); kill(g); sfx.shatter && sfx.shatter(); ring(sp, 2.4, 0xffe8a0, 0.5); flash(0.2, '#fff6d0'); popupT('HOLY!', V3(sp.x, sp.y + 1.2, 0), '#fff2a0', 10); for (let i = 0; i < 30; i++) emit({ x: sp.x, y: sp.y, vx: rnd(-5, 5), vy: rnd(1, 7), life: rnd(0.5, 1.1), s0: 0.15, s1: 0.04, c0: 0xffffff, c1: 0xffd870, g: 8 }); let bt = 0, tk = 0;
        addFx((dt2) => { bt += dt2; tk += dt2; for (let i = 0; i < 3; i++) emit({ x: sp.x + rnd(-1, 1), y: sp.y + rnd(0, 0.5), vx: rnd(-0.5, 0.5), vy: rnd(1.5, 3.5), life: rnd(0.6, 1.2), s0: 0.3, s1: 0.9, c0: 0xffffff, c1: 0xcfd8e0, a: 0.5, smoke: true, g: -1 });
          if (doll === d0 && doll) { const tick = tk > 0.25; if (tick) tk = 0; for (const q of doll.list) { const b = q.body.position; if (Math.abs(b.x - sp.x) < 1.6 && b.y < sp.y + 2.2) { q.burn = Math.min(0.75, (q.burn || 0) + dt2 * 0.35); if (tick) { hurt(q, 6, V3(b.x, b.y, 0), true, 'burn'); sfx.sizzle && Math.random() < 0.4 && sfx.sizzle(); } } } if (tick) { mood = Math.max(mood, 0.6); haptic({ intensity: 0.3, sharpness: 0.5 }); } }
          return bt < 3.4; }); return false; }
      return true; });
  }
  // --- electric fence: a live fence drops in front of him and cooks him ---
  function doFence(A) {
    const x = clamp(A.p.x, -RW / 2 + 1.4, RW / 2 - 1.4), W = 2.5, H = 3.3, g = new THREE.Group(), wires = [];
    for (const s of [-1, 1]) { const p = mkM(new THREE.CylinderGeometry(0.08, 0.1, H, 10), 0x3a3d42, 40); p.position.set(s * W / 2, H / 2, 0); g.add(p); for (let i = 0; i < 4; i++) { const ins = mkM(new THREE.BoxGeometry(0.16, 0.1, 0.12), 0xe8e0c8, 10); ins.position.set(s * W / 2, 0.5 + i * 0.8, 0.08); g.add(ins); } }
    for (let i = 0; i < 4; i++) { const w = mkM(new THREE.CylinderGeometry(0.025, 0.025, W, 6), 0xc8d0da, 150); w.rotation.z = PI / 2; w.position.set(0, 0.5 + i * 0.8, 0.1); g.add(w); wires.push(0.5 + i * 0.8); }
    const sign = mkM(new THREE.BoxGeometry(0.5, 0.4, 0.04), 0xffd23f, 30); sign.position.set(0, 3.05, 0.1); g.add(sign); const bolt1 = mkM(new THREE.ConeGeometry(0.08, 0.28, 3), 0x1d1f24, 5); bolt1.position.set(0, 3.05, 0.13); bolt1.rotation.z = PI; g.add(bolt1);
    g.position.set(x, RH, 0.65); track(g); sfx.thud(); let t = 0, tick = 0, snd = 0; const D = 3.0, d0 = doll;
    addFx((dt) => { t += dt; const k = t < 0.25 ? t / 0.25 : 1, kin = k * k; g.position.y = t < 0.25 ? RH * (1 - kin) : (t > D - 0.3 ? (t - D + 0.3) * 25 : 0);
      if (t > 0.25 && t < D - 0.3) {
        for (let i = 0; i < 2; i++) { const a = wires[(Math.random() * 4) | 0], b = wires[(Math.random() * 4) | 0]; bolt(V3(x - W / 2 + rnd(0, W), a, 0.75), V3(x - W / 2 + rnd(0, W), b, 0.75), 0x9fd8ff, 0.12); }
        emit({ x: x + rnd(-W / 2, W / 2), y: rnd(0.4, 3), life: 0.2, s0: 0.3, s1: 0.1, c0: 0xffffff, c1: 0x4aa8ff, a: 0.8 }); snd -= dt; if (snd <= 0) { snd = 0.18; sfx.sizzle && sfx.sizzle(); } hapStart(0.45, 0.8);
        tick += dt; if (doll === d0 && doll && tick > 0.1) { tick = 0; let sum = 0; for (const q of doll.list) { const b = q.body, dx = b.position.x - x; if (Math.abs(dx) < W / 2 + 0.2 && b.position.y < H) { const pt = V3(b.position.x, b.position.y, 0.6); sum += hurt(q, 4, pt, true, 'shock'); q.zap = 0.3; bolt(V3(x + clamp(dx, -W / 2, W / 2), wires[(Math.random() * 4) | 0], 0.75), pt, 0xbfe6ff, 0.1); b.velocity.x += rnd(-3, 3); b.velocity.y += rnd(0, 2.5); b.angularVelocity.z += rnd(-6, 6); } } if (sum) { popup('-' + sum, V3(x, 2.6, 0), sum); mood = Math.max(mood, 0.9); } }
      } else if (t >= D - 0.3) hapStop();
      if (t > D + 0.2) { kill(g); hapStop(); return false; } return true; });
  }
  // --- meat grinder: sucks him into a funnel ---
  /* ---- machines: the zombie is picked up, carried to the machine and fed in so he really goes inside ---- */
  function hoist(tx, ty, dt, k, maxv) {
    standing = false;
    const c = doll.parts.chest.body, ex = tx - c.position.x, ey = ty - c.position.y, vx = clamp(ex * k, -maxv, maxv), vy = clamp(ey * k, -maxv, maxv), r = Math.min(1, 14 * dt);
    for (const q of doll.list) { if (q.gone) continue; const b = q.body; b.velocity.z = -b.position.z * 10; b.velocity.x += (vx - b.velocity.x) * r; b.velocity.y += (vy - b.velocity.y) * r; b.angularVelocity.scale(1 - Math.min(1, 7 * dt), b.angularVelocity); }
    return Math.hypot(ex, ey);
  }
  function swallow(q) { if (q.gone) return; q.gone = true; q.group.visible = false; const b = q.body; b.velocity.set(0, 0, 0); b.angularVelocity.set(0, 0, 0); }
  const chunkGeo = new THREE.IcosahedronGeometry(1, 0), chunkMat = [phong(0xb3203a, 20), phong(0xd9626f, 20), phong(0x7a1220, 10)];
  function spitChunk(list, x, y, vx, vy) { const m = new THREE.Mesh(chunkGeo, chunkMat[(Math.random() * 3) | 0]), s = rnd(0.05, 0.12); m.scale.set(s, s * rnd(0.6, 1), s); m.position.set(x, y, rnd(-0.1, 0.35)); track(m); list.push({ m, vx, vy, s }); if (list.length > 60) { const o = list.shift(); o.m.visible = false; } }
  function stepChunks(list, dt) { for (const c of list) { if (c.done) continue; c.vy -= 22 * dt; c.m.position.x += c.vx * dt; c.m.position.y += c.vy * dt; c.m.rotation.x += dt * 6; if (c.m.position.y < c.s * 0.5) { c.m.position.y = c.s * 0.4; c.done = true; } if (Math.abs(c.m.position.x) > RW / 2 - 0.1) { c.m.position.x = Math.sign(c.m.position.x) * (RW / 2 - 0.1); c.vx = 0; } } }
  const zgroan = (vol, rate) => { zvPlay('zgroan' + (1 + ((Math.random() * 3) | 0)), vol, rate) || yelp(0.5); };

  // --- meat grinder: lifted over the hopper, fed in feet first, minced out of the nozzle ---
  function doGrinder(A) {
    if (!doll) return; const x = clamp(A.p.x, -RW / 2 + 1.5, RW / 2 - 1.5), g = new THREE.Group(), d0 = doll, chunks = [];
    bx(g, roundBox(1.7, 0.9, 1.1, 0.1, 3), 0x4d555f, 0, 0.45, 0, 70); bx(g, roundBox(1.76, 0.1, 1.16, 0.04, 2), 0x8d96a3, 0, 0.93, 0, 120);
    for (let i = 0; i < 6; i++) { const st = bx(g, new THREE.BoxGeometry(0.14, 0.5, 0.02), i % 2 ? 0x1c1d22 : 0xffc400, -0.62 + i * 0.25, 0.4, 0.56, 20); st.rotation.z = 0.5; }
    const body = bx(g, new THREE.CylinderGeometry(0.8, 0.86, 0.85, 24), 0xaab3c0, 0, 1.35, 0, 140); for (const yy of [1.1, 1.6]) { const r = bx(g, new THREE.TorusGeometry(0.84, 0.035, 8, 28), 0xe2e8f0, 0, yy, 0, 160); r.rotation.x = PI / 2; }
    const fun = bx(g, new THREE.CylinderGeometry(1.08, 0.64, 1.0, 28, 1, true), 0xc4ccd8, 0, 2.2, 0, 150); fun.material.side = THREE.DoubleSide;
    const inn = new THREE.Mesh(new THREE.CylinderGeometry(1.04, 0.62, 1.0, 28, 1, true), new THREE.MeshBasicMaterial({ color: 0x4a0e12, side: THREE.BackSide })); inn.position.y = 2.2; g.add(inn);
    for (const yy of [2.7, 1.72]) { const r = bx(g, new THREE.TorusGeometry(yy > 2 ? 1.08 : 0.66, 0.07, 10, 32), 0xe9eef6, 0, yy, 0, 180); r.rotation.x = PI / 2; }
    for (let i = 0; i < 7; i++) { const a = -1.1 + i * 0.37, sp = bx(g, new THREE.BoxGeometry(0.05, rnd(0.15, 0.4), 0.02), 0x7a1018, Math.sin(a) * 0.9, 2.45, Math.cos(a) * 0.9, 5); sp.rotation.y = a; }
    const noz = bx(g, new THREE.CylinderGeometry(0.26, 0.3, 0.55, 14), 0x8d96a3, 1.05, 0.62, 0, 120); noz.rotation.z = PI / 2; const fl = bx(g, new THREE.CylinderGeometry(0.36, 0.36, 0.07, 14), 0x5a6068, 0.8, 0.62, 0, 60); fl.rotation.z = PI / 2;
    const wheel = new THREE.Group(); wheel.position.set(-1.0, 1.1, 0.0); const rim = new THREE.Mesh(new THREE.TorusGeometry(0.42, 0.06, 8, 24), phong(0x2a2d32, 60)); wheel.add(rim); for (let i = 0; i < 6; i++) { const sp = new THREE.Mesh(new THREE.BoxGeometry(0.84, 0.05, 0.05), phong(0x2a2d32, 60)); sp.rotation.z = i * PI / 6; wheel.add(sp); } const hub = new THREE.Mesh(new THREE.CylinderGeometry(0.1, 0.1, 0.16, 10), phong(0xc92a2a, 80)); hub.rotation.x = PI / 2; wheel.add(hub); wheel.position.z = 0.6; g.add(wheel);
    bx(g, roundBox(0.5, 0.42, 0.14, 0.04, 2), 0x2a2d32, -0.45, 0.55, 0.6, 40); const lr = bx(g, new THREE.SphereGeometry(0.06, 8, 6), 0xff2a2a, -0.58, 0.62, 0.69, 200), lgn = bx(g, new THREE.SphereGeometry(0.06, 8, 6), 0x2aff5a, -0.38, 0.62, 0.69, 200); bx(g, new THREE.CylinderGeometry(0.07, 0.07, 0.05, 10), 0xe0e0e0, -0.48, 0.44, 0.69, 100).rotation.x = PI / 2;
    const pipe = bx(g, new THREE.CylinderGeometry(0.06, 0.06, 1.4, 8), 0x5a6068, 0.62, 2.4, -0.6, 50);
    const tray = bx(g, roundBox(0.7, 0.06, 0.5, 0.02, 2), 0x6a717c, 1.52, 0.04, 0, 60); const mince = bx(g, new THREE.SphereGeometry(1, 12, 8), 0xa81c34, 1.6, 0.06, 0.05, 20); mince.scale.set(0.01, 0.01, 0.01);
    g.traverse((m) => { if (m.isMesh) m.castShadow = true; }); g.position.set(x, -2.6, -0.1); track(g); sfx.rumble(); hapStart(0.5, 0.4); popupT('GRIND TIME!', V3(x, 3.9, 0), '#ff5a3a', 8.5); zgroan(0.6, 0.95);
    let t = 0, tick = 0, fed = 0, st = 0, over = 0, pop = 0; const FEED = 1.35, nz = V3(x + 1.35, 0.62, 0.5);
    addFx((dt) => { t += dt; wheel.rotation.z -= dt * (st >= 1 ? 14 : 3); const run = st >= 1 && st < 3; lr.material.color.setHex(run && ((t * 6) | 0) % 2 ? 0xff2a2a : 0x4a0a0a); lgn.material.color.setHex(run ? 0x1a4a22 : 0x2aff5a);
      g.position.y = st === 0 ? -2.6 + 2.6 * Math.min(1, t / 0.4) * (2 - Math.min(1, t / 0.4)) : st === 3 ? -2.6 * Math.min(1, (t - over) / 0.4) : 0; g.position.x = x + (run ? Math.sin(t * 70) * 0.012 : 0); stepChunks(chunks, dt);
      if (doll !== d0 || !doll) { if (st < 3) { st = 3; over = t; hapStop(); } }
      else if (st === 0 && t > 0.4) { st = 1; }
      else if (st === 1) { const d = hoist(x, 4.7, dt, 9, 13); if (d < 0.6 || t > FEED + 0.6) { st = 2; zgroan(0.85, 0.9); } }
      else if (st === 2) { shake(0.1); hapStart(0.55, 0.3); tick += dt; const hit = tick > 0.11; if (hit) tick = 0, pop += 1; let alive = 0, sum = 0; const r = Math.min(1, 10 * dt);
        for (const q of doll.list) { if (q.gone) continue; const b = q.body; alive++; b.velocity.z = -b.position.z * 10; b.velocity.x += ((x - b.position.x) * 8 - b.velocity.x) * r; b.angularVelocity.scale(1 - 4 * dt, b.angularVelocity);
          if (b.position.y > 2.6) b.velocity.y = -2.2;
          else if (b.position.y > 1.3) { b.velocity.y = -0.95; if (hit) { const pt = V3(b.position.x, b.position.y, 0.5); sum += hurt(q, 6, pt, true, 'crush', 0, -1); bloodBurst(V3(x + rnd(-0.5, 0.5), 2.7, 0.7), 3, 0, 1, 5, 0.8); if (b.position.y < 2.5 && Math.random() < 0.22) tear(q, 0, -1); } }
          else { swallow(q); fed++; } }
        if (hit) { sfx.chop && sfx.chop(); haptic({ intensity: 0.4, sharpness: 0.3 }); mood = Math.max(mood, 0.9); for (let i = 0; i < 2; i++) spitChunk(chunks, nz.x, nz.y, rnd(2, 5.5), rnd(1, 4)); emit({ x: nz.x, y: nz.y, vx: rnd(3, 6), vy: rnd(1, 3), life: 0.5, s0: 0.2, s1: 0.08, c0: 0xff4a3a, c1: 0x6a0a0e, g: 12 }); bloodBurst(nz, 5, 1, 0.4, 7, 0.9); const k = Math.min(1, fed / 12); mince.scale.set(0.12 + 0.36 * k, 0.06 + 0.2 * k, 0.2 + 0.2 * k); if (sum && Math.random() < 0.5) popup('-' + sum, V3(x, 3.0, 0), sum); if (pop % 7 === 0 && !dead) zgroan(0.7, rnd(0.8, 0.95)); }
        emit({ x: x + rnd(-0.1, 0.1), y: 3.2, vx: rnd(-0.3, 0.3), vy: rnd(0.6, 1.4), life: 0.9, s0: 0.2, s1: 0.5, c0: 0x777777, c1: 0x333333, a: 0.3, smoke: true, g: -0.3 });
        if (alive === 0 || t > 9) { st = 3; over = t; hapStop(); if (!dead) hurt(doll.parts.chest, 9999, V3(x, 1, 0), true, 'crush', 0, -1); popupT('MINCED!', V3(x, 3.3, 0), '#ff3b30', 10); sfx.slam && sfx.slam(); } }
      if (st === 3 && t > over + 0.6) { kill(g); return false; } return true; });
  }
  // --- lawnmower: runs him over, chewing everything low ---
  function doMower(A) {
    const s = sideOf(A.p.x), g = new THREE.Group(), add = (geo, mat, x, y, z) => { const m = new THREE.Mesh(geo, mat); m.position.set(x, y, z); m.castShadow = true; g.add(m); return m; }, red = phong(0xc8261f, 80), dark = phong(0x1c1d22, 30);
    add(roundBox(1.5, 0.42, 1.0, 0.12, 3), red, 0, 0.5, 0); add(roundBox(0.5, 0.4, 0.5, 0.1, 2), phong(0x2b2e34, 60), -0.35, 0.86, 0); add(new THREE.CylinderGeometry(0.1, 0.1, 0.25, 8), phong(0xb8c0cc, 120), -0.35, 1.16, 0);
    for (const z of [-0.3, 0.3]) { const h = add(new THREE.BoxGeometry(0.06, 1.2, 0.06), phong(0x2a2d32, 60), -0.8, 1.15, z); h.rotation.z = 0.35; } const bar = add(new THREE.BoxGeometry(0.06, 0.06, 0.7), phong(0x2a2d32, 60), -1.05, 1.7, 0); bar.rotation.z = 0.35;
    const blade = add(new THREE.BoxGeometry(1.0, 0.04, 0.1), phong(0xc8d0da, 150), 0.1, 0.28, 0.51); const wheels = []; for (const wx of [-0.55, 0.55]) for (const wz of [-0.55, 0.55]) { const w = add(new THREE.CylinderGeometry(0.2, 0.2, 0.12, 12), dark, wx, 0.22, wz); w.rotation.x = PI / 2; wheels.push(w); }
    g.scale.x = -s; let x = -s * (RW / 2 + 2); g.position.set(x, 0, 0); track(g); sfx.rumble(); hapStart(0.5, 0.6); popupT('MOW MOW MOW!', V3(A.p.x, 2.8, 0), '#9cff3a', 8.5); let t = 0, tick = 0; const spd = 9;
    addFx((dt) => { t += dt; x += s * spd * dt; g.position.x = x; blade.rotation.z += dt * 40; for (const w of wheels) w.rotation.y += dt * 30; tick += dt; const hit = tick > 0.1; if (hit) tick = 0;
      emit({ x: x + s * 0.8, y: 0.3, vx: s * rnd(2, 6), vy: rnd(1, 4), life: 0.5, s0: 0.12, s1: 0.04, c0: 0x9cff3a, c1: 0x3a7a1a, g: 12 }); emit({ x: x - s * 1.0, y: 0.9, vx: -s * 1, vy: 0.5, life: 0.5, s0: 0.15, s1: 0.45, c0: 0x8a8580, c1: 0x4a4540, a: 0.5, smoke: true });
      if (doll) { let sum = 0; for (const q of doll.list) { const b = q.body, dx = b.position.x - (x + s * 0.8); if (Math.abs(dx) < 0.9 && b.position.y < 1.3) { b.velocity.x += s * spd * 3 * dt; b.velocity.y = Math.max(b.velocity.y, 2.5); if (hit) { const pt = V3(b.position.x, 0.35, 0.5); sum += hurt(q, 9, pt, true, 'slash', s, 0.4); bloodBurst(pt, 5, -s * 0.3, 1, 8, 0.9); if (jointOf(q) && Math.random() < 0.14) tear(q, s, 0.6); } } } if (sum) { popup('-' + sum, V3(x + s * 1.2, 1.8, 0), sum); shake(0.3); sfx.chop && sfx.chop(); haptic({ intensity: 0.5, sharpness: 0.4 }); mood = Math.max(mood, 0.9); } }
      if (Math.abs(x) > RW / 2 + 2.5 && t > 0.3) { kill(g); hapStop(); return false; } return true; });
  }
  // --- silver bullet revolver: slow powerful shot, drops him ---
  function doRevolver(A) {
    cd = 0.55; gunId = 'revolver'; gun.vis = 1.0; gun.kick = 0.5; placeGun('revolver', A.p); muzzleFlash(true); casing(true); const from = gun.muz.clone(); sfx.snipe && sfx.snipe(); shake(0.3); haptic('thud');
    let dx = A.p.x - from.x, dy = A.p.y - from.y; const L = Math.hypot(dx, dy) || 1; dx /= L; dy /= L; let best = null, bt = 30;
    if (doll) for (const q of doll.list) { const rx = q.body.position.x - from.x, ry = q.body.position.y - from.y, tp = rx * dx + ry * dy; if (tp > 0.2 && tp < bt && Math.abs(rx * dy - ry * dx) < 0.34) { bt = tp; best = q; } } if (A.part) { best = A.part; bt = L; }
    const end = best ? V3(from.x + dx * bt, from.y + dy * bt, 0) : A.p.clone(); tracer(from, end, 0xe8f2ff); tracer(from, end, 0xffffff);
    if (best) { const head = best.name === 'head'; hurt(best, head ? 150 : 70, end, false, 'bullet', dx, dy); if (jointOf(best) && head) tear(best, dx, dy); pushAt(best, dx * 22, dy * 22 + 3, end); bloodBurst(V3(end.x, end.y, 0.5), 18, dx, dy, 12, 1.2); sparks(end, 12, 0xffffff, 0xcfe0ff, 9, 0.09); ring(end, 1.0, 0xcfe8ff, 0.25); popupT(head ? 'SILVER HEADSHOT!' : 'SILVER!', V3(end.x, end.y + 1, 0), '#cfe8ff', 9.5); if (head) slow = Math.max(slow, 0.35); }
    else { decal(end.x, end.y, 0.4, 'hole'); puff(end, 0xb59a74, 6); sparks(end, 8, 0xffffff, 0xcfe0ff, 7, 0.08); }
  }
  // --- burial: dirt pours from above and buries him ---
  // --- burial: laid in a grave, shovelled over, headstone planted ---
  function ripTex() { const c = document.createElement('canvas'); c.width = 128; c.height = 160; const x = c.getContext('2d'); x.fillStyle = '#8d939c'; x.fillRect(0, 0, 128, 160); for (let i = 0; i < 260; i++) { x.fillStyle = 'rgba(' + (i % 2 ? '255,255,255' : '0,0,0') + ',0.06)'; x.fillRect(Math.random() * 128, Math.random() * 160, 3, 2); } x.fillStyle = '#4a4f57'; x.font = 'bold 54px Arial'; x.textAlign = 'center'; x.fillText('RIP', 64, 74); x.fillRect(46, 92, 36, 6); x.fillRect(58, 84, 12, 30); const tx = new THREE.CanvasTexture(c); return tx; }
  function doBurial(A) {
    if (!doll) return; const x = clamp(A.p.x, -RW / 2 + 1.35, RW / 2 - 1.35), d0 = doll, g = new THREE.Group(), dirt = phong(0x6a4a2c, 6), dirt2 = phong(0x4a3320, 6);
    const pit = new THREE.Mesh(new THREE.PlaneGeometry(2.1, 1.0), new THREE.MeshBasicMaterial({ color: 0x120a05 })); pit.rotation.x = -PI / 2; pit.position.set(0, 0.012, 0.15); g.add(pit);
    for (const e of [-1, 1]) { const r = new THREE.Mesh(new THREE.SphereGeometry(1, 14, 8, 0, 6.28, 0, PI / 2), dirt2); r.scale.set(0.5, 0.3, 0.7); r.position.set(e * 1.2, 0, 0.3); g.add(r); }
    const lip = new THREE.Mesh(new THREE.TorusGeometry(0.5, 0.05, 6, 16), dirt); lip.scale.set(2.1, 1, 1); lip.rotation.x = PI / 2; lip.position.set(0, 0.03, 0.15); g.add(lip);
    const sh = new THREE.Group(); const handle = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.035, 1.5, 8), phong(0x8a5a2a, 20)); handle.position.y = 0.75; sh.add(handle); const grip = new THREE.Mesh(new THREE.BoxGeometry(0.22, 0.05, 0.05), phong(0x8a5a2a, 20)); grip.position.y = 1.5; sh.add(grip); const blade = new THREE.Mesh(roundBox(0.34, 0.42, 0.04, 0.02, 2), phong(0xaab3c0, 120)); blade.position.y = -0.12; sh.add(blade); sh.position.set(-x * 0 + (x > 0 ? -1 : 1) * 1.5, 0.9, 0.8); sh.rotation.z = (x > 0 ? 1 : -1) * 0.5; sh.visible = false; g.add(sh);
    g.traverse((m) => { if (m.isMesh) m.castShadow = true; }); g.position.set(x, 0, 0); g.scale.set(0.01, 1, 0.01); track(g);
    const mound = new THREE.Mesh(new THREE.SphereGeometry(1, 20, 10, 0, 6.28, 0, PI / 2), dirt); mound.scale.set(1.75, 0.01, 1.2); mound.position.set(x, 0, 0.3); mound.castShadow = true; track(mound);
    const stone = new THREE.Group(); const sb = new THREE.Mesh(roundBox(0.62, 0.8, 0.14, 0.05, 2), new THREE.MeshStandardMaterial({ map: ripTex(), roughness: 0.9, metalness: 0 })); sb.position.y = 0.4; stone.add(sb); stone.position.set(x, -0.9, 1.75); stone.rotation.z = 0.08; stone.castShadow = true; track(stone);
    sfx.rumble(); popupT('BURIED ALIVE!', V3(x, 3.6, 0), '#c9a070', 8.5); zgroan(0.7, 0.95);
    let t = 0, st = 0, tt = 0, throws = 0, sw = 0, over = 0, tick = 0, mh = 0; const side = x > 0 ? -1 : 1, THROWS = 6, PERIOD = 0.72;
    addFx((dt) => { t += dt; const open = Math.min(1, t / 0.35); g.scale.set(open, 1, open);
      if (doll !== d0 || !doll) { if (st < 4) { st = 4; over = t; hapStop(); } }
      else if (st === 0 && t > 0.4) st = 1;
      else if (st === 1) { const d = hoist(x, 1.9, dt, 8, 12); if (d < 0.5 || t > 1.7) { st = 2; tt = 0; sh.visible = true; for (const q of doll.list) { const b = q.body; b.velocity.set(0, -4, 0); } } }
      else if (st === 2) { tt += dt; tick += dt; sw += dt; const hit = tick > 0.15; if (hit) tick = 0;
        const ph = (tt % PERIOD) / PERIOD, scoop = ph < 0.5 ? ph / 0.5 : 1 - (ph - 0.5) / 0.5; sh.position.x = side * (1.5 - 0.5 * Math.sin(ph * PI)); sh.position.y = 0.7 + 0.9 * Math.sin(ph * PI); sh.rotation.z = side * (0.5 - 1.5 * Math.sin(ph * PI)); sh.rotation.y = 0;
        if (Math.floor(tt / PERIOD) > throws - 1 && throws < THROWS) { throws++; for (let i = 0; i < 14; i++) emit({ x: x + side * 0.4, y: 1.5, vx: -side * rnd(1.5, 3.5), vy: rnd(1, 4), life: rnd(0.5, 0.9), s0: rnd(0.12, 0.22), s1: 0.1, c0: 0x8a6a44, c1: 0x4a3320, g: 11 }); sfx.thud && sfx.thud(); haptic({ intensity: 0.35, sharpness: 0.3 }); shake(0.12); puff(V3(x, 0.6, 0.4), 0x8a7a64, 4); if (throws === 2 || throws === 4) zgroan(0.45, 0.75); }
        mh = Math.min(1, 0.12 + throws / THROWS * 0.88); mound.scale.y = 0.01 + 1.25 * mh; stone.position.y = -0.9; mood = Math.max(mood, 0.85);
        const r = Math.min(1, 10 * dt); for (const q of doll.list) { const b = q.body, dxp = b.position.x - x; b.velocity.z = -b.position.z * 10; if (Math.abs(dxp) < 1.6) { b.velocity.x += (-dxp * 6 - b.velocity.x) * r; if (b.position.y > 0.3) b.velocity.y = Math.min(b.velocity.y, -4.5); b.angularVelocity.scale(1 - 3 * dt, b.angularVelocity); if (hit && throws > 0) hurt(q, 0.6, V3(b.position.x, b.position.y, 0.3), true, 'bleed', 0, 0); } }
        if (throws >= THROWS && tt > THROWS * PERIOD + 0.1) { st = 3; tt = 0; sh.visible = false; if (!dead) hurt(doll.parts.chest, 9999, V3(x, 0.5, 0), true, 'bleed', 0, 0); popupT('R.I.P.', V3(x, 2.6, 0), '#c9a070', 10); sfx.slam && sfx.slam(); shake(0.4); puff(V3(x, 0.5, 0.6), 0x8a7a64, 8); } }
      else if (st === 3) { tt += dt; stone.position.y = Math.min(0, -0.9 + tt * 4); if (tt > 2.2) { st = 4; over = t; } }
      if (st === 4) { const k = Math.min(1, (t - over) / 0.5); mound.scale.y = Math.max(0.01, 0.01 + 1.25 * mh * (1 - k)); stone.position.y = -0.9 * k; if (k >= 1) { kill(g); kill(mound); kill(stone); return false; } }
      return true; });
  }

  // ================= 10 extra zombie ways (50 total) =================
  const dollCx = (A) => clamp(doll ? doll.parts.chest.body.position.x : A.p.x, -RW / 2 + 1.3, RW / 2 - 1.3);
  const bx = (g, geo, col, x, y, z, sh) => { const m = mkM(geo, col, sh); m.position.set(x, y, z); g.add(m); return m; };
  // --- garbage truck: barrels through and flattens him ---
  function doTruck(A) {
    const s = sideOf(A.p.x), g = new THREE.Group(); const wheels = [];
    bx(g, roundBox(2.6, 1.0, 1.3, 0.1, 3), 0x2f7a3a, -0.4, 1.0, 0, 40); bx(g, roundBox(1.0, 1.2, 1.3, 0.12, 3), 0x3d9a4a, 1.45, 0.95, 0, 50);
    bx(g, new THREE.BoxGeometry(0.06, 0.55, 1.1), 0x9fd8ff, 1.97, 1.15, 0, 120); bx(g, new THREE.BoxGeometry(0.2, 0.2, 1.4), 0x888d96, 2.05, 0.55, 0, 80);
    for (const wx of [-1.2, 0.2, 1.5]) for (const wz of [-0.68, 0.68]) { const w = bx(g, new THREE.CylinderGeometry(0.34, 0.34, 0.2, 14), 0x1c1d22, wx, 0.34, wz, 20); w.rotation.x = PI / 2; wheels.push(w); }
    for (const lz of [-0.45, 0.45]) { const l = new THREE.Mesh(new THREE.SphereGeometry(0.1, 8, 6), new THREE.MeshBasicMaterial({ color: 0xfff3a0 })); l.position.set(2.0, 0.85, lz); g.add(l); }
    g.scale.x = -s; let x = -s * (RW / 2 + 3.2); g.position.set(x, 0, 0.15); track(g); sfx.rumble(); hapStart(0.6, 0.5); popupT('ROADKILL!', V3(A.p.x, 3.0, 0), '#9cff3a', 8.5); let t = 0, tick = 0; const spd = 10;
    addFx((dt) => { t += dt; x += s * spd * dt; g.position.x = x; for (const w of wheels) w.rotation.y += dt * 24; tick += dt; const hit = tick > 0.1; if (hit) tick = 0;
      emit({ x: x - s * 2.2, y: 1.6, vx: -s * 1.5, vy: 1, life: 0.6, s0: 0.15, s1: 0.5, c0: 0x6a6a6a, c1: 0x2a2a2a, a: 0.5, smoke: true });
      if (doll) { let sum = 0; for (const q of doll.list) { const b = q.body, dx = b.position.x - (x + s * 2.0); if (dx * s > -0.2 && dx * s < 1.0 && b.position.y < 2.1) { b.velocity.x = s * spd * 1.15; b.velocity.y = Math.max(b.velocity.y, 3); if (hit) { const pt = V3(b.position.x, Math.max(0.3, b.position.y), 0.5); sum += hurt(q, 16, pt, true, 'slam', s, 0.4); bloodBurst(pt, 5, s * 0.4, 0.8, 8, 0.9); } } else if (b.position.y < 0.5 && Math.abs(b.position.x - (x - s * 0.4)) < 1.2) { if (hit) { sum += hurt(q, 12, V3(b.position.x, 0.2, 0.5), true, 'slam', 0, -1); } b.velocity.y = Math.min(b.velocity.y, 0); } }
        if (sum) { popup('-' + sum, V3(x + s * 2, 2.2, 0), sum); shake(0.5); sfx.thud && sfx.thud(); haptic({ intensity: 0.7, sharpness: 0.3 }); mood = Math.max(mood, 0.95); } }
      if (Math.abs(x) > RW / 2 + 3.4 && t > 0.3) { kill(g); hapStop(); return false; } return true; });
  }
  // --- crowbar: hooks him and slams him into the wall ---
  function doCrowbar(A) {
    cd = 0.9; const s = sideOf(A.p.x), g = new THREE.Group(), L = 1.7; bx(g, new THREE.CylinderGeometry(0.06, 0.06, L, 10), 0xc8261f, 0, L / 2, 0, 90); const hk = bx(g, new THREE.TorusGeometry(0.2, 0.06, 8, 12, 4.2), 0xc8261f, -s * 0.2, 0.02, 0, 90); hk.rotation.z = s > 0 ? PI - 0.4 : 0.3 - 0.0; bx(g, new THREE.ConeGeometry(0.1, 0.22, 8), 0xdd3a30, 0, L + 0.08, 0, 90);
    track(g); const px = A.p.x, py = A.p.y; g.position.set(px + s * 0.9, py - 0.5, 0.4); let t = 0, hits = 0, d0 = doll;
    addFx((dt) => { t += dt; g.rotation.z = -s * (-1.1 + Math.min(1, t / 0.28) * 2.4) + (t > 0.28 ? -s * Math.min(0.4, (t - 0.28) * 2) : 0); g.position.x = px + s * (0.9 - Math.min(1, t / 0.28) * 0.9);
      if (hits === 0 && t > 0.2 && doll === d0 && doll) { hits = 1; sfx.chop && sfx.chop(); shake(0.4); haptic('thud'); let sum = 0; const p = V3(px, py, 0.5); for (const q of doll.list) { const b = q.body.position; if (Math.hypot(b.x - px, b.y - py) < 1.1) { sum += hurt(q, 26, p, true, 'slam', -s, 0.3); pushAt(q, -s * 30, 3, p); } } sparks(p, 10, 0xffffff, 0xff7a3a, 8, 0.07); bloodBurst(p, 12, -s, 0.3, 10, 1); if (sum) { popup('-' + sum, p, sum); mood = 0.95; } popupT('CRACK!', V3(px, py + 0.9, 0), '#ffd24a', 8.5); }
      if (hits === 1 && t > 0.55 && doll === d0 && doll) { hits = 2; let sum = 0; const wall = -s * RW / 2; for (const q of doll.list) { const b = q.body; b.velocity.x = -s * 34; b.velocity.y += 2; } sfx.thud && sfx.thud(); shake(0.35); }
      if (hits === 2 && doll === d0 && doll) { let sum = 0; for (const q of doll.list) { const b = q.body; if (Math.abs(b.position.x) > RW / 2 - 0.5 && Math.abs(b.velocity.x) > 8) { const pt = V3(b.position.x, b.position.y, 0.4); sum += hurt(q, 10, pt, true, 'slam', -s, 0); bloodBurst(pt, 4, -s * 0.5, 0.2, 7, 0.9); } } if (sum) { hits = 3; popup('-' + sum, V3(-s * (RW / 2 - 0.6), 2, 0), sum); shake(0.6); sfx.thud && sfx.thud(); haptic('thud'); } }
      if (t > 1.6) { kill(g); return false; } return true; });
  }
  // --- wood chipper: feet first ---
  // --- wood chipper: carried up onto the feed chute, slid between the rollers and chipped out of the spout ---
  function doChipper(A) {
    if (!doll) return; const f = A.p.x >= 0 ? -1 : 1, xm = -f * (RW / 2 - 1.6), g = new THREE.Group(), d0 = doll, chunks = [], rollers = [];
    const OR = 0xe8731a; bx(g, roundBox(1.5, 2.1, 1.3, 0.14, 3), OR, 0, 1.25, 0, 60); bx(g, roundBox(1.56, 0.22, 1.36, 0.06, 2), 0x2a2d32, 0, 2.3, 0, 40); bx(g, roundBox(1.6, 0.18, 1.0, 0.05, 2), 0x2a2d32, 0.1, 0.22, 0, 30);
    bx(g, roundBox(0.62, 1.0, 1.1, 0.08, 2), 0xc95c10, -0.98, 0.9, 0, 40); for (let i = 0; i < 5; i++) bx(g, new THREE.BoxGeometry(0.04, 0.8, 0.02), 0x1c1d22, -0.98 + (i - 2) * 0.1, 0.9, 0.56, 10);
    for (const wx of [-0.55, 0.45]) { const w = bx(g, new THREE.CylinderGeometry(0.34, 0.34, 0.14, 16), 0x16171b, wx, 0.34, 0.66, 10); w.rotation.x = PI / 2; const hb = bx(g, new THREE.CylinderGeometry(0.14, 0.14, 0.16, 10), 0xb8c0cc, wx, 0.34, 0.66, 120); hb.rotation.x = PI / 2; }
    const sign = bx(g, new THREE.BoxGeometry(0.5, 0.28, 0.02), 0xffc400, 0.1, 1.15, 0.66, 20); for (let i = 0; i < 4; i++) bx(g, new THREE.BoxGeometry(0.06, 0.3, 0.025), 0x1c1d22, -0.08 + i * 0.12, 1.15, 0.665, 5).rotation.z = 0.5;
    const T = new THREE.Vector2(2.15, 3.0), M = new THREE.Vector2(0.75, 1.8), len = T.distanceTo(M), ang = Math.atan2(T.y - M.y, T.x - M.x);
    const plate = bx(g, new THREE.BoxGeometry(len, 0.07, 0.95), 0x2a2d32, (T.x + M.x) / 2, (T.y + M.y) / 2, 0, 40); plate.rotation.z = ang; const back = bx(g, new THREE.BoxGeometry(len, 0.5, 0.05), OR, (T.x + M.x) / 2, (T.y + M.y) / 2 + 0.2, -0.5, 60); back.rotation.z = ang; const rail = bx(g, new THREE.BoxGeometry(len, 0.07, 0.05), 0x8d96a3, (T.x + M.x) / 2, (T.y + M.y) / 2 + 0.06, 0.5, 60); rail.rotation.z = ang;
    for (const ry of [2.0, 1.62]) { const rg = new THREE.Group(); rg.position.set(0.78, ry, 0); const cy = new THREE.Mesh(new THREE.CylinderGeometry(0.17, 0.17, 0.95, 12), phong(0x8d96a3, 140)); cy.rotation.x = PI / 2; rg.add(cy); for (let i = 0; i < 6; i++) { const a = i * PI / 3, tooth = new THREE.Mesh(new THREE.BoxGeometry(0.07, 0.05, 0.95), phong(0x5a6068, 60)); tooth.position.set(Math.cos(a) * 0.19, Math.sin(a) * 0.19, 0); tooth.rotation.z = a; rg.add(tooth); } g.add(rg); rollers.push(rg); }
    const spout = new THREE.Group(); spout.position.set(-0.35, 2.4, 0); const s1 = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.34, 0.8, 14), phong(OR, 60)); s1.position.y = 0.4; spout.add(s1); const s2 = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.3, 0.65, 14), phong(OR, 60)); s2.position.set(-0.22, 0.95, 0); s2.rotation.z = 0.9; spout.add(s2); g.add(spout);
    const ex = bx(g, new THREE.CylinderGeometry(0.06, 0.06, 0.7, 8), 0x5a6068, -1.05, 1.75, 0, 80);
    g.traverse((m) => { if (m.isMesh) m.castShadow = true; }); g.scale.x = f; g.position.set(xm, -3.0, 0); track(g);
    const spW = V3(xm - f * 0.88, 3.7, 0.2), pathP = (lx, ly) => V3(xm + f * lx, ly, 0), P0 = pathP(T.x, T.y), MM = pathP(M.x, M.y);
    let dx = MM.x - P0.x, dy = MM.y - P0.y; const L = Math.hypot(dx, dy); dx /= L; dy /= L; let nx = -dy, ny = dx; if (ny < 0) { nx = -nx; ny = -ny; }
    sfx.rumble(); hapStart(0.5, 0.7); popupT('CHIP CHIP!', V3(xm + f * 1.1, 4.4, 0), '#e0771f', 8.5); zgroan(0.6, 0.95);
    let t = 0, tick = 0, st = 0, over = 0, pop = 0; const stage = { x: xm + f * 2.0, y: 5.0 };
    addFx((dt) => { t += dt; const run = st >= 1 && st < 3; for (const r of rollers) r.rotation.z += dt * (run ? 16 : 2) * -f; g.position.y = st === 0 ? -3.0 + 3.0 * Math.min(1, t / 0.4) * (2 - Math.min(1, t / 0.4)) : st === 3 ? -3.0 * Math.min(1, (t - over) / 0.45) : 0; g.rotation.z = run ? Math.sin(t * 60) * 0.006 : 0; stepChunks(chunks, dt);
      if (run && Math.random() < 0.5) { emit({ x: xm + f * 0, y: 3.45, vx: -f * rnd(0.6, 1.4), vy: rnd(0.8, 1.6), life: 0.8, s0: 0.2, s1: 0.5, c0: 0x888888, c1: 0x333333, a: 0.3, smoke: true, g: -0.3 }); }
      if (doll !== d0 || !doll) { if (st < 3) { st = 3; over = t; hapStop(); } }
      else if (st === 0 && t > 0.45) st = 1;
      else if (st === 1) { const d = hoist(stage.x, stage.y, dt, 9, 13); if (d < 0.6 || t > 1.9) { st = 2; zgroan(0.85, 0.9); } }
      else if (st === 2) { shake(0.12); hapStart(0.6, 0.6); tick += dt; const hit = tick > 0.1; if (hit) { tick = 0; pop++; } let alive = 0, sum = 0; const r = Math.min(1, 10 * dt);
        for (const q of doll.list) { if (q.gone) continue; alive++; const b = q.body; b.velocity.z = -b.position.z * 10; const lx = (b.position.x - xm) * f, rx = b.position.x - P0.x, ry = b.position.y - P0.y, along = rx * dx + ry * dy, perp = (rx - nx * 0.45) * nx + (ry - ny * 0.45) * ny - 0.0;
          if (lx > 0.78 || b.position.y > 2.35) { const sp = along < 0.6 ? 2.8 : 1.9; b.velocity.x = dx * sp - nx * perp * 7; b.velocity.y = dy * sp - ny * perp * 7; b.angularVelocity.scale(1 - 4 * dt, b.angularVelocity); }
          else { b.velocity.x = -f * 1.5; b.velocity.y = (1.8 - b.position.y) * 4; b.angularVelocity.scale(1 - 6 * dt, b.angularVelocity); if (hit) { const pt = V3(b.position.x, b.position.y, 0.5); sum += hurt(q, 12, pt, true, 'slash', -f, 0.3); bloodBurst(V3(xm + f * 0.78, 1.8, 0.7), 4, f * 0.6, 0.6, 8, 0.9); if (lx > 0.3 && Math.random() < 0.2) tear(q, -f, 0.4); } if (lx < 0.15) swallow(q); } }
        if (hit) { sfx.chop && sfx.chop(); haptic({ intensity: 0.5, sharpness: 0.6 }); mood = Math.max(mood, 0.95); for (let i = 0; i < 3; i++) { spitChunk(chunks, spW.x, spW.y, -f * rnd(2.5, 6), rnd(1.5, 4.5)); } for (let i = 0; i < 4; i++) emit({ x: spW.x, y: spW.y, vx: -f * rnd(3, 8), vy: rnd(1, 5), life: 0.7, s0: 0.1, s1: 0.04, c0: Math.random() < 0.5 ? 0xd9b27a : 0xcc1122, c1: 0x7a5a30, g: 11 }); if (sum) popup('-' + sum, V3(xm + f * 0.5, 2.9, 0), sum); if (pop % 7 === 0 && !dead) zgroan(0.7, rnd(0.8, 0.95)); }
        if (alive === 0 || t > 9) { st = 3; over = t; hapStop(); if (!dead) hurt(doll.parts.chest, 9999, V3(xm, 1, 0), true, 'slash', -f, 0.3); popupT('CHIPPED!', V3(xm, 3.6, 0), '#ff3b30', 10); sfx.slam && sfx.slam(); } }
      if (st === 3 && t > over + 0.7) { kill(g); return false; } return true; });
  }
  // --- spike pit: floor spikes shoot up ---
  function doSpikePit(A) {
    const x = dollCx(A), g = new THREE.Group(), sp = []; for (let i = 0; i < 7; i++) { const c = bx(g, new THREE.ConeGeometry(0.11, 1.3, 8), 0xb8c0cc, (i - 3) * 0.34, 0.65, ((i % 2) - 0.5) * 0.4, 130); c.userData.h = rnd(0.8, 1.2); sp.push(c); }
    g.position.set(x, 0, 0.3); track(g); const slab = new THREE.Mesh(new THREE.BoxGeometry(2.6, 0.06, 1.2), phong(0x15100c, 5)); slab.position.set(x, 0.03, 0.3); track(slab); sfx.rumble(); shake(0.3); popupT('IMPALED!', V3(x, 3.0, 0), '#ff5a5a', 8.5);
    let t = 0, tick = 0; const D = 3.2, d0 = doll, up = 0.12;
    addFx((dt) => { t += dt; const k = t < up ? t / up : (t > D ? Math.max(0, 1 - (t - D) / 0.3) : 1); for (const c of sp) { c.scale.y = Math.max(0.01, k * c.userData.h); c.position.y = 0.65 * c.scale.y; } tick += dt;
      if (t < up + 0.02 && !g.userData.launched && doll === d0 && doll) { g.userData.launched = 1; sfx.thud && sfx.thud(); for (const q of doll.list) { const b = q.body; if (Math.abs(b.position.x - x) < 1.5 && b.position.y < 1.5) { b.velocity.y = 9; b.velocity.x *= 0.3; hurt(q, 14, V3(b.position.x, 0.5, 0.3), true, 'stab', 0, 1); } } }
      if (doll === d0 && doll && t > 0.2 && t < D) { const hit = tick > 0.18; if (hit) tick = 0; let sum = 0; for (const q of doll.list) { const b = q.body; if (Math.abs(b.position.x - x) < 1.4 && b.position.y < 1.4) { b.velocity.y = Math.max(b.velocity.y, -3); b.velocity.x *= 1 - 2.5 * dt; if (hit) { const pt = V3(b.position.x, Math.min(b.position.y, 1), 0.3); sum += hurt(q, 9, pt, true, 'stab', 0, 1); bloodBurst(pt, 4, 0, 1, 6, 0.8); } } } if (sum) { popup('-' + sum, V3(x, 1.8, 0), sum); haptic({ intensity: 0.4, sharpness: 0.7 }); mood = 0.9; } }
      if (t > D + 0.4) { kill(g); kill(slab); return false; } return true; });
  }
  // --- zombie dog: leaps on him and mauls ---
  function doZDog(A) {
    const s = sideOf(A.p.x), g = new THREE.Group(), legs = []; bx(g, roundBox(0.9, 0.38, 0.34, 0.1, 3), 0x6b7a4f, 0, 0.55, 0, 15); const hd = bx(g, roundBox(0.38, 0.3, 0.32, 0.08, 3), 0x7a8a5a, 0.62, 0.72, 0, 15); bx(g, new THREE.BoxGeometry(0.28, 0.1, 0.24), 0x2a0a0c, 0.86, 0.66, 0, 5); bx(g, new THREE.BoxGeometry(0.4, 0.08, 0.1), 0xc83a3a, 0.2, 0.62, 0.17, 5);
    for (const e of [-1, 1]) { const ey = new THREE.Mesh(new THREE.SphereGeometry(0.05, 8, 6), new THREE.MeshBasicMaterial({ color: 0xf0ff4a })); ey.position.set(0.74, 0.8, e * 0.12); g.add(ey); }
    const tail = bx(g, new THREE.CylinderGeometry(0.03, 0.05, 0.5, 6), 0x6b7a4f, -0.55, 0.7, 0, 15); tail.rotation.z = 0.8;
    for (const lx of [-0.3, 0.3]) for (const lz of [-0.12, 0.12]) { const l = bx(g, new THREE.BoxGeometry(0.1, 0.38, 0.1), 0x5a6a42, lx, 0.2, lz, 10); legs.push(l); }
    g.scale.x = -s; let x = s * (RW / 2 + 0.8); g.position.set(x, 0, 0.25); track(g); sfx.screech && sfx.screech(); popupT('GRRRR!', V3(A.p.x, 2.8, 0), '#9cff3a', 8.5);
    let t = 0, st = 0, bt = 0, tick = 0, ph = 0; const d0 = doll, D = 2.8; let tgt = null;
    addFx((dt) => { t += dt; ph += dt * 16;
      if (doll !== d0 || !doll) { st = 3; }
      if (st === 0) { const cxp = doll.parts.chest.body.position.x; x += -s * 8 * dt; g.position.x = x; g.position.y = Math.abs(Math.sin(ph)) * 0.12; for (let i = 0; i < legs.length; i++) legs[i].rotation.z = Math.sin(ph + i * 1.6) * 0.7; if (Math.abs(cxp - x) < 1.3) { st = 1; tgt = doll.parts.head || doll.parts.chest; } }
      else if (st === 1) { bt += dt; tick += dt; const b = tgt.body.position; g.position.x += (b.x - s * 0.25 - g.position.x) * dt * 14; g.position.y += (Math.max(0.1, b.y - 0.4) - g.position.y) * dt * 10; g.rotation.z = Math.sin(bt * 30) * 0.25; hd.rotation.z = Math.sin(bt * 40) * 0.25;
        for (const q of doll.list) { if (q === tgt) { q.body.velocity.x += Math.sin(bt * 22) * 14 * dt * 20; q.body.velocity.y += Math.cos(bt * 18) * 3 * dt * 20; } }
        if (tick > 0.12) { tick = 0; const pt = V3(b.x, b.y, 0.5); const sum = hurt(tgt, 11, pt, true, 'bite', -s, 0.2); bloodBurst(pt, 5, -s * 0.3, 0.6, 7, 0.9); if (sum) { popup('-' + sum, V3(b.x, b.y + 0.5, 0), sum); haptic({ intensity: 0.4, sharpness: 0.6 }); shake(0.15); mood = 0.95; } if (jointOf(tgt) && Math.random() < 0.06) tear(tgt, -s, 0.4); }
        if (bt > D) st = 2; }
      else { x += s * 9 * dt; g.position.x = x; g.position.y = Math.abs(Math.sin(ph)) * 0.12; g.rotation.z = 0; for (let i = 0; i < legs.length; i++) legs[i].rotation.z = Math.sin(ph + i * 1.6) * 0.7; if (Math.abs(x) > RW / 2 + 1.2) { kill(g); return false; } }
      if (st === 3) { kill(g); return false; } return true; });
  }
  // --- noose: hang him from a dead tree ---
  function doNoose(A) {
    const x = dollCx(A), g = new THREE.Group(); const br = bx(g, new THREE.CylinderGeometry(0.1, 0.16, 3.4, 8), 0x3a2a1c, 0, RH - 0.4, 0, 6); br.rotation.z = PI / 2; const tw = bx(g, new THREE.CylinderGeometry(0.04, 0.07, 1.0, 6), 0x3a2a1c, 0.9, RH - 0.1, 0, 6); tw.rotation.z = -0.7; g.position.set(x, 0, 0); track(g);
    const rope = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.035, 1, 6), phong(0xb08a54, 5)); track(rope); popupT('HANG IN THERE', V3(x, 3.3, 0), '#c9a070', 8.5); sfx.rumble(); const d0 = doll;
    let t = 0, tick = 0, snapped = false; const D = 3.6, ay = RH - 0.45;
    addFx((dt) => { t += dt; const head = doll && doll === d0 ? doll.parts.head : null; let hx = x, hy = ay - 1.4;
      if (head) { const b = head.body; hx = b.position.x; hy = b.position.y;
        if (!snapped) { const tx = x, ty = ay - 2.0; const k = Math.min(1, t / 0.6); b.velocity.y += (ty - b.position.y) * 40 * k * dt + 14 * k * dt; b.velocity.x += (tx - b.position.x) * 6 * k * dt; b.velocity.x *= 1 - 1.2 * dt; b.velocity.y *= 1 - 2 * dt;
          for (const q of doll.list) if (q !== head) { q.body.velocity.x *= 1 - 0.4 * dt; q.body.angularVelocity.scale(1 - 0.6 * dt, q.body.angularVelocity); }
          tick += dt; if (tick > 0.25 && t > 0.5) { tick = 0; const s2 = hurt(head, 8, V3(hx, hy, 0.5), true, 'choke', 0, 0); if (s2) { popup('-' + s2, V3(hx, hy + 0.5, 0), s2); haptic({ intensity: 0.3, sharpness: 0.3 }); mood = 0.95; } } } }
      const ddx = hx - x, ddy = hy + 0.2 - ay, len = Math.max(0.1, Math.hypot(ddx, ddy)); rope.scale.y = len; rope.position.set(x + ddx / 2, ay + ddy / 2, 0); rope.rotation.z = Math.atan2(-ddx, ddy);
      if (!snapped && t > D) { snapped = true; popupT('SNAP!', V3(hx, hy + 0.8, 0), '#ffd24a', 8); puff(V3(x, ay, 0), 0x8a6a44, 6); } if (snapped) { rope.visible = false; } if (t > D + 1.2 || (!head && t > 0.6)) { kill(g); kill(rope); return false; } return true; });
  }
  // --- explosive barrels: a chain of blasts ---
  function doBarrels(A) {
    const x = dollCx(A), bs = []; for (let i = 0; i < 3; i++) { const g = new THREE.Group(); bx(g, new THREE.CylinderGeometry(0.34, 0.34, 0.8, 14), 0xc8261f, 0, 0, 0, 40); bx(g, new THREE.CylinderGeometry(0.355, 0.355, 0.12, 14), 0xf2c230, 0, 0.15, 0, 40); bx(g, new THREE.CylinderGeometry(0.355, 0.355, 0.12, 14), 0xf2c230, 0, -0.2, 0, 40); const bxp = x + (i - 1) * 0.95; g.position.set(bxp, RH + i * 1.4, 0.15 + (i % 2) * 0.2); track(g); bs.push({ g, vy: 0, x: bxp, landed: false, fuse: 0.55 + i * 0.5, boom: false }); }
    popupT('BOOM BOOM BOOM', V3(x, 3.4, 0), '#ff9a2a', 8.5); let t = 0;
    addFx((dt) => { t += dt; let alive = 0;
      for (const b of bs) { if (b.boom) continue; alive++; if (!b.landed) { b.vy -= 26 * dt; b.g.position.y += b.vy * dt; b.g.rotation.z += dt * 2; if (b.g.position.y <= 0.4) { b.g.position.y = 0.4; b.landed = true; b.g.rotation.z = 0; sfx.thud && sfx.thud(); puff(V3(b.x, 0.2, 0), 0x8a8580, 3); } } else { b.fuse -= dt; if (b.fuse < 0.3) b.g.children.forEach((c) => c.material.emissive && c.material.emissive.setRGB(Math.sin(t * 40) * 0.5 + 0.5, 0.1, 0)); if (b.fuse <= 0) { b.boom = true; const p = V3(b.x, 0.8, 0); kill(b.g); explode(p, 3.0, 26, 55, { burn: true, size: 1.8 }); sparks(p, 14, 0xffd24a, 0xff3a10, 10, 0.09); } } }
      if (!alive) return false; return true; });
  }
  // --- brain bait: lures a horde that turns on him ---
  function doBrainBait(A) {
    const bait = new THREE.Group(); bx(bait, new THREE.SphereGeometry(0.28, 14, 10), 0xe88aa0, 0, 0, 0, 80).scale.set(1.2, 0.9, 1); bx(bait, new THREE.CylinderGeometry(0.025, 0.025, 1.2, 6), 0x8a8f98, 0, 0.8, 0, 60); const bX = clamp(A.p.x, -RW / 2 + 1.2, RW / 2 - 1.2), bY = Math.max(0.9, Math.min(A.p.y, 2.2)); bait.position.set(bX, bY, 0.4); track(bait); popupT('BRAAAINS!', V3(bX, bY + 1.1, 0), '#ff8aa8', 9); sfx.screech && sfx.screech();
    const cols = [0x5d7090, 0x7a4a4a, 0x4a6a4a, 0x6a5a3a, 0x555a70, 0x6a4a6a], figs = [], d0 = doll;
    const vars = [{ tie: true }, { brain: true, skin: 0xa8bf86 }, { noArm: 1, skin: 0x92ae74 }, { runner: true, skin: 0xa4b880, tie: false }, { skin: 0x8fa878, hair: 0x6a6258 }, { crawl: true, tie: false, skin: 0x93aa78 }];
    for (let i = 0; i < 6; i++) { const side = i % 2 ? 1 : -1, g = zWalker(cols[i], vars[i]); g.position.set(side * (RW / 2 + 0.8 + (i >> 1) * 1.1), 0, -0.1 + (i % 3) * 0.42); g.scale.setScalar(vars[i].crawl ? 1.05 : 1.08 + (i % 2) * 0.05); g.visible = false; track(g); figs.push({ g, side, v: vars[i], ph: rnd(0, 6), off: (i - 2.5) * 0.95 + rnd(-0.1, 0.1), tick: rnd(0, 0.3), delay: i * 0.18 + rnd(0, 0.2), prevS: 0, moan: rnd(0.5, 2) }); }
    let t = 0, turn = -1;
    addFx((dt) => { t += dt; const cx = doll && doll === d0 ? doll.parts.chest.body.position.x : bX, eaten = bait.userData.gone === 1; bait.position.y = bY + Math.sin(t * 4) * 0.06; bait.rotation.z = Math.sin(t * 3) * 0.15;
      for (const f of figs) { const g = f.g; if (t < f.delay) continue; g.visible = true; const tx = (eaten ? cx : bX) + f.off, dx = tx - g.position.x; g.rotation.y = (dx > 0 ? 1 : -1) * PI / 2;
        const sp = f.v.crawl ? 2.3 : f.v.runner ? 7.5 : 4.2 * (0.55 + 0.9 * Math.max(0, Math.sin(f.ph * 0.5 + 1))), tm = t * 1 + f.ph, far = Math.abs(dx) > 0.3;
        if (far) { f.ph += dt * (f.v.crawl ? 5 : f.v.runner ? 12 : 8); g.position.x += clamp(dx, -1, 1) * sp * dt; zAnim(g, f.ph, 'walk', tm); const sg = Math.sign(Math.sin(f.ph)); if (sg !== f.prevS && f.prevS !== 0) dirtPuff(V3(g.position.x, 0.02, 0), 2); f.prevS = sg; f.moan -= dt; if (f.moan <= 0) { f.moan = rnd(2, 4); if (Math.random() < 0.5) sfx.screech && sfx.screech(); } }
        else { f.near = true; g.position.x += (tx - g.position.x) * dt * 4;
          if (!(eaten && doll === d0 && doll)) zAnim(g, f.ph, 'reach', tm);
          else { zAnim(g, f.ph, 'bite', tm); f.tick -= dt; if (f.tick <= 0) { f.tick = 0.28; let best = null, bd = 9; for (const q of doll.list) { const d = Math.abs(q.body.position.x - g.position.x) + Math.abs(q.body.position.y - 0.9) * 0.4; if (d < bd) { bd = d; best = q; } } if (best && bd < 2.2) { const b = best.body.position, pt = V3(b.x, b.y, 0.5), sum = hurt(best, 9, pt, true, 'bite', f.side, 0.2); bloodBurst(pt, 4, f.side * 0.3, 0.6, 7, 0.9); if (sum) { popup('-' + sum, V3(b.x, b.y + 0.4, 0), sum); mood = 0.95; } best.body.velocity.x += -f.side * 4; if (jointOf(best) && Math.random() < 0.05) tear(best, -f.side, 0.3); } } } }
        g.position.y = 0; }
      if (turn < 0 && figs.filter((f) => f.near).length >= 2) turn = t + 1.0;
      if (turn > 0 && !bait.userData.gone && t > turn) { bait.userData.gone = 1; kill(bait); popupT('NOM NOM!', V3(bX, bY + 0.8, 0), '#ff8aa8', 8.5); puff(V3(bX, bY, 0), 0xe88aa0, 6); turn = 1e9; }
      if (t > 8) { for (const f of figs) kill(f.g); kill(bait); return false; } return true; });
  }
  // --- sky drop: launched high, slammed into the floor ---
  function doSkyDrop(A) {
    const x = dollCx(A), d0 = doll; if (!doll) return; popupT('SKY DROP!', V3(x, 3.4, 0), '#7ac8ff', 9); sfx.whoosh && sfx.whoosh(); haptic('thud'); let t = 0, st = 0, landed = false;
    for (const q of doll.list) { q.body.velocity.set(rnd(-1, 1), 44, 0); q.body.angularVelocity.set(0, 0, rnd(-5, 5)); }
    addFx((dt) => { t += dt; if (doll !== d0 || !doll) return false; const c = doll.parts.chest.body;
      if (st === 0) { if (t < 0.5) { for (const q of doll.list) q.body.velocity.y = Math.max(q.body.velocity.y, 40); emit({ x: c.position.x + rnd(-0.3, 0.3), y: c.position.y, vx: rnd(-0.5, 0.5), vy: -rnd(2, 5), life: 0.5, s0: 0.15, s1: 0.05, c0: 0xbfe6ff, c1: 0x7a9ac0, a: 0.6 }); } if (t > 0.62 || c.position.y > RH - 0.9) { st = 1; popupT('DOWN!', V3(c.position.x, RH - 1.2, 0), '#ffd24a', 8); for (const q of doll.list) { q.body.velocity.set(rnd(-0.6, 0.6), -52, 0); } } }
      else if (st === 1) { emit({ x: c.position.x + rnd(-0.3, 0.3), y: c.position.y + 0.5, vx: 0, vy: rnd(2, 5), life: 0.4, s0: 0.15, s1: 0.05, c0: 0xffffff, c1: 0x7a9ac0, a: 0.6 }); for (const q of doll.list) q.body.velocity.y = Math.min(q.body.velocity.y, -30);
        if (c.position.y < 1.0) { st = 2; const p = V3(c.position.x, 0.2, 0.4); let sum = 0; for (const q of doll.list) { sum += hurt(q, 24, V3(q.body.position.x, Math.max(0.2, q.body.position.y), 0.4), true, 'slam', 0, -1); q.body.velocity.set(rnd(-4, 4), 5, 0); bloodBurst(V3(q.body.position.x, 0.3, 0.5), 4, rnd(-1, 1), 1, 8, 1); } ring(p, 3.2, 0xffffff, 0.5); puff(p, 0x9a8a74, 12); sparks(p, 14, 0xffffff, 0xcfe0ff, 9, 0.09); decal(p.x, 0.02, 1.6, 'scorch'); shake(1.1); flash(0.3, '#fff'); sfx.boom && sfx.boom(0.8); haptic('thud'); mood = 1; if (sum) popup('-' + sum, V3(p.x, 1.5, 0), sum); return false; } }
      if (t > 2.5) return false; return true; });
  }
  // --- sunlight beam: burns him to ash ---
  function doSunbeam(A) {
    const x = dollCx(A), g = new THREE.Group(), mat = new THREE.MeshBasicMaterial({ color: 0xfff0a0, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide }); const beam = new THREE.Mesh(new THREE.CylinderGeometry(0.55, 1.1, RH, 20, 1, true), mat); beam.position.y = RH / 2; g.add(beam); g.position.set(x, 0, 0.3); track(g);
    const sun = new THREE.Mesh(new THREE.SphereGeometry(0.5, 14, 10), new THREE.MeshBasicMaterial({ color: 0xfff6c0 })); sun.position.set(x, RH + 0.1, 0.2); track(sun); popupT('SUNRISE!', V3(x, 3.4, 0), '#ffe27a', 9); sfx.rumble(); flash(0.35, '#fff3b0');
    let t = 0, tick = 0; const D = 3.6, d0 = doll;
    addFx((dt) => { t += dt; const k = Math.min(1, t / 0.3) * (t > D ? Math.max(0, 1 - (t - D) / 0.4) : 1); mat.opacity = (0.32 + Math.sin(t * 25) * 0.05) * k; sun.scale.setScalar(0.8 + k * 0.4); tick += dt;
      if (doll === d0 && doll && t > 0.25 && t < D) { const hit = tick > 0.14; if (hit) tick = 0; let sum = 0; for (const q of doll.list) { const b = q.body, p = b.position; if (Math.abs(p.x - x) < 1.2) { q.flame = Math.max(q.flame || 0, 1.2); q.burn = Math.min(1, (q.burn || 0) + dt * 0.5); setTint(q, q.burn, 0); b.velocity.y += 4 * dt; emit({ x: p.x + rnd(-0.2, 0.2), y: p.y + rnd(-0.2, 0.2), vx: rnd(-0.6, 0.6), vy: rnd(1, 3), life: rnd(0.6, 1.0), s0: 0.1, s1: 0.2, c0: 0x6a6a6a, c1: 0x222222, a: 0.7, smoke: true }); if (Math.random() < 0.25) emit({ x: p.x + rnd(-0.2, 0.2), y: p.y, vx: rnd(-0.4, 0.4), vy: rnd(1, 3), life: 0.5, s0: 0.06, s1: 0.02, c0: 0xffd24a, c1: 0xff5a10 }); if (hit) sum += hurt(q, 6, null, true, 'burn'); } } if (sum) { onFire = Math.max(onFire, 3); popup('-' + sum, V3(x, 2.2, 0), sum); mood = 0.95; haptic({ intensity: 0.3, sharpness: 0.5 }); sfx.sizzle && Math.random() < 0.5 && sfx.sizzle(); } }
      if (t > D + 0.5) { kill(g); kill(sun); return false; } return true; });
  }

  /* ---- using a tool ---- */
  /* tap anywhere near the zombie and the way snaps onto him (drag-in assist, like Kick the Buddy) */
  const snapTo = (A, part) => { if (!doll || dead) return A; const b = doll.parts[part || 'chest'].body.position; if (Math.abs(A.p.x - b.x) < 1.7) { const q = Object.assign({}, A); q.p = V3(b.x, A.p.y, A.p.z); return q; } return A; };
  function useStart(x, y) {
    ptr.down = true; ptr.x = x; ptr.y = y; if (grace > 0) grace = 0; const A = aim(x, y);
    switch (tool) {
      case 'hammer': if (cd <= 0) doHammer(A.p); break;
      case 'shotgun': if (cd <= 0) doShotgun(A); break;
      case 'dynamite': if (cd <= 0) { cd = 0.28; spawnDynamite(A.p); } break;
      case 'rocket': if (cd <= 0) doRocket(A); break;
      case 'anvil': if (cd <= 0) { cd = 0.5; spawnAnvil(A.p); } break;
      case 'saw': if (cd <= 0) { cd = 0.5; spawnSaw(A.p); } break;
      case 'hole': if (cd <= 0) { cd = 1.0; openHole(snapTo(A).p); } break;
      case 'katana': katanaStart(A.p); break;
      case 'grenade': if (cd <= 0) { cd = 0.4; spawnGrenade(A.p); } break;
      case 'mine': if (cd <= 0) { cd = 0.4; spawnMine(snapTo(A).p); } break;
      case 'ball': if (cd <= 0) { cd = 1.2; spawnBall(A.p); } break;
      case 'lightning': if (cd <= 0) { cd = 0.7; doLightning(A); } break;
      case 'guillotine': if (cd <= 0) { cd = 1.1; doGuillotine(snapTo(A, 'head')); } break;
      case 'meteor': if (cd <= 0) { cd = 1.4; doMeteor(A); } break;
      case 'crossbow': if (cd <= 0) doCrossbow(A); break;
      case 'fence': if (cd <= 0) { cd = 3.0; doFence(A); } break;
      case 'acid': if (cd <= 0) { cd = 1.5; doAcid(A); } break;
      case 'beartrap': if (cd <= 0) { cd = 0.5; spawnBeartrap(snapTo(A, 'pelvis').p); } break;
      case 'nuke': if (cd <= 0) { cd = 2.2; doNuke(A); } break;
      case 'grinder': if (cd <= 0) { cd = 4.0; doGrinder(A); } break;
      case 'axe': if (cd <= 0) doAxe(A); break;
      case 'holy': if (cd <= 0) { cd = 1.0; doHolyWater(A); } break;
      case 'airstrike': if (cd <= 0) { cd = 3.0; doAirstrike(A); } break;
      case 'crusher': if (cd <= 0) { cd = 2.2; doCrusher(snapTo(A)); } break;
      case 'bat': if (cd <= 0) doBat(A); break;
      case 'coffin': if (cd <= 0) { cd = 1.0; spawnPiano(snapTo(A).p, true); } break;
      case 'graves': if (cd <= 0) { cd = 3.8; doGraveyard(A); } break;
      case 'sniper': if (cd <= 0) doSniper(A); break;
      case 'molotov': if (cd <= 0) { cd = 0.9; doMolotov(A); } break;
      case 'horde': if (cd <= 0) { cd = 4.0; doHorde(A); } break;
      case 'machete': if (cd <= 0) doMachete(A); break;
      case 'shovel': if (cd <= 0) doShovel(A); break;
      case 'revolver': if (cd <= 0) doRevolver(A); break;
      case 'mower': if (cd <= 0) { cd = 1.6; doMower(A); } break;
      case 'burial': if (cd <= 0) { cd = 3.0; doBurial(A); } break;
      case 'truck': if (cd <= 0) { cd = 2.0; doTruck(A); } break;
      case 'crowbar': if (cd <= 0) doCrowbar(A); break;
      case 'chipper': if (cd <= 0) { cd = 4.0; doChipper(A); } break;
      case 'spikepit': if (cd <= 0) { cd = 2.0; doSpikePit(A); } break;
      case 'zdog': if (cd <= 0) { cd = 3.4; doZDog(A); } break;
      case 'noose': if (cd <= 0) { cd = 4.2; doNoose(A); } break;
      case 'barrels': if (cd <= 0) { cd = 3.0; doBarrels(A); } break;
      case 'brainbait': if (cd <= 0) { cd = 5.0; doBrainBait(A); } break;
      case 'skydrop': if (cd <= 0) { cd = 2.8; doSkyDrop(A); } break;
      case 'sunbeam': if (cd <= 0) { cd = 4.2; doSunbeam(A); } break;
      case 'pistol': case 'flame': case 'chainsaw': case 'minigun': gunId = tool; gun.vis = 0.3; gun.kick = 0; break;
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
    for (let i = effects.length - 1; i >= 0; i--) { let keep = false; try { keep = effects[i](dt); } catch (err) { console.error('fx', err); } if (!keep) effects.splice(i, 1); }
    for (let i = things.length - 1; i >= 0; i--) { const t = things[i]; t.mesh.position.copy(t.body.position); if (t.kind !== 'saw' || true) t.mesh.quaternion.copy(t.body.quaternion); if (t.kind === 'saw') t.mesh.quaternion.set(0, 0, 0, 1); let ok = false; try { ok = t.update(dt); } catch (err) { console.error('thing', err); } if (!ok) { try { dropThing(t); } catch (err) {} things.splice(i, 1); } }
    updRockets(dt); updHoles(dt); updAcid(dt);
    if (doll) for (const q of doll.list) {
      if (q.flame > 0) { q.flame -= dt; const b = q.body, n = (dt * 60 * 0.9) | 0 || (Math.random() < 0.9 ? 1 : 0); for (let i = 0; i < n; i++) { emit({ x: b.position.x + rnd(-0.12, 0.12), y: b.position.y + rnd(-0.1, 0.2), vx: rnd(-0.6, 0.6), vy: rnd(1.5, 3.2), life: rnd(0.3, 0.55), s0: 0.22, s1: 0.06, c0: 0xffd45a, c1: 0xff3a08, g: -1, a: 0.85 }); } if (Math.random() < 0.3) emit({ x: b.position.x, y: b.position.y + 0.2, vy: rnd(1, 2.4), vx: rnd(-0.4, 0.4), life: 0.8, s0: 0.2, s1: 0.8, c0: 0x4a4540, c1: 0x1c1a18, g: -1, a: 0.5, smoke: true }); if (Math.random() < 0.05) hurt(q, 1, null, true); }
      if (q.shock > 0 && !(tzOn && ptr.down)) { q.shock = Math.max(0, q.shock - dt * 6); setTint(q, q.burn || 0, q.shock); }
    }
    updateGore(dt); updParticles(dt); updDecals(dt);
    if (mood > 0) mood -= dt; { const st = dead ? 2 : mood > 0 ? faceKind : 0; if (st !== faceHurt) { faceHurt = st; setFace(st); } if (groanMouth > 0 && doll) { groanMouth -= dt; const f = doll.parts.head.group.userData.face; if (f && f.mouth) { const base = faceHurt === 2 ? 2.7 : faceHurt === 3 ? 2.2 : 1.9; f.mouth.scale.y = groanMouth > 0 ? base * (1 + 0.22 * Math.sin(performance.now() * 0.03)) : base; } } }
    shakeAmp *= Math.pow(0.002, dt); if (shakeAmp < 0.004) shakeAmp = 0;
  }
  /* the zombie shambles on his feet until something hurts him, grabs him or shoves him: then he drops like a ragdoll */
  function standStep(h) {
    if (!doll || dead || hold.on) { standing = false; return; }
    standT += h; const r = Math.min(1, 12 * h), sw = Math.sin(standT * 1.3) * 0.035; let far = 0;
    for (const s of standRest) {
      const b = s.q.body; if (s.q.gone) continue; const arm = /arm|hand/.test(s.q.name), a = arm ? Math.sin(standT * 1.8 + s.ph) * 0.05 : 0, hd = s.q.name === 'head' ? Math.sin(standT * 0.9) * 0.04 : 0;
      const tx = s.p.x + sw + a + hd, ty = s.p.y, dx = tx - b.position.x, dy = ty - b.position.y, dz = s.p.z - b.position.z; far = Math.max(far, Math.hypot(dx, dy));
      b.velocity.x += (dx * 12 - b.velocity.x) * r; b.velocity.y += (dy * 12 - b.velocity.y) * r; b.velocity.z += (dz * 12 - b.velocity.z) * r;
      b.angularVelocity.scale(1 - r, b.angularVelocity); { const qq = b.quaternion, rq = s.r, sg = qq.x * rq.x + qq.y * rq.y + qq.z * rq.z + qq.w * rq.w < 0 ? -1 : 1, tt = Math.min(1, 9 * h); qq.x += (rq.x * sg - qq.x) * tt; qq.y += (rq.y * sg - qq.y) * tt; qq.z += (rq.z * sg - qq.z) * tt; qq.w += (rq.w * sg - qq.w) * tt; const nn = Math.hypot(qq.x, qq.y, qq.z, qq.w) || 1; qq.x /= nn; qq.y /= nn; qq.z /= nn; qq.w /= nn; }
    }
    if (far > 0.5) standing = false;
  }
  function waysStep(h) { if (standing) standStep(h); if (mag.on) magnetStep(h); for (const x of holes) holePull(x); if (doll) for (const q of doll.list) { if (q.ice > 0) { const b = q.body; b.velocity.scale(1 - 0.05 * q.ice, b.velocity); b.angularVelocity.scale(1 - 0.05 * q.ice, b.angularVelocity); if (frozenT > 0) { b.force.y += b.mass * cfg().gravity; b.velocity.scale(0.92, b.velocity); b.angularVelocity.scale(0.9, b.angularVelocity); } } } }
  function clearWays() { clearThings(); effects.length = 0; endUse(); hideGuns(); mood = 0; faceHurt = 0; groanMouth = 0; grace = 1.6; hp = MAXHP; dead = false; deadT = 0; stumps.length = 0; onFire = 0; slow = 0; hpShown = -1; hpBar(); frozenT = 0; mag.on = false; buzzStop(); clearPins(); for (const o of fxObjs.splice(0)) scene.remove(o); for (const c of casings.splice(0)) scene.remove(c.m); }

  /* ------------------------------------------------------------------ 6. input + loop */
  let orbitId = -1, orbitLast = null, acc = 0, last = 0, running = false;
  function bindInput() {
    const el = renderer.domElement, seen = {};
    el.addEventListener('pointerdown', (e) => {
      const now = performance.now(); seen[e.pointerId] = now;
      /* heal a stuck pointer (a lost pointerup would otherwise block every tap): the same id pressing again, or one silent for 1.2s, is stale */
      const stale = (id) => id >= 0 && (id === e.pointerId || now - (seen[id] || 0) > 1200);
      if (stale(ptr.id)) { ptr.id = -1; endUse(); }
      if (stale(hold.id) || (hold.on && hold.id < 0)) { release(); hold.id = -1; }
      if (stale(orbitId)) { orbitId = -1; orbitLast = null; }
      if (hold.on || orbitId >= 0 || ptr.id >= 0) return; audioInit();
      try { el.setPointerCapture(e.pointerId); } catch (x) {}
      if (tool === 'hand') { if (grab(e.clientX, e.clientY)) { hold.id = e.pointerId; } }
      else { ptr.id = e.pointerId; useStart(e.clientX, e.clientY); }
      e.preventDefault();
    });
    el.addEventListener('pointermove', (e) => {
      seen[e.pointerId] = performance.now();
      if (e.pointerId === hold.id) moveHold(e.clientX, e.clientY);
      if (e.pointerId === ptr.id) useMove(e.clientX, e.clientY);
    });
    const up = (e) => { if (e.pointerId === ptr.id) { ptr.id = -1; endUse(); } if (e.pointerId === hold.id) { release(); hold.id = -1; } if (e.pointerId === orbitId) { orbitId = -1; orbitLast = null; } };
    el.addEventListener('pointerup', up); el.addEventListener('pointercancel', up); el.addEventListener('lostpointercapture', up); window.addEventListener('pointerup', up); window.addEventListener('blur', () => { ptr.id = -1; endUse(); release(); hold.id = -1; orbitId = -1; orbitLast = null; });
    document.getElementById('btnReset').addEventListener('click', () => { audioInit(); haptic('tick'); clearBlood(); ptr.id = -1; orbitId = -1; orbitLast = null; hold.id = -1; resetDoll(); });
  }

  function frame(t) {
    requestAnimationFrame(frame);
    const raw = t - last; watchQuality(raw); let dt = Math.min(0.11, Math.max(0.0001, raw / 1000)); last = t; if (slow > 0) { slow -= dt; dt *= 0.3; }
    if (mode === 'play') {
      acc += dt; let n = 0;
      try { while (acc >= FIX && n < MAXSUB) { driveHold(); waysStep(FIX); world.step(FIX); acc -= FIX; n++; } } catch (err) { acc = 0; console.error('step', err); }
      if (acc > FIX) acc = 0;
      try { safety(); sync(); } catch (err) { console.error('sync', err); }
      try { updateWays(dt); } catch (err) { console.error('ways', err); }
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
    initWorld(); initScene(); initFx(); initGore(); initWays2(); sfxPlus(); initWays3(); sfx4(); initProps(); if (mode !== 'play') resetDoll(); if (m !== 'edit' && (m || window.mode || 'play') === 'play') { buildPanel(); setTool('hand'); loadShop(); }
    try {
      lib.showGameParameters({
        name: '50 Ways to Kill a Zombie',
        params: {
          'Gravity': { key: 'gravity', type: 'slider', min: 6, max: 45, step: 1, onChange: (v) => { window.gameConfig.gravity = v; applyConfig(); } },
          'Wall bounce': { key: 'bounce', type: 'slider', min: 0, max: 0.8, step: 0.05, onChange: (v) => { window.gameConfig.bounce = v; applyConfig(); } },
          'Zombie size': { key: 'scale', type: 'slider', min: 0.5, max: 1, step: 0.02, onChange: (v) => { window.gameConfig.scale = v; resetDoll(); } },
          'Grab strength': { key: 'grab', type: 'slider', min: 0.4, max: 2, step: 0.1, onChange: (v) => { window.gameConfig.grab = v; } },
          'Unlock all ways (testing)': { key: 'unlockAll', type: 'checkbox', onChange: (v) => { window.gameConfig.unlockAll = !!v; refreshPanel(); } }
        }
      });
    } catch (e) {}
    if (mode === 'play') bindInput(); else { document.getElementById('hint').classList.add('off'); document.getElementById('btnReset').style.display = 'none'; const pn = document.getElementById('panel'); if (pn) pn.style.display = 'none'; }
    window.__rag = { face: setFace, yelp, scream, setHp: (v) => { hp = v; hpBar(); }, addCoins: (n) => addCoins(n), world, get doll() { return doll; }, cam, camera, grab, moveHold, release, hold, resetDoll, setTool, useStart, useMove, endUse, ptr, TOOLS, get dmg() { return totalDmg; }, things, holes, rockets, P, step: (n) => { for (let i = 0; i < n; i++) { driveHold(); waysStep(FIX); world.step(FIX); } sync(); updateWays(n * FIX); }, render: () => { placeCamera(); renderer.render(scene, camera); }, ROOM: [RW, RH, RD], scene, gunMeshes, gun };
    window.__quality = (force) => { if (force != null) { autoQ = null; applyQuality(force); } return { tier: TIERS[qTier].name, fps: autoQ && autoQ.lastFps }; };
    if (!running) { running = true; requestAnimationFrame(frame); }
    preloadImages(['wood_back', ...TOOLS.map((t) => t.asset)].map(assetUrl), setLoaderProgress).then(() => hideLoader(700, () => setTimeout(introDrop, 150)));
  }
  window.run = run;
})();
