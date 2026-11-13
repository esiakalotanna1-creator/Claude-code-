import React from 'react';
import {
  Hero, Pose, basePose, poseAt, faceAt, kf, clamp, easeOut, easeIn, rnd, camT, LOOKS, LEG_LEN, HEAD, joints, toWorld,
  Kitchen, KITCHEN, stand, Rooftop, Schematic, SCH, SchLabel, CountUp, DrawOn, TitleCard, HudChip, Sparkle, Glow, Foreground, Stars,
  CookieStack, ShotProps,
} from '../../engine';

// "What if every jump took you twice as high?" Twelve shots: the kitchen, the rooftop, the sky, the schematic and
// space. The power: a JUMP chip with the jump's number and height, a whoosh trail under him. Each shot is a pure
// function of its own clock t.

const PIP = LOOKS.pipHood;
const GOLD = '#FFC857';

/** The JUMP chip: names the jump and how high it goes. */
const Chip: React.FC<{ t: number; label: string }> = ({ t, label }) => (t < 2 ? null : <HudChip f={t} label={label} icon="dot" />);

/** Speed lines under a rising body: short streaks, fading. */
const Trail: React.FC<{ x: number; y: number; t: number; n?: number; len?: number; o?: number }> = ({ x, y, t, n = 9, len = 240, o = 0.7 }) => (
  <g opacity={o}>
    {Array.from({ length: n }).map((_, i) => {
      const dx = (rnd(7, i) - 0.5) * 160;
      const ph = (t * 0.35 + rnd(3, i)) % 1;
      return <path key={i} d={`M ${x + dx} ${y + 40 + ph * 200} L ${x + dx} ${y + 40 + ph * 200 + len * (0.4 + rnd(5, i))}`} stroke="#FFF6E0" strokeWidth={6} strokeLinecap="round" opacity={1 - ph} />;
    })}
  </g>
);

/** A cookie jar: glass, a cork lid, cookies inside. x y = the base centre. */
const Jar: React.FC<{ x: number; y: number; s?: number; rot?: number }> = ({ x, y, s = 1, rot = 0 }) => (
  <g transform={`translate(${x} ${y}) rotate(${rot}) scale(${s})`}>
    <ellipse cx={0} cy={2} rx={34} ry={7} fill="#000" opacity={0.3} />
    <rect x={-30} y={-78} width={60} height={78} rx={14} fill="#CFE4EA" opacity={0.55} stroke="#2A2230" strokeWidth={4} />
    {[[-12, -18], [10, -22], [-2, -40], [-14, -52], [12, -50]].map(([cx, cy], i) => (
      <g key={i}>
        <circle cx={cx} cy={cy} r={13} fill="#C98A4A" stroke="#7A4A22" strokeWidth={2} />
        <circle cx={cx - 3} cy={cy - 2} r={2.6} fill="#4A2A18" />
        <circle cx={cx + 4} cy={cy + 3} r={2.2} fill="#4A2A18" />
      </g>
    ))}
    <rect x={-24} y={-92} width={48} height={16} rx={5} fill="#9A6A42" stroke="#2A2230" strokeWidth={4} />
    <rect x={-20} y={-72} width={8} height={54} rx={4} fill="#FFFFFF" opacity={0.35} />
  </g>
);

// ---------- the kitchen: Pip under the top shelf ----------
const K_STAND = stand(KITCHEN, 0.7, 0.16);
const JAR = KITCHEN.P(0.7, 0.3, 0.02);
const kBase: Partial<Pose> = { x: K_STAND.x, y: K_STAND.y, scale: K_STAND.scale, yaw: 0.15, look: 0.2 };
// how high the hips must rise for his raised mitten to reach the jar
const REACH = (() => {
  const p = { ...basePose, ...kBase, armR: { a: 172, b: 0 } } as Pose;
  const h = toWorld(p, joints(p).armR.end);
  return h.y - (JAR.y - 46);
})();

