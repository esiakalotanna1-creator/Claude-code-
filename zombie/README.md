# 50 Ways to Kill a Zombie
Kick the Buddy-style zombie sandbox in a ruined room. Pick an item from the scrollable grid at the bottom, then use it on the zombie.

Wreck the zombie to earn coins, then buy new ways to kill him. 50 ways in total: 25 are free, 25 more unlock with coins. The "Unlock all ways (testing)" checkbox in the settings panel (gameConfig.unlockAll) opens every way for testing; switch it off before publishing. Each way has its own damage, physics, particles, sound and haptics. Damage total shows top-left. The zombie starts rotten but intact; wounds, blood, ribs and bones appear part by part as he takes damage, and a new zombie resets them.

## Files
- `index.html` — HUD, item panel and the `#loader` loading screen (shown while the libraries and pictures download).
- `game.js` — the whole sandbox: ruined room, zombie physics, the ways, shop and `run(mode)`.
- `loader.js` — preloads every item picture, drives the loading bar and fades the loading screen out.
- `tests/loader.test.mjs` — unit test for the loading-bar math (`node tests/loader.test.mjs`).
- `quality.js` — automatic graphics quality (no menu, always on): guesses a tier (low / mid / high / ultra) from the device, then watches the median fps and steps resolution, shadows, particle density and physics rate down or back up.
- `batch.js` — draws each particle pool (sparks, smoke, blood drops) as a single batched point cloud instead of hundreds of sprites.
- `tests/quality.test.mjs` — unit tests for the tier guess and the auto-quality controller.
