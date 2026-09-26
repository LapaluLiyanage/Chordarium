# Chordarium Server (Phase 1, Plan 1 of 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Flask JSON API that turns a YouTube link into a beat-synced chord timeline (7ths, sus, dim/hdim, aug, 6ths, inversions), stores and edits it, and exports ChordPro / TXT / JSON / PDF / MIDI.

**Architecture:** Small single-purpose modules under `server/engine/` each transform audio or segments; `pipeline.py` chains them and reports progress; `jobs.py` runs the pipeline in a background thread and persists status via `store.py` (SQLite); `export/` renders the stored timeline; `app.py` exposes everything over HTTP. All chord-symbol logic lives in `server/theory/chord.py`.

**Tech Stack:** Python 3.12, Flask 3.1, yt-dlp + ffmpeg, librosa 0.11, Demucs 4 (htdemucs), beat_this, BTC-ISMIR19 (PyTorch 2.5.1), SQLite, ReportLab, mido, pytest.

**Spec:** `docs/superpowers/specs/2026-09-26-chordarium-design.md`

**Plan 2 (separate, later):** React + Vite client (Home, Analyzing, Tracker, Chord Editor, Export modal).

**Two small additions to the spec made by this plan:** job state `cancelled` (for `POST /api/jobs/<id>/cancel`), and a `warnings: list[str]` field on the timeline (carries the "BTC weights missing" notice to the UI).

## Global Constraints

- Python **3.12** virtual environment at `.venv/` (system Python 3.14 is too new for torch 2.5.1). No `madmom`.
- Audio sample rate everywhere: **22050 Hz mono**.
- Chord labels stored in Harte notation (`C:maj7`, `A:min7/b3`, `N`); displayed via `server/theory/chord.py` only.
- Max song length **900 s** (15 min); live streams rejected.
- `torch==2.5.1`, `torchaudio==2.5.1` (CPU wheels) — newer torchaudio breaks Demucs 4.0.1's audio saving.
- BTC repo + weights are cloned by `scripts/setup_models.py` into `server/engine/weights/` and never committed.
- Commits: conventional prefix (`feat:`, `test:`, `chore:`), author = repo owner only. **No `Co-Authored-By` or "Generated with" lines.**
- Run all commands from the repo root with the venv activated (`.venv\Scripts\activate`).

## Review Focus

1. YouTube URLs pasted with extra junk (`youtu.be/ID?si=…`, `watch?v=ID&t=42s&list=…`, `/shorts/ID`, `music.youtube.com`, no `https://`) must all resolve to the 11-char ID → Task 8 `test_parse_video_id_variants`.
2. Songs with silent intros/outros must not start the chord sheet with empty `N.C.` bars → Task 13 `test_leading_and_trailing_silence_trimmed`.
3. Flat keys must spell chords with flats and slash basses by letter (`Bbmaj7`, `D7/F#` — never `A#maj7` or `D7/Gb`) → Task 1 `test_format_flats_and_letter_spelled_bass`, Task 13 `test_chordpro_grid`.
4. Transpose/capo wrap-around on slash chords (`B`+2 → `C#`, `G/B` with capo 2 → `F/A`) → Task 1 `test_transpose_wraps_and_moves_bass`, `test_render_capo`.
5. Fast chord changes where two boundaries snap to the same beat must not produce negative-length or overlapping segments → Task 3 `test_two_boundaries_snap_to_same_beat`.

---

### Task 1: Project scaffold + chord theory

**Files:**
- Create: `requirements.txt`, `pytest.ini`, `server/__init__.py`, `server/theory/__init__.py`, `server/theory/chord.py`, `server/tests/__init__.py`
- Test: `server/tests/test_chord.py`

**Interfaces:**
- Produces (`server.theory.chord`):
  - `SHARPS: list[str]`, `FLATS: list[str]`, `QUALITY_INTERVALS: dict[str, tuple[int, ...]]`
  - `@dataclass(frozen=True) class Chord(root: int, quality: str, bass: int | None = None)`
  - `parse(label: str) -> Chord | None` (raises `ValueError` on unknown root/quality/bass)
  - `to_harte(chord: Chord | None) -> str`
  - `format_symbol(chord: Chord | None, prefer_flats: bool = False) -> str` (`None` → `"N.C."`)
  - `note_names(chord: Chord, prefer_flats: bool = False) -> list[str]`
  - `pitch_classes(chord: Chord) -> list[int]`
  - `transpose(chord: Chord | None, semitones: int) -> Chord | None`
  - `simplify(chord: Chord | None) -> Chord | None`
  - `midi_notes(chord: Chord) -> list[int]` (bass first)
  - `render(label: str, transpose_by: int = 0, capo: int = 0, simplify_chord: bool = False, prefer_flats: bool = False) -> str`
  - `key_prefers_flats(key_label: str, transpose_by: int = 0) -> bool`
  - `format_key(key_label: str, transpose_by: int = 0) -> str` (e.g. `"Bb major"`)
  - `key_symbol(key_label: str, transpose_by: int = 0) -> str` (e.g. `"Gm"`)

- [ ] **Step 1: Install Python 3.12 and create the venv**

```powershell
winget install -e --id Python.Python.3.12
py -3.12 -m venv .venv
.venv\Scripts\activate
python --version
```
Expected: `Python 3.12.x`

- [ ] **Step 2: Create `requirements.txt` and install**

```text
flask==3.1.*
yt-dlp
numpy>=1.26,<2.3
scipy>=1.13
librosa==0.11.*
soundfile>=0.12
torch==2.5.1
torchaudio==2.5.1
demucs==4.0.1
beat_this @ https://github.com/CPJKU/beat_this/archive/main.zip
rotary-embedding-torch
einops
soxr
tqdm
pyyaml
reportlab==4.*
mido==1.3.*
pytest==8.*
pypdf>=4
```

```powershell
pip install torch==2.5.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```
Expected: installs without errors.

- [ ] **Step 3: Create `pytest.ini` and empty package files**

`pytest.ini`:
```ini
[pytest]
testpaths = server/tests
pythonpath = .
markers =
    slow: needs ML models (beat_this / BTC weights); run with -m slow
addopts = -m "not slow"
```

Create empty files: `server/__init__.py`, `server/theory/__init__.py`, `server/tests/__init__.py`.

- [ ] **Step 4: Write the failing tests**

`server/tests/test_chord.py`:
```python
import pytest

from server.theory import chord as ch
from server.theory.chord import Chord


def test_parse_basic_forms():
    assert ch.parse("C") == Chord(0, "maj")
    assert ch.parse("N") is None
    assert ch.parse("X") is None
    assert ch.parse("A:min7/b3") == Chord(9, "min7", 0)
    assert ch.parse("C:maj/E") == Chord(0, "maj", 4)
    assert ch.parse("C:maj/1") == Chord(0, "maj", None)
    assert ch.parse("Bb:7") == Chord(10, "7")


@pytest.mark.parametrize("bad", ["H:maj", "C:weird", "C:maj/Q"])
def test_parse_rejects_garbage(bad):
    with pytest.raises(ValueError):
        ch.parse(bad)


def test_harte_round_trip_every_vocabulary_chord():
    for root in range(12):
        for quality in ch.QUALITY_INTERVALS:
            c = Chord(root, quality)
            assert ch.parse(ch.to_harte(c)) == c
            inv = Chord(root, quality, (root + ch.QUALITY_INTERVALS[quality][1]) % 12)
            assert ch.parse(ch.to_harte(inv)) == inv


def test_format_symbols():
    assert ch.format_symbol(ch.parse("A:min7/b3")) == "Am7/C"
    assert ch.format_symbol(ch.parse("B:hdim7")) == "Bm7b5"
    assert ch.format_symbol(ch.parse("C:minmaj7")) == "CmMaj7"
    assert ch.format_symbol(None) == "N.C."


def test_format_flats_and_letter_spelled_bass():
    assert ch.format_symbol(ch.parse("A#:maj7"), prefer_flats=True) == "Bbmaj7"
    assert ch.format_symbol(ch.parse("D:7/3"), prefer_flats=True) == "D7/F#"
    assert ch.format_symbol(ch.parse("A#:maj/3"), prefer_flats=True) == "Bb/D"


def test_transpose_wraps_and_moves_bass():
    assert ch.transpose(ch.parse("B:maj"), 2) == Chord(1, "maj")
    assert ch.transpose(ch.parse("G:maj/3"), 5) == Chord(0, "maj", 4)
    assert ch.transpose(None, 3) is None


def test_render_capo():
    assert ch.render("G:maj/3", capo=2) == "F/A"
    assert ch.render("C:maj", transpose_by=-1, prefer_flats=True) == "B"
    assert ch.render("N", transpose_by=4) == "N.C."


def test_simplify():
    assert ch.render("C:maj7/3", simplify_chord=True) == "C"
    assert ch.render("B:hdim7", simplify_chord=True) == "Bdim"
    assert ch.render("D:sus4", simplify_chord=True) == "D"
    assert ch.render("E:min7", simplify_chord=True) == "Em"


def test_note_names_and_midi():
    assert ch.note_names(ch.parse("C:min7")) == ["C", "Eb", "G", "Bb"]
    assert ch.midi_notes(ch.parse("C:min7")) == [36, 60, 63, 67, 70]
    assert ch.midi_notes(ch.parse("G:maj/3")) == [47, 67, 71, 74]


def test_keys():
    assert ch.key_prefers_flats("F:maj") is True
    assert ch.key_prefers_flats("G:maj") is False
    assert ch.key_prefers_flats("G:min") is True
    assert ch.key_prefers_flats("E:min") is False
    assert ch.key_prefers_flats("G:maj", 3) is True
    assert ch.format_key("A#:maj") == "Bb major"
    assert ch.format_key("G:min", 1) == "G# minor"
    assert ch.key_symbol("G:min") == "Gm"
    assert ch.key_symbol("C:maj", 3) == "Eb"
```

- [ ] **Step 5: Run to verify failure**

Run: `python -m pytest server/tests/test_chord.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'server.theory.chord'`

- [ ] **Step 6: Implement `server/theory/chord.py`**

