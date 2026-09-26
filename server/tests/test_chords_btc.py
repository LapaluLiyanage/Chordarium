import numpy as np
import pytest

from server.engine import chords_btc
from server.engine.chords_btc import DEFAULT_WEIGHTS_DIR, frames_to_segments, idx_to_label
from server.tests.synth import chord_audio, label_at, write_wav


def test_idx_to_label():
    assert idx_to_label(0) == "C:min"
    assert idx_to_label(1) == "C:maj"
    assert idx_to_label(14 * 7 + 9) == "G:7"
    assert idx_to_label(168) == "N"
    assert idx_to_label(169) == "N"


def test_frames_to_segments_top2_and_merging():
    probs = np.zeros((6, 170))
    probs[0:3, 1], probs[0:3, 8] = 0.7, 0.3       # C:maj, alt C:maj7
    probs[3:6, 169], probs[3:6, 1] = 0.9, 0.1     # N
    segs = frames_to_segments(probs, frame_sec=0.5, duration=2.9)
    assert [(s["label"], s["alt"]) for s in segs] == [("C:maj", "C:maj7"), ("N", None)]
    assert segs[0]["confidence"] == 0.7
    assert segs[-1]["end"] == 2.9


def test_is_available_false_for_empty_dir(tmp_path):
    assert chords_btc.is_available(tmp_path) is False


@pytest.mark.slow
@pytest.mark.skipif(not chords_btc.is_available(DEFAULT_WEIGHTS_DIR), reason="run scripts/setup_models.py")
def test_btc_on_synthetic_chords(tmp_path):
    y = np.concatenate([chord_audio([0, 4, 7, 11], 4.0, 0), chord_audio([7, 11, 2, 5], 4.0, 7)])
    segs = chords_btc.recognize(write_wav(tmp_path / "x.wav", y), DEFAULT_WEIGHTS_DIR)
    assert label_at(segs, 2.0).startswith("C:")
    assert label_at(segs, 6.0).startswith("G:")