export const S1: React.FC<ShotProps> = ({ t, len }) => {
  const pose = poseAt(t, [
    { f: 0, p: { ...kBase, headTilt: -14, armL: { a: 16, b: -6 }, armR: { a: 16, b: -6 } } },
    { f: 8, p: { squash: 0.04 } },
    { f: 16, p: { squash: 0.2, armL: { a: -38, b: 10 }, armR: { a: -38, b: 10 }, tilt: 8 }, ease: easeOut },
  ]);
  return (
    <g transform={camT(K_STAND.x - 20, kf(t, [[0, 470], [len, 480]]), kf(t, [[0, 1.75], [len, 1.85]]))}>
      <Kitchen t={t + 20} id="k1" />
      <Jar x={JAR.x} y={JAR.y} s={0.75} />
      <Hero look={PIP} pose={{ ...pose, ...faceAt(t, [[0, 'smug']]) }} rimId="rimR" shadow={0.5} />
      <Foreground blur={10}>
        <path d="M 1290 1000 Q 1320 780 1440 720 Q 1400 840 1420 1000 Z" fill="#0E1610" />
      </Foreground>
    </g>
  );
};

export const S2: React.FC<ShotProps> = ({ t, len }) => {
  const up = Math.sin(Math.PI * clamp((t - 3) / 24));
  const grabbed = t >= 14;
  const pose = poseAt(t, [
    { f: 0, p: { ...kBase, squash: 0.2, armL: { a: -38, b: 10 }, armR: { a: -38, b: 10 }, tilt: 8 } },
    { f: 4, p: { squash: -0.18, armL: { a: 150, b: 6 }, armR: { a: 172, b: 0 }, tilt: 0, headTilt: -10 }, ease: easeOut },
    { f: 10, p: { squash: -0.05 } },
    { f: 18, p: { armR: { a: 150, b: 40 }, headTilt: 0 } },
    { f: 26, p: { squash: 0, armL: { a: 40, b: 20 } } },
    { f: 28, p: { squash: 0.22 }, ease: easeOut },
    { f: 31, p: { squash: 0.05 } },
  ]);
  const p = { ...pose, y: pose.y - REACH * up };
  const hand = toWorld(p, joints(p).armR.end);
  return (
    <g transform={camT(960, 520, kf(t, [[0, 1.02], [len, 1.08]]))}>
      <Kitchen t={t + 40} id="k2" />
      {grabbed ? <Jar x={hand.x + 4} y={hand.y + 48} s={0.75} rot={-10} /> : <Jar x={JAR.x} y={JAR.y} s={0.75} />}
      {up > 0.15 && t < 14 ? <Trail x={p.x} y={p.y + LEG_LEN * p.scale} t={t} n={7} len={120} /> : null}
      <Hero look={PIP} pose={{ ...p, ...faceAt(t, [[0, 'smug'], [12, 'happy']]) }} rimId="rimR" shadow={up < 0.1 ? 0.5 : 0} />
      {t >= 14 && t < 20 ? <Sparkle x={hand.x} y={hand.y - 30} t={t - 14} s={1.2} /> : null}
      <Chip t={t} label="JUMP 1 · 0.5 m" />
    </g>
  );
};

export const S3: React.FC<ShotProps> = ({ t, len }) => {
  const pose = poseAt(t, [
    { f: 0, p: { ...kBase, squash: 0.08, yaw: 0.35, look: 0.8, armR: { a: 70, b: 80 }, armL: { a: 16, b: -6 } } },
    { f: 6, p: { squash: 0, tilt: -6, headTilt: 6 }, ease: easeOut },
  ]);
  const hand = toWorld(pose, joints(pose).armR.end);
  return (
    <g transform={camT(K_STAND.x, kf(t, [[0, 520], [len, 515]]), kf(t, [[0, 2.1], [len, 2.25]]))}>
      <Kitchen t={t + 72} id="k3" />
      <Hero look={PIP} pose={{ ...pose, ...faceAt(t, [[0, 'smug']]) }} rimId="rimR" shadow={0.5} />
      <Jar x={hand.x + 10} y={hand.y + 50} s={0.8} rot={-6} />
      <Chip t={t + 30} label="JUMP 1 · 0.5 m" />
    </g>
  );
};