```python
"""Chord symbols: Harte-label parsing, letter-correct spelling, transposition."""
from __future__ import annotations

from dataclasses import dataclass

SHARPS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLATS = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
LETTERS = "CDEFGAB"
_NATURAL_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_NAME_TO_PC = {
    **{n: i for i, n in enumerate(SHARPS)},
    **{n: i for i, n in enumerate(FLATS)},
    "Cb": 11, "Fb": 4, "E#": 5, "B#": 0,
}

QUALITY_INTERVALS: dict[str, tuple[int, ...]] = {
    "maj": (0, 4, 7), "min": (0, 3, 7), "dim": (0, 3, 6), "aug": (0, 4, 8),
    "min6": (0, 3, 7, 9), "maj6": (0, 4, 7, 9), "min7": (0, 3, 7, 10),
    "minmaj7": (0, 3, 7, 11), "maj7": (0, 4, 7, 11), "7": (0, 4, 7, 10),
    "dim7": (0, 3, 6, 9), "hdim7": (0, 3, 6, 10), "sus2": (0, 2, 7), "sus4": (0, 5, 7),
}
QUALITY_SYMBOL = {
    "maj": "", "min": "m", "dim": "dim", "aug": "aug", "min6": "m6", "maj6": "6",
    "min7": "m7", "minmaj7": "mMaj7", "maj7": "maj7", "7": "7", "dim7": "dim7",
    "hdim7": "m7b5", "sus2": "sus2", "sus4": "sus4",
}
SIMPLE_QUALITY = {
    "maj": "maj", "maj6": "maj", "maj7": "maj", "7": "maj", "sus2": "maj", "sus4": "maj",
    "aug": "aug", "min": "min", "min6": "min", "min7": "min", "minmaj7": "min",
    "dim": "dim", "dim7": "dim", "hdim7": "dim",
}
_DEGREE_TO_INTERVAL = {
    "1": 0, "b2": 1, "2": 2, "b3": 3, "3": 4, "4": 5, "b5": 6, "5": 7,
    "#5": 8, "b6": 8, "6": 9, "bb7": 9, "b7": 10, "7": 11,
}
_INTERVAL_TO_DEGREE = {
    0: "1", 1: "b2", 2: "2", 3: "b3", 4: "3", 5: "4", 6: "b5", 7: "5",
    8: "#5", 9: "6", 10: "b7", 11: "7",
}
_INTERVAL_LETTER_STEPS = {0: 0, 1: 1, 2: 1, 3: 2, 4: 2, 5: 3, 6: 4, 7: 4, 8: 4, 9: 5, 10: 6, 11: 6}
_ACCIDENTALS = {-1: "b", 0: "", 1: "#"}
_FLAT_MAJOR_ROOTS = {5, 10, 3, 8, 1}
_FLAT_MINOR_ROOTS = {2, 7, 0, 5, 10, 3}


@dataclass(frozen=True)
class Chord:
    root: int
    quality: str
    bass: int | None = None


def parse(label: str) -> Chord | None:
    label = label.strip()
    if label in ("", "N", "X"):
        return None
    body, _, bass_part = label.partition("/")
    root_s, _, quality = body.partition(":")
    quality = quality or "maj"
    if root_s not in _NAME_TO_PC:
        raise ValueError(f"Unknown chord root: {root_s!r}")
    if quality not in QUALITY_INTERVALS:
        raise ValueError(f"Unknown chord quality: {quality!r}")
    root = _NAME_TO_PC[root_s]
    bass = None
    if bass_part:
        if bass_part in _DEGREE_TO_INTERVAL:
            bass = (root + _DEGREE_TO_INTERVAL[bass_part]) % 12
        elif bass_part in _NAME_TO_PC:
            bass = _NAME_TO_PC[bass_part]
        else:
            raise ValueError(f"Unknown bass note: {bass_part!r}")
        if bass == root:
            bass = None
    return Chord(root, quality, bass)


def to_harte(chord: Chord | None) -> str:
    if chord is None:
        return "N"
    s = f"{SHARPS[chord.root]}:{chord.quality}"
    if chord.bass is not None:
        s += "/" + _INTERVAL_TO_DEGREE[(chord.bass - chord.root) % 12]
    return s


def root_name(pc: int, prefer_flats: bool) -> str:
    return (FLATS if prefer_flats else SHARPS)[pc % 12]


def spell(root: str, interval: int) -> str:
    """Name the note `interval` semitones above `root`, using the right letter."""
    letter = LETTERS[(LETTERS.index(root[0]) + _INTERVAL_LETTER_STEPS[interval % 12]) % 7]
    target = (_NAME_TO_PC[root] + interval) % 12
    diff = (target - _NATURAL_PC[letter] + 6) % 12 - 6
    if diff in _ACCIDENTALS:
        return letter + _ACCIDENTALS[diff]
    return (FLATS if "b" in root else SHARPS)[target]


def format_symbol(chord: Chord | None, prefer_flats: bool = False) -> str:
    if chord is None:
        return "N.C."
    root = root_name(chord.root, prefer_flats)
    s = root + QUALITY_SYMBOL[chord.quality]
    if chord.bass is not None:
        s += "/" + spell(root, chord.bass - chord.root)
    return s


def note_names(chord: Chord, prefer_flats: bool = False) -> list[str]:
    root = root_name(chord.root, prefer_flats)
    return [spell(root, i) for i in QUALITY_INTERVALS[chord.quality]]


def pitch_classes(chord: Chord) -> list[int]:
    return [(chord.root + i) % 12 for i in QUALITY_INTERVALS[chord.quality]]


def transpose(chord: Chord | None, semitones: int) -> Chord | None:
    if chord is None:
        return None
    bass = None if chord.bass is None else (chord.bass + semitones) % 12
    return Chord((chord.root + semitones) % 12, chord.quality, bass)


def simplify(chord: Chord | None) -> Chord | None:
    if chord is None:
        return None
    return Chord(chord.root, SIMPLE_QUALITY[chord.quality], None)


def midi_notes(chord: Chord) -> list[int]:
    bass = 36 + (chord.bass if chord.bass is not None else chord.root)
    return [bass] + [60 + chord.root + i for i in QUALITY_INTERVALS[chord.quality]]


def render(label: str, transpose_by: int = 0, capo: int = 0,
           simplify_chord: bool = False, prefer_flats: bool = False) -> str:
    c = parse(label)
    if simplify_chord:
        c = simplify(c)
    return format_symbol(transpose(c, transpose_by - capo), prefer_flats)


def _parse_key(key_label: str) -> tuple[int, str]:
    c = parse(key_label)
    if c is None or c.quality not in ("maj", "min"):
        raise ValueError(f"Not a key: {key_label!r}")
    return c.root, c.quality


def key_prefers_flats(key_label: str, transpose_by: int = 0) -> bool:
    root, mode = _parse_key(key_label)
    root = (root + transpose_by) % 12
    return root in (_FLAT_MAJOR_ROOTS if mode == "maj" else _FLAT_MINOR_ROOTS)


def format_key(key_label: str, transpose_by: int = 0) -> str:
    root, mode = _parse_key(key_label)
    name = root_name(root + transpose_by, key_prefers_flats(key_label, transpose_by))
    return f"{name} {'major' if mode == 'maj' else 'minor'}"


def key_symbol(key_label: str, transpose_by: int = 0) -> str:
    root, mode = _parse_key(key_label)
    name = root_name(root + transpose_by, key_prefers_flats(key_label, transpose_by))
    return name + ("m" if mode == "min" else "")
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `python -m pytest server/tests/test_chord.py -v`
Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add requirements.txt pytest.ini server/__init__.py server/theory server/tests/__init__.py server/tests/test_chord.py
git commit -m "feat: scaffold server and add chord theory module"
```

---

### Task 2: Synthetic test audio + 144-template recognizer

**Files:**
- Create: `server/engine/__init__.py`, `server/engine/chords_tmpl.py`, `server/tests/synth.py`
- Test: `server/tests/test_chords_tmpl.py`

**Interfaces:**
- Consumes: `server.theory.chord.SHARPS`, `QUALITY_INTERVALS`
- Produces:
  - `server.tests.synth`: `SR = 22050`, `chord_audio(pcs: list[int], seconds: float, bass_pc: int | None = None) -> np.ndarray`, `silence(seconds: float) -> np.ndarray`, `progression(items: list[tuple[list[int], float, int | None]]) -> np.ndarray`, `click_track(bpm: float = 120, seconds: float = 12) -> np.ndarray`, `write_wav(path, y) -> Path`, `label_at(segments, t) -> str | None`
  - `server.engine.chords_tmpl`: `TEMPLATE_QUALITIES: list[str]` (12), `build_templates() -> tuple[list[str], np.ndarray]` (144 labels, 144×12), `viterbi(log_emit: np.ndarray, p_stay: float = 0.95) -> np.ndarray`, `recognize(y: np.ndarray, sr: int, hop: int = 2048) -> list[dict]`
  - **Segment dict** (used by every later task): `{"start": float, "end": float, "label": str, "alt": str | None, "confidence": float}`; later tasks add `"bass": str | None` and `"edited": bool`.

- [ ] **Step 1: Write the synthetic-audio helper**

`server/tests/synth.py`:
```python
"""Deterministic test audio: chords as near-pure tones with known answers."""
from pathlib import Path

import numpy as np
import soundfile as sf

SR = 22050


def _tone(midi: int, seconds: float, amp: float = 1.0) -> np.ndarray:
    f = 440.0 * 2 ** ((midi - 69) / 12)
    t = np.arange(int(seconds * SR)) / SR
    return amp * sum((0.3 ** (h - 1)) * np.sin(2 * np.pi * f * h * t) for h in range(1, 4))


def chord_audio(pcs: list[int], seconds: float, bass_pc: int | None = None) -> np.ndarray:
    y = sum(_tone(60 + pc, seconds) for pc in pcs)
    if bass_pc is not None:
        y = y + _tone(36 + bass_pc, seconds, amp=1.5)
    fade = int(0.01 * SR)
    env = np.ones_like(y)
    env[:fade] = np.linspace(0, 1, fade)
    env[-fade:] = np.linspace(1, 0, fade)
    y = y * env
    return (0.5 * y / np.max(np.abs(y))).astype(np.float32)


def silence(seconds: float) -> np.ndarray:
    return np.zeros(int(seconds * SR), dtype=np.float32)


def progression(items: list[tuple[list[int], float, int | None]]) -> np.ndarray:
    return np.concatenate([chord_audio(p, s, b) for p, s, b in items])


def click_track(bpm: float = 120, seconds: float = 12) -> np.ndarray:
    y = np.zeros(int(seconds * SR), dtype=np.float32)
    n = int(0.03 * SR)
    burst = np.random.default_rng(0).standard_normal(n) * np.exp(-np.linspace(0, 8, n))
    for k, t in enumerate(np.arange(0, seconds - 0.05, 60.0 / bpm)):
        i = int(t * SR)
        seg = y[i:i + n]
        seg += (1.0 if k % 4 == 0 else 0.5) * burst[:len(seg)].astype(np.float32)
    return 0.5 * y


def write_wav(path, y: np.ndarray) -> Path:
    path = Path(path)
    sf.write(path, y, SR)
    return path


def label_at(segments: list[dict], t: float) -> str | None:
    for s in segments:
        if s["start"] <= t < s["end"]:
            return s["label"]
    return None
```

Create empty `server/engine/__init__.py`.

- [ ] **Step 2: Write the failing tests**

`server/tests/test_chords_tmpl.py`:
```python
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
```

- [ ] **Step 3: Run to verify failure**

Run: `python -m pytest server/tests/test_chords_tmpl.py -v`
Expected: FAIL — `ImportError: cannot import name 'chords_tmpl'`

- [ ] **Step 4: Implement `server/engine/chords_tmpl.py`**

```python
"""144-template chord recognizer (12 roots x 12 qualities) on CQT chroma + Viterbi."""
import librosa
import numpy as np

from server.theory.chord import QUALITY_INTERVALS, SHARPS

TEMPLATE_QUALITIES = ["maj", "min", "7", "maj7", "min7", "dim", "dim7",
                      "hdim7", "aug", "sus2", "sus4", "min6"]
HOP = 2048
ROOT_WEIGHT = 1.5
P_STAY = 0.95
BETA = 20.0
SILENCE_RATIO = 0.02


def build_templates() -> tuple[list[str], np.ndarray]:
    labels, rows = [], []
    for quality in TEMPLATE_QUALITIES:
        for root in range(12):
            v = np.zeros(12)
            for i in QUALITY_INTERVALS[quality]:
                v[(root + i) % 12] = 1.0
            v[root] = ROOT_WEIGHT
            rows.append(v / np.linalg.norm(v))
            labels.append(f"{SHARPS[root]}:{quality}")
    return labels, np.array(rows)


def viterbi(log_emit: np.ndarray, p_stay: float = P_STAY) -> np.ndarray:
    """Most likely state path; transitions: stay=p_stay, any other state uniform."""
    n_states, n_frames = log_emit.shape
    log_stay = np.log(p_stay)
    log_move = np.log((1 - p_stay) / (n_states - 1))
    states = np.arange(n_states)
    delta = log_emit[:, 0].copy()
    back = np.zeros((n_states, n_frames), dtype=int)
    for t in range(1, n_frames):
        best_prev = int(delta.argmax())
        stay = delta + log_stay
        move = delta[best_prev] + log_move
        choose_stay = stay >= move
        back[:, t] = np.where(choose_stay, states, best_prev)
        delta = np.where(choose_stay, stay, move) + log_emit[:, t]
    path = np.zeros(n_frames, dtype=int)
    path[-1] = int(delta.argmax())
    for t in range(n_frames - 1, 0, -1):
        path[t - 1] = back[path[t], t]
    return path


def recognize(y: np.ndarray, sr: int, hop: int = HOP) -> list[dict]:
    labels, templates = build_templates()
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop)
    chroma = chroma / (np.linalg.norm(chroma, axis=0, keepdims=True) + 1e-9)
    scores = templates @ chroma
    rms = librosa.feature.rms(y=y, frame_length=hop * 2, hop_length=hop)[0]
    n = min(scores.shape[1], len(rms))
    scores, rms = scores[:, :n], rms[:n]
    path = viterbi(BETA * scores)
    silent = rms < SILENCE_RATIO * (rms.max() + 1e-9)
    frame_labels = ["N" if silent[i] else labels[path[i]] for i in range(n)]

    duration = len(y) / sr
    times = np.minimum(librosa.frames_to_time(np.arange(n + 1), sr=sr, hop_length=hop), duration)
    segments, start = [], 0
    for i in range(1, n + 1):
        if i < n and frame_labels[i] == frame_labels[start]:
            continue
        label = frame_labels[start]
        if label == "N":
            alt, conf = None, 1.0
        else:
            mean = scores[:, start:i].mean(axis=1)
            best = labels.index(label)
            alt = next(labels[k] for k in np.argsort(mean)[::-1] if k != best)
            conf = float(np.clip(mean[best], 0.0, 1.0))
        segments.append({"start": float(times[start]), "end": float(times[i]),
                         "label": label, "alt": alt, "confidence": round(conf, 3)})
        start = i
    return segments
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest server/tests/test_chords_tmpl.py -v`
Expected: all PASS. If `test_recognizes_advanced_progression` fails on one chord, print `segs` and tune `ROOT_WEIGHT` (1.3–2.0) — do not change the test's expected labels.

- [ ] **Step 6: Commit**

```bash
git add server/engine/__init__.py server/engine/chords_tmpl.py server/tests/synth.py server/tests/test_chords_tmpl.py
git commit -m "feat: add 144-template chord recognizer with viterbi smoothing"
```

---

### Task 3: Beat snapping and segment merging

**Files:**
- Create: `server/engine/snap.py`
- Test: `server/tests/test_snap.py`

