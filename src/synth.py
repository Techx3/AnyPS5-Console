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
