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
