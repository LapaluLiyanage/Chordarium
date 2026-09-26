"""Beat and downbeat tracking with beat_this (CPJKU)."""
from pathlib import Path

import numpy as np

_models: dict[str, object] = {}


def summarize(beats: list[float], downbeats: list[float]) -> dict:
    beats = [round(float(b), 3) for b in beats]
    downbeats = [round(float(d), 3) for d in downbeats] or beats[::4]
    tempo = 0.0 if len(beats) < 2 else round(60.0 / float(np.median(np.diff(beats))), 1)
    return {"beats": beats, "downbeats": downbeats, "tempo": tempo}


def detect_beats(wav_path: Path, device: str = "cpu") -> dict:
    from beat_this.inference import File2Beats

    if device not in _models:
        _models[device] = File2Beats(checkpoint_path="final0", device=device, dbn=False)
    beats, downbeats = _models[device](str(wav_path))
    return summarize(list(beats), list(downbeats))
