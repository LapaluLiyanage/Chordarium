# Chordarium

Paste a YouTube link, get the song's chords — including 7ths, extensions, sus
chords and inversions — synced to the video, editable, and exportable as a
chord sheet (ChordPro, PDF, TXT, MIDI, JSON).

**Status:** Phase 1 design. See
[`docs/superpowers/specs/2026-09-26-chordarium-design.md`](docs/superpowers/specs/2026-09-26-chordarium-design.md).

## Stack

- **Server:** Flask API, yt-dlp + ffmpeg, Demucs (stem separation), beat_this
  (beats), BTC transformer (large-vocabulary chord recognition) with a
  144-template chroma fallback, SQLite.
- **Client:** React + Vite + TypeScript, YouTube IFrame player.

## Roadmap

1. **Phase 1** — local Flask + React app: analyze, synced tracker, chord
   editor, exports.
2. **Phase 2** — public web platform to publish and share chord sheets.
