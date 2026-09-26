"""Krumhansl-Schmuckler key estimation over whole-song chroma."""
import librosa
import numpy as np

from server.theory.chord import SHARPS

MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def estimate_key(y: np.ndarray, sr: int) -> str:
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=2048).mean(axis=1)
    best_score, best_key = -np.inf, "C:maj"
    for mode, profile in (("maj", MAJOR_PROFILE), ("min", MINOR_PROFILE)):
        for root in range(12):
            score = np.corrcoef(chroma, np.roll(profile, root))[0, 1]
            if score > best_score:
                best_score, best_key = score, f"{SHARPS[root]}:{mode}"
    return best_key
