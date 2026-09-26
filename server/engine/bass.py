"""Find the bass note of each chord segment and turn it into a slash chord."""
import librosa
import numpy as np

from server.theory.chord import SHARPS, Chord, parse, pitch_classes, to_harte

BASS_FMIN = librosa.note_to_hz("C1")
BASS_OCTAVES = 3            # C1..B3 (~33-247 Hz)
HOP = 512
MIN_ENERGY_RATIO = 0.05


def bass_pitch_classes(y: np.ndarray, sr: int, segments: list[dict]) -> list[int | None]:
    cqt = np.abs(librosa.cqt(y, sr=sr, hop_length=HOP, fmin=BASS_FMIN,
                             n_bins=12 * BASS_OCTAVES, bins_per_octave=12))
    times = librosa.frames_to_time(np.arange(cqt.shape[1]), sr=sr, hop_length=HOP)
    loudest_frame = cqt.sum(axis=0).max() + 1e-9
    result: list[int | None] = []
    for s in segments:
        mask = (times >= s["start"]) & (times < s["end"])
        if not mask.any():
            result.append(None)
            continue
        profile = cqt[:, mask].mean(axis=1)
        if profile.sum() < MIN_ENERGY_RATIO * loudest_frame:
            result.append(None)
            continue
        result.append(int(profile.reshape(BASS_OCTAVES, 12).sum(axis=0).argmax()))
    return result


def apply_inversions(segments: list[dict], bass_pcs: list[int | None]) -> list[dict]:
    out = []
    for s, pc in zip(segments, bass_pcs):
        c = parse(s["label"])
        if c is None:
            out.append({**s, "label": "N", "bass": None})
            continue
        is_inversion = pc is not None and pc != c.root and pc in pitch_classes(c)
        c = Chord(c.root, c.quality, pc if is_inversion else None)
        bass_pc = c.bass if c.bass is not None else c.root
        out.append({**s, "label": to_harte(c), "bass": SHARPS[bass_pc]})
    return out