// ---------- the rooftop ----------
const ROOF_Y = 790;
export const S4: React.FC<ShotProps> = ({ t, len }) => {
  const y = kf(t, [[0, 1650], [9, 640], [13, 600], [16, ROOF_Y]], easeOut);
  const pose = poseAt(t, [
    { f: 0, p: { x: 900, y: 1650, scale: 1.8, yaw: 0.1, look: 0.2, armL: { a: 160, b: 10 }, armR: { a: 160, b: 10 }, squash: -0.15 } },
    { f: 12, p: { armL: { a: 110, b: 20 }, armR: { a: 110, b: 20 }, squash: 0 } },
    { f: 16, p: { squash: 0.25, armL: { a: 60, b: 30 }, armR: { a: 60, b: 30 } }, ease: easeOut },
    { f: 22, p: { squash: 0, armL: { a: 20, b: 6 }, armR: { a: 20, b: 6 } } },
  ]);
  return (
    <g transform={camT(960, 540, kf(t, [[0, 1.0], [len, 1.04]]))}>
      <Rooftop t={t + 10} sunX={1260} sunY={560} low={260} />
      {t < 14 ? <Trail x={900} y={y + LEG_LEN * 1.8} t={t} len={320} /> : null}
      <Hero look={PIP} pose={{ ...pose, y, ...faceAt(t, [[0, 'happy'], [17, 'smug']]) }} rimId="rimR" shadow={t > 15 ? 0.6 : 0} />
      <Chip t={t} label="JUMP 5 · 8 m" />
    </g>
  );
};

export const S5: React.FC<ShotProps> = ({ t, len }) => {
  const pose = poseAt(t, [
    { f: 0, p: { x: 940, y: 790, scale: 1.8, yaw: -0.2, look: -0.4, armL: { a: 20, b: 6 }, armR: { a: 20, b: 6 } } },
    { f: 10, p: { armR: { a: 150, b: 120 }, headTilt: 4 }, ease: easeOut },
    { f: 18, p: { armR: { a: 30, b: 20 } } },
  ]);
  return (
    <g transform={camT(kf(t, [[0, 960], [len, 950]]), 470, kf(t, [[0, 1.55], [len, 1.65]]))}>
      <Rooftop t={t + 41} sunX={1260} sunY={560} low={260} />
      <Hero look={PIP} pose={{ ...pose, glasses: clamp((t - 10) / 8), ...faceAt(t, [[0, 'smug'], [14, 'cool']]) }} rimId="rimR" shadow={0.6} />
      {t > 18 ? <Sparkle x={1000} y={300} t={t - 18} s={0.8} /> : null}
      <Chip t={t + 30} label="JUMP 5 · 8 m" />
    </g>
  );
};