**Interfaces:**
- Consumes: segment dicts (Task 2)
- Produces: `snap_segments(segments: list[dict], beats: list[float]) -> list[dict]`, `merge_identical(segments: list[dict]) -> list[dict]` — both return new dicts, never mutate input.

- [ ] **Step 1: Write the failing tests**

`server/tests/test_snap.py`:
```python
from server.engine.snap import merge_identical, snap_segments


def seg(start, end, label, conf=0.8):
    return {"start": start, "end": end, "label": label, "alt": None, "confidence": conf}


BEATS = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5]


def test_boundaries_move_to_nearest_beat():
    out = snap_segments([seg(0.0, 1.12, "C:maj"), seg(1.12, 2.93, "G:maj"), seg(2.93, 4.0, "A:min")], BEATS)
    assert [(s["start"], s["end"]) for s in out] == [(0.0, 1.0), (1.0, 3.0), (3.0, 4.0)]


def test_short_segment_merges_into_more_confident_neighbour():
    out = snap_segments([seg(0.0, 1.0, "C:maj", 0.9), seg(1.0, 1.2, "E:min", 0.3),
                         seg(1.2, 2.0, "G:maj", 0.5)], BEATS)
    assert [s["label"] for s in out] == ["C:maj", "G:maj"]
    assert out[0]["end"] == out[1]["start"]


def test_two_boundaries_snap_to_same_beat():
    out = snap_segments([seg(0.0, 0.95, "C:maj"), seg(0.95, 1.05, "D:min"),
                         seg(1.05, 2.0, "G:maj")], BEATS)
    for a, b in zip(out, out[1:]):
        assert a["end"] == b["start"]
    assert all(s["end"] > s["start"] for s in out)
    assert out[0]["start"] == 0.0 and out[-1]["end"] == 2.0


def test_merge_identical_weights_confidence_by_duration():
    out = merge_identical([seg(0, 1, "C:maj", 1.0), seg(1, 4, "C:maj", 0.6), seg(4, 5, "G:maj")])
    assert len(out) == 2
    assert out[0]["end"] == 4
    assert abs(out[0]["confidence"] - 0.7) < 1e-6


def test_no_beats_only_merges_and_does_not_mutate():
    segs = [seg(0, 1, "C:maj"), seg(1, 2, "C:maj")]
    out = snap_segments(segs, [])
    assert len(out) == 1 and segs[0]["end"] == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest server/tests/test_snap.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'server.engine.snap'`

- [ ] **Step 3: Implement `server/engine/snap.py`**

```python
"""Align chord boundaries to beats and clean up tiny / duplicate segments."""
import numpy as np


def merge_identical(segments: list[dict]) -> list[dict]:
    out: list[dict] = []
    for s in segments:
        if out and out[-1]["label"] == s["label"]:
            prev = out[-1]
            d1, d2 = prev["end"] - prev["start"], s["end"] - s["start"]
            if d1 + d2 > 0:
                prev["confidence"] = round((prev["confidence"] * d1 + s["confidence"] * d2) / (d1 + d2), 6)
            prev["end"] = s["end"]
        else:
            out.append(dict(s))
    return out


def _merge_short(segments: list[dict], min_len: float) -> list[dict]:
    segs = [dict(s) for s in segments]
    while len(segs) > 1:
        lengths = [s["end"] - s["start"] for s in segs]
        i = int(np.argmin(lengths))
        if lengths[i] >= min_len - 1e-6:
            break
        if i == 0:
            j = 1
        elif i == len(segs) - 1:
            j = i - 1
        else:
            j = i - 1 if segs[i - 1]["confidence"] >= segs[i + 1]["confidence"] else i + 1
        if j < i:
            segs[j]["end"] = segs[i]["end"]
        else:
            segs[j]["start"] = segs[i]["start"]
        del segs[i]
    return segs


def snap_segments(segments: list[dict], beats: list[float]) -> list[dict]:
    if not segments:
        return []
    if len(beats) < 2:
        return merge_identical([dict(s) for s in segments])
    b = np.asarray(beats, dtype=float)
    bounds = [segments[0]["start"]]
    for s in segments[1:]:
        bounds.append(float(b[np.abs(b - s["start"]).argmin()]))
    bounds.append(segments[-1]["end"])
    for i in range(1, len(bounds)):
        bounds[i] = max(bounds[i], bounds[i - 1])
    snapped = []
    for i, s in enumerate(segments):
        if bounds[i + 1] - bounds[i] > 1e-6:
            snapped.append({**s, "start": bounds[i], "end": bounds[i + 1]})
    min_len = float(np.median(np.diff(b)))
    return merge_identical(_merge_short(snapped, min_len))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest server/tests/test_snap.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add server/engine/snap.py server/tests/test_snap.py
git commit -m "feat: snap chord boundaries to beats and merge short segments"
```

---

### Task 4: Bass detection and inversions

**Files:**
- Create: `server/engine/bass.py`
- Test: `server/tests/test_bass.py`

**Interfaces:**
- Consumes: `chord.parse`, `chord.to_harte`, `chord.pitch_classes`, `chord.SHARPS`, `Chord`
- Produces: `bass_pitch_classes(y: np.ndarray, sr: int, segments: list[dict]) -> list[int | None]`, `apply_inversions(segments: list[dict], bass_pcs: list[int | None]) -> list[dict]` (adds `"bass": str | None`, rewrites `label` with a Harte slash when the bass is a non-root chord tone).

- [ ] **Step 1: Write the failing tests**

`server/tests/test_bass.py`:
```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest server/tests/test_bass.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'server.engine.bass'`

- [ ] **Step 3: Implement `server/engine/bass.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest server/tests/test_bass.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add server/engine/bass.py server/tests/test_bass.py
git commit -m "feat: detect bass notes and label chord inversions"
```

---

### Task 5: Key estimation

**Files:**
- Create: `server/engine/key.py`
- Test: `server/tests/test_key.py`

**Interfaces:**
- Produces: `estimate_key(y: np.ndarray, sr: int) -> str` — returns `"<SHARP-ROOT>:maj"` or `"<SHARP-ROOT>:min"`.

- [ ] **Step 1: Write the failing tests**

`server/tests/test_key.py`:
```python
from server.engine.key import estimate_key
from server.tests.synth import SR, progression


def test_c_major_cadence():
    y = progression([([0, 4, 7], 1.5, 0), ([5, 9, 0], 1.5, 5), ([7, 11, 2], 1.5, 7), ([0, 4, 7], 1.5, 0)])
    assert estimate_key(y, SR) == "C:maj"


def test_a_minor_cadence():
    y = progression([([9, 0, 4], 1.5, 9), ([2, 5, 9], 1.5, 2), ([4, 8, 11], 1.5, 4), ([9, 0, 4], 1.5, 9)])
    assert estimate_key(y, SR) == "A:min"
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest server/tests/test_key.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'server.engine.key'`

- [ ] **Step 3: Implement `server/engine/key.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest server/tests/test_key.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add server/engine/key.py server/tests/test_key.py
git commit -m "feat: estimate song key with krumhansl-schmuckler profiles"
```

---

### Task 6: Beat tracking (beat_this)

**Files:**
- Create: `server/engine/beats.py`
- Test: `server/tests/test_beats.py`

**Interfaces:**
- Produces: `detect_beats(wav_path: Path, device: str = "cpu") -> dict` → `{"beats": list[float], "downbeats": list[float], "tempo": float}`; `summarize(beats, downbeats) -> dict` (pure, same shape).

- [ ] **Step 1: Write the failing tests**

`server/tests/test_beats.py`:
```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest server/tests/test_beats.py -v -m "slow or not slow"`
Expected: FAIL — `ModuleNotFoundError: No module named 'server.engine.beats'`

- [ ] **Step 3: Implement `server/engine/beats.py`**

```python
"""Beat and downbeat tracking with beat_this (CPJKU)."""
from pathlib import Path

import numpy as np

_models: dict[str, object] = {}


def summarize(beats: list[float], downbeats: list[float]) -> dict:
    beats = [round(float(b), 3) for b in beats]
    downbeats = [round(float(d), 3) for d in downbeats] or beats[::4]
    tempo = 0.0 if len(beats) < 2 else round(60.0 / float(np.median(np.diff(beats))), 1)
    return {"beats": beats, "downbeats": downbeats, "tempo": tempo}


def detect_beats(wav_path: Path, device: str = "cpu") -> dict:
    from beat_this.inference import File2Beats

    if device not in _models:
        _models[device] = File2Beats(checkpoint_path="final0", device=device, dbn=False)
    beats, downbeats = _models[device](str(wav_path))
    return summarize(list(beats), list(downbeats))
```

- [ ] **Step 4: Run tests to verify they pass (including slow)**

Run: `python -m pytest server/tests/test_beats.py -v -m "slow or not slow"`
Expected: all PASS (first run downloads the `final0` checkpoint). If `File2Beats` import fails, run `python -c "import beat_this.inference as m; print(dir(m))"` and match the class name from the installed version.

- [ ] **Step 5: Commit**

```bash
git add server/engine/beats.py server/tests/test_beats.py
git commit -m "feat: add beat and downbeat tracking with beat_this"
```

---

### Task 7: BTC large-vocabulary recognizer + model setup script

**Files:**
- Create: `server/engine/chords_btc.py`, `scripts/setup_models.py`
- Test: `server/tests/test_chords_btc.py`

**Interfaces:**
- Consumes: `server.engine.snap.merge_identical`, `chord.SHARPS`
- Produces: `DEFAULT_WEIGHTS_DIR: Path`, `is_available(weights_dir: Path) -> bool`, `idx_to_label(idx: int) -> str`, `frames_to_segments(probs: np.ndarray, frame_sec: float, duration: float) -> list[dict]`, `recognize(wav_path: Path, weights_dir: Path, device: str = "cpu") -> list[dict]`

- [ ] **Step 1: Write the setup script and fetch the model**

`scripts/setup_models.py`:
```python
"""Clone BTC-ISMIR19 (code + pretrained weights) into server/engine/weights/."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.engine.chords_btc import DEFAULT_WEIGHTS_DIR, REPO_DIRNAME, is_available  # noqa: E402

REPO_URL = "https://github.com/jayg996/BTC-ISMIR19.git"


def main() -> int:
    DEFAULT_WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    repo = DEFAULT_WEIGHTS_DIR / REPO_DIRNAME
    if not repo.exists():
        subprocess.run(["git", "clone", "--depth", "1", REPO_URL, str(repo)], check=True)
    if is_available(DEFAULT_WEIGHTS_DIR):
        print(f"BTC model ready: {repo}")
        return 0
    print(f"Cloned {repo} but the large-vocab weights file is missing.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

(The script imports `chords_btc`, so create the module in Step 4 first if running strictly in order; Step 5 runs the script.)

- [ ] **Step 2: Write the failing tests**

`server/tests/test_chords_btc.py`:
```python
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
```

- [ ] **Step 3: Run to verify failure**

Run: `python -m pytest server/tests/test_chords_btc.py -v`
Expected: FAIL — `ImportError: cannot import name 'chords_btc'`

- [ ] **Step 4: Implement `server/engine/chords_btc.py`**

```python
"""Wrapper around BTC (Park et al., ISMIR 2019), large-vocabulary chord model."""
import sys
from pathlib import Path

import numpy as np

from server.engine.snap import merge_identical
from server.theory.chord import SHARPS

DEFAULT_WEIGHTS_DIR = Path(__file__).resolve().parent / "weights"
REPO_DIRNAME = "BTC-ISMIR19"
WEIGHTS_RELPATH = Path("test") / "btc_model_large_voca.pt"
BTC_QUALITIES = ["min", "maj", "dim", "aug", "min6", "maj6", "min7",
                 "minmaj7", "maj7", "7", "dim7", "hdim7", "sus2", "sus4"]
_cache: dict[tuple[str, str], tuple] = {}


def is_available(weights_dir: Path) -> bool:
    return (Path(weights_dir) / REPO_DIRNAME / WEIGHTS_RELPATH).is_file()


def idx_to_label(idx: int) -> str:
    if idx >= 168:
        return "N"
    return f"{SHARPS[idx // 14]}:{BTC_QUALITIES[idx % 14]}"


def frames_to_segments(probs: np.ndarray, frame_sec: float, duration: float) -> list[dict]:
    top = probs.argmax(axis=1)
    segs, start, n = [], 0, len(top)
    for i in range(1, n + 1):
        if i < n and top[i] == top[start]:
            continue
        mean = probs[start:i].mean(axis=0)
        best = int(top[start])
        label = idx_to_label(best)
        alt = None
        if label != "N":
            alt = next((idx_to_label(int(k)) for k in np.argsort(mean)[::-1]
                        if int(k) != best and idx_to_label(int(k)) not in ("N", label)), None)
        segs.append({"start": round(start * frame_sec, 3), "end": round(min(i * frame_sec, duration), 3),
                     "label": label, "alt": alt, "confidence": round(float(mean[best]), 3)})
        start = i
    return merge_identical(segs)


