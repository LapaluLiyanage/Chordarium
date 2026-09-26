# Chordarium

Paste a YouTube link, get the song's chords — including 7ths, extensions, sus
chords and inversions — synced to the video, editable, and exportable as a
chord sheet (ChordPro, PDF, TXT, MIDI, JSON).

**Status:** Phase 1 server (API) built; React client next. See
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
