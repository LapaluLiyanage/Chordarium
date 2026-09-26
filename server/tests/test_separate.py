import subprocess
from pathlib import Path

import numpy as np

from server.engine import separate
from server.tests.synth import SR, chord_audio, write_wav


def test_cuda_oom_retries_on_cpu(tmp_path, monkeypatch):
    wav = tmp_path / "audio.wav"
    wav.write_bytes(b"")
    calls = []

    def fake_run(cmd, capture_output, text):
        calls.append(cmd)
        device = cmd[cmd.index("-d") + 1]
        if device == "cuda":
            return subprocess.CompletedProcess(cmd, 1, "", "RuntimeError: CUDA out of memory")
        stem_dir = tmp_path / "stems" / "htdemucs" / "audio"
        stem_dir.mkdir(parents=True, exist_ok=True)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(separate.subprocess, "run", fake_run)
    stems = separate.separate(wav, tmp_path / "stems", device="cuda")
    assert [c[c.index("-d") + 1] for c in calls] == ["cuda", "cpu"]
    assert stems["bass"] == tmp_path / "stems" / "htdemucs" / "audio" / "bass.wav"


def test_other_failure_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(separate.subprocess, "run",
                        lambda cmd, capture_output, text: subprocess.CompletedProcess(cmd, 1, "", "boom"))
    try:
        separate.separate(tmp_path / "a.wav", tmp_path, device="cpu")
    except RuntimeError as e:
        assert "boom" in str(e)
    else:
        raise AssertionError("expected RuntimeError")


def test_load_mix_sums_and_trims(tmp_path):
    a = write_wav(tmp_path / "a.wav", chord_audio([0], 1.0))
    b = write_wav(tmp_path / "b.wav", chord_audio([7], 1.5))
    mix = separate.load_mix([Path(a), Path(b)], SR)
    assert len(mix) == SR
    assert np.max(np.abs(mix)) > 0.5