def _load(weights_dir: Path, device: str):
    key = (str(weights_dir), device)
    if key in _cache:
        return _cache[key]
    import torch
    import yaml

    repo = Path(weights_dir) / REPO_DIRNAME
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))
    from btc_model import BTC_model

    cfg = yaml.safe_load((repo / "run_config.yaml").read_text())
    cfg["feature"]["large_voca"] = True
    cfg["model"]["num_chords"] = 170
    model = BTC_model(config=cfg["model"]).to(device)
    ckpt = torch.load(repo / WEIGHTS_RELPATH, map_location=device, weights_only=False)
    model.load_state_dict(ckpt["model"])
    model.eval()
    _cache[key] = (model, cfg, np.asarray(ckpt["mean"]), np.asarray(ckpt["std"]))
    return _cache[key]


def recognize(wav_path: Path, weights_dir: Path, device: str = "cpu") -> list[dict]:
    import librosa
    import torch

    model, cfg, mean, std = _load(weights_dir, device)
    feat, sr = cfg["feature"], cfg["mp3"]["song_hz"]
    timestep = cfg["model"]["timestep"]
    y, _ = librosa.load(str(wav_path), sr=sr, mono=True)
    cqt = librosa.cqt(y, sr=sr, n_bins=feat["n_bins"], bins_per_octave=feat["bins_per_octave"],
                      hop_length=feat["hop_length"])
    x = (np.log(np.abs(cqt) + 1e-6).T - mean) / std
    n_frames = x.shape[0]
    x = np.pad(x, ((0, (-n_frames) % timestep), (0, 0)))
    chunks = []
    with torch.no_grad():
        t = torch.tensor(x, dtype=torch.float32, device=device).unsqueeze(0)
        for i in range(0, t.shape[1], timestep):
            hidden, _ = model.self_attn_layers(t[:, i:i + timestep, :])
            logits = model.output_layer.output_projection(hidden)
            chunks.append(torch.softmax(logits, dim=-1)[0].cpu().numpy())
    probs = np.concatenate(chunks)[:n_frames]
    return frames_to_segments(probs, feat["hop_length"] / sr, duration=len(y) / sr)
```

- [ ] **Step 5: Fetch the model and verify the BTC repo matches the wrapper's assumptions**

```powershell
python scripts/setup_models.py
Select-String -Path server/engine/weights/BTC-ISMIR19/run_config.yaml -Pattern "song_hz|n_bins|bins_per_octave|hop_length|timestep|feature_size"
Select-String -Path server/engine/weights/BTC-ISMIR19/btc_model.py -Pattern "self_attn_layers|output_layer|output_projection|config\["
Select-String -Path server/engine/weights/BTC-ISMIR19/utils/mir_eval_modules.py -Pattern "def idx2voca_chord" -Context 0,20
```
Expected: `BTC model ready`; config has `song_hz: 22050`, `n_bins: 144`, `bins_per_octave: 24`, `hop_length: 2048`, `timestep: 108`; `btc_model.py` defines `self_attn_layers`, `output_layer`, `output_projection` and reads `config['...']` (dict access); `idx2voca_chord` uses quality order `min, maj, dim, aug, min6, maj6, min7, minmaj7, maj7, 7, dim7, hdim7, sus2, sus4` with 168 = `X`, 169 = `N`. If any name or order differs, update `chords_btc.py` (and `BTC_QUALITIES`) to match the repo — the repo is the source of truth.

- [ ] **Step 6: Run tests to verify they pass (including slow)**

Run: `python -m pytest server/tests/test_chords_btc.py -v -m "slow or not slow"`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add server/engine/chords_btc.py scripts/setup_models.py server/tests/test_chords_btc.py
git commit -m "feat: add BTC large-vocabulary chord recognizer and model setup script"
```

---

### Task 8: YouTube ingest

**Files:**
- Create: `server/engine/ingest.py`
- Test: `server/tests/test_ingest.py`

**Interfaces:**
- Produces: `MAX_DURATION = 900`, `class IngestError(Exception)` (message is user-facing), `parse_video_id(url: str) -> str | None`, `probe(video_id: str) -> dict` (`{"title": str, "duration": float}`), `download_wav(video_id: str, out_dir: Path) -> Path`, `fetch_audio(video_id: str, out_dir: Path) -> tuple[dict, Path]`

- [ ] **Step 1: Write the failing tests**

`server/tests/test_ingest.py`:
```python
import pytest
from yt_dlp.utils import DownloadError

from server.engine import ingest
from server.engine.ingest import IngestError, parse_video_id

VID = "dQw4w9WgXcQ"


@pytest.mark.parametrize("url", [
    f"https://www.youtube.com/watch?v={VID}",
    f"https://youtube.com/watch?v={VID}&t=42s&list=PL123",
    f"https://www.youtube.com/watch?feature=share&v={VID}",
    f"https://youtu.be/{VID}?si=abcDEF",
    f"https://www.youtube.com/shorts/{VID}",
    f"https://music.youtube.com/watch?v={VID}&feature=share",
    f"https://m.youtube.com/watch?v={VID}",
    f"youtube.com/watch?v={VID}",
    f"  https://www.youtube.com/embed/{VID}  ",
])
def test_parse_video_id_variants(url):
    assert parse_video_id(url) == VID


@pytest.mark.parametrize("url", ["", "hello", "https://vimeo.com/123",
                                 "https://www.youtube.com/watch?v=short", "https://youtu.be/"])
def test_parse_video_id_rejects(url):
    assert parse_video_id(url) is None


class FakeYDL:
    info: dict = {}
    error: str | None = None

    def __init__(self, opts):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def extract_info(self, url, download=False):
        if FakeYDL.error:
            raise DownloadError(FakeYDL.error)
        return FakeYDL.info


@pytest.fixture
def fake_ydl(monkeypatch):
    FakeYDL.info, FakeYDL.error = {}, None
    monkeypatch.setattr(ingest, "YoutubeDL", FakeYDL)
    return FakeYDL


def test_probe_ok(fake_ydl):
    fake_ydl.info = {"title": "Song", "duration": 200, "live_status": "not_live"}
    assert ingest.probe(VID) == {"title": "Song", "duration": 200.0}


@pytest.mark.parametrize("info,msg", [
    ({"title": "x", "duration": 0, "is_live": True}, "Live streams"),
    ({"title": "x", "duration": 1200}, "limit is 15 min"),
])
def test_probe_rejects(fake_ydl, info, msg):
    fake_ydl.info = info
    with pytest.raises(IngestError, match=msg):
        ingest.probe(VID)


@pytest.mark.parametrize("err,msg", [
    ("ERROR: [youtube] x: Private video. Sign in if you've been granted access", "private"),
    ("ERROR: [youtube] x: Sign in to confirm your age", "age-restricted"),
    ("ERROR: [youtube] x: Video unavailable", "unavailable"),
    ("ERROR: something new broke", "pip install -U yt-dlp"),
])
def test_probe_maps_errors(fake_ydl, err, msg):
    fake_ydl.error = err
    with pytest.raises(IngestError, match=msg):
        ingest.probe(VID)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest server/tests/test_ingest.py -v`
Expected: FAIL — `ImportError: cannot import name 'ingest'`

- [ ] **Step 3: Implement `server/engine/ingest.py`**

```python
"""YouTube link -> mono 22.05 kHz WAV via yt-dlp + ffmpeg."""
import re
import subprocess
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

MAX_DURATION = 900
SAMPLE_RATE = 22050
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_YT_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}


class IngestError(Exception):
    """Raised with a message that is safe to show to the user."""


def parse_video_id(url: str) -> str | None:
    url = url.strip()
    if not url:
        return None
    if "://" not in url:
        url = "https://" + url
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    candidate = None
    if host == "youtu.be":
        candidate = parsed.path.lstrip("/").split("/")[0]
    elif host in _YT_HOSTS:
        parts = [p for p in parsed.path.split("/") if p]
        if parts[:1] == ["watch"]:
            candidate = parse_qs(parsed.query).get("v", [None])[0]
        elif len(parts) >= 2 and parts[0] in ("shorts", "embed", "live"):
            candidate = parts[1]
    return candidate if candidate and _ID_RE.match(candidate) else None


def _watch_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def _friendly(message: str) -> str:
    m = message.lower()
    if "private video" in m:
        return "This video is private."
    if "confirm your age" in m or "age-restricted" in m:
        return "This video is age-restricted and can't be downloaded."
    if "video unavailable" in m or "has been removed" in m:
        return "This video is unavailable or was removed."
    return "Couldn't download this video. Try updating yt-dlp: pip install -U yt-dlp"


def probe(video_id: str) -> dict:
    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "noplaylist": True}
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(_watch_url(video_id), download=False)
    except DownloadError as e:
        raise IngestError(_friendly(str(e))) from e
    if info.get("is_live") or info.get("live_status") in ("is_live", "is_upcoming"):
        raise IngestError("Live streams can't be analyzed.")
    duration = float(info.get("duration") or 0)
    if duration > MAX_DURATION:
        raise IngestError(f"This video is {int(duration // 60)} min long; the limit is 15 min.")
    return {"title": info.get("title") or video_id, "duration": duration}


def download_wav(video_id: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    opts = {"format": "bestaudio/best", "outtmpl": str(out_dir / "source.%(ext)s"),
            "quiet": True, "no_warnings": True, "noplaylist": True}
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(_watch_url(video_id), download=True)
            source = Path(ydl.prepare_filename(info))
    except DownloadError as e:
        raise IngestError(_friendly(str(e))) from e
    wav = out_dir / "audio.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(source),
                    "-ac", "1", "-ar", str(SAMPLE_RATE), str(wav)], check=True, capture_output=True)
    source.unlink(missing_ok=True)
    return wav


def fetch_audio(video_id: str, out_dir: Path) -> tuple[dict, Path]:
    meta = probe(video_id)
    return meta, download_wav(video_id, out_dir)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest server/tests/test_ingest.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add server/engine/ingest.py server/tests/test_ingest.py
git commit -m "feat: add youtube ingest with url parsing and friendly errors"
```

---

### Task 9: Stem separation (Demucs)

**Files:**
- Create: `server/engine/separate.py`
- Test: `server/tests/test_separate.py`

**Interfaces:**
- Produces: `STEMS = ("bass", "drums", "other", "vocals")`, `pick_device() -> str`, `separate(wav: Path, out_dir: Path, device: str | None = None) -> dict[str, Path]`, `load_mix(paths: list[Path], sr: int) -> np.ndarray`

- [ ] **Step 1: Write the failing tests**

`server/tests/test_separate.py`:
```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest server/tests/test_separate.py -v`
Expected: FAIL — `ImportError: cannot import name 'separate'`

- [ ] **Step 3: Implement `server/engine/separate.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest server/tests/test_separate.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add server/engine/separate.py server/tests/test_separate.py
git commit -m "feat: add demucs stem separation with cpu fallback"
```

---

### Task 10: Analysis pipeline

**Files:**
- Create: `server/engine/pipeline.py`
- Test: `server/tests/test_pipeline.py`

**Interfaces:**
- Consumes: `ingest.fetch_audio`, `separate.separate/load_mix`, `beats.detect_beats`, `chords_btc.is_available/recognize/DEFAULT_WEIGHTS_DIR`, `chords_tmpl.recognize`, `snap.snap_segments/merge_identical`, `bass.bass_pitch_classes/apply_inversions`, `key.estimate_key`
- Produces:
  - `SR = 22050`, `class Cancelled(Exception)`
  - `@dataclass class Options(mode: str = "fast", engine: str = "auto", weights_dir: Path = DEFAULT_WEIGHTS_DIR)`
  - `ProgressFn = Callable[[str, int, str], None]` — `(state, percent, message)`
  - `analyze(video_id: str, work_dir: Path, options: Options, progress: ProgressFn, fetch_audio=ingest.fetch_audio) -> dict` — returns the **timeline** (spec §2 contract + `warnings`).

- [ ] **Step 1: Write the failing tests**