// ---------- the sky: from dusk blue (alt 0) to the black of space (alt 1) ----------
const SkyBack: React.FC<{ t: number; alt: number; id: string }> = ({ t, alt, id }) => {
  const mix = (a: string, b: string, u: number) => {
    const p = (s: string) => [1, 3, 5].map((i) => parseInt(s.slice(i, i + 2), 16));
    const A = p(a), B = p(b);
    return `rgb(${A.map((v, i) => Math.round(v + (B[i] - v) * u)).join(',')})`;
  };
  return (
    <g>
      <defs>
        <linearGradient id={`${id}g`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={mix('#3E6FB0', '#03040C', alt)} />
          <stop offset="0.6" stopColor={mix('#8DB6E2', '#0A1030', alt)} />
          <stop offset="1" stopColor={mix('#F6C79A', '#123060', alt)} />
        </linearGradient>
      </defs>
      <rect x={-600} y={-600} width={3120} height={2280} fill={`url(#${id}g)`} />
      {alt > 0.4 ? <Stars seed={4} x0={-200} y0={-200} w={2320} h={1400} t={t} n={140} o={clamp((alt - 0.4) / 0.4)} /> : null}
    </g>
  );
};

/** Clouds sliding down the frame (we're rising through them). */
const Clouds: React.FC<{ t: number; speed: number; o?: number }> = ({ t, speed, o = 0.9 }) => (
  <g opacity={o}>
    {Array.from({ length: 9 }).map((_, i) => {
      const x = -100 + rnd(11, i) * 2100;
      const y = ((rnd(12, i) * 1600 + t * speed * (0.6 + rnd(13, i))) % 1700) - 300;
      const s = 0.8 + rnd(14, i) * 1.2;
      return (
        <g key={i} transform={`translate(${x} ${y}) scale(${s})`}>
          {[[-80, 10, 70], [0, 0, 95], [90, 14, 66], [-30, 34, 80], [50, 36, 74]].map(([cx, cy, r], k) => (
            <circle key={k} cx={cx} cy={cy} r={r} fill="#FFF4EA" />
          ))}
          <ellipse cx={0} cy={70} rx={190} ry={22} fill="#F2C6A8" opacity={0.6} />
        </g>
      );
    })}
  </g>
);

/** A cartoon bird in profile, facing right. eye: where it looks (-1 down .. 1 up); worry 0..1 raises a brow and a drop. */
const Bird: React.FC<{ x: number; y: number; s: number; t: number; flap?: number; eye?: number; worry?: number; face?: number }> = ({ x, y, s, t, flap = 1, eye = 0, worry = 0, face = 1 }) => {
  const w = Math.sin(t * 0.9 * flap) * 26;
  return (
    <g transform={`translate(${x} ${y}) scale(${s * face} ${s})`}>
      <path d={`M -10 0 Q -40 ${-30 - w} -80 ${-10 - w}`} stroke="#2A2230" strokeWidth={10} fill="none" strokeLinecap="round" />
      <ellipse cx={0} cy={0} rx={46} ry={28} fill="#5E6C84" stroke="#2A2230" strokeWidth={5} />
      <circle cx={40} cy={-18} r={22} fill="#6E7C94" stroke="#2A2230" strokeWidth={5} />
      <path d="M 58 -20 L 82 -12 L 58 -6 Z" fill="#F2A23A" stroke="#2A2230" strokeWidth={3} strokeLinejoin="round" />
      <circle cx={46} cy={-22} r={8} fill="#FFFFFF" />
      <circle cx={48} cy={-22 - 4 * eye} r={4} fill="#111" />
      {worry > 0 ? <path d={`M 36 ${-34 - 4 * worry} L 56 ${-30 + 2 * worry}`} stroke="#2A2230" strokeWidth={4} strokeLinecap="round" /> : null}
      {worry > 0.5 ? <path d="M 26 -40 Q 22 -30 26 -26 Q 30 -30 26 -40 Z" fill="#9FD8FF" opacity={(worry - 0.5) * 2} /> : null}
      <path d={`M -10 0 Q -30 ${-20 + w} -70 ${10 + w}`} stroke="#3E4A5E" strokeWidth={12} fill="none" strokeLinecap="round" />
      <path d="M -44 6 L -70 14 L -48 -6" fill="#4E5A70" stroke="#2A2230" strokeWidth={3} />
    </g>
  );
};

export const S6: React.FC<ShotProps> = ({ t, len }) => {
  const y = kf(t, [[0, 1500], [len, -120]], (u) => u);
  const pose: Pose = { ...basePose, x: 980, y, scale: 0.9, yaw: 0, look: 0, armL: { a: 168, b: 4 }, armR: { a: 168, b: 4 }, squash: -0.12, ...faceAt(t, [[0, 'happy']]) };
  return (
    <g transform={camT(960, 540, 1.0)}>
      <SkyBack t={t} alt={0} id="sky6" />
      <Clouds t={t} speed={26} />
      {Array.from({ length: 8 }).map((_, i) => (
        <Bird key={i} x={300 + i * 190 + (i % 2) * 40} y={520 + ((i * 37) % 3) * 60 - (i % 2) * 40} s={0.9} t={t + i * 3} eye={y < 560 ? 1 : 0} worry={y < 500 ? 1 : 0} face={i % 3 === 0 ? -1 : 1} />
      ))}
      <Trail x={980} y={y + LEG_LEN * 0.9} t={t} len={260} />
      <Hero look={PIP} pose={pose} rimId="rimR" shadow={0} />
      <Chip t={t} label="JUMP 8 · 64 m" />
    </g>
  );
};

export const S7: React.FC<ShotProps> = ({ t, len }) => {
  const py = kf(t, [[0, 900], [18, -300]], (u) => u);
  return (
    <g>
      <g filter="url(#blur6)">
        <g transform={camT(960, 540, 1.0)}>
          <SkyBack t={t} alt={0.05} id="sky7" />
          <Clouds t={t + 40} speed={30} o={0.8} />
          <Hero look={PIP} pose={{ ...basePose, x: 640, y: py, scale: 1.1, armL: { a: 168, b: 4 }, armR: { a: 168, b: 4 }, squash: -0.12, expr: 'happy' }} rimId="rimR" shadow={0} />
        </g>
      </g>
      <Bird x={1180} y={kf(t, [[0, 600], [len, 590]])} s={6.5} t={t} flap={0.6} eye={kf(t, [[0, 0], [8, 1]])} worry={clamp((t - 10) / 14)} face={-1} />
      <Chip t={t + 30} label="JUMP 8 · 64 m" />
    </g>
  );
};

// ---------- the title on the roof: he crouches, then launches straight up out of frame ----------
export const S8: React.FC<ShotProps> = ({ t, len }) => {
  const feet = 840;
  const go = t >= 52;
  const y0 = feet - LEG_LEN * 0.62;
  const pose = poseAt(t, [
    { f: 0, p: { x: 960, y: y0, scale: 0.62, yaw: 0, armL: { a: 20, b: 6 }, armR: { a: 20, b: 6 } } },
    { f: 36, p: {} },
    { f: 46, p: { squash: 0.25, armL: { a: -40, b: 10 }, armR: { a: -40, b: 10 } }, ease: easeOut },
    { f: 52, p: { squash: -0.2, armL: { a: 168, b: 4 }, armR: { a: 168, b: 4 } }, ease: easeOut },
  ]);
  const y = go ? y0 - easeIn(clamp((t - 52) / 12)) * 1400 : y0;
  return (
    <g transform={camT(960, kf(t, [[0, 520], [len, 545]]), kf(t, [[0, 1.0], [len, 1.06]]))}>
      <Rooftop t={t + 80} sunX={960} sunY={690 - 40 * easeOut(clamp(t / 40))} />
      {go ? <Trail x={960} y={y + LEG_LEN * 0.62} t={t} len={300} /> : null}
      <Hero look={PIP} pose={{ ...pose, y, ...faceAt(t, [[0, 'smug'], [40, 'happy']]) }} rimId="rimR" shadow={go ? 0 : 0.6} />
      <TitleCard t={t} lines={['WHAT IF EVERY JUMP', 'WENT TWICE AS HIGH?']} accent="TWICE" accentT={40} size={92} y={170} />
    </g>
  );
};

// ---------- the schematic: the doubling ladder ----------
const RUNGS: [string, string, number][] = [
  ['JUMP 1', '0.5 m', 0], ['JUMP 5', '8 m', 1], ['JUMP 8', '64 m', 2], ['JUMP 15', '8 km · PLANES', 3], ['JUMP 20', '262 km', 4], ['JUMP 21', '524 km', 5],
];
export const S9: React.FC<ShotProps> = ({ t, len }) => {
  const X0 = 360;
  return (
    <g transform={`translate(960 540) scale(${kf(t, [[0, 1], [len, 1.05]])}) translate(-960 -540)`}>
      <Schematic t={t} id="sch9" />
      <SchLabel x={960} y={130} t={t - 2} text="EVERY JUMP x2" size={64} />
      {RUNGS.map(([a, b, i]) => {
        const y = 900 - i * 128;
        const w = 120 + 210 * i;
        const at = 6 + i * 9;
        return (
          <g key={a}>
            <DrawOn d={`M ${X0} ${y} L ${X0 + w} ${y}`} t={t - at} dur={6} color={i === 5 ? SCH.live : SCH.line} width={i === 5 ? 14 : 10} />
            <SchLabel x={X0 - 30} y={y + 12} t={t - at} text={a} size={34} anchor="end" color={SCH.dim} />
            <SchLabel x={X0 + w + 26} y={y + 12} t={t - at - 3} text={b} size={40} anchor="start" color={i === 5 ? SCH.live : SCH.line} />
          </g>
        );
      })}
      {/* the space station's orbit, between jump 20 and jump 21 */}
      <DrawOn d="M 300 326 L 1760 326" t={t - 50} dur={10} color="#7FD4FF" width={4} />
      <SchLabel x={1760} y={362} t={t - 56} text="SPACE STATION · 400 km" size={30} anchor="end" color="#7FD4FF" />
    </g>
  );
};

// ---------- space: the Earth below, the station, Pip rising past it ----------
const Earth: React.FC<{ y: number; r?: number; t: number }> = ({ y, r = 2600, t }) => (
  <g>
    <circle cx={960} cy={y + r} r={r + 60} fill="#4FA8FF" opacity={0.25} />
    <circle cx={960} cy={y + r} r={r + 24} fill="#7FC8FF" opacity={0.35} />
    <circle cx={960} cy={y + r} r={r} fill="#1F5FA8" />
    {Array.from({ length: 10 }).map((_, i) => (
      <ellipse key={i} cx={(rnd(21, i) * 2400 - 240 + t * 0.6) % 2400 - 240} cy={y + 60 + rnd(22, i) * 220} rx={160 + rnd(23, i) * 200} ry={22 + rnd(24, i) * 18} fill="#FFFFFF" opacity={0.7} />
    ))}
    <path d={`M -400 ${y + 150} Q 300 ${y + 90} 700 ${y + 200} Q 1000 ${y + 260} 1300 ${y + 150}`} fill="#3E8A4A" opacity={0.85} />
  </g>
);

const Station: React.FC<{ x: number; y: number; s?: number; t: number; stare?: number }> = ({ x, y, s = 1, t, stare = 0 }) => (
  <g transform={`translate(${x} ${y}) scale(${s})`}>
    <rect x={-420} y={-10} width={840} height={20} fill="#B9BEC8" stroke="#2A2230" strokeWidth={4} />
    {[-360, -230, 230, 360].map((px) => (
      <g key={px}>
        <rect x={px - 50} y={-150} width={100} height={130} fill="#2E3E8A" stroke="#C9A24A" strokeWidth={4} />
        <rect x={px - 50} y={20} width={100} height={130} fill="#2E3E8A" stroke="#C9A24A" strokeWidth={4} />
        {[0, 1, 2].map((k) => <path key={k} d={`M ${px - 50} ${-110 + k * 40} L ${px + 50} ${-110 + k * 40} M ${px - 50} ${60 + k * 40} L ${px + 50} ${60 + k * 40}`} stroke="#6A7AC8" strokeWidth={3} />)}
      </g>
    ))}
    <rect x={-120} y={-44} width={240} height={88} rx={30} fill="#E4E6EA" stroke="#2A2230" strokeWidth={5} />
    <rect x={-40} y={-80} width={80} height={160} rx={26} fill="#D4D7DE" stroke="#2A2230" strokeWidth={5} />
    {/* a window with an astronaut staring out */}
    <circle cx={60} cy={0} r={26} fill="#1A2440" stroke="#2A2230" strokeWidth={4} />
    <circle cx={60} cy={2} r={16} fill="#F2D2B8" />
    <circle cx={54} cy={-2} r={3.4} fill="#111" />
    <circle cx={66} cy={-2} r={3.4} fill="#111" />
    <ellipse cx={60} cy={9} rx={4} ry={2 + 4 * stare} fill="#3A1418" />
    <Glow x={0} y={0} r={160} o={0.15} kind="cool" />
  </g>
);

export const S10: React.FC<ShotProps> = ({ t, len }) => {
  const y = kf(t, [[0, 1450], [len, -60]], (u) => u);
  const pose: Pose = { ...basePose, x: 560, y, scale: 0.8, yaw: 0.2, look: 0.6, armL: { a: 168, b: 4 }, armR: { a: 150, b: 10 }, squash: -0.1, ...faceAt(t, [[0, 'happy'], [36, 'shock']]) };
  return (
    <g transform={camT(960, 540, kf(t, [[0, 1.0], [len, 1.05]]))}>
      <SkyBack t={t} alt={1} id="sp10" />
      <Earth y={kf(t, [[0, 820], [len, 900]])} t={t} />
      <Station x={1150} y={kf(t, [[0, 470], [len, 520]])} s={0.8} t={t} stare={clamp((t - 30) / 10)} />
      <Trail x={560} y={y + LEG_LEN * 0.8} t={t} len={300} o={0.5} />
      <Hero look={PIP} pose={pose} rimId="rimBlue" shadow={0} />
      <Chip t={t} label="JUMP 21 · 524 km" />
    </g>
  );
};

export const S11: React.FC<ShotProps> = ({ t, len }) => {
  const sc = 3.4 * (1 + 0.04 * clamp(t / len));
  const bob = Math.sin(t / 9) * 8;
  const head = { x: 960, y: 520 + bob };
  const pose: Pose = {
    ...basePose, x: head.x, y: head.y - HEAD.y * sc, scale: sc, yaw: 0.1, look: 0, armL: { a: 100, b: 20 }, armR: { a: 100, b: 20 },
    headTilt: kf(t, [[0, 0], [24, 16]]), ...faceAt(t, [[0, 'happy'], [20, 'oops'], [40, 'worried']]),
  };
  return (
    <g>
      <SkyBack t={t} alt={1} id="sp11" />
      <g filter="url(#blur6)">
        <Earth y={kf(t, [[0, 940], [len, 920]])} r={3400} t={t + 60} />
      </g>
      <Hero look={PIP} pose={pose} rimId="rimBlue" shadow={0} />
      <Chip t={t + 30} label="JUMP 21 · 524 km" />
    </g>
  );
};

export const S12: React.FC<ShotProps> = ({ t, len }) => {
  const fall = easeIn(clamp((t - 6) / 30));
  const y = 420 + fall * 1100;
  const pose: Pose = {
    ...basePose, x: 960, y, scale: 0.75, yaw: 0, look: 0, spin: fall * 40, armL: { a: 150 + Math.sin(t) * 20, b: 30 }, armR: { a: 150 - Math.sin(t) * 20, b: 30 },
    legL: { a: 20, b: 30 }, legR: { a: -10, b: 20 }, expr: 'shock',
  };
  return (
    <g transform={camT(960, 540, kf(t, [[0, 1.0], [len, 0.92]]))}>
      <SkyBack t={t} alt={1} id="sp12" />
      <Earth y={760} r={2200} t={t + 120} />
      <Hero look={PIP} pose={pose} rimId="rimRed" shadow={0} />
      {t > 6 ? <Trail x={960} y={y - 400} t={t} len={200} o={0.4} /> : null}
    </g>
  );
};

// cookie stacks are unused for now but kept in the import list for later beats
export const _unused = CookieStack;
