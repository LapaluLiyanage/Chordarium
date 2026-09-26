import subprocess
from pathlib import Path

import numpy as np
import pytest

from server.engine import separate
from server.tests.synth import SR, chord_audio, write_wav


class FakePopen:
    """Stands in for Demucs: `script` maps device -> (timeouts_before_exit, returncode, stderr)."""
    script: dict = {}
    instances: list = []

    def __init__(self, cmd, stdout=None, stderr=None, text=None):
        self.cmd = cmd
        self.device = cmd[cmd.index("-d") + 1]
        self.timeouts, self.code, self.err = FakePopen.script[self.device]
        self.returncode = None
        self.killed = False
        FakePopen.instances.append(self)

    def communicate(self, timeout=None):
        if self.timeouts > 0:
            self.timeouts -= 1
            raise subprocess.TimeoutExpired(self.cmd, timeout)
        self.returncode = self.code
        return "", self.err

    def kill(self):
        self.killed = True

    def wait(self):
        return self.returncode


@pytest.fixture
def fake_popen(monkeypatch):
    FakePopen.script, FakePopen.instances = {}, []
    monkeypatch.setattr(separate.subprocess, "Popen", FakePopen)
    return FakePopen


def test_cuda_oom_retries_on_cpu(tmp_path, fake_popen):
    fake_popen.script = {"cuda": (0, 1, "RuntimeError: CUDA out of memory"), "cpu": (2, 0, "")}
    polls = []
    stems = separate.separate(tmp_path / "audio.wav", tmp_path / "stems", device="cuda",
                              on_poll=lambda: polls.append(1))
    assert [p.device for p in fake_popen.instances] == ["cuda", "cpu"]
    assert len(polls) == 2
    assert stems["bass"] == tmp_path / "stems" / "htdemucs" / "audio" / "bass.wav"


def test_other_failure_raises(tmp_path, fake_popen):
    fake_popen.script = {"cpu": (0, 1, "boom")}
    with pytest.raises(RuntimeError, match="boom"):
        separate.separate(tmp_path / "a.wav", tmp_path, device="cpu")


def test_cancel_during_separation_kills_demucs(tmp_path, fake_popen):
    fake_popen.script = {"cpu": (100, 0, "")}

    class Stop(Exception):
        pass

    def on_poll():
        raise Stop()

    with pytest.raises(Stop):
        separate.separate(tmp_path / "a.wav", tmp_path, device="cpu", on_poll=on_poll)
    assert fake_popen.instances[0].killed is True


def test_load_mix_sums_and_trims(tmp_path):
    a = write_wav(tmp_path / "a.wav", chord_audio([0], 1.0))
    b = write_wav(tmp_path / "b.wav", chord_audio([7], 1.5))
    mix = separate.load_mix([Path(a), Path(b)], SR)
    assert len(mix) == SR
    assert np.max(np.abs(mix)) > 0.5
