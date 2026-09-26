"""Demucs htdemucs stem separation (Accurate mode)."""
import subprocess
import sys
from pathlib import Path

import librosa
import numpy as np

STEMS = ("bass", "drums", "other", "vocals")
MIN_GPU_BYTES = 2 * 1024 ** 3


def pick_device() -> str:
    try:
        import torch
        if torch.cuda.is_available() and torch.cuda.mem_get_info()[0] >= MIN_GPU_BYTES:
            return "cuda"
    except Exception:
        pass
    return "cpu"


def separate(wav: Path, out_dir: Path, device: str | None = None) -> dict[str, Path]:
    device = device or pick_device()
    cmd = [sys.executable, "-m", "demucs", "-n", "htdemucs", "-d", device, "-o", str(out_dir), str(wav)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        if device == "cuda" and "out of memory" in result.stderr.lower():
            return separate(wav, out_dir, "cpu")
        raise RuntimeError(f"Demucs failed: {result.stderr.strip()[-500:]}")
    stem_dir = Path(out_dir) / "htdemucs" / Path(wav).stem
    return {name: stem_dir / f"{name}.wav" for name in STEMS}


def load_mix(paths: list[Path], sr: int) -> np.ndarray:
    signals = [librosa.load(str(p), sr=sr, mono=True)[0] for p in paths]
    n = min(len(s) for s in signals)
    return np.sum([s[:n] for s in signals], axis=0).astype(np.float32)
