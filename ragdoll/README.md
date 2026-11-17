# 40 Ways to Kill the Ragdoll
Kick the Buddy-style ragdoll sandbox. Pick an item from the scrollable grid at the bottom, then use it on the ragdoll.

Wreck the ragdoll to earn coins, then buy new ways to kill him. 40 ways in total: 10 are free, 30 more unlock with coins. The "Unlock all ways (testing)" checkbox in the settings panel (gameConfig.unlockAll) opens every way for testing; switch it off before publishing. Each way has its own damage, physics, particles, sound and haptics. Damage total shows top-left.

## Files
- `index.html` — HUD, item panel and the `#loader` loading screen (shown while the libraries and pictures download).
- `game.js` — the whole sandbox: room, ragdoll physics, the ways, shop and `run(mode)`.
- `loader.js` — preloads every item picture, drives the loading bar and fades the loading screen out.
- `tests/loader.test.mjs` — unit test for the loading-bar math (`node tests/loader.test.mjs`).
- `quality.js` — automatic graphics quality (no menu, always on): guesses a tier (low / mid / high / ultra) from the device, then watches the median fps and steps resolution, shadows, particle density and physics rate down or back up.
- `batch.js` — draws each particle pool (sparks, smoke, blood drops) as a single batched point cloud instead of hundreds of sprites.
- `tests/quality.test.mjs` — unit tests for the tier guess and the auto-quality controller.
