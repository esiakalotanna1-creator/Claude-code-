/* One-draw-call particle batch: hands out sprite-like slots ({ position, scale, material.color, material.opacity,
 * visible }) so the effect code can treat them like THREE.Sprite, but all of them render as a single THREE.Points. */
export function makeSpriteBatch(THREE, scene, n, map, additive) {
  const pos = new Float32Array(n * 3), col = new Float32Array(n * 3), size = new Float32Array(n), alpha = new Float32Array(n), geo = new THREE.BufferGeometry();
  const attr = (a, k) => { const b = new THREE.BufferAttribute(a, k); b.setUsage(THREE.DynamicDrawUsage); return b; };
  geo.setAttribute('position', attr(pos, 3)); geo.setAttribute('color', attr(col, 3)); geo.setAttribute('size', attr(size, 1)); geo.setAttribute('alpha', attr(alpha, 1)); geo.setDrawRange(0, 0);
  const mat = new THREE.ShaderMaterial({
    uniforms: { map: { value: map }, uScale: { value: 500 } }, transparent: true, depthWrite: false, blending: additive ? THREE.AdditiveBlending : THREE.NormalBlending,
    vertexShader: 'attribute float size; attribute float alpha; attribute vec3 color; uniform float uScale; varying vec3 vC; varying float vA;\n' +
      'void main() { vC = color; vA = alpha; vec4 mv = modelViewMatrix * vec4(position, 1.0); gl_Position = projectionMatrix * mv; gl_PointSize = max(1.0, size * projectionMatrix[1][1] * uScale / -mv.z); }',
    fragmentShader: 'uniform sampler2D map; varying vec3 vC; varying float vA;\nvoid main() { vec4 t = texture2D(map, gl_PointCoord); gl_FragColor = vec4(vC * t.rgb, t.a * vA); if (gl_FragColor.a < 0.004) discard; }'
  });
  const pts = new THREE.Points(geo, mat); pts.frustumCulled = false; pts.renderOrder = 6; scene.add(pts);
  const slots = []; for (let i = 0; i < n; i++) slots.push({ position: new THREE.Vector3(), scale: new THREE.Vector3(1, 1, 1), material: { color: new THREE.Color(), opacity: 1 }, visible: false });
  // write the visible slots into the buffers; call once per frame before rendering. viewH: drawing-buffer height in px
  function flush(viewH) {
    mat.uniforms.uScale.value = viewH * 0.5; let k = 0;
    for (let i = 0; i < n; i++) { const s = slots[i]; if (!s.visible) continue; const j = k * 3, p = s.position, c = s.material.color; pos[j] = p.x; pos[j + 1] = p.y; pos[j + 2] = p.z; col[j] = c.r; col[j + 1] = c.g; col[j + 2] = c.b; size[k] = s.scale.x; alpha[k] = s.material.opacity; k++; }
    geo.setDrawRange(0, k); if (k) { for (const a of ['position', 'color', 'size', 'alpha']) { const b = geo.attributes[a]; b.updateRange.offset = 0; b.updateRange.count = k * b.itemSize; b.needsUpdate = true; } }
  }
  return { slots, flush, points: pts };
}
