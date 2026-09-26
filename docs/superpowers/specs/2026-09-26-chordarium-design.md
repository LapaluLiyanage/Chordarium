# Chordarium — Phase 1 Design Spec

Date: 2026-09-26 · Status: awaiting review

## 1. Goal

A local web app that takes a YouTube link, recognizes the song's chords —
including advanced chords (7ths, 6ths, sus, dim/hdim, aug, minMaj7) and
inversions (slash chords such as `C/E`) — and plays them back in sync with the
video, in the spirit of Yamaha Chord Tracker. Users can correct chords and
export chord sheets.

**Success criteria**

- Paste a link → a synced, editable chord timeline in ≤ 60 s (Fast mode) or
  ≤ 5 min (Accurate mode) for a 4-minute song on the dev laptop (CPU).
- Chord labels cover the BTC large vocabulary plus slash-chord inversions.
- Exports (ChordPro, PDF, TXT, MIDI, JSON) reflect the user's edits and the
  current transpose / capo / simplify settings.
- Re-opening a previously analyzed video is instant and keeps edits.

**Out of scope (Phase 1):** public hosting, accounts, publishing, lyrics,
audio pitch-shifting, sending chords to a hardware keyboard.

**Phase 2 (separate spec later):** public web platform where users publish
and share chord sheets. Server-side YouTube downloading violates YouTube's
Terms of Service and is actively blocked, so Phase 2 must revisit ingestion
(e.g. user file upload). Phase 1 keeps ingestion behind one swappable module.

## 2. Architecture

```
chordarium/
├── server/                  Flask JSON API (Python 3.12 venv)
│   ├── app.py               routes
│   ├── jobs.py              background jobs (ThreadPoolExecutor, 1 worker) + status
│   ├── store.py             SQLite persistence
│   ├── engine/
│   │   ├── ingest.py        YouTube URL → mono WAV (yt-dlp + ffmpeg)
│   │   ├── separate.py      WAV → stems (Demucs htdemucs), Accurate mode only
│   │   ├── beats.py         beats, downbeats, tempo (beat_this)
│   │   ├── chords_btc.py    BTC large-vocab model → segments + top-2 labels
│   │   ├── chords_tmpl.py   144-template chroma matcher (fallback / baseline)
│   │   ├── bass.py          bass pitch per segment → inversion
│   │   ├── key.py           key estimation (Krumhansl-Schmuckler on chroma)
│   │   ├── snap.py          beat-snapping + short-segment merging
│   │   └── pipeline.py      orchestrates steps, reports progress
│   ├── theory/
│   │   └── chord.py         parse / format / transpose / capo / simplify / spell notes
│   └── export/
│       ├── chordpro.py  pdf.py  txt.py  midi.py  json_export.py
└── client/                  React + Vite + TypeScript
    └── src/pages/{Home,Analyzing,Tracker}, components/{ChordLane,ChordHero,
        DiagramPanel,Controls,ChordEditor,ExportModal}
```

**Core contract — the chord timeline** (the only thing UI, exports and the
future platform read):

```json
{
  "video_id": "abc123", "title": "...", "duration": 241.3,
  "key": "G:min", "tempo": 124.0, "time_signature": 4,
  "beats": [0.48, 0.97, ...], "downbeats": [0.48, 2.42, ...],
  "segments": [
    {"start": 0.48, "end": 2.42, "label": "C:min7", "alt": "C:min",
     "confidence": 0.81, "bass": "C", "edited": false}
  ],
  "engine": {"chords": "btc-large", "separated": true, "version": "1"}
}
```

Labels use Harte notation internally (`C:maj7`, `A:min7/b3`, `N` = no chord)
and are rendered as lead-sheet symbols (`Cmaj7`, `Am7/C`) by `theory/chord.py`.

## 3. Engine

| Step | Tool | Notes |
|---|---|---|
| Ingest | yt-dlp `bestaudio` → ffmpeg 22.05 kHz mono WAV | Rejects live streams, > 15 min, private/age-restricted |
| Separate | Demucs `htdemucs`, 4 stems | Accurate mode only. Harmony input = bass + other; bass stem → `bass.py`; vocals dropped |
| Beats | beat_this | Downbeats define bars; tempo = median inter-beat interval |
| Chords | BTC (ISMIR 2019) `voca=True`, 170 classes | Keep top-2 per frame → `label`, `alt`, `confidence` |
| Fallback | 144 templates (12 roots × 12 qualities) on CQT chroma + Viterbi smoothing | Used if BTC weights missing (warning shown) or `engine=template` |
| Inversion | Strongest bass-range pitch class per segment (bass stem, or ≤ 250 Hz band of the mix in Fast mode) | Slash added only if it is a non-root chord tone |
| Key | Krumhansl-Schmuckler over whole-song chroma | Output e.g. `G:min` |
| Snap | Boundaries → nearest beat; segments < 1 beat merged into the stronger neighbour | Consecutive identical labels merged |

Template qualities (144 = 12 × 12): maj, min, 7, maj7, min7, dim, dim7,
hdim7, aug, sus2, sus4, min6 — kept as a transparent baseline for comparing
against BTC.