`server/tests/test_pipeline.py`:
```python
from server.engine import pipeline
from server.engine.pipeline import Options, analyze
from server.tests.synth import label_at, progression, write_wav


def fake_fetch(video_id, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    y = progression([([0, 4, 7], 4.0, 0), ([7, 11, 2], 4.0, 11), ([9, 0, 4], 4.0, 9)])
    return {"title": "Fixture Song", "duration": 12.0}, write_wav(out_dir / "audio.wav", y)


def fake_beats(wav_path, device="cpu"):
    beats = [i * 0.5 for i in range(24)]
    return {"beats": beats, "downbeats": beats[::4], "tempo": 120.0}


def run(tmp_path, monkeypatch, **opts):
    monkeypatch.setattr(pipeline.beats, "detect_beats", fake_beats)
    states = []
    timeline = analyze("vid00000001", tmp_path / "work", Options(**opts),
                       lambda s, p, m: states.append(s), fetch_audio=fake_fetch)
    return timeline, states


def test_fast_template_pipeline(tmp_path, monkeypatch):
    t, states = run(tmp_path, monkeypatch, mode="fast", engine="template")
    assert states == ["downloading", "beats", "chords", "bass", "key"]
    assert t["video_id"] == "vid00000001" and t["title"] == "Fixture Song"
    assert t["tempo"] == 120.0 and t["time_signature"] == 4
    assert t["engine"] == {"chords": "template", "separated": False, "version": "1"}
    assert t["warnings"] == []
    assert label_at(t["segments"], 2.0) == "C:maj"
    assert label_at(t["segments"], 6.0) == "G:maj/3"
    assert label_at(t["segments"], 10.0) == "A:min"
    beat_set = set(t["beats"])
    for s in t["segments"][1:]:
        assert s["start"] in beat_set
    assert all(s["edited"] is False and "bass" in s for s in t["segments"])
    assert t["key"] in ("C:maj", "A:min", "G:maj")


def test_missing_btc_weights_warns_and_falls_back(tmp_path, monkeypatch):
    t, _ = run(tmp_path, monkeypatch, mode="fast", engine="auto", weights_dir=tmp_path / "nothing")
    assert t["engine"]["chords"] == "template"
    assert "setup_models.py" in t["warnings"][0]


def test_progress_callback_can_cancel(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline.beats, "detect_beats", fake_beats)

    def progress(state, pct, msg):
        if state == "beats":
            raise pipeline.Cancelled()

    try:
        analyze("vid00000001", tmp_path / "w", Options(engine="template"), progress, fetch_audio=fake_fetch)
    except pipeline.Cancelled:
        pass
    else:
        raise AssertionError("expected Cancelled")
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest server/tests/test_pipeline.py -v`
Expected: FAIL — `ImportError: cannot import name 'pipeline'`

- [ ] **Step 3: Implement `server/engine/pipeline.py`**

```python
"""YouTube video id -> chord timeline, reporting progress along the way."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import librosa
import soundfile as sf

from server.engine import bass, beats, chords_btc, chords_tmpl, ingest, key, separate, snap
from server.engine.chords_btc import DEFAULT_WEIGHTS_DIR

SR = 22050
ENGINE_VERSION = "1"
ProgressFn = Callable[[str, int, str], None]
MISSING_WEIGHTS_WARNING = ("BTC model weights not found, so the simpler template recognizer was used. "
                           "Run `python scripts/setup_models.py` for better accuracy.")


class Cancelled(Exception):
    pass


@dataclass
class Options:
    mode: str = "fast"            # "fast" | "accurate"
    engine: str = "auto"          # "auto" | "btc" | "template"
    weights_dir: Path = field(default_factory=lambda: DEFAULT_WEIGHTS_DIR)


def analyze(video_id: str, work_dir: Path, options: Options, progress: ProgressFn,
            fetch_audio=ingest.fetch_audio) -> dict:
    work_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []

    progress("downloading", 5, "Downloading audio")
    meta, wav = fetch_audio(video_id, work_dir)
    y, _ = librosa.load(str(wav), sr=SR, mono=True)
    harmonic_y, bass_y, harmonic_path, separated = y, y, wav, False

    if options.mode == "accurate":
        progress("separating", 15, "Separating vocals, drums and bass (the slow part)")
        stems = separate.separate(wav, work_dir / "stems")
        harmonic_y = separate.load_mix([stems["bass"], stems["other"]], SR)
        bass_y, _ = librosa.load(str(stems["bass"]), sr=SR, mono=True)
        harmonic_path = work_dir / "harmonic.wav"
        sf.write(harmonic_path, harmonic_y, SR)
        separated = True

    progress("beats", 45, "Detecting beats")
    beat_info = beats.detect_beats(wav)

    progress("chords", 60, "Recognizing chords")
    if options.engine != "template" and chords_btc.is_available(options.weights_dir):
        segments = chords_btc.recognize(harmonic_path, options.weights_dir)
        engine_name = "btc-large"
    else:
        if options.engine != "template":
            warnings.append(MISSING_WEIGHTS_WARNING)
        segments = chords_tmpl.recognize(harmonic_y, SR)
        engine_name = "template"

    progress("bass", 80, "Detecting bass notes and inversions")
    segments = snap.snap_segments(segments, beat_info["beats"])
    segments = bass.apply_inversions(segments, bass.bass_pitch_classes(bass_y, SR, segments))
    segments = [{**s, "edited": False} for s in snap.merge_identical(segments)]

    progress("key", 92, "Estimating key")
    key_label = key.estimate_key(harmonic_y, SR)

    return {
        "video_id": video_id,
        "title": meta["title"],
        "duration": round(len(y) / SR, 3),
        "key": key_label,
        "tempo": beat_info["tempo"],
        "time_signature": 4,
        "beats": beat_info["beats"],
        "downbeats": beat_info["downbeats"],
        "segments": segments,
        "engine": {"chords": engine_name, "separated": separated, "version": ENGINE_VERSION},
        "warnings": warnings,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest server/tests/test_pipeline.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add server/engine/pipeline.py server/tests/test_pipeline.py
git commit -m "feat: add analysis pipeline chaining ingest, beats, chords, bass and key"
```

---

### Task 11: SQLite store

**Files:**
- Create: `server/store.py`
- Test: `server/tests/test_store.py`, `server/tests/conftest.py`

**Interfaces:**
- Consumes: `chord.parse`, `chord.to_harte`, `chord.SHARPS`
- Produces: `class Store(path: Path | str)` with
  `create_job(video_id: str, mode: str) -> str`, `update_job(job_id: str, **fields) -> None` (fields ⊆ state, progress, message, error, song_id),
  `get_job(job_id: str) -> dict | None`, `fail_interrupted_jobs() -> int`,
  `save_song(timeline: dict) -> str`, `get_song(song_id: str) -> dict | None` (keys: id, video_id, title, duration, key, tempo, created_at, updated_at, timeline),
  `get_song_by_video(video_id: str) -> dict | None`, `list_songs() -> list[dict]` (no timeline),
  `update_segment(song_id: str, index: int, label: str, apply_to_all: bool = False) -> dict` (raises `KeyError` unknown song, `IndexError` bad index, `ValueError` bad label),
  `reset_song(song_id: str) -> dict`, `delete_song(song_id: str) -> bool`
- Produces fixture `timeline` in `server/tests/conftest.py` used by Tasks 11–15.

- [ ] **Step 1: Write the shared timeline fixture**

`server/tests/conftest.py`:
```python
import copy

import pytest

TIMELINE = {
    "video_id": "abcdefghijk",
    "title": "Test Song",
    "duration": 8.0,
    "key": "G:min",
    "tempo": 120.0,
    "time_signature": 4,
    "beats": [i * 0.5 for i in range(16)],
    "downbeats": [0.0, 2.0, 4.0, 6.0],
    "segments": [
        {"start": 0.0, "end": 2.0, "label": "C:min7", "alt": "C:min", "confidence": 0.8, "bass": "C", "edited": False},
        {"start": 2.0, "end": 4.0, "label": "F:7", "alt": "F:maj", "confidence": 0.7, "bass": "F", "edited": False},
        {"start": 4.0, "end": 5.0, "label": "A#:maj7", "alt": None, "confidence": 0.6, "bass": "A#", "edited": False},
        {"start": 5.0, "end": 6.0, "label": "D#:maj7", "alt": None, "confidence": 0.6, "bass": "D#", "edited": False},
        {"start": 6.0, "end": 8.0, "label": "D:7/3", "alt": "D:7", "confidence": 0.5, "bass": "F#", "edited": False},
    ],
    "engine": {"chords": "btc-large", "separated": True, "version": "1"},
    "warnings": [],
}


@pytest.fixture
def timeline():
    return copy.deepcopy(TIMELINE)
```

- [ ] **Step 2: Write the failing tests**

`server/tests/test_store.py`:
```python
import pytest

from server.store import Store


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "test.db")


def test_job_lifecycle(store):
    job_id = store.create_job("abcdefghijk", "fast")
    assert store.get_job(job_id)["state"] == "queued"
    store.update_job(job_id, state="chords", progress=60, message="Recognizing chords")
    job = store.get_job(job_id)
    assert (job["state"], job["progress"], job["message"]) == ("chords", 60, "Recognizing chords")
    assert store.get_job("missing") is None


def test_update_job_rejects_unknown_fields(store):
    job_id = store.create_job("abcdefghijk", "fast")
    with pytest.raises(ValueError):
        store.update_job(job_id, video_id="other")


def test_fail_interrupted_jobs(store):
    running = store.create_job("abcdefghijk", "fast")
    store.update_job(running, state="beats")
    done = store.create_job("abcdefghijk", "fast")
    store.update_job(done, state="done")
    assert store.fail_interrupted_jobs() == 1
    assert store.get_job(running)["state"] == "failed"
    assert store.get_job(done)["state"] == "done"


def test_save_is_upsert_by_video(store, timeline):
    first = store.save_song(timeline)
    timeline["title"] = "Renamed"
    assert store.save_song(timeline) == first
    song = store.get_song(first)
    assert song["title"] == "Renamed" and song["timeline"]["key"] == "G:min"
    assert store.get_song_by_video("abcdefghijk")["id"] == first
    assert [s["id"] for s in store.list_songs()] == [first]
    assert "timeline" not in store.list_songs()[0]


def test_edit_single_and_apply_to_all(store, timeline):
    timeline["segments"][2]["label"] = "C:min7"
    song_id = store.save_song(timeline)
    t = store.update_segment(song_id, 0, "A#:maj/3")
    assert t["segments"][0]["label"] == "A#:maj/3" and t["segments"][0]["bass"] == "D"
    assert t["segments"][0]["edited"] is True
    assert t["segments"][2]["label"] == "C:min7"
    t = store.update_segment(song_id, 2, "G:min", apply_to_all=True)
    assert t["segments"][2]["label"] == "G:min"


def test_edit_apply_to_all_changes_every_match(store, timeline):
    timeline["segments"][3]["label"] = "C:min7"
    song_id = store.save_song(timeline)
    t = store.update_segment(song_id, 0, "N", apply_to_all=True)
    assert [s["label"] for s in t["segments"]][:4] == ["N", "F:7", "A#:maj7", "N"]
    assert t["segments"][0]["bass"] is None


def test_edit_errors(store, timeline):
    song_id = store.save_song(timeline)
    with pytest.raises(KeyError):
        store.update_segment("missing", 0, "C:maj")
    with pytest.raises(IndexError):
        store.update_segment(song_id, 99, "C:maj")
    with pytest.raises(ValueError):
        store.update_segment(song_id, 0, "H:maj")


def test_reset_and_delete(store, timeline):
    song_id = store.save_song(timeline)
    store.update_segment(song_id, 0, "G:maj")
    assert store.reset_song(song_id)["segments"][0]["label"] == "C:min7"
    assert store.delete_song(song_id) is True
    assert store.get_song(song_id) is None
    assert store.delete_song(song_id) is False
```

- [ ] **Step 3: Run to verify failure**

Run: `python -m pytest server/tests/test_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'server.store'`

- [ ] **Step 4: Implement `server/store.py`**

