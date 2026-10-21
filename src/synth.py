import array
import math
import random
import wave
from pathlib import Path

RATE = 44100


def _write(path, left, right):
    data = array.array("h")
    for a, b in zip(left, right):
        data.append(max(-32767, min(32767, int(a * 32767))))
        data.append(max(-32767, min(32767, int(b * 32767))))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(data.tobytes())


def _env(t, attack, release, total):
    if t < attack:
        return t / attack
    if t > total - release:
        return max(0.0, (total - t) / release)
    return 1.0


def swell(path):
    total = 6.5
    n = int(RATE * total)
    notes = [130.81, 196.0, 261.63, 329.63, 392.0, 523.25]
    rng = random.Random(4)
    detune = [(f, rng.uniform(-0.6, 0.6), rng.uniform(0, math.tau)) for f in notes for _ in range(2)]
    left, right = [], []
    for i in range(n):
        t = i / RATE
        e = _env(t, 2.2, 3.2, total) ** 1.5
        s = 0.0
        for k, (f, d, ph) in enumerate(detune):
            s += math.sin(math.tau * (f + d) * t + ph) * (0.9 if k < 6 else 0.5)
        shimmer = math.sin(math.tau * 1046.5 * t) * max(0.0, math.sin(math.pi * min(1.0, t / total))) * 0.15
        v = (s / len(detune) + shimmer) * e * 0.55
        pan = 0.5 + 0.2 * math.sin(t * 0.7)
        left.append(v * (1.2 - pan))
        right.append(v * (0.2 + pan))
    _write(path, left, right)


def chime(path, freqs=(880.0, 1318.5, 1760.0), total=1.6):
    n = int(RATE * total)
    left, right = [], []
    for i in range(n):
        t = i / RATE
        v = 0.0
        for k, f in enumerate(freqs):
            start = k * 0.06
            if t >= start:
                tt = t - start
                v += math.sin(math.tau * f * tt) * math.exp(-tt * (3.2 + k)) * (0.5 / (k + 1))
        left.append(v * 0.5)
        right.append(v * 0.45)
    _write(path, left, right)


def tick(path):
    chime(path, (1567.98,), 0.18)


def music(path, rate=22050, length=32):
    chords = [(130.81, 196.0, 246.94, 329.63), (110.0, 164.81, 220.0, 246.94),
              (87.31, 130.81, 220.0, 261.63), (98.0, 146.83, 196.0, 293.66)]
    chords = [[round(f * length) / length for f in c] for c in chords]
    step = length / len(chords)
    n = int(rate * length)
    tau = math.tau
    out = array.array("h")
    for i in range(n):
        t = i / rate
        v = 0.0
        for k, chord in enumerate(chords):
            dt = ((t - (k * step + step / 2) + length / 2) % length) - length / 2
            if abs(dt) >= step * 0.75:
                continue
            env = math.cos(math.pi * dt / (step * 1.5)) ** 2
            for j, f in enumerate(chord):
                v += math.sin(tau * f * t + j) * env * (0.26 if j == 0 else 0.18)
        shimmer = 0.04 * math.sin(tau * (1046.5 * 1) * t) * (0.5 + 0.5 * math.sin(tau * t / length * 4))
        sample = int(max(-1.0, min(1.0, (v * 0.32 + shimmer * 0.3))) * 32767)
        out.append(sample)
        out.append(sample)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(out.tobytes())


def ensure_music(folder):
    p = Path(folder) / "music.wav"
    if not p.exists():
        tmp = p.with_suffix(".tmp.wav")
        music(tmp)
        tmp.replace(p)
    return p


def ensure(folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    out = {}
    for name, fn in (("swell", swell), ("chime", chime), ("tick", tick)):
        p = folder / f"{name}.wav"
        if not p.exists():
            fn(p)
        out[name] = p
    return out
