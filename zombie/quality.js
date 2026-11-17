/* Auto graphics quality: picks a starting tier from the device, then watches the real frame rate in the
 * background and steps the tier down (or back up) so the game holds a smooth fps. No UI — always "auto". */

// tier 0 = lowest. pr: max pixel ratio, shadow: 0 off / 1 basic / 2 soft, map: shadow map size,
// fx: share of cosmetic particles kept, iters: physics solver iterations, step: physics rate (Hz), sub: max physics steps per frame
export const TIERS = [
  { name: 'low', pr: 0.75, shadow: 0, map: 0, fx: 0.45, iters: 9, step: 60, sub: 2, decals: 40 },
  { name: 'mid', pr: 1, shadow: 1, map: 512, fx: 0.7, iters: 12, step: 90, sub: 3, decals: 70 },
  { name: 'high', pr: 1.5, shadow: 1, map: 1024, fx: 1, iters: 16, step: 120, sub: 4, decals: 130 },
  { name: 'ultra', pr: 2, shadow: 2, map: 1024, fx: 1, iters: 22, step: 120, sub: 6, decals: 130 }
];

// first guess from what the browser tells us about the hardware
export function initialTier(d) {
  const cores = d.cores || 4, mem = d.memory || 4, gpu = (d.gpu || '').toLowerCase();
  if (d.lowGpu || /swiftshader|llvmpipe|software|mali-[4t][0-9]{0,2}\b|adreno \(tm\) [1-4][0-9]{2}\b|powervr sgx/.test(gpu)) return 0;
  if (!d.mobile) return cores >= 8 && mem >= 8 ? 3 : 2;
  if (cores <= 4 || mem <= 2) return 0;
  if (cores <= 6 || mem <= 4) return 1;
  return 2;
}

const median = (a) => { const s = a.slice().sort((x, y) => x - y); return s[s.length >> 1]; };

// feed it every frame's duration in ms; it answers with a new tier index when the tier should change
export class AutoQuality {
  constructor(tier, opt = {}) {
    this.tier = tier; this.max = opt.max == null ? TIERS.length - 1 : opt.max;
    this.win = opt.win || 90; this.low = opt.low || 47; this.high = opt.high || 57; this.goodNeeded = opt.goodNeeded || 4;
    this.samples = []; this.good = 0; this.warm = opt.warm == null ? 45 : opt.warm; this.blocked = {}; this.fails = {}; this.t = 0;
  }
  sample(ms) {
    if (this.warm > 0) { this.warm--; return null; }
    if (!(ms > 0) || ms > 250) return null; // tab switches, stalls while loading
    this.t += ms; this.samples.push(ms); if (this.samples.length < this.win) return null;
    const fps = 1000 / median(this.samples); this.samples.length = 0; this.lastFps = fps;
    // too slow: drop a tier, and keep the failed tier off for longer each time it fails
    if (fps < this.low && this.tier > 0) { const f = this.fails[this.tier] = (this.fails[this.tier] || 0) + 1; this.blocked[this.tier] = this.t + 40000 * 2 ** (f - 1); this.good = 0; this.warm = 20; return --this.tier; }
    if (fps > this.high) { this.good++; const up = this.tier + 1; if (this.good >= this.goodNeeded && up <= this.max && !(this.blocked[up] > this.t)) { this.good = 0; this.warm = 20; return ++this.tier; } }
    else this.good = 0;
    return null;
  }
}
