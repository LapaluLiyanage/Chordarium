"""Wrapper around BTC (Park et al., ISMIR 2019), large-vocabulary chord model."""
import sys
from pathlib import Path

import numpy as np

from server.engine.snap import merge_identical
from server.theory.chord import SHARPS

DEFAULT_WEIGHTS_DIR = Path(__file__).resolve().parent / "weights"
REPO_DIRNAME = "BTC-ISMIR19"
WEIGHTS_RELPATH = Path("test") / "btc_model_large_voca.pt"
BTC_QUALITIES = ["min", "maj", "dim", "aug", "min6", "maj6", "min7",
                 "minmaj7", "maj7", "7", "dim7", "hdim7", "sus2", "sus4"]
_cache: dict[tuple[str, str], tuple] = {}


def is_available(weights_dir: Path) -> bool:
    return (Path(weights_dir) / REPO_DIRNAME / WEIGHTS_RELPATH).is_file()


def idx_to_label(idx: int) -> str:
    if idx >= 168:
        return "N"
    return f"{SHARPS[idx // 14]}:{BTC_QUALITIES[idx % 14]}"


def frames_to_segments(probs: np.ndarray, frame_sec: float, duration: float) -> list[dict]:
    top = probs.argmax(axis=1)
    segs, start, n = [], 0, len(top)
    for i in range(1, n + 1):
        if i < n and top[i] == top[start]:
            continue
        mean = probs[start:i].mean(axis=0)
        best = int(top[start])
        label = idx_to_label(best)
        alt = None
        if label != "N":
            alt = next((idx_to_label(int(k)) for k in np.argsort(mean)[::-1]
                        if int(k) != best and idx_to_label(int(k)) not in ("N", label)), None)
        segs.append({"start": round(start * frame_sec, 3), "end": round(min(i * frame_sec, duration), 3),
                     "label": label, "alt": alt, "confidence": round(float(mean[best]), 3)})
        start = i
    return merge_identical(segs)


def _load(weights_dir: Path, device: str):
    key = (str(weights_dir), device)
    if key in _cache:
        return _cache[key]
    import torch
    import yaml

    repo = Path(weights_dir) / REPO_DIRNAME
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))
    from btc_model import BTC_model

    cfg = yaml.safe_load((repo / "run_config.yaml").read_text())
    cfg["feature"]["large_voca"] = True
    cfg["model"]["num_chords"] = 170
    # BTC's 2019 code uses `np.float` (removed in NumPy 1.24); alias it only while building/loading.
    np.float = float
    try:
        model = BTC_model(config=cfg["model"]).to(device)
        ckpt = torch.load(repo / WEIGHTS_RELPATH, map_location=device, weights_only=False)
    finally:
        del np.float
    model.load_state_dict(ckpt["model"])
    model.eval()
    _cache[key] = (model, cfg, np.asarray(ckpt["mean"]), np.asarray(ckpt["std"]))
    return _cache[key]


def recognize(wav_path: Path, weights_dir: Path, device: str = "cpu") -> list[dict]:
    import librosa
    import torch

    model, cfg, mean, std = _load(weights_dir, device)
    feat, sr = cfg["feature"], cfg["mp3"]["song_hz"]
    timestep = cfg["model"]["timestep"]
    y, _ = librosa.load(str(wav_path), sr=sr, mono=True)
    cqt = librosa.cqt(y, sr=sr, n_bins=feat["n_bins"], bins_per_octave=feat["bins_per_octave"],
                      hop_length=feat["hop_length"])
    x = (np.log(np.abs(cqt) + 1e-6).T - mean) / std
    n_frames = x.shape[0]
    x = np.pad(x, ((0, (-n_frames) % timestep), (0, 0)))
    chunks = []
    with torch.no_grad():
        t = torch.tensor(x, dtype=torch.float32, device=device).unsqueeze(0)
        for i in range(0, t.shape[1], timestep):
            hidden, _ = model.self_attn_layers(t[:, i:i + timestep, :])
            logits = model.output_layer.output_projection(hidden)
            chunks.append(torch.softmax(logits, dim=-1)[0].cpu().numpy())
    probs = np.concatenate(chunks)[:n_frames]
    return frames_to_segments(probs, feat["hop_length"] / sr, duration=len(y) / sr)
