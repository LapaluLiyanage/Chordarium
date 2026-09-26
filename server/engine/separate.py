"""Demucs htdemucs stem separation (Accurate mode)."""
import subprocess
import sys
from pathlib import Path
from typing import Callable

import librosa
import numpy as np

STEMS = ("bass", "drums", "other", "vocals")
MIN_GPU_BYTES = 2 * 1024 ** 3
POLL_SECONDS = 1.0


def pick_device() -> str:
    try:
        import torch
        if torch.cuda.is_available() and torch.cuda.mem_get_info()[0] >= MIN_GPU_BYTES:
            return "cuda"
    except Exception:
        pass
    return "cpu"


def separate(wav: Path, out_dir: Path, device: str | None = None,
             on_poll: Callable[[], None] | None = None) -> dict[str, Path]:
    """Run Demucs; `on_poll` is called about once a second and may raise to cancel (Demucs is killed)."""
    device = device or pick_device()
    cmd = [sys.executable, "-m", "demucs", "-n", "htdemucs", "-d", device, "-o", str(out_dir), str(wav)]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    try:
        while True:
            try:
                _, stderr = proc.communicate(timeout=POLL_SECONDS)
                break
            except subprocess.TimeoutExpired:
                if on_poll:
                    on_poll()
    except BaseException:
        proc.kill()
        proc.wait()
        raise
    if proc.returncode != 0:
        if device == "cuda" and "out of memory" in stderr.lower():
            return separate(wav, out_dir, "cpu", on_poll)
        raise RuntimeError(f"Demucs failed: {stderr.strip()[-500:]}")
    stem_dir = Path(out_dir) / "htdemucs" / Path(wav).stem
    return {name: stem_dir / f"{name}.wav" for name in STEMS}


def load_mix(paths: list[Path], sr: int) -> np.ndarray:
    signals = [librosa.load(str(p), sr=sr, mono=True)[0] for p in paths]
    n = min(len(s) for s in signals)
    return np.sum([s[:n] for s in signals], axis=0).astype(np.float32)
