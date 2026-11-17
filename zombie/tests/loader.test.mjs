import assert from 'node:assert';
import { loadFraction } from '../loader.js';
assert.strictEqual(loadFraction(0, 0), 1);
assert.ok(Math.abs(loadFraction(0, 10) - 0.15) < 1e-9);
assert.strictEqual(loadFraction(10, 10), 1);
assert.strictEqual(loadFraction(20, 10), 1);
assert.ok(loadFraction(5, 10) > loadFraction(4, 10));
console.log('loader tests ok');
