"""Step 2, free: the voice with Kokoro (local, no API key) instead of ElevenLabs.

python <skill>/scripts/voice_kokoro.py <slug> [--force]
Needs kokoro-onnx and the model files (kokoro-v1.0.onnx, voices-v1.0.bin) in assets/tts/ above the studio, or in the
folder named by KOKORO_DIR. Each sentence is spoken separately, then joined with a short pause; word times inside a
sentence are spread by letter count (good to about a tenth of a second for these short lines). It writes the same
files voice.py's API step writes (voice_raw.mp3, words_raw.json, voice_meta.json with a matching signature), then
runs voice.py, which skips the API and only tightens the pauses.

episode.json "voice": {"engine": "kokoro", "id": "af_heart", "speed": 1.0, "lang": "en-us"}
"""
import hashlib, json, os, pathlib, re, subprocess, sys

import numpy as np

from wi import SR, ep_dir, load_episode, load_json, out_dir, pub_dir, save_json, STUDIO

slug = sys.argv[1]
ep = load_episode(slug)
V = {'id': 'TX3LPaxmHKxFdv7VOQHJ', 'model': 'eleven_multilingual_v2', 'settings': {'stability': 0.4, 'similarity_boost': 0.8, 'style': 0.35, 'use_speaker_boost': True}}
V.update(ep.get('voice', {}))
text = ' '.join(b['text'].strip() for b in ep['script'])
sig = hashlib.sha1(json.dumps([text, V], sort_keys=True).encode()).hexdigest()[:12]   # the same signature voice.py checks
meta = load_json(out_dir(slug) / 'voice_meta.json', {})
raw_mp3 = pub_dir(slug) / 'voice_raw.mp3'
if '--force' in sys.argv or meta.get('sig') != sig or not raw_mp3.exists():
    from kokoro_onnx import Kokoro
    from scipy.signal import resample_poly
    d = pathlib.Path(os.environ.get('KOKORO_DIR', ''))
    if not (d / 'kokoro-v1.0.onnx').exists():
        for up in [STUDIO, *STUDIO.parents]:
            if (up / 'assets' / 'tts' / 'kokoro-v1.0.onnx').exists():
                d = up / 'assets' / 'tts'
                break
    k = Kokoro(str(d / 'kokoro-v1.0.onnx'), str(d / 'voices-v1.0.bin'))
    sents = re.findall(r'[^.?!]+[.?!]+', text) or [text]
    audio, words, t = [], [], 0.0
    pause = np.zeros(int(0.4 * SR), np.float32)
    for s in sents:
        s = s.strip()
        a, sr = k.create(s, voice=V['id'], speed=V.get('speed', 1.0), lang=V.get('lang', 'en-us'))
        a = resample_poly(np.asarray(a, np.float64), SR, sr).astype(np.float32)
        idx = np.where(np.abs(a) > 0.01)[0]
        a = a[max(0, idx[0] - int(0.02 * SR)): idx[-1] + int(0.05 * SR)] if len(idx) else a
        dur = len(a) / SR
        toks = [(m.group(0), m.end()) for m in re.finditer(r"[\w'’]+", s)]
        letters = sum(len(w) for w, _ in toks) or 1
        c = t + 0.03
        span = dur - 0.08
        for i, (w, end) in enumerate(toks):
            wd = span * len(w) / letters
            nxt = toks[i + 1][1] - len(toks[i + 1][0]) if i + 1 < len(toks) else len(s)
            words.append({'w': w, 's': round(c, 3), 'e': round(c + wd * 0.92, 3), 'p': s[end:nxt].strip()})
            c += wd
        audio += [a, pause]
        t += dur + len(pause) / SR
    y = np.concatenate(audio)
    y *= 0.9 / max(1e-6, np.abs(y).max())
    wav = out_dir(slug) / 'voice_kokoro.wav'
    import wave
    with wave.open(str(wav), 'wb') as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(SR)
        f.writeframes((np.clip(y, -1, 1) * 32767).astype('<i2').tobytes())
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(wav), '-codec:a', 'libmp3lame', '-b:a', '192k', str(raw_mp3)], check=True)
    save_json(out_dir(slug) / 'words_raw.json', words)
    save_json(out_dir(slug) / 'voice_meta.json', {'sig': sig, 'chars': len(text), 'engine': 'kokoro'})
    print(f'Kokoro voice {V["id"]}: {len(sents)} sentences, {t:.2f} s raw, 0 credits')
else:
    print('Voice unchanged: reusing it.')
subprocess.run([sys.executable, str(pathlib.Path(__file__).with_name('voice.py')), slug], check=True)
