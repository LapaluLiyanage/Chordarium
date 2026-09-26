import pytest

from server.engine.beats import detect_beats, summarize
from server.tests.synth import click_track, write_wav


def test_summarize_tempo_and_downbeat_fallback():
    out = summarize([0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0], [])
    assert out["tempo"] == 120.0
    assert out["downbeats"] == [0.0, 2.0, 4.0]


def test_summarize_too_few_beats():
    assert summarize([1.0], []) == {"beats": [1.0], "downbeats": [1.0], "tempo": 0.0}


@pytest.mark.slow
def test_detects_120_bpm_click_track(tmp_path):
    wav = write_wav(tmp_path / "clicks.wav", click_track(bpm=120, seconds=12))
    out = detect_beats(wav)
    assert 115 <= out["tempo"] <= 125
    assert len(out["beats"]) >= 15