```python
"""SQLite persistence for analysis jobs and song chord timelines."""
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from server.theory.chord import SHARPS, parse, to_harte

SCHEMA = """
CREATE TABLE IF NOT EXISTS songs (
    id TEXT PRIMARY KEY,
    video_id TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    duration REAL NOT NULL,
    key TEXT NOT NULL,
    tempo REAL NOT NULL,
    timeline_json TEXT NOT NULL,
    original_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    video_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    state TEXT NOT NULL,
    progress INTEGER NOT NULL DEFAULT 0,
    message TEXT,
    error TEXT,
    song_id TEXT,
    created_at TEXT NOT NULL
);
"""
JOB_FIELDS = {"state", "progress", "message", "error", "song_id"}
FINAL_STATES = ("done", "failed", "cancelled")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path):
        self._conn = sqlite3.connect(str(Path(path)), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._lock = threading.Lock()

    def _exec(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    # ---- jobs ----
    def create_job(self, video_id: str, mode: str) -> str:
        job_id = uuid.uuid4().hex
        self._exec("INSERT INTO jobs (id, video_id, mode, state, progress, message, created_at) "
                   "VALUES (?, ?, ?, 'queued', 0, 'Waiting to start', ?)", (job_id, video_id, mode, _now()))
        return job_id

    def update_job(self, job_id: str, **fields) -> None:
        unknown = set(fields) - JOB_FIELDS
        if unknown:
            raise ValueError(f"Unknown job fields: {sorted(unknown)}")
        if not fields:
            return
        cols = ", ".join(f"{k} = ?" for k in fields)
        self._exec(f"UPDATE jobs SET {cols} WHERE id = ?", (*fields.values(), job_id))

    def get_job(self, job_id: str) -> dict | None:
        row = self._exec("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None

    def fail_interrupted_jobs(self) -> int:
        cur = self._exec("UPDATE jobs SET state = 'failed', error = 'The server restarted during analysis.' "
                         f"WHERE state NOT IN {FINAL_STATES}")
        return cur.rowcount

    # ---- songs ----
    def save_song(self, timeline: dict) -> str:
        blob = json.dumps(timeline)
        meta = (timeline["title"], timeline["duration"], timeline["key"], timeline["tempo"])
        existing = self.get_song_by_video(timeline["video_id"])
        if existing:
            self._exec("UPDATE songs SET title=?, duration=?, key=?, tempo=?, timeline_json=?, original_json=?, "
                       "updated_at=? WHERE id=?", (*meta, blob, blob, _now(), existing["id"]))
            return existing["id"]
        song_id = uuid.uuid4().hex
        now = _now()
        self._exec("INSERT INTO songs (id, video_id, title, duration, key, tempo, timeline_json, original_json, "
                   "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                   (song_id, timeline["video_id"], *meta, blob, blob, now, now))
        return song_id

    @staticmethod
    def _song(row: sqlite3.Row | None, with_timeline: bool = True) -> dict | None:
        if row is None:
            return None
        song = {k: row[k] for k in ("id", "video_id", "title", "duration", "key", "tempo",
                                    "created_at", "updated_at")}
        if with_timeline:
            song["timeline"] = json.loads(row["timeline_json"])
        return song

    def get_song(self, song_id: str) -> dict | None:
        return self._song(self._exec("SELECT * FROM songs WHERE id = ?", (song_id,)).fetchone())

    def get_song_by_video(self, video_id: str) -> dict | None:
        return self._song(self._exec("SELECT * FROM songs WHERE video_id = ?", (video_id,)).fetchone())

    def list_songs(self) -> list[dict]:
        rows = self._exec("SELECT * FROM songs ORDER BY updated_at DESC").fetchall()
        return [self._song(r, with_timeline=False) for r in rows]

    def _write_timeline(self, song_id: str, timeline: dict) -> None:
        self._exec("UPDATE songs SET timeline_json = ?, updated_at = ? WHERE id = ?",
                   (json.dumps(timeline), _now(), song_id))

    def update_segment(self, song_id: str, index: int, label: str, apply_to_all: bool = False) -> dict:
        song = self.get_song(song_id)
        if song is None:
            raise KeyError(song_id)
        timeline = song["timeline"]
        segments = timeline["segments"]
        if not 0 <= index < len(segments):
            raise IndexError(index)
        chord = parse(label)
        new_label = to_harte(chord)
        bass = None if chord is None else SHARPS[chord.bass if chord.bass is not None else chord.root]
        target = segments[index]["label"]
        for i, seg in enumerate(segments):
            if i == index or (apply_to_all and seg["label"] == target):
                seg.update(label=new_label, bass=bass, edited=True)
        self._write_timeline(song_id, timeline)
        return timeline

    def reset_song(self, song_id: str) -> dict:
        row = self._exec("SELECT original_json FROM songs WHERE id = ?", (song_id,)).fetchone()
        if row is None:
            raise KeyError(song_id)
        timeline = json.loads(row["original_json"])
        self._write_timeline(song_id, timeline)
        return timeline

    def delete_song(self, song_id: str) -> bool:
        return self._exec("DELETE FROM songs WHERE id = ?", (song_id,)).rowcount > 0
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest server/tests/test_store.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add server/store.py server/tests/conftest.py server/tests/test_store.py
git commit -m "feat: add sqlite store for jobs and editable chord timelines"
```

---

### Task 12: Background job runner

**Files:**
- Create: `server/jobs.py`
- Test: `server/tests/test_jobs.py`

**Interfaces:**
- Consumes: `Store` (Task 11), `pipeline.analyze/Options/Cancelled` (Task 10), `ingest.IngestError` (Task 8)
- Produces: `class JobRunner(store: Store, work_root: Path, analyze_fn=pipeline.analyze, keep_audio: bool = False)` with `submit(video_id: str, mode: str) -> str`, `cancel(job_id: str) -> bool`, `shutdown(wait: bool = True) -> None`

- [ ] **Step 1: Write the failing tests**

`server/tests/test_jobs.py`:
```python
import threading

from server.engine.ingest import IngestError
from server.jobs import JobRunner
from server.store import Store


def make(tmp_path, analyze_fn, keep_audio=False):
    store = Store(tmp_path / "db.sqlite")
    return store, JobRunner(store, tmp_path / "audio", analyze_fn=analyze_fn, keep_audio=keep_audio)


def test_successful_job_saves_song_and_cleans_audio(tmp_path, timeline):
    def analyze(video_id, work_dir, options, progress):
        work_dir.mkdir(parents=True, exist_ok=True)
        (work_dir / "audio.wav").write_bytes(b"x")
        assert options.mode == "accurate"
        progress("chords", 60, "Recognizing chords")
        return timeline

    store, runner = make(tmp_path, analyze)
    job_id = runner.submit("abcdefghijk", "accurate")
    runner.shutdown(wait=True)
    job = store.get_job(job_id)
    assert job["state"] == "done" and job["progress"] == 100
    assert store.get_song(job["song_id"])["title"] == "Test Song"
    assert not (tmp_path / "audio" / "abcdefghijk").exists()


def test_ingest_error_message_reaches_job(tmp_path):
    def analyze(*a):
        raise IngestError("This video is private.")

    store, runner = make(tmp_path, analyze)
    job_id = runner.submit("abcdefghijk", "fast")
    runner.shutdown(wait=True)
    job = store.get_job(job_id)
    assert (job["state"], job["error"]) == ("failed", "This video is private.")


def test_unexpected_error_is_wrapped(tmp_path):
    def analyze(*a):
        raise RuntimeError("kaboom")

    store, runner = make(tmp_path, analyze)
    job_id = runner.submit("abcdefghijk", "fast")
    runner.shutdown(wait=True)
    assert store.get_job(job_id)["error"] == "Analysis failed: kaboom"


def test_cancel_running_job(tmp_path, timeline):
    started, release = threading.Event(), threading.Event()

    def analyze(video_id, work_dir, options, progress):
        started.set()
        release.wait(5)
        progress("chords", 60, "Recognizing chords")
        return timeline

    store, runner = make(tmp_path, analyze)
    job_id = runner.submit("abcdefghijk", "fast")
    assert started.wait(5)
    assert runner.cancel(job_id) is True
    release.set()
    runner.shutdown(wait=True)
    assert store.get_job(job_id)["state"] == "cancelled"
    assert store.list_songs() == []


def test_cancel_unknown_job(tmp_path):
    _, runner = make(tmp_path, lambda *a: None)
    assert runner.cancel("nope") is False
    runner.shutdown()
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest server/tests/test_jobs.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'server.jobs'`

- [ ] **Step 3: Implement `server/jobs.py`**

```python
"""Runs analysis jobs one at a time in a background thread."""
import logging
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from server.engine import pipeline
from server.engine.ingest import IngestError
from server.store import Store

log = logging.getLogger(__name__)


class JobRunner:
    def __init__(self, store: Store, work_root: Path, analyze_fn=pipeline.analyze, keep_audio: bool = False):
        self._store = store
        self._work_root = Path(work_root)
        self._analyze = analyze_fn
        self._keep_audio = keep_audio
        self._cancel_flags: dict[str, threading.Event] = {}
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="chordarium-job")

    def submit(self, video_id: str, mode: str) -> str:
        job_id = self._store.create_job(video_id, mode)
        self._cancel_flags[job_id] = threading.Event()
        self._pool.submit(self._run, job_id, video_id, mode)
        return job_id

    def cancel(self, job_id: str) -> bool:
        flag = self._cancel_flags.get(job_id)
        if flag is None:
            return False
        flag.set()
        job = self._store.get_job(job_id)
        if job and job["state"] == "queued":
            self._store.update_job(job_id, state="cancelled", message="Cancelled")
        return True

    def shutdown(self, wait: bool = True) -> None:
        self._pool.shutdown(wait=wait)

    def _run(self, job_id: str, video_id: str, mode: str) -> None:
        flag = self._cancel_flags[job_id]
        work_dir = self._work_root / video_id

        def progress(state: str, percent: int, message: str) -> None:
            if flag.is_set():
                raise pipeline.Cancelled()
            self._store.update_job(job_id, state=state, progress=percent, message=message)

        try:
            if flag.is_set():
                raise pipeline.Cancelled()
            timeline = self._analyze(video_id, work_dir, pipeline.Options(mode=mode), progress)
            if flag.is_set():
                raise pipeline.Cancelled()
            song_id = self._store.save_song(timeline)
            self._store.update_job(job_id, state="done", progress=100, message="Done", song_id=song_id)
        except pipeline.Cancelled:
            self._store.update_job(job_id, state="cancelled", message="Cancelled")
        except IngestError as e:
            self._store.update_job(job_id, state="failed", error=str(e), message="Failed")
        except Exception as e:
            log.exception("Job %s failed", job_id)
            self._store.update_job(job_id, state="failed", error=f"Analysis failed: {e}", message="Failed")
        finally:
            self._cancel_flags.pop(job_id, None)
            if not self._keep_audio:
                shutil.rmtree(work_dir, ignore_errors=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest server/tests/test_jobs.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add server/jobs.py server/tests/test_jobs.py
git commit -m "feat: add background job runner with cancellation"
```

---

### Task 13: Chord grid + ChordPro / TXT / JSON export

**Files:**
- Create: `server/export/__init__.py`, `server/export/grid.py`, `server/export/chordpro.py`, `server/export/txt.py`, `server/export/json_export.py`
- Test: `server/tests/test_export_text.py`

**Interfaces:**
- Consumes: `chord.render`, `chord.parse`, `chord.simplify`, `chord.transpose`, `chord.format_symbol`, `chord.note_names`, `chord.key_prefers_flats`, `chord.format_key`, `chord.key_symbol`; timeline fixture (Task 11)
- Produces (`server.export.grid`):
  - `@dataclass(frozen=True) class ExportOptions(transpose: int = 0, capo: int = 0, simplify: bool = False, bars_per_row: int = 4)`
  - `build_bars(timeline: dict, opts: ExportOptions) -> list[list[str]]` (each bar = beat slots; `"."` = chord continues)
  - `grid_lines(bars: list[list[str]], per_row: int) -> list[str]`
  - `chord_legend(timeline: dict, opts: ExportOptions) -> list[tuple[str, list[str]]]`
  - `header(timeline: dict, opts: ExportOptions) -> dict` (`title`, `key_text`, `key_symbol`, `tempo`, `capo`)
- Produces: `to_chordpro(timeline, opts) -> str`, `to_txt(timeline, opts) -> str`, `to_json(timeline, opts) -> str`

- [ ] **Step 1: Write the failing tests**

`server/tests/test_export_text.py`:
```python
import json

from server.export.chordpro import to_chordpro
from server.export.grid import ExportOptions, build_bars, chord_legend, grid_lines
from server.export.json_export import to_json
from server.export.txt import to_txt


def test_build_bars_marks_continuations(timeline):
    assert build_bars(timeline, ExportOptions()) == [
        ["Cm7", ".", ".", "."],
        ["F7", ".", ".", "."],
        ["Bbmaj7", ".", "Ebmaj7", "."],
        ["D7/F#", ".", ".", "."],
    ]


def test_transpose_capo_simplify(timeline):
    bars = build_bars(timeline, ExportOptions(transpose=2, capo=2, simplify=True))
    assert [b[0] for b in bars] == ["Cm", "F", "Bb", "D"]
    bars = build_bars(timeline, ExportOptions(transpose=1))
    assert bars[0][0] == "C#m7" and bars[3][0] == "D#7/G"


def test_leading_and_trailing_silence_trimmed(timeline):
    timeline["duration"] = 12.0
    timeline["beats"] = [i * 0.5 for i in range(24)]
    timeline["downbeats"] = [0.0, 2.0, 4.0, 6.0, 8.0, 10.0]
    for s in timeline["segments"]:
        s["start"] += 2.0
        s["end"] += 2.0
    timeline["segments"].insert(0, {"start": 0.0, "end": 2.0, "label": "N", "alt": None,
                                    "confidence": 1.0, "bass": None, "edited": False})
    timeline["segments"].append({"start": 10.0, "end": 12.0, "label": "N", "alt": None,
                                 "confidence": 1.0, "bass": None, "edited": False})
    bars = build_bars(timeline, ExportOptions())
    assert bars[0][0] == "Cm7" and bars[-1][0] == "D7/F#" and len(bars) == 4


def test_missing_downbeats_fall_back_to_every_fourth_beat(timeline):
    timeline["downbeats"] = []
    assert len(build_bars(timeline, ExportOptions())) == 4


def test_grid_lines_wrap_rows():
    bars = [["C", "."], ["G", "."], ["Am", "."]]
    assert grid_lines(bars, 2) == ["| C . | G . |", "| Am . |"]


def test_chord_legend(timeline):
    legend = dict(chord_legend(timeline, ExportOptions()))
    assert legend["Cm7"] == ["C", "Eb", "G", "Bb"]
    assert legend["D7/F#"] == ["D", "F#", "A", "C"]


def test_chordpro_grid(timeline):
    assert to_chordpro(timeline, ExportOptions(capo=0)) == (
        "{title: Test Song}\n"
        "{key: Gm}\n"
        "{tempo: 120}\n"
        "\n"
        "{start_of_grid}\n"
        "| Cm7 . . . | F7 . . . | Bbmaj7 . Ebmaj7 . | D7/F# . . . |\n"
        "{end_of_grid}\n"
    )
    assert "{capo: 3}" in to_chordpro(timeline, ExportOptions(capo=3))


def test_txt(timeline):
    text = to_txt(timeline, ExportOptions(bars_per_row=2))
    assert text.splitlines()[:5] == [
        "Test Song",
        "=========",
        "Key: G minor | Tempo: 120 BPM",
        "",
        "| Cm7 . . . | F7 . . . |",
    ]
    assert text.rstrip().endswith("Chords: Cm7, F7, Bbmaj7, Ebmaj7, D7/F#")


def test_json_round_trips(timeline):
    assert json.loads(to_json(timeline, ExportOptions())) == timeline
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest server/tests/test_export_text.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'server.export'`

