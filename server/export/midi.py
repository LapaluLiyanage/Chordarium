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
    # MIDI meta text is latin-1; non-Latin titles (Sinhala, CJK, emoji) become "?".
    name = timeline["title"].encode("latin-1", "replace").decode("latin-1")
    track.append(mido.MetaMessage("track_name", name=name, time=0))
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
