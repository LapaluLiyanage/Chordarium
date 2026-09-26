"""Deterministic test audio: chords as near-pure tones with known answers."""
from pathlib import Path

import numpy as np
import soundfile as sf

SR = 22050


def _tone(midi: int, seconds: float, amp: float = 1.0) -> np.ndarray:
    f = 440.0 * 2 ** ((midi - 69) / 12)
    t = np.arange(int(seconds * SR)) / SR
    return amp * sum((0.3 ** (h - 1)) * np.sin(2 * np.pi * f * h * t) for h in range(1, 4))


def chord_audio(pcs: list[int], seconds: float, bass_pc: int | None = None) -> np.ndarray:
    y = sum(_tone(60 + pc, seconds) for pc in pcs)
    if bass_pc is not None:
        y = y + _tone(36 + bass_pc, seconds, amp=1.5)
    fade = int(0.01 * SR)
    env = np.ones_like(y)
    env[:fade] = np.linspace(0, 1, fade)
    env[-fade:] = np.linspace(1, 0, fade)
    y = y * env
    return (0.5 * y / np.max(np.abs(y))).astype(np.float32)


def silence(seconds: float) -> np.ndarray:
    return np.zeros(int(seconds * SR), dtype=np.float32)


def progression(items: list[tuple[list[int], float, int | None]]) -> np.ndarray:
    return np.concatenate([chord_audio(p, s, b) for p, s, b in items])


def click_track(bpm: float = 120, seconds: float = 12) -> np.ndarray:
    y = np.zeros(int(seconds * SR), dtype=np.float32)
    n = int(0.03 * SR)
    burst = np.random.default_rng(0).standard_normal(n) * np.exp(-np.linspace(0, 8, n))
    for k, t in enumerate(np.arange(0, seconds - 0.05, 60.0 / bpm)):
        i = int(t * SR)
        seg = y[i:i + n]
        seg += (1.0 if k % 4 == 0 else 0.5) * burst[:len(seg)].astype(np.float32)
    return 0.5 * y


def write_wav(path, y: np.ndarray) -> Path:
    path = Path(path)
    sf.write(path, y, SR)
    return path


def label_at(segments: list[dict], t: float) -> str | None:
    for s in segments:
        if s["start"] <= t < s["end"]:
            return s["label"]
    return None
