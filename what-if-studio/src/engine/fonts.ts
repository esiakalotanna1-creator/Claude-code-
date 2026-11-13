import { loadFont } from '@remotion/fonts';
import { staticFile } from 'remotion';
import { STUDIO } from '../studio.config';

// Three faces: a heavy display face for the title card, a mono for on-screen readouts (timers, labels, chips),
// and a handwriting face for chalk and notes. The Google faces load at render time (they need a connection);
// a local title face from studio.config.ts loads from public/ and works offline.

// Local copies of the three Google faces (public/fonts/, latin subset), so renders work offline and behind a proxy.
for (const w of ['600', '700', '800']) loadFont({ family: 'Bricolage Grotesque', url: staticFile('fonts/bricolage-' + w + '.woff2'), weight: w });
loadFont({ family: 'Fragment Mono', url: staticFile('fonts/fragment-400.woff2'), weight: '400' });
for (const w of ['400', '700']) loadFont({ family: 'Kalam', url: staticFile('fonts/kalam-' + w + '.woff2'), weight: w });
if (STUDIO.titleFont) loadFont({ family: STUDIO.titleFont.family, url: staticFile(STUDIO.titleFont.file), weight: STUDIO.titleFont.weight });

export const FONT = {
  title: STUDIO.titleFont ? STUDIO.titleFont.family : 'Bricolage Grotesque',
  ui: 'Fragment Mono',
  hand: 'Kalam',
};
