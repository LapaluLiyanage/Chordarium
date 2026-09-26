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
# Letter offset for each semitone above the tonic: b2, b3, #4, b6, b7 (borrowed chords read as flats).
_KEY_DEGREE_LETTER_STEPS = {0: 0, 1: 1, 2: 1, 3: 2, 4: 2, 5: 3, 6: 3, 7: 4, 8: 5, 9: 5, 10: 6, 11: 6}
_AWKWARD_NAMES = {"Cb", "Fb", "E#", "B#"}
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


def root_name_in_key(pc: int, tonic: str) -> str:
    """Name a chord root by its scale degree in the key whose tonic is `tonic`."""
    degree = (pc - _NAME_TO_PC[tonic]) % 12
    letter = LETTERS[(LETTERS.index(tonic[0]) + _KEY_DEGREE_LETTER_STEPS[degree]) % 7]
    diff = (pc % 12 - _NATURAL_PC[letter] + 6) % 12 - 6
    name = letter + _ACCIDENTALS[diff] if diff in _ACCIDENTALS else None
    if name is None or name in _AWKWARD_NAMES:
        return root_name(pc, "b" in tonic)
    return name


def _root(chord: Chord, prefer_flats: bool, tonic: str | None) -> str:
    return root_name_in_key(chord.root, tonic) if tonic else root_name(chord.root, prefer_flats)


def format_symbol(chord: Chord | None, prefer_flats: bool = False, tonic: str | None = None) -> str:
    if chord is None:
        return "N.C."
    root = _root(chord, prefer_flats, tonic)
    s = root + QUALITY_SYMBOL[chord.quality]
    if chord.bass is not None:
        s += "/" + spell(root, chord.bass - chord.root)
    return s


def note_names(chord: Chord, prefer_flats: bool = False, tonic: str | None = None) -> list[str]:
    root = _root(chord, prefer_flats, tonic)
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


def render(label: str, transpose_by: int = 0, capo: int = 0, simplify_chord: bool = False,
           prefer_flats: bool = False, tonic: str | None = None) -> str:
    c = parse(label)
    if simplify_chord:
        c = simplify(c)
    return format_symbol(transpose(c, transpose_by - capo), prefer_flats, tonic)


def _parse_key(key_label: str) -> tuple[int, str]:
    c = parse(key_label)
    if c is None or c.quality not in ("maj", "min"):
        raise ValueError(f"Not a key: {key_label!r}")
    return c.root, c.quality


def key_prefers_flats(key_label: str, transpose_by: int = 0) -> bool:
    root, mode = _parse_key(key_label)
    root = (root + transpose_by) % 12
    return root in (_FLAT_MAJOR_ROOTS if mode == "maj" else _FLAT_MINOR_ROOTS)


def key_spelling(key_label: str, transpose_by: int = 0) -> str:
    """Tonic name of the (transposed) key, e.g. 'Db' for C major moved up 1."""
    root, _ = _parse_key(key_label)
    return root_name(root + transpose_by, key_prefers_flats(key_label, transpose_by))


def format_key(key_label: str, transpose_by: int = 0) -> str:
    root, mode = _parse_key(key_label)
    name = root_name(root + transpose_by, key_prefers_flats(key_label, transpose_by))
    return f"{name} {'major' if mode == 'maj' else 'minor'}"


def key_symbol(key_label: str, transpose_by: int = 0) -> str:
    root, mode = _parse_key(key_label)
    name = root_name(root + transpose_by, key_prefers_flats(key_label, transpose_by))
    return name + ("m" if mode == "min" else "")
