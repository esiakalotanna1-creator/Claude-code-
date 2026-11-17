import assert from 'node:assert';
import { TIERS, initialTier, AutoQuality } from '../quality.js';
// device guesses
assert.strictEqual(initialTier({ mobile: true, cores: 4, memory: 2 }), 0);
assert.strictEqual(initialTier({ mobile: true, cores: 8, memory: 8 }), 2);
assert.strictEqual(initialTier({ mobile: false, cores: 8, memory: 8 }), 3);
assert.strictEqual(initialTier({ mobile: false, cores: 16, gpu: 'Google SwiftShader' }), 0);
// tiers get cheaper going down
for (let i = 1; i < TIERS.length; i++) assert.ok(TIERS[i].pr >= TIERS[i - 1].pr && TIERS[i].fx >= TIERS[i - 1].fx && TIERS[i].iters >= TIERS[i - 1].iters);
// slow frames step down, fast frames eventually step back up (but not straight into a tier that just failed)
const q = new AutoQuality(2, { warm: 0, win: 10 });
let r = null; for (let i = 0; i < 10; i++) r = q.sample(33); assert.strictEqual(r, 1);
for (let i = 0; i < 40; i++) q.sample(33); assert.strictEqual(q.tier, 0);
for (let i = 0; i < 200; i++) q.sample(16); assert.strictEqual(q.tier, 0, 'blocked right after failing');
for (let i = 0; i < 4000; i++) q.sample(16); assert.ok(q.tier >= 1, 'recovers once the block expires');
// long stalls are ignored
const z = new AutoQuality(3, { warm: 0, win: 10 }); for (let i = 0; i < 50; i++) assert.strictEqual(z.sample(900), null); assert.strictEqual(z.tier, 3);
console.log('quality tests ok');