**Modes:** Fast (no Demucs, ~30 s) and Accurate (Demucs, ~2–4 min CPU; CUDA
used if available with ≥ 2 GB free, else CPU).

**Job states:** `queued → downloading → separating → beats → chords → bass →
key → done | failed`, each with `progress` 0–100 and a human `message`.

## 4. API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/analyze` `{url, mode}` | Returns `{job_id}`; returns cached `{song_id}` if the video was analyzed before |
| GET | `/api/jobs/<id>` | `{state, progress, message, song_id?, error?}` |
| POST | `/api/jobs/<id>/cancel` | Cancel a queued/running job |
| GET | `/api/songs` | Library list |
| GET | `/api/songs/<id>` | Chord timeline (with edits applied) |
| PUT | `/api/songs/<id>/segments/<idx>` | Edit a chord `{label, apply_to_all?}` |
| POST | `/api/songs/<id>/reset` | Discard edits |
| GET | `/api/songs/<id>/export?fmt=&transpose=&capo=&simplify=&bars_per_row=` | Download export |
| DELETE | `/api/songs/<id>` | Remove from library |

**Storage (SQLite):** `songs(id, video_id UNIQUE, title, duration, key, tempo,
timeline_json, original_json, created_at, updated_at)`,
`jobs(id, video_id, mode, state, progress, message, error, song_id, created_at)`.
Audio files live in `server/data/audio/<video_id>/` and may be deleted after
analysis (config flag); the timeline alone is enough for playback via the
YouTube embed.

## 5. UI

Reference: Claude Design prompt in the brainstorming session; screens Home,
Analyzing, Tracker, Chord Editor, Export modal.

- **Tracker:** YouTube IFrame player; meta chips (key, BPM, capo); large
  current chord + next chord + beat countdown; horizontally scrolling chord
  lane of bars/beats with a fixed centre playhead (click → seek); diagram panel
  (piano computed from spelled notes, bass note highlighted; guitar from the
  chords-db voicing library, piano-only when a voicing is missing).
- **Controls:** transpose −6…+6, capo 0–7, speed 0.5–1.5× (IFrame
  `setPlaybackRate`), Simplify (reduce to triad root quality, drop bass),
  A–B loop.
- **Sync:** poll `player.getCurrentTime()` via `requestAnimationFrame`;
  binary-search the active segment.
- **Chord Editor:** popover with `alt` and the next-best suggestion, root grid
  + quality list + bass selector, "this chord / all matching", reset.
- Transpose / capo / simplify are view settings, stored per song in
  `localStorage`, and passed to export.

## 6. Export

All exporters take `(timeline, transpose, capo, simplify)` and work bar by
bar from downbeats (chords that change mid-bar are written per beat).

- **ChordPro (`.cho`):** `{title}`, `{key}`, `{tempo}`, `{capo}` metadata +
  `{start_of_grid}` with `| Cm7 . . . | F7 . . . |` rows.
- **PDF:** ReportLab; header (title, key, tempo, capo), 4 or 8 bars per row,
  legend of used chords with spelled notes.
- **TXT:** same grid as plain text.
- **MIDI:** block chords (spelled notes, bass in octave 2) on each segment,
  tempo track from detected BPM (mido).
- **JSON:** the timeline contract as-is.

## 7. Errors

| Case | Behaviour |
|---|---|
| Invalid / non-YouTube URL | 400 with message, before creating a job |
| Private, age-restricted, removed, live, > 15 min | Job `failed` with specific message |
| yt-dlp extractor failure | `failed`: "Update yt-dlp: pip install -U yt-dlp" |
| BTC weights missing | Continue with template engine; `engine.chords="template"` + UI warning |
| Demucs out of memory on GPU | Retry on CPU |
| No harmony detected (all `N`) | `done` with empty-state message in UI |
| Server restart mid-job | Running jobs marked `failed` on startup |

## 8. Testing

- **pytest — theory:** parse/format round-trip for every vocabulary label,
  transpose, capo, simplify, slash handling, enharmonic spelling by key.
- **pytest — engine:** synthetic audio (numpy-generated tones) for `Cmaj7`,
  `G/B`, `Am7`, `Dsus4` → template and BTC engines return the expected label
  (BTC test skipped if weights absent); snap/merge unit tests; key estimation
  on synthetic progressions.
- **pytest — exports:** golden-file tests for ChordPro/TXT/JSON; PDF and MIDI
  parsed back and checked for bar count and notes.
- **pytest — API/pipeline:** Flask test client; yt-dlp mocked with a short
  fixture WAV; job lifecycle incl. failure paths.
- **Vitest — client:** active-segment lookup, chord formatting, lane layout
  math. Manual browser check of the Tracker flow.

## 9. Setup constraints

- Python 3.12 virtual environment (system Python 3.14 is too new for parts of
  the torch/audio stack). `madmom` is not used (Python < 3.10 only).
- Dependencies: flask, yt-dlp, torch/torchaudio, demucs, beat_this, librosa,
  numpy, scipy, reportlab, mido, pytest. ffmpeg on PATH (installed).
- BTC pretrained weights downloaded by a setup script into
  `server/engine/weights/` (not committed); verify the repository's license
  before redistributing.
- Client: Node (installed), Vite + React + TypeScript; dev proxy `/api` →
  Flask on port 5000.