- [ ] **Step 3: Implement `server/export/grid.py`**

Create empty `server/export/__init__.py`, then:

```python
"""Shared bar/beat grid used by every chord-sheet exporter."""
import bisect
from dataclasses import dataclass

from server.theory import chord as ch

NO_CHORD = "N.C."
HOLD = "."


@dataclass(frozen=True)
class ExportOptions:
    transpose: int = 0
    capo: int = 0
    simplify: bool = False
    bars_per_row: int = 4


def _shape_shift(opts: ExportOptions) -> int:
    return opts.transpose - opts.capo


def _prefer_flats(timeline: dict, opts: ExportOptions) -> bool:
    return ch.key_prefers_flats(timeline["key"], _shape_shift(opts))


def _label_at(segments: list[dict], starts: list[float], t: float) -> str:
    i = bisect.bisect_right(starts, t) - 1
    if i >= 0 and segments[i]["start"] <= t < segments[i]["end"]:
        return segments[i]["label"]
    return "N"


def build_bars(timeline: dict, opts: ExportOptions) -> list[list[str]]:
    beats = timeline["beats"]
    downbeats = timeline["downbeats"] or beats[::timeline.get("time_signature", 4)]
    if not beats or not downbeats:
        return []
    segments = timeline["segments"]
    starts = [s["start"] for s in segments]
    flats = _prefer_flats(timeline, opts)
    bounds = list(downbeats) + [timeline["duration"]]
    bars, prev = [], None
    for i in range(len(downbeats)):
        start, end = bounds[i], bounds[i + 1]
        bar_beats = [b for b in beats if start - 1e-6 <= b < end - 1e-6] or [start]
        slots = []
        for j, beat in enumerate(bar_beats):
            symbol = ch.render(_label_at(segments, starts, beat + 0.01), transpose_by=opts.transpose,
                               capo=opts.capo, simplify_chord=opts.simplify, prefer_flats=flats)
            slots.append(symbol if j == 0 or symbol != prev else HOLD)
            prev = symbol
        bars.append(slots)

    def empty(bar: list[str]) -> bool:
        return all(s in (NO_CHORD, HOLD) for s in bar)

    while bars and empty(bars[0]):
        bars.pop(0)
    while bars and empty(bars[-1]):
        bars.pop()
    return bars


def grid_lines(bars: list[list[str]], per_row: int) -> list[str]:
    lines = []
    for i in range(0, len(bars), per_row):
        row = bars[i:i + per_row]
        lines.append("| " + " | ".join(" ".join(bar) for bar in row) + " |")
    return lines


def chord_legend(timeline: dict, opts: ExportOptions) -> list[tuple[str, list[str]]]:
    flats = _prefer_flats(timeline, opts)
    seen: dict[str, list[str]] = {}
    for seg in timeline["segments"]:
        c = ch.parse(seg["label"])
        if c is None:
            continue
        if opts.simplify:
            c = ch.simplify(c)
        c = ch.transpose(c, _shape_shift(opts))
        symbol = ch.format_symbol(c, flats)
        if symbol not in seen:
            seen[symbol] = ch.note_names(c, flats)
    return list(seen.items())


def header(timeline: dict, opts: ExportOptions) -> dict:
    return {
        "title": timeline["title"],
        "key_text": ch.format_key(timeline["key"], opts.transpose),
        "key_symbol": ch.key_symbol(timeline["key"], opts.transpose),
        "tempo": round(timeline["tempo"]),
        "capo": opts.capo,
    }
```

- [ ] **Step 4: Implement the three text exporters**

`server/export/chordpro.py`:
```python
"""ChordPro (.cho) export using a bar grid section."""
from server.export.grid import ExportOptions, build_bars, grid_lines, header


def to_chordpro(timeline: dict, opts: ExportOptions) -> str:
    h = header(timeline, opts)
    lines = [f"{{title: {h['title']}}}", f"{{key: {h['key_symbol']}}}", f"{{tempo: {h['tempo']}}}"]
    if h["capo"]:
        lines.append(f"{{capo: {h['capo']}}}")
    lines += ["", "{start_of_grid}", *grid_lines(build_bars(timeline, opts), opts.bars_per_row), "{end_of_grid}"]
    return "\n".join(lines) + "\n"
```

`server/export/txt.py`:
```python
"""Plain-text chord sheet export."""
from server.export.grid import ExportOptions, build_bars, chord_legend, grid_lines, header


def to_txt(timeline: dict, opts: ExportOptions) -> str:
    h = header(timeline, opts)
    meta = f"Key: {h['key_text']} | Tempo: {h['tempo']} BPM"
    if h["capo"]:
        meta += f" | Capo: {h['capo']}"
    lines = [h["title"], "=" * len(h["title"]), meta, ""]
    lines += grid_lines(build_bars(timeline, opts), opts.bars_per_row)
    lines += ["", "Chords: " + ", ".join(symbol for symbol, _ in chord_legend(timeline, opts))]
    return "\n".join(lines) + "\n"
```

`server/export/json_export.py`:
```python
"""JSON export: the stored chord timeline, unchanged."""
import json

from server.export.grid import ExportOptions


def to_json(timeline: dict, opts: ExportOptions) -> str:
    return json.dumps(timeline, indent=2)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest server/tests/test_export_text.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add server/export server/tests/test_export_text.py
git commit -m "feat: add chord grid and chordpro, txt, json exports"
```

---

### Task 14: PDF and MIDI export

**Files:**
- Create: `server/export/pdf.py`, `server/export/midi.py`
- Test: `server/tests/test_export_binary.py`

**Interfaces:**
- Consumes: `grid.ExportOptions/build_bars/chord_legend/header`, `chord.parse/simplify/transpose/midi_notes`
- Produces: `to_pdf(timeline, opts) -> bytes`, `to_midi(timeline, opts) -> bytes` (MIDI applies `transpose` and `simplify`; **not** `capo`, since capo changes guitar shapes, not sounding pitch)

- [ ] **Step 1: Write the failing tests**

`server/tests/test_export_binary.py`:
```python
from io import BytesIO

import mido
from pypdf import PdfReader

from server.export.grid import ExportOptions
from server.export.midi import to_midi
from server.export.pdf import to_pdf


def pdf_text(data: bytes) -> str:
    return "\n".join(page.extract_text() for page in PdfReader(BytesIO(data)).pages)


def test_pdf_contains_header_grid_and_legend(timeline):
    # capo 2 turns Cm7 into Bbm7 and D7/F# into C7/E (shapes), header key stays sounding G minor
    data = to_pdf(timeline, ExportOptions(capo=2))
    assert data.startswith(b"%PDF")
    text = pdf_text(data)
    for expected in ["Test Song", "G minor", "120 BPM", "Capo 2", "Bbm7", "C7/E", "Bb Db F Ab"]:
        assert expected in text


def test_pdf_paginates_long_songs(timeline):
    seg = timeline["segments"][0]
    timeline["duration"] = 400.0
    timeline["beats"] = [i * 0.5 for i in range(800)]
    timeline["downbeats"] = timeline["beats"][::4]
    timeline["segments"] = [{**seg, "start": 0.0, "end": 400.0}]
    assert len(PdfReader(BytesIO(to_pdf(timeline, ExportOptions()))).pages) >= 2


def first_chord_notes(data: bytes) -> set[int]:
    mid = mido.MidiFile(file=BytesIO(data))
    notes, tick = set(), 0
    for msg in mid.tracks[0]:
        tick += msg.time
        if msg.type == "note_on" and msg.velocity > 0 and tick == 0:
            notes.add(msg.note)
    return notes


def test_midi_first_chord_and_transpose(timeline):
    assert first_chord_notes(to_midi(timeline, ExportOptions())) == {36, 60, 63, 67, 70}
    assert first_chord_notes(to_midi(timeline, ExportOptions(transpose=2))) == {38, 62, 65, 69, 72}
    assert first_chord_notes(to_midi(timeline, ExportOptions(capo=5))) == {36, 60, 63, 67, 70}


def test_midi_tempo_and_length(timeline):
    mid = mido.MidiFile(file=BytesIO(to_midi(timeline, ExportOptions())))
    tempos = [m.tempo for m in mid.tracks[0] if m.type == "set_tempo"]
    assert tempos == [mido.bpm2tempo(120.0)]
    assert abs(mid.length - 8.0) < 0.05
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest server/tests/test_export_binary.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'server.export.midi'`

- [ ] **Step 3: Implement `server/export/pdf.py`**

```python
"""PDF chord sheet: header, bar grid, chord legend."""
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from server.export.grid import HOLD, ExportOptions, build_bars, chord_legend, header

MARGIN = 18 * mm
ROW_H = 12 * mm


def to_pdf(timeline: dict, opts: ExportOptions) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    h = header(timeline, opts)
    c.setTitle(h["title"])

    y = height - MARGIN
    c.setFont("Helvetica-Bold", 20)
    c.drawString(MARGIN, y, h["title"])
    y -= 9 * mm
    meta = f"Key: {h['key_text']}   {h['tempo']} BPM"
    if h["capo"]:
        meta += f"   Capo {h['capo']}"
    c.setFont("Helvetica", 11)
    c.drawString(MARGIN, y, meta)
    y -= 12 * mm

    bars = build_bars(timeline, opts)
    col_w = (width - 2 * MARGIN) / opts.bars_per_row
    for i in range(0, len(bars), opts.bars_per_row):
        if y < MARGIN + ROW_H:
            c.showPage()
            y = height - MARGIN
        row = bars[i:i + opts.bars_per_row]
        for k, bar in enumerate(row):
            x = MARGIN + k * col_w
            c.line(x, y - ROW_H + 4 * mm, x, y + 3 * mm)
            slot_w = (col_w - 4) / len(bar)
            for s, slot in enumerate(bar):
                c.setFont("Helvetica" if slot == HOLD else "Helvetica-Bold", 12)
                c.drawString(x + 3 + s * slot_w, y - 3 * mm, slot)
        end_x = MARGIN + len(row) * col_w
        c.line(end_x, y - ROW_H + 4 * mm, end_x, y + 3 * mm)
        y -= ROW_H

    legend = chord_legend(timeline, opts)
    if legend:
        if y < MARGIN + 20 * mm:
            c.showPage()
            y = height - MARGIN
        y -= 4 * mm
        c.setFont("Helvetica-Bold", 12)
        c.drawString(MARGIN, y, "Chords")
        y -= 6 * mm
        c.setFont("Helvetica", 10)
        for symbol, notes in legend:
            if y < MARGIN:
                c.showPage()
                y = height - MARGIN
                c.setFont("Helvetica", 10)
            c.drawString(MARGIN, y, f"{symbol}:  {' '.join(notes)}")
            y -= 5 * mm

    c.save()
    return buf.getvalue()
```

- [ ] **Step 4: Implement `server/export/midi.py`**

```python
"""MIDI export: block chords at detected tempo (sounding pitch: capo ignored)."""
from io import BytesIO

import mido

from server.export.grid import ExportOptions
from server.theory import chord as ch

TICKS_PER_BEAT = 480
VELOCITY = 80


def to_midi(timeline: dict, opts: ExportOptions) -> bytes:
    bpm = timeline["tempo"] or 120.0
    tempo = mido.bpm2tempo(bpm)
    mid = mido.MidiFile(ticks_per_beat=TICKS_PER_BEAT)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.append(mido.MetaMessage("track_name", name=timeline["title"], time=0))
    track.append(mido.MetaMessage("set_tempo", tempo=tempo, time=0))

    def tick(seconds: float) -> int:
        return round(mido.second2tick(seconds, TICKS_PER_BEAT, tempo))

    events = []
    for seg in timeline["segments"]:
        c = ch.parse(seg["label"])
        if c is None:
            continue
        if opts.simplify:
            c = ch.simplify(c)
        c = ch.transpose(c, opts.transpose)
        on, off = tick(seg["start"]), tick(seg["end"])
        if off <= on:
            continue
        for note in ch.midi_notes(c):
            events.append((on, 1, mido.Message("note_on", note=note, velocity=VELOCITY)))
            events.append((off, 0, mido.Message("note_off", note=note, velocity=0)))

    events.sort(key=lambda e: (e[0], e[1]))
    last = 0
    for at, _, msg in events:
        msg.time = at - last
        last = at
        track.append(msg)

    buf = BytesIO()
    mid.save(file=buf)
    return buf.getvalue()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest server/tests/test_export_binary.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add server/export/pdf.py server/export/midi.py server/tests/test_export_binary.py
git commit -m "feat: add pdf chord sheet and midi exports"
```

