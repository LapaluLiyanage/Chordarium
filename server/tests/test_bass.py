import numpy as np

from server.engine.bass import apply_inversions, bass_pitch_classes
from server.tests.synth import SR, chord_audio, silence

G_MAJ = [7, 11, 2]


def seg(start, end, label):
    return {"start": start, "end": end, "label": label, "alt": None, "confidence": 0.8}


def test_bass_pitch_class_per_segment():
    y = np.concatenate([chord_audio(G_MAJ, 2.0, 11), chord_audio(G_MAJ, 2.0, 7), silence(1.0)])
    segs = [seg(0, 2, "G:maj"), seg(2, 4, "G:maj"), seg(4, 5, "N")]
    assert bass_pitch_classes(y, SR, segs) == [11, 7, None]


def test_apply_inversions():
    segs = [seg(0, 1, "G:maj"), seg(1, 2, "G:maj"), seg(2, 3, "G:maj"), seg(3, 4, "G:maj"), seg(4, 5, "N")]
    out = apply_inversions(segs, [11, 2, 9, 7, None])
    assert [s["label"] for s in out] == ["G:maj/3", "G:maj/5", "G:maj", "G:maj", "N"]
    assert [s["bass"] for s in out] == ["B", "D", "G", "G", None]
    assert segs[0]["label"] == "G:maj"
