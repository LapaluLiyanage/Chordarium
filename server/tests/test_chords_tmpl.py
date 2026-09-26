import numpy as np

from server.engine import chords_tmpl
from server.tests.synth import SR, chord_audio, label_at, progression, silence


def test_144_unique_templates():
    labels, matrix = chords_tmpl.build_templates()
    assert len(labels) == 144 == len(set(labels))
    assert matrix.shape == (144, 12)
    np.testing.assert_allclose(np.linalg.norm(matrix, axis=1), 1.0)


def test_viterbi_prefers_staying():
    log_emit = np.array([[0.0, 0.0, -0.2, 0.0], [-0.1, -0.1, 0.0, -0.1]])
    path = chords_tmpl.viterbi(10 * log_emit, p_stay=0.95)
    assert list(path) == [0, 0, 0, 0]


def test_recognizes_advanced_progression():
    y = progression([
        ([0, 4, 7, 11], 2.0, 0),   # Cmaj7
        ([9, 0, 4], 2.0, 9),       # Am
        ([7, 11, 2, 5], 2.0, 7),   # G7
        ([2, 7, 9], 2.0, 2),       # Dsus4
    ])
    segs = chords_tmpl.recognize(y, SR)
    assert label_at(segs, 1.0) == "C:maj7"
    assert label_at(segs, 3.0) == "A:min"
    assert label_at(segs, 5.0) == "G:7"
    assert label_at(segs, 7.0) == "D:sus4"


def test_silence_is_no_chord_and_fields_are_sane():
    y = np.concatenate([silence(1.5), chord_audio([0, 4, 7], 2.0, 0)])
    segs = chords_tmpl.recognize(y, SR)
    assert label_at(segs, 0.5) == "N"
    assert label_at(segs, 2.5) == "C:maj"
    for s in segs:
        assert s["end"] > s["start"]
        assert 0.0 <= s["confidence"] <= 1.0
        if s["label"] != "N":
            assert s["alt"] and s["alt"] != s["label"]
    assert segs[-1]["end"] <= len(y) / SR + 1e-6