---

### Task 15: Flask API + end-to-end smoke test

**Files:**
- Create: `server/app.py`
- Test: `server/tests/test_app.py`
- Modify: `README.md` (add "Run the server" section)

**Interfaces:**
- Consumes: `Store`, `JobRunner`, `ingest.parse_video_id`, all exporters, `ExportOptions`
- Produces: `create_app(config: dict | None = None, store: Store | None = None, runner=None) -> Flask`; routes per spec §4. Runner duck type: `submit(video_id, mode) -> str`, `cancel(job_id) -> bool`.

- [ ] **Step 1: Write the failing tests**

`server/tests/test_app.py`:
```python
import pytest

from server.app import create_app
from server.store import Store

VID = "dQw4w9WgXcQ"


class FakeRunner:
    def __init__(self, store):
        self.store, self.submitted = store, []

    def submit(self, video_id, mode):
        self.submitted.append((video_id, mode))
        return self.store.create_job(video_id, mode)

    def cancel(self, job_id):
        return self.store.get_job(job_id) is not None


@pytest.fixture
def ctx(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    runner = FakeRunner(store)
    app = create_app({"DATA_DIR": tmp_path, "TESTING": True}, store=store, runner=runner)
    return app.test_client(), store, runner


def test_analyze_validates_input(ctx):
    client, _, runner = ctx
    assert client.post("/api/analyze", json={"url": "https://vimeo.com/1"}).status_code == 400
    assert client.post("/api/analyze", json={"url": f"https://youtu.be/{VID}", "mode": "turbo"}).status_code == 400
    assert client.post("/api/analyze", json={}).status_code == 400
    assert runner.submitted == []


def test_analyze_starts_job_then_polls(ctx):
    client, store, runner = ctx
    r = client.post("/api/analyze", json={"url": f"https://youtu.be/{VID}?si=x", "mode": "accurate"})
    assert r.status_code == 202
    job_id = r.get_json()["job_id"]
    assert runner.submitted == [(VID, "accurate")]
    assert client.get(f"/api/jobs/{job_id}").get_json()["state"] == "queued"
    assert client.get("/api/jobs/nope").status_code == 404
    assert client.post(f"/api/jobs/{job_id}/cancel").get_json() == {"cancelled": True}
    assert client.post("/api/jobs/nope/cancel").status_code == 404


def test_analyze_returns_cached_song(ctx, timeline):
    client, store, runner = ctx
    timeline["video_id"] = VID
    song_id = store.save_song(timeline)
    r = client.post("/api/analyze", json={"url": f"https://www.youtube.com/watch?v={VID}"})
    assert r.status_code == 200 and r.get_json() == {"song_id": song_id, "cached": True}
    assert runner.submitted == []


def test_song_crud_and_edits(ctx, timeline):
    client, store, _ = ctx
    song_id = store.save_song(timeline)
    assert client.get("/api/songs").get_json()[0]["id"] == song_id
    assert client.get(f"/api/songs/{song_id}").get_json()["timeline"]["key"] == "G:min"
    r = client.put(f"/api/songs/{song_id}/segments/0", json={"label": "C:min"})
    assert r.status_code == 200 and r.get_json()["segments"][0]["label"] == "C:min"
    assert client.put(f"/api/songs/{song_id}/segments/0", json={"label": "H:maj"}).status_code == 400
    assert client.put(f"/api/songs/{song_id}/segments/99", json={"label": "C:maj"}).status_code == 404
    assert client.put("/api/songs/nope/segments/0", json={"label": "C:maj"}).status_code == 404
    assert client.post(f"/api/songs/{song_id}/reset").get_json()["segments"][0]["label"] == "C:min7"
    assert client.delete(f"/api/songs/{song_id}").status_code == 204
    assert client.get(f"/api/songs/{song_id}").status_code == 404


@pytest.mark.parametrize("fmt,mimetype,ext", [
    ("chordpro", "text/plain", "cho"), ("txt", "text/plain", "txt"), ("json", "application/json", "json"),
    ("pdf", "application/pdf", "pdf"), ("midi", "audio/midi", "mid"),
])
def test_exports(ctx, timeline, fmt, mimetype, ext):
    client, store, _ = ctx
    song_id = store.save_song(timeline)
    r = client.get(f"/api/songs/{song_id}/export?fmt={fmt}&transpose=1&capo=2&simplify=1&bars_per_row=8")
    assert r.status_code == 200
    assert r.mimetype == mimetype
    assert r.headers["Content-Disposition"] == f'attachment; filename="Test-Song.{ext}"'


@pytest.mark.parametrize("query", ["fmt=docx", "fmt=pdf&transpose=9", "fmt=pdf&capo=-1",
                                   "fmt=pdf&bars_per_row=5", "fmt=pdf&transpose=abc"])
def test_export_rejects_bad_params(ctx, timeline, query):
    client, store, _ = ctx
    song_id = store.save_song(timeline)
    assert client.get(f"/api/songs/{song_id}/export?{query}").status_code == 400
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest server/tests/test_app.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'server.app'`

- [ ] **Step 3: Implement `server/app.py`**

```python
"""Chordarium HTTP API."""
import logging
import os
import re
from pathlib import Path

from flask import Flask, Response, jsonify, request

from server.engine.ingest import parse_video_id
from server.export.chordpro import to_chordpro
from server.export.grid import ExportOptions
from server.export.json_export import to_json
from server.export.midi import to_midi
from server.export.pdf import to_pdf
from server.export.txt import to_txt
from server.jobs import JobRunner
from server.store import Store

EXPORTERS = {
    "chordpro": (to_chordpro, "text/plain", "cho"),
    "txt": (to_txt, "text/plain", "txt"),
    "json": (to_json, "application/json", "json"),
    "pdf": (to_pdf, "application/pdf", "pdf"),
    "midi": (to_midi, "audio/midi", "mid"),
}
MODES = ("fast", "accurate")


class BadRequest(Exception):
    pass


def _int_arg(name: str, default: int, lo: int, hi: int, allowed: tuple[int, ...] | None = None) -> int:
    raw = request.args.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise BadRequest(f"{name} must be a whole number")
    if not lo <= value <= hi or (allowed and value not in allowed):
        raise BadRequest(f"{name} is out of range")
    return value


def _slug(title: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-") or "chordarium"


def create_app(config: dict | None = None, store: Store | None = None, runner=None) -> Flask:
    app = Flask(__name__)
    app.config.update(DATA_DIR=Path(os.environ.get("CHORDARIUM_DATA", Path(__file__).parent / "data")),
                      KEEP_AUDIO=False)
    if config:
        app.config.update(config)
    data_dir = Path(app.config["DATA_DIR"])
    data_dir.mkdir(parents=True, exist_ok=True)
    store = store or Store(data_dir / "chordarium.db")
    store.fail_interrupted_jobs()
    runner = runner or JobRunner(store, data_dir / "audio", keep_audio=app.config["KEEP_AUDIO"])

    def error(message: str, status: int):
        return jsonify({"error": message}), status

    @app.errorhandler(BadRequest)
    def _bad_request(e):
        return error(str(e), 400)

    @app.post("/api/analyze")
    def analyze():
        body = request.get_json(silent=True) or {}
        mode = body.get("mode", "fast")
        if mode not in MODES:
            raise BadRequest("mode must be 'fast' or 'accurate'")
        video_id = parse_video_id(str(body.get("url", "")))
        if not video_id:
            raise BadRequest("That doesn't look like a YouTube video link.")
        cached = store.get_song_by_video(video_id)
        if cached:
            return jsonify({"song_id": cached["id"], "cached": True})
        return jsonify({"job_id": runner.submit(video_id, mode)}), 202

    @app.get("/api/jobs/<job_id>")
    def get_job(job_id):
        job = store.get_job(job_id)
        return jsonify(job) if job else error("Job not found", 404)

    @app.post("/api/jobs/<job_id>/cancel")
    def cancel_job(job_id):
        if store.get_job(job_id) is None:
            return error("Job not found", 404)
        return jsonify({"cancelled": runner.cancel(job_id)})

    @app.get("/api/songs")
    def list_songs():
        return jsonify(store.list_songs())

    @app.get("/api/songs/<song_id>")
    def get_song(song_id):
        song = store.get_song(song_id)
        return jsonify(song) if song else error("Song not found", 404)

    @app.put("/api/songs/<song_id>/segments/<int:index>")
    def edit_segment(song_id, index):
        body = request.get_json(silent=True) or {}
        try:
            timeline = store.update_segment(song_id, index, str(body.get("label", "")),
                                            bool(body.get("apply_to_all", False)))
        except KeyError:
            return error("Song not found", 404)
        except IndexError:
            return error("Chord index out of range", 404)
        except ValueError as e:
            return error(str(e), 400)
        return jsonify(timeline)

    @app.post("/api/songs/<song_id>/reset")
    def reset_song(song_id):
        try:
            return jsonify(store.reset_song(song_id))
        except KeyError:
            return error("Song not found", 404)

    @app.delete("/api/songs/<song_id>")
    def delete_song(song_id):
        return ("", 204) if store.delete_song(song_id) else error("Song not found", 404)

    @app.get("/api/songs/<song_id>/export")
    def export_song(song_id):
        song = store.get_song(song_id)
        if song is None:
            return error("Song not found", 404)
        fmt = request.args.get("fmt", "pdf")
        if fmt not in EXPORTERS:
            raise BadRequest(f"fmt must be one of {', '.join(EXPORTERS)}")
        opts = ExportOptions(
            transpose=_int_arg("transpose", 0, -6, 6),
            capo=_int_arg("capo", 0, 0, 7),
            simplify=request.args.get("simplify") in ("1", "true"),
            bars_per_row=_int_arg("bars_per_row", 4, 4, 8, allowed=(4, 8)),
        )
        render, mimetype, ext = EXPORTERS[fmt]
        data = render(song["timeline"], opts)
        if isinstance(data, str):
            data = data.encode("utf-8")
        filename = f"{_slug(song['title'])}.{ext}"
        return Response(data, mimetype=mimetype,
                        headers={"Content-Disposition": f'attachment; filename="{filename}"'})

    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    create_app().run(host="127.0.0.1", port=5000, debug=False)
```

- [ ] **Step 4: Run tests to verify they pass, then the full suite**

Run: `python -m pytest server/tests/test_app.py -v`
Expected: all PASS.

Run: `python -m pytest -m "slow or not slow"`
Expected: all PASS (BTC test skips only if `setup_models.py` was not run).

- [ ] **Step 5: End-to-end smoke test against a real YouTube video**

Terminal 1:
```powershell
python -m server.app
```

Terminal 2 (use any short, public song you are allowed to analyze):
```powershell
$r = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/api/analyze -ContentType application/json -Body '{"url":"https://www.youtube.com/watch?v=<VIDEO_ID>","mode":"fast"}'
do { Start-Sleep 2; $j = Invoke-RestMethod "http://127.0.0.1:5000/api/jobs/$($r.job_id)"; "$($j.state) $($j.progress)% $($j.message)" } until ($j.state -in 'done','failed','cancelled')
Invoke-WebRequest "http://127.0.0.1:5000/api/songs/$($j.song_id)/export?fmt=chordpro" -OutFile song.cho; Get-Content song.cho
Invoke-WebRequest "http://127.0.0.1:5000/api/songs/$($j.song_id)/export?fmt=pdf" -OutFile song.pdf
```
Expected: states progress `downloading → beats → chords → bass → key → done`; `song.cho` shows a bar grid with plausible chords; `song.pdf` opens with header, grid and legend. Repeat once with `"mode":"accurate"` on a different video and confirm the job passes through `separating`. Delete `song.cho`/`song.pdf` afterwards (not committed).

- [ ] **Step 6: Add run instructions to `README.md`**

Append to `README.md`:
````markdown
## Run the server (Phase 1)

```powershell
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install torch==2.5.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
python scripts/setup_models.py      # BTC chord model (one time)
python -m pytest                    # fast tests; add -m "slow or not slow" for model tests
python -m server.app                # API on http://127.0.0.1:5000
```

Requires ffmpeg on PATH.
````

- [ ] **Step 7: Commit**

```bash
git add server/app.py server/tests/test_app.py README.md
git commit -m "feat: add flask api for analysis jobs, songs, edits and exports"
git push
```
