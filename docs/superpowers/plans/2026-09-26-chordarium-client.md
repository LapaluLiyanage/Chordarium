# Chordarium Client (Phase 1, Plan 2 of 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A React web app on top of the Chordarium API: paste a YouTube link, watch analysis progress, then play the video with a Yamaha Chord Tracker-style synced chord display (big current/next chord, scrolling chord lane, piano/guitar diagrams), change transpose/capo/speed/simplify, edit chords, and export chord sheets.

**Architecture:** Vite + React + TypeScript SPA in `client/`, dev-proxied to Flask on port 5000. Pure logic (chord theory port, sync math, view settings) lives in small tested modules; pages compose presentational components. Chord symbol rendering is a TypeScript port of `server/theory/chord.py`, kept in lock-step by a shared test-case file (`shared/chord_cases.json`) that both pytest and Vitest run.

**Tech Stack:** Node 24, Vite (create-vite 9), React 19, TypeScript, react-router-dom 7, Vitest 5 + Testing Library + jsdom, `@tombatossals/chords-db` 0.5 (guitar voicings, MIT), YouTube IFrame Player API.

**Spec:** `docs/superpowers/specs/2026-09-26-chordarium-design.md` (§5 UI, §6 Export). Server API as built in Plan 1 (`server/app.py`).

## Global Constraints

- All client code under `client/`; shared fixtures under `shared/`. Run npm commands from `client/`, pytest from repo root with `.venv` active.
- API base path `/api` (Vite proxy → `http://127.0.0.1:5000`). Never hard-code the Flask port in app code.
- Chord labels from the API are Harte strings; display only through `client/src/theory/chord.ts`, whose behaviour must equal `server/theory/chord.py` on every case in `shared/chord_cases.json`.
- Display spelling: `tonic = keySpelling(timeline.key, transpose - capo)`; symbols = `render(label, {transpose, capo, simplify, tonic})` (same rule as `server/export/grid.py`).
- View settings ranges: transpose −6…+6, capo 0…7, speed ∈ {0.5, 0.75, 1, 1.25, 1.5}, stored per song in `localStorage` key `chordarium:view:<songId>`; every storage access wrapped in try/catch.
- Chord edits are saved in **concert pitch**: a chord picked in the displayed (transposed/capo) space is shifted by `-(transpose - capo)` before sending.
- Test files are excluded from `tsc` (Vitest type-strips them); `npm run build` must stay clean.
- Commits: conventional prefix, author = repo owner only, **no `Co-Authored-By` / "Generated with" lines**.

## Review Focus

1. Editing a chord while transpose/capo is active must save the concert-pitch chord, not the displayed one → Task 11 `saves manual picks in concert pitch`.
2. Browsers that block `localStorage` (private mode, disabled site data) must still let the user transpose/capo → Task 4 `works when storage throws`.
3. Playhead before the first chord or inside an `N` (no-chord) gap must show `N.C.`/`—` without breaking the next-chord preview → Task 4 `upcomingIndex skips no-chord segments`, Task 8 hero test.
4. A job that fails or is cancelled mid-analysis must stop polling and show the reason → Task 6 `shows failure and stops polling`.
5. TS and Python chord rendering drifting apart (e.g. a future spelling fix on one side) → Task 2 shared cases run by both pytest and Vitest.

---

### Task 1: Scaffold the client

**Files:**
- Create: `client/` (Vite react-ts template), `client/vite.config.ts` (replace), `client/src/test/setup.ts`, `client/src/test/setup.test.ts`
- Modify: `client/package.json` (scripts), `client/tsconfig.app.json` (exclude tests, JSON modules)

**Interfaces:**
- Produces: `npm test` (Vitest, jsdom, jest-dom matchers, `requestAnimationFrame` polyfill), `npm run build`, dev proxy `/api`.

- [ ] **Step 1: Generate the template and install dependencies**

```powershell
npm create vite@latest client -- --template react-ts
cd client
npm install
npm install react-router-dom @tombatossals/chords-db
npm install -D vitest jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event
```
If create-vite asks to "install and start now", answer No.

- [ ] **Step 2: Replace `client/vite.config.ts`**

```ts
/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': 'http://127.0.0.1:5000' },
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    css: false,
  },
})
```

- [ ] **Step 3: Test setup**

`client/src/test/setup.ts`:
```ts
import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

if (typeof globalThis.requestAnimationFrame !== 'function') {
  globalThis.requestAnimationFrame = (cb: FrameRequestCallback) =>
    setTimeout(() => cb(performance.now()), 16) as unknown as number
  globalThis.cancelAnimationFrame = (id: number) => clearTimeout(id)
}

afterEach(() => {
  cleanup()
  try {
    localStorage.clear()
  } catch {
    /* storage may be mocked to throw */
  }
})
```

`client/src/test/setup.test.ts`:
```ts
import { expect, it } from 'vitest'

it('provides DOM matchers and requestAnimationFrame', () => {
  document.body.innerHTML = '<p>hi</p>'
  expect(document.querySelector('p')).toHaveTextContent('hi')
  expect(typeof requestAnimationFrame).toBe('function')
})
```

- [ ] **Step 4: Scripts and tsconfig**

In `client/package.json` `"scripts"`, add `"test": "vitest run"` and `"test:watch": "vitest"` (keep `dev`, `build`, `preview`, `lint`).

In `client/tsconfig.app.json`, add inside `compilerOptions`: `"resolveJsonModule": true`, and at top level:
```json
"exclude": ["src/**/*.test.ts", "src/**/*.test.tsx", "src/test"]
```

- [ ] **Step 5: Run tests and build**

Run: `npm test`
Expected: `1 passed`.
Run: `npm run build`
Expected: build succeeds, `dist/` created (git-ignored).

- [ ] **Step 6: Commit**

```bash
git add client/.gitignore client/package.json client/package-lock.json client/index.html client/vite.config.ts client/tsconfig*.json client/eslint.config.js client/public client/src
git commit -m "chore: scaffold react client with vite, vitest and api proxy"
```

---

### Task 2: Shared chord cases + TypeScript chord theory

**Files:**
- Create: `shared/chord_cases.json`, `server/tests/test_chord_shared.py`, `client/src/theory/chord.ts`
- Test: `client/src/theory/chord.test.ts`

**Interfaces:**
- Produces (`client/src/theory/chord.ts`):
  - `SHARPS: string[]`, `QUALITIES: string[]` (14, server order), `QUALITY_INTERVALS: Record<string, number[]>`, `QUALITY_SYMBOL: Record<string, string>`
  - `interface Chord { root: number; quality: string; bass: number | null }`
  - `parse(label: string): Chord | null` (throws `Error` on garbage), `toHarte(c: Chord | null): string`
  - `rootNameInKey(pc: number, tonic: string): string`, `formatSymbol(c: Chord | null, opts?: { preferFlats?: boolean; tonic?: string }): string`
  - `noteNames(c: Chord, opts?): string[]`, `transpose(c: Chord | null, n: number): Chord | null`, `simplify(c: Chord | null): Chord | null`, `pitchClasses(c: Chord): number[]`
  - `render(label: string, opts?: { transpose?: number; capo?: number; simplify?: boolean; preferFlats?: boolean; tonic?: string }): string`
  - `keySpelling(key: string, transposeBy?: number): string`, `formatKey(key: string, transposeBy?: number): string`

- [ ] **Step 1: Write the shared cases**

`shared/chord_cases.json`:
```json
{
  "render": [
    {"label": "A:min7/b3", "expected": "Am7/C"},
    {"label": "B:hdim7", "expected": "Bm7b5"},
    {"label": "C:minmaj7", "expected": "CmMaj7"},
    {"label": "A#:maj7", "prefer_flats": true, "expected": "Bbmaj7"},
    {"label": "D:7/3", "prefer_flats": true, "expected": "D7/F#"},
    {"label": "G:maj/3", "capo": 2, "expected": "F/A"},
    {"label": "C:maj", "transpose": -1, "prefer_flats": true, "expected": "B"},
    {"label": "N", "transpose": 4, "expected": "N.C."},
    {"label": "C:maj7/3", "simplify": true, "expected": "C"},
    {"label": "B:hdim7", "simplify": true, "expected": "Bdim"},
    {"label": "D:sus4", "simplify": true, "expected": "D"},
    {"label": "A#:maj", "tonic": "C", "expected": "Bb"},
    {"label": "D#:maj/3", "tonic": "C", "expected": "Eb/G"},
    {"label": "D#:min", "tonic": "E", "expected": "D#m"},
    {"label": "B:maj", "tonic": "Gb", "expected": "B"},
    {"label": "D:7/3", "transpose": 1, "tonic": "G#", "expected": "D#7/G"},
    {"label": "C:min7", "capo": 2, "tonic": "F", "expected": "Bbm7"}
  ],
  "notes": [
    {"label": "C:min7", "expected": ["C", "Eb", "G", "Bb"]},
    {"label": "A#:maj", "tonic": "C", "expected": ["Bb", "D", "F"]},
    {"label": "D:7", "tonic": "G", "expected": ["D", "F#", "A", "C"]}
  ],
  "key_spelling": [
    {"key": "C:maj", "transpose": 1, "expected": "Db"},
    {"key": "G:min", "transpose": 0, "expected": "G"},
    {"key": "G:maj", "transpose": 3, "expected": "Bb"},
    {"key": "E:min", "transpose": 0, "expected": "E"}
  ],
  "format_key": [
    {"key": "A#:maj", "transpose": 0, "expected": "Bb major"},
    {"key": "G:min", "transpose": 1, "expected": "G# minor"}
  ]
}
```

- [ ] **Step 2: Pin the Python side to the shared cases**

`server/tests/test_chord_shared.py`:
```python
"""The TypeScript port (client/src/theory/chord.ts) runs these same cases."""
import json
from pathlib import Path

import pytest

from server.theory import chord as ch

CASES = json.loads((Path(__file__).resolve().parents[2] / "shared" / "chord_cases.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES["render"], ids=lambda c: c["label"])
def test_render(case):
    assert ch.render(case["label"], transpose_by=case.get("transpose", 0), capo=case.get("capo", 0),
                     simplify_chord=case.get("simplify", False), prefer_flats=case.get("prefer_flats", False),
                     tonic=case.get("tonic")) == case["expected"]


@pytest.mark.parametrize("case", CASES["notes"], ids=lambda c: c["label"])
def test_notes(case):
    assert ch.note_names(ch.parse(case["label"]), tonic=case.get("tonic")) == case["expected"]


@pytest.mark.parametrize("case", CASES["key_spelling"], ids=lambda c: c["key"])
def test_key_spelling(case):
    assert ch.key_spelling(case["key"], case["transpose"]) == case["expected"]


@pytest.mark.parametrize("case", CASES["format_key"], ids=lambda c: c["key"])
def test_format_key(case):
    assert ch.format_key(case["key"], case["transpose"]) == case["expected"]
```

Run (repo root): `.venv\Scripts\python -m pytest server/tests/test_chord_shared.py -q`
Expected: all PASS immediately — this pins existing Python behaviour as the contract; the RED step for this task is the TypeScript test below.

- [ ] **Step 3: Write the failing TypeScript test**

`client/src/theory/chord.test.ts`:
```ts
import { describe, expect, it } from 'vitest'
import cases from '../../../shared/chord_cases.json'
import { formatKey, keySpelling, noteNames, parse, render, toHarte, transpose, QUALITIES } from './chord'

type RenderCase = { label: string; expected: string; transpose?: number; capo?: number; simplify?: boolean; prefer_flats?: boolean; tonic?: string }
type NotesCase = { label: string; expected: string[]; tonic?: string }
type KeyCase = { key: string; transpose: number; expected: string }

describe('shared chord cases (must match server/theory/chord.py)', () => {
  it.each(cases.render as RenderCase[])('render $label → $expected', (c) => {
    expect(render(c.label, { transpose: c.transpose, capo: c.capo, simplify: c.simplify, preferFlats: c.prefer_flats, tonic: c.tonic })).toBe(c.expected)
  })
  it.each(cases.notes as NotesCase[])('notes $label', (c) => {
    expect(noteNames(parse(c.label)!, { tonic: c.tonic })).toEqual(c.expected)
  })
  it.each(cases.key_spelling as KeyCase[])('keySpelling $key +$transpose', (c) => {
    expect(keySpelling(c.key, c.transpose)).toBe(c.expected)
  })
  it.each(cases.format_key as KeyCase[])('formatKey $key +$transpose', (c) => {
    expect(formatKey(c.key, c.transpose)).toBe(c.expected)
  })
})

describe('parse / toHarte / transpose', () => {
  it('handles no-chord and garbage', () => {
    expect(parse('N')).toBeNull()
    expect(parse('X')).toBeNull()
    expect(() => parse('H:maj')).toThrow()
    expect(() => parse('C:weird')).toThrow()
  })
  it('round-trips every vocabulary chord with an inversion', () => {
    for (let root = 0; root < 12; root++) {
      for (const quality of QUALITIES) {
        const c = { root, quality, bass: null }
        expect(parse(toHarte(c))).toEqual(c)
      }
    }
    expect(toHarte({ root: 7, quality: 'maj', bass: 11 })).toBe('G:maj/3')
  })
  it('transposes root and bass with wrap-around', () => {
    expect(transpose(parse('G:maj/3'), 5)).toEqual({ root: 0, quality: 'maj', bass: 4 })
    expect(transpose(parse('B:maj'), 2)).toEqual({ root: 1, quality: 'maj', bass: null })
  })
})
```

Run (in `client/`): `npm test -- src/theory`
Expected: FAIL — `Failed to resolve import "./chord"`.

- [ ] **Step 4: Implement `client/src/theory/chord.ts`**

```ts
/** TypeScript port of server/theory/chord.py — keep in sync via shared/chord_cases.json. */

export interface Chord {
  root: number
  quality: string
  bass: number | null
}

export const SHARPS = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
export const FLATS = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']
const LETTERS = 'CDEFGAB'
const NATURAL_PC: Record<string, number> = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 }
const NAME_TO_PC: Record<string, number> = {
  ...Object.fromEntries(SHARPS.map((n, i) => [n, i])),
  ...Object.fromEntries(FLATS.map((n, i) => [n, i])),
  Cb: 11, Fb: 4, 'E#': 5, 'B#': 0,
}

export const QUALITY_INTERVALS: Record<string, number[]> = {
  maj: [0, 4, 7], min: [0, 3, 7], dim: [0, 3, 6], aug: [0, 4, 8],
  min6: [0, 3, 7, 9], maj6: [0, 4, 7, 9], min7: [0, 3, 7, 10], minmaj7: [0, 3, 7, 11],
  maj7: [0, 4, 7, 11], '7': [0, 4, 7, 10], dim7: [0, 3, 6, 9], hdim7: [0, 3, 6, 10],
  sus2: [0, 2, 7], sus4: [0, 5, 7],
}
export const QUALITIES = Object.keys(QUALITY_INTERVALS)
export const QUALITY_SYMBOL: Record<string, string> = {
  maj: '', min: 'm', dim: 'dim', aug: 'aug', min6: 'm6', maj6: '6', min7: 'm7', minmaj7: 'mMaj7',
  maj7: 'maj7', '7': '7', dim7: 'dim7', hdim7: 'm7b5', sus2: 'sus2', sus4: 'sus4',
}
const SIMPLE_QUALITY: Record<string, string> = {
  maj: 'maj', maj6: 'maj', maj7: 'maj', '7': 'maj', sus2: 'maj', sus4: 'maj', aug: 'aug',
  min: 'min', min6: 'min', min7: 'min', minmaj7: 'min', dim: 'dim', dim7: 'dim', hdim7: 'dim',
}
const DEGREE_TO_INTERVAL: Record<string, number> = {
  '1': 0, b2: 1, '2': 2, b3: 3, '3': 4, '4': 5, b5: 6, '5': 7, '#5': 8, b6: 8, '6': 9, bb7: 9, b7: 10, '7': 11,
}
const INTERVAL_TO_DEGREE = ['1', 'b2', '2', 'b3', '3', '4', 'b5', '5', '#5', '6', 'b7', '7']
const INTERVAL_LETTER_STEPS = [0, 1, 1, 2, 2, 3, 4, 4, 4, 5, 6, 6]
const KEY_DEGREE_LETTER_STEPS = [0, 1, 1, 2, 2, 3, 3, 4, 5, 5, 6, 6]
const AWKWARD = new Set(['Cb', 'Fb', 'E#', 'B#'])
const FLAT_MAJOR_ROOTS = new Set([5, 10, 3, 8, 1])
const FLAT_MINOR_ROOTS = new Set([2, 7, 0, 5, 10, 3])

const mod12 = (n: number) => ((n % 12) + 12) % 12
const accidental = (diff: number): string | null => (diff === -1 ? 'b' : diff === 0 ? '' : diff === 1 ? '#' : null)

export function parse(label: string): Chord | null {
  const text = label.trim()
  if (text === '' || text === 'N' || text === 'X') return null
  const [body, bassPart = ''] = text.split('/', 2)
  const [rootS, qualityRaw = ''] = body.split(':', 2)
  const quality = qualityRaw || 'maj'
  if (!(rootS in NAME_TO_PC)) throw new Error(`Unknown chord root: ${rootS}`)
  if (!(quality in QUALITY_INTERVALS)) throw new Error(`Unknown chord quality: ${quality}`)
  const root = NAME_TO_PC[rootS]
  let bass: number | null = null
  if (bassPart) {
    if (bassPart in DEGREE_TO_INTERVAL) bass = mod12(root + DEGREE_TO_INTERVAL[bassPart])
    else if (bassPart in NAME_TO_PC) bass = NAME_TO_PC[bassPart]
    else throw new Error(`Unknown bass note: ${bassPart}`)
    if (bass === root) bass = null
  }
  return { root, quality, bass }
}

export function toHarte(c: Chord | null): string {
  if (!c) return 'N'
  let s = `${SHARPS[c.root]}:${c.quality}`
  if (c.bass !== null) s += '/' + INTERVAL_TO_DEGREE[mod12(c.bass - c.root)]
  return s
}

function rootName(pc: number, preferFlats: boolean): string {
  return (preferFlats ? FLATS : SHARPS)[mod12(pc)]
}

function spell(root: string, interval: number): string {
  const letter = LETTERS[(LETTERS.indexOf(root[0]) + INTERVAL_LETTER_STEPS[mod12(interval)]) % 7]
  const target = mod12(NAME_TO_PC[root] + interval)
  const acc = accidental(mod12(target - NATURAL_PC[letter] + 6) - 6)
  if (acc !== null) return letter + acc
  return (root.includes('b') ? FLATS : SHARPS)[target]
}

export function rootNameInKey(pc: number, tonic: string): string {
  const degree = mod12(pc - NAME_TO_PC[tonic])
  const letter = LETTERS[(LETTERS.indexOf(tonic[0]) + KEY_DEGREE_LETTER_STEPS[degree]) % 7]
  const acc = accidental(mod12(mod12(pc) - NATURAL_PC[letter] + 6) - 6)
  const name = acc === null ? null : letter + acc
  if (name === null || AWKWARD.has(name)) return rootName(pc, tonic.includes('b'))
  return name
}

type SpellOpts = { preferFlats?: boolean; tonic?: string }

function rootOf(c: Chord, opts: SpellOpts): string {
  return opts.tonic ? rootNameInKey(c.root, opts.tonic) : rootName(c.root, Boolean(opts.preferFlats))
}

export function formatSymbol(c: Chord | null, opts: SpellOpts = {}): string {
  if (!c) return 'N.C.'
  const root = rootOf(c, opts)
  let s = root + QUALITY_SYMBOL[c.quality]
  if (c.bass !== null) s += '/' + spell(root, c.bass - c.root)
  return s
}

export function noteNames(c: Chord, opts: SpellOpts = {}): string[] {
  const root = rootOf(c, opts)
  return QUALITY_INTERVALS[c.quality].map((i) => spell(root, i))
}

export function pitchClasses(c: Chord): number[] {
  return QUALITY_INTERVALS[c.quality].map((i) => mod12(c.root + i))
}

export function transpose(c: Chord | null, n: number): Chord | null {
  if (!c) return null
  return { root: mod12(c.root + n), quality: c.quality, bass: c.bass === null ? null : mod12(c.bass + n) }
}

export function simplify(c: Chord | null): Chord | null {
  if (!c) return null
  return { root: c.root, quality: SIMPLE_QUALITY[c.quality], bass: null }
}

export type RenderOpts = { transpose?: number; capo?: number; simplify?: boolean; preferFlats?: boolean; tonic?: string }

export function render(label: string, opts: RenderOpts = {}): string {
  let c = parse(label)
  if (opts.simplify) c = simplify(c)
  return formatSymbol(transpose(c, (opts.transpose ?? 0) - (opts.capo ?? 0)), opts)
}

function parseKey(key: string): [number, 'maj' | 'min'] {
  const c = parse(key)
  if (!c || (c.quality !== 'maj' && c.quality !== 'min')) throw new Error(`Not a key: ${key}`)
  return [c.root, c.quality]
}

function keyPrefersFlats(key: string, transposeBy = 0): boolean {
  const [root, mode] = parseKey(key)
  return (mode === 'maj' ? FLAT_MAJOR_ROOTS : FLAT_MINOR_ROOTS).has(mod12(root + transposeBy))
}

export function keySpelling(key: string, transposeBy = 0): string {
  const [root] = parseKey(key)
  return rootName(root + transposeBy, keyPrefersFlats(key, transposeBy))
}

export function formatKey(key: string, transposeBy = 0): string {
  const [, mode] = parseKey(key)
  return `${keySpelling(key, transposeBy)} ${mode === 'maj' ? 'major' : 'minor'}`
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run (client): `npm test -- src/theory`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add shared/chord_cases.json server/tests/test_chord_shared.py client/src/theory
git commit -m "feat: port chord theory to typescript with shared cross-language cases"
```

---

### Task 3: API types and client

**Files:**
- Create: `client/src/types.ts`, `client/src/api.ts`, `client/src/test/fixtures.ts`
- Test: `client/src/api.test.ts`

**Interfaces:**
- Produces (`types.ts`): `Segment`, `Timeline`, `SongSummary`, `Song`, `JobState`, `Job`, `ExportFormat`, `ExportRequest { fmt; transpose; capo; simplify; barsPerRow: 4 | 8 }`
- Produces (`api.ts`): `class ApiError extends Error { status: number }`; `api.analyze(url, mode)`, `api.job(id)`, `api.cancelJob(id)`, `api.songs()`, `api.song(id)`, `api.editSegment(songId, index, label, applyToAll)`, `api.reset(songId)`, `api.deleteSong(songId)`; `exportUrl(songId, req: ExportRequest): string`
- Produces (`test/fixtures.ts`): `TIMELINE: Timeline` (same data as `server/tests/conftest.py`), `SONG: Song`, `makeSong(patch?): Song`

- [ ] **Step 1: Types**

`client/src/types.ts`:
```ts
export interface Segment {
  start: number
  end: number
  label: string
  alt: string | null
  confidence: number
  bass: string | null
  edited: boolean
}

export interface Timeline {
  video_id: string
  title: string
  duration: number
  key: string
  tempo: number
  time_signature: number
  beats: number[]
  downbeats: number[]
  segments: Segment[]
  engine: { chords: string; separated: boolean; version: string }
  warnings: string[]
}

export interface SongSummary {
  id: string
  video_id: string
  title: string
  duration: number
  key: string
  tempo: number
  created_at: string
  updated_at: string
}

export interface Song extends SongSummary {
  timeline: Timeline
}

export type JobState =
  | 'queued' | 'downloading' | 'separating' | 'beats' | 'chords' | 'bass' | 'key'
  | 'done' | 'failed' | 'cancelled'

export interface Job {
  id: string
  video_id: string
  mode: 'fast' | 'accurate'
  state: JobState
  progress: number
  message: string | null
  error: string | null
  song_id: string | null
  created_at: string
}

export type ExportFormat = 'pdf' | 'chordpro' | 'txt' | 'midi' | 'json'

export interface ExportRequest {
  fmt: ExportFormat
  transpose: number
  capo: number
  simplify: boolean
  barsPerRow: 4 | 8
}
```

`client/src/test/fixtures.ts`:
```ts
import type { Song, Timeline } from '../types'

export const TIMELINE: Timeline = {
  video_id: 'abcdefghijk',
  title: 'Test Song',
  duration: 8.0,
  key: 'G:min',
  tempo: 120.0,
  time_signature: 4,
  beats: Array.from({ length: 16 }, (_, i) => i * 0.5),
  downbeats: [0, 2, 4, 6],
  segments: [
    { start: 0, end: 2, label: 'C:min7', alt: 'C:min', confidence: 0.8, bass: 'C', edited: false },
    { start: 2, end: 4, label: 'F:7', alt: 'F:maj', confidence: 0.7, bass: 'F', edited: false },
    { start: 4, end: 5, label: 'A#:maj7', alt: null, confidence: 0.6, bass: 'A#', edited: false },
    { start: 5, end: 6, label: 'D#:maj7', alt: null, confidence: 0.6, bass: 'D#', edited: false },
    { start: 6, end: 8, label: 'D:7/3', alt: 'D:7', confidence: 0.4, bass: 'F#', edited: false },
  ],
  engine: { chords: 'btc-large', separated: true, version: '1' },
  warnings: [],
}

export function makeSong(patch: Partial<Timeline> = {}): Song {
  const timeline = structuredClone({ ...TIMELINE, ...patch })
  return {
    id: 's1', video_id: timeline.video_id, title: timeline.title, duration: timeline.duration,
    key: timeline.key, tempo: timeline.tempo, created_at: '2026-09-26T00:00:00Z',
    updated_at: '2026-09-26T00:00:00Z', timeline,
  }
}

export const SONG: Song = makeSong()
```

- [ ] **Step 2: Write the failing test**

`client/src/api.test.ts`:
```ts
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError, exportUrl } from './api'

function reply(status: number, body?: unknown) {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status, headers: { 'Content-Type': 'application/json' },
  })
}

afterEach(() => vi.unstubAllGlobals())

describe('api', () => {
  it('posts analyze requests as JSON', async () => {
    const fetchMock = vi.fn().mockResolvedValue(reply(202, { job_id: 'j1' }))
    vi.stubGlobal('fetch', fetchMock)
    await expect(api.analyze('https://youtu.be/x', 'accurate')).resolves.toEqual({ job_id: 'j1' })
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/analyze')
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body)).toEqual({ url: 'https://youtu.be/x', mode: 'accurate' })
  })

  it('turns error responses into ApiError with the server message', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(reply(400, { error: 'Not a YouTube link' })))
    const err = await api.analyze('nope', 'fast').catch((e) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect(err.message).toBe('Not a YouTube link')
    expect(err.status).toBe(400)
  })

  it('returns undefined for 204 responses', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(reply(204)))
    await expect(api.deleteSong('s1')).resolves.toBeUndefined()
  })

  it('sends segment edits with apply_to_all', async () => {
    const fetchMock = vi.fn().mockResolvedValue(reply(200, { segments: [] }))
    vi.stubGlobal('fetch', fetchMock)
    await api.editSegment('s1', 3, 'G:maj', true)
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/songs/s1/segments/3')
    expect(init.method).toBe('PUT')
    expect(JSON.parse(init.body)).toEqual({ label: 'G:maj', apply_to_all: true })
  })
})

describe('exportUrl', () => {
  it('encodes every export option', () => {
    expect(exportUrl('s1', { fmt: 'chordpro', transpose: -2, capo: 3, simplify: true, barsPerRow: 8 }))
      .toBe('/api/songs/s1/export?fmt=chordpro&transpose=-2&capo=3&simplify=1&bars_per_row=8')
  })
})
```

Run: `npm test -- src/api`
Expected: FAIL — `Failed to resolve import "./api"`.

- [ ] **Step 3: Implement `client/src/api.ts`**

```ts
import type { ExportRequest, Job, Song, SongSummary, Timeline } from './types'

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init.headers ?? {}) },
  })
  if (!res.ok) {
    let message = res.statusText || `Request failed (${res.status})`
    try {
      const body = await res.json()
      if (body?.error) message = body.error
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(message, res.status)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export type AnalyzeResponse = { job_id?: string; song_id?: string; cached?: boolean }

export const api = {
  analyze: (url: string, mode: 'fast' | 'accurate') =>
    request<AnalyzeResponse>('/analyze', { method: 'POST', body: JSON.stringify({ url, mode }) }),
  job: (id: string) => request<Job>(`/jobs/${id}`),
  cancelJob: (id: string) => request<{ cancelled: boolean }>(`/jobs/${id}/cancel`, { method: 'POST' }),
  songs: () => request<SongSummary[]>('/songs'),
  song: (id: string) => request<Song>(`/songs/${id}`),
  editSegment: (songId: string, index: number, label: string, applyToAll: boolean) =>
    request<Timeline>(`/songs/${songId}/segments/${index}`, {
      method: 'PUT', body: JSON.stringify({ label, apply_to_all: applyToAll }),
    }),
  reset: (songId: string) => request<Timeline>(`/songs/${songId}/reset`, { method: 'POST' }),
  deleteSong: (songId: string) => request<void>(`/songs/${songId}`, { method: 'DELETE' }),
}

export function exportUrl(songId: string, req: ExportRequest): string {
  const params = new URLSearchParams({
    fmt: req.fmt,
    transpose: String(req.transpose),
    capo: String(req.capo),
    simplify: req.simplify ? '1' : '0',
    bars_per_row: String(req.barsPerRow),
  })
  return `/api/songs/${songId}/export?${params.toString()}`
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- src/api`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add client/src/types.ts client/src/api.ts client/src/api.test.ts client/src/test/fixtures.ts
git commit -m "feat: add typed api client for the chordarium server"
```

---

### Task 4: Sync math and per-song view settings

**Files:**
- Create: `client/src/sync.ts`, `client/src/hooks/useViewSettings.ts`
- Test: `client/src/sync.test.ts`, `client/src/hooks/useViewSettings.test.ts`

**Interfaces:**
- Produces (`sync.ts`): `PX_PER_SECOND = 120`, `activeIndex(segments, t): number` (−1 if none), `upcomingIndex(segments, t): number` (first non-`N` segment starting after `t`, −1 if none), `beatsUntil(beats, t, target): number`, `laneOffset(t, width): number`
- Produces (`useViewSettings.ts`): `RATES = [0.5, 0.75, 1, 1.25, 1.5]`, `interface ViewSettings { transpose; capo; simplify; rate }`, `DEFAULT_VIEW`, `normalizeView(v): ViewSettings`, `useViewSettings(songId): [ViewSettings, (patch: Partial<ViewSettings>) => void]`

- [ ] **Step 1: Write the failing tests**

`client/src/sync.test.ts`:
```ts
import { describe, expect, it } from 'vitest'
import { activeIndex, beatsUntil, laneOffset, upcomingIndex } from './sync'
import { TIMELINE } from './test/fixtures'

const segs = TIMELINE.segments
const withGap = [
  { ...segs[0], start: 1, end: 2 },
  { ...segs[0], start: 2, end: 3, label: 'N' },
  { ...segs[1], start: 3, end: 5 },
]

describe('activeIndex', () => {
  it('finds the segment containing t', () => {
    expect(activeIndex(segs, 0)).toBe(0)
    expect(activeIndex(segs, 2)).toBe(1)
    expect(activeIndex(segs, 5.5)).toBe(3)
  })
  it('returns -1 before the first and after the last segment', () => {
    expect(activeIndex(withGap, 0.5)).toBe(-1)
    expect(activeIndex(segs, 8)).toBe(-1)
  })
})

describe('upcomingIndex', () => {
  it('is the next segment after t', () => {
    expect(upcomingIndex(segs, 1)).toBe(1)
    expect(upcomingIndex(segs, 7)).toBe(-1)
  })
  it('skips no-chord segments', () => {
    expect(upcomingIndex(withGap, 1.5)).toBe(2)
    expect(upcomingIndex(withGap, 0)).toBe(0)
  })
})

describe('beatsUntil / laneOffset', () => {
  it('counts beats after t up to and including the target', () => {
    expect(beatsUntil(TIMELINE.beats, 1.0, 2.0)).toBe(2)
    expect(beatsUntil(TIMELINE.beats, 1.9, 2.0)).toBe(1)
    expect(beatsUntil(TIMELINE.beats, 2.0, 2.0)).toBe(0)
  })
  it('centres the playhead', () => {
    expect(laneOffset(0, 800)).toBe(400)
    expect(laneOffset(2, 800)).toBe(160)
  })
})
```

`client/src/hooks/useViewSettings.test.ts`:
```ts
import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { DEFAULT_VIEW, normalizeView, useViewSettings } from './useViewSettings'

afterEach(() => vi.restoreAllMocks())

describe('normalizeView', () => {
  it('clamps ranges and snaps speed', () => {
    expect(normalizeView({ transpose: 9, capo: -1, rate: 3 })).toEqual({ ...DEFAULT_VIEW, transpose: 6, capo: 0, rate: 1 })
    expect(normalizeView({ transpose: -8, capo: 12, rate: 0.75, simplify: true }))
      .toEqual({ transpose: -6, capo: 7, rate: 0.75, simplify: true })
  })
})

describe('useViewSettings', () => {
  it('starts with defaults and persists changes per song', () => {
    const { result, unmount } = renderHook(() => useViewSettings('s1'))
    expect(result.current[0]).toEqual(DEFAULT_VIEW)
    act(() => result.current[1]({ transpose: 2, capo: 1 }))
    expect(result.current[0]).toMatchObject({ transpose: 2, capo: 1 })
    unmount()
    expect(renderHook(() => useViewSettings('s1')).result.current[0]).toMatchObject({ transpose: 2, capo: 1 })
    expect(renderHook(() => useViewSettings('s2')).result.current[0]).toEqual(DEFAULT_VIEW)
  })

  it('works when storage throws', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked') })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked') })
    const { result } = renderHook(() => useViewSettings('s1'))
    act(() => result.current[1]({ transpose: 3 }))
    expect(result.current[0].transpose).toBe(3)
  })
})
```

Run: `npm test -- src/sync src/hooks`
Expected: FAIL — cannot resolve `./sync` / `./useViewSettings`.

- [ ] **Step 2: Implement `client/src/sync.ts`**

```ts
import type { Segment } from './types'

export const PX_PER_SECOND = 120

function firstStartAfter(segments: Segment[], t: number): number {
  let lo = 0
  let hi = segments.length
  while (lo < hi) {
    const mid = (lo + hi) >> 1
    if (segments[mid].start <= t) lo = mid + 1
    else hi = mid
  }
  return lo
}

export function activeIndex(segments: Segment[], t: number): number {
  const i = firstStartAfter(segments, t) - 1
  return i >= 0 && t < segments[i].end ? i : -1
}

export function upcomingIndex(segments: Segment[], t: number): number {
  for (let j = firstStartAfter(segments, t); j < segments.length; j++) {
    if (segments[j].label !== 'N') return j
  }
  return -1
}

export function beatsUntil(beats: number[], t: number, target: number): number {
  return beats.filter((b) => b > t + 1e-6 && b <= target + 1e-6).length
}

export function laneOffset(t: number, width: number): number {
  return width / 2 - t * PX_PER_SECOND
}
```

- [ ] **Step 3: Implement `client/src/hooks/useViewSettings.ts`**

```ts
import { useCallback, useState } from 'react'

export const RATES = [0.5, 0.75, 1, 1.25, 1.5]

export interface ViewSettings {
  transpose: number
  capo: number
  simplify: boolean
  rate: number
}

export const DEFAULT_VIEW: ViewSettings = { transpose: 0, capo: 0, simplify: false, rate: 1 }

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, Math.round(Number(v) || 0)))

export function normalizeView(v: Partial<ViewSettings>): ViewSettings {
  const m = { ...DEFAULT_VIEW, ...v }
  return {
    transpose: clamp(m.transpose, -6, 6),
    capo: clamp(m.capo, 0, 7),
    simplify: Boolean(m.simplify),
    rate: RATES.includes(m.rate) ? m.rate : 1,
  }
}

function read(key: string): ViewSettings {
  try {
    const raw = localStorage.getItem(key)
    return raw ? normalizeView(JSON.parse(raw)) : DEFAULT_VIEW
  } catch {
    return DEFAULT_VIEW
  }
}

export function useViewSettings(songId: string): [ViewSettings, (patch: Partial<ViewSettings>) => void] {
  const key = `chordarium:view:${songId}`
  const [settings, setSettings] = useState<ViewSettings>(() => read(key))
  const update = useCallback(
    (patch: Partial<ViewSettings>) => {
      setSettings((prev) => {
        const next = normalizeView({ ...prev, ...patch })
        try {
          localStorage.setItem(key, JSON.stringify(next))
        } catch {
          /* storage unavailable: keep in memory only */
        }
        return next
      })
    },
    [key],
  )
  return [settings, update]
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- src/sync src/hooks`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add client/src/sync.ts client/src/sync.test.ts client/src/hooks
git commit -m "feat: add playhead sync math and per-song view settings"
```

---

### Task 5: App shell, styles and Home page

**Files:**
- Create: `client/src/App.tsx` (replace template), `client/src/styles.css`, `client/src/pages/HomePage.tsx`, `client/src/test/router.tsx`
- Modify: `client/src/main.tsx` (replace), `client/index.html` (title)
- Delete: `client/src/App.css`, `client/src/index.css`, `client/src/assets/react.svg`, `client/public/vite.svg` (template leftovers)
- Test: `client/src/pages/HomePage.test.tsx`, `client/src/App.test.tsx`

**Interfaces:**
- Consumes: `api.analyze`, `api.songs`, `formatKey`
- Produces: `AppRoutes()` (routes `/`, `/jobs/:jobId`, `/songs/:songId`), `App()` (BrowserRouter + AppRoutes), `HomePage`, test helper `renderAt(path, routes)`. Pages `AnalyzingPage` (Task 6) and `TrackerPage` (Task 12) are imported by `App.tsx`; until they exist, this task creates minimal placeholders `client/src/pages/AnalyzingPage.tsx` and `client/src/pages/TrackerPage.tsx` exporting a component that renders `<main className="page" />` — Tasks 6 and 12 replace them.

- [ ] **Step 1: Test helper and failing tests**

`client/src/test/router.tsx` (`ui()` builds a fresh element so `rerender(ui())` really re-renders):
```tsx
import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter, Routes } from 'react-router-dom'

export function renderAt(path: string, routes: ReactElement) {
  const ui = () => (
    <MemoryRouter initialEntries={[path]}>
      <Routes>{routes}</Routes>
    </MemoryRouter>
  )
  return { ...render(ui()), ui }
}
```

`client/src/pages/HomePage.test.tsx`:
```tsx
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { renderAt } from '../test/router'
import { HomePage } from './HomePage'

vi.mock('../api', () => ({ api: { analyze: vi.fn(), songs: vi.fn() } }))
import { api } from '../api'
const mocked = vi.mocked(api)

function renderHome() {
  return renderAt('/', (
    <>
      <Route path="/" element={<HomePage />} />
      <Route path="/jobs/:jobId" element={<p>JOB PAGE</p>} />
      <Route path="/songs/:songId" element={<p>SONG PAGE</p>} />
    </>
  ))
}

beforeEach(() => {
  mocked.songs.mockResolvedValue([])
})

describe('HomePage', () => {
  it('starts a fast analysis and opens the job page', async () => {
    mocked.analyze.mockResolvedValue({ job_id: 'j1' })
    const user = userEvent.setup()
    renderHome()
    await user.type(screen.getByLabelText(/youtube link/i), 'https://youtu.be/dQw4w9WgXcQ')
    await user.click(screen.getByRole('button', { name: /analyze/i }))
    expect(mocked.analyze).toHaveBeenCalledWith('https://youtu.be/dQw4w9WgXcQ', 'fast')
    expect(await screen.findByText('JOB PAGE')).toBeInTheDocument()
  })

  it('uses accurate mode when chosen and opens cached songs directly', async () => {
    mocked.analyze.mockResolvedValue({ song_id: 's9', cached: true })
    const user = userEvent.setup()
    renderHome()
    await user.click(screen.getByLabelText(/accurate/i))
    await user.type(screen.getByLabelText(/youtube link/i), 'https://youtu.be/dQw4w9WgXcQ')
    await user.click(screen.getByRole('button', { name: /analyze/i }))
    expect(mocked.analyze).toHaveBeenCalledWith('https://youtu.be/dQw4w9WgXcQ', 'accurate')
    expect(await screen.findByText('SONG PAGE')).toBeInTheDocument()
  })

  it('shows the server error message', async () => {
    mocked.analyze.mockRejectedValue(new Error("That doesn't look like a YouTube video link."))
    const user = userEvent.setup()
    renderHome()
    await user.type(screen.getByLabelText(/youtube link/i), 'hello')
    await user.click(screen.getByRole('button', { name: /analyze/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent("doesn't look like a YouTube")
  })

  it('lists recent songs or an empty state', async () => {
    mocked.songs.mockResolvedValue([{
      id: 's1', video_id: 'abcdefghijk', title: 'Autumn Leaves', duration: 200, key: 'G:min', tempo: 124,
      created_at: '', updated_at: '',
    }])
    renderHome()
    const link = await screen.findByRole('link', { name: /autumn leaves/i })
    expect(link).toHaveAttribute('href', '/songs/s1')
    expect(screen.getByText(/G minor · 124 BPM/)).toBeInTheDocument()
  })

  it('shows an empty library message', async () => {
    renderHome()
    expect(await screen.findByText(/no songs yet/i)).toBeInTheDocument()
  })
})
```

`client/src/App.test.tsx`:
```tsx
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { expect, it, vi } from 'vitest'
import { AppRoutes } from './App'

vi.mock('./api', () => ({ api: { analyze: vi.fn(), songs: vi.fn().mockResolvedValue([]) } }))

it('renders the brand and the home page at /', async () => {
  render(<MemoryRouter initialEntries={['/']}><AppRoutes /></MemoryRouter>)
  expect(screen.getByRole('link', { name: 'Chordarium' })).toHaveAttribute('href', '/')
  expect(await screen.findByRole('heading', { name: /paste a youtube link/i })).toBeInTheDocument()
})
```

Run: `npm test -- src/pages/HomePage src/App`
Expected: FAIL — cannot resolve `./HomePage` / `./App` exports.

- [ ] **Step 2: Styles**

`client/src/styles.css`:
```css
:root {
  --bg: #111316;
  --surface: #1a1d22;
  --surface-2: #23272e;
  --text: #eceef1;
  --muted: #9aa3ad;
  --line: #2e333b;
  --accent: #f2a541;
  --accent-ink: #1b1204;
  --danger: #ff6b6b;
  --radius: 12px;
  --font: "Inter", system-ui, -apple-system, "Segoe UI", sans-serif;
  --chord-font: "Inter", "Segoe UI", system-ui, sans-serif;
  color-scheme: dark;
}
@media (prefers-color-scheme: light) {
  :root {
    --bg: #f6f5f2; --surface: #ffffff; --surface-2: #efede8; --text: #1b1d21; --muted: #5f6670;
    --line: #dcd8cf; --accent: #c7720a; --accent-ink: #ffffff; color-scheme: light;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text); font-family: var(--font); }
a { color: inherit; }
button, input, select { font: inherit; color: inherit; }
button { cursor: pointer; }
.muted { color: var(--muted); }

.topbar { display: flex; align-items: center; justify-content: space-between; padding: 14px 24px; border-bottom: 1px solid var(--line); }
.brand { font-weight: 800; letter-spacing: -0.02em; text-decoration: none; font-size: 1.2rem; }
.soon { color: var(--muted); font-size: 0.85rem; }
.page { max-width: 1200px; margin: 0 auto; padding: 24px 16px 64px; }

.button { display: inline-flex; align-items: center; gap: 6px; padding: 10px 16px; border-radius: 10px; border: 1px solid var(--line); background: var(--surface-2); text-decoration: none; }
.button.primary { background: var(--accent); color: var(--accent-ink); border-color: transparent; font-weight: 700; }
.button[aria-pressed="true"] { outline: 2px solid var(--accent); }
.button:disabled { opacity: 0.6; cursor: default; }

.analyze-form { display: grid; gap: 12px; background: var(--surface); padding: 20px; border-radius: var(--radius); border: 1px solid var(--line); }
.analyze-form input[type="text"] { width: 100%; padding: 14px; border-radius: 10px; border: 1px solid var(--line); background: var(--bg); font-size: 1.05rem; }
.mode { display: flex; gap: 16px; flex-wrap: wrap; }
.error { color: var(--danger); }

.library { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 16px; margin-top: 16px; }
.song-card { display: grid; gap: 6px; text-decoration: none; background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); overflow: hidden; }
.song-card img { width: 100%; aspect-ratio: 16 / 9; object-fit: cover; background: var(--surface-2); }
.song-card div { padding: 0 12px 12px; }

.steps { list-style: none; padding: 0; display: grid; gap: 8px; }
.steps li { padding: 10px 12px; border-radius: 10px; background: var(--surface); border: 1px solid var(--line); }
.steps li[data-status="done"] { color: var(--muted); }
.steps li[data-status="active"] { border-color: var(--accent); }
progress { width: 100%; height: 10px; accent-color: var(--accent); }

.tracker { display: grid; gap: 16px; }
.tracker-top { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr); gap: 16px; }
@media (max-width: 800px) { .tracker-top { grid-template-columns: 1fr; } }
.player { aspect-ratio: 16 / 9; width: 100%; background: #000; border-radius: var(--radius); overflow: hidden; }
.player iframe, .player > div { width: 100%; height: 100%; }
.chips { display: flex; gap: 8px; flex-wrap: wrap; }
.chip-meta { padding: 4px 10px; border-radius: 999px; background: var(--surface-2); font-size: 0.85rem; }
.banner { padding: 10px 14px; border-radius: 10px; background: var(--surface-2); border-left: 4px solid var(--accent); }

.hero { display: grid; align-content: center; justify-items: start; gap: 8px; padding: 20px; background: var(--surface); border-radius: var(--radius); border: 1px solid var(--line); }
.hero-current { font-family: var(--chord-font); font-weight: 800; font-size: clamp(4rem, 10vw, 8.5rem); line-height: 1; letter-spacing: -0.03em; color: var(--accent); }
.hero-next { display: flex; align-items: center; gap: 12px; font-size: 1.6rem; font-weight: 700; }
.hero-next-label { font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.1em; color: var(--muted); }
.beat-dots { display: inline-flex; gap: 6px; }
.dot { width: 10px; height: 10px; border-radius: 50%; background: var(--line); }
.dot.on { background: var(--accent); }

.lane { position: relative; height: 96px; overflow: hidden; background: var(--surface); border-radius: var(--radius); border: 1px solid var(--line); }
.lane-playhead { position: absolute; left: 50%; top: 0; bottom: 0; width: 2px; background: var(--accent); z-index: 2; }
.lane-track { position: absolute; top: 0; bottom: 0; left: 0; will-change: transform; }
.beat-tick { position: absolute; bottom: 0; width: 1px; height: 10px; background: var(--line); }
.bar-line { position: absolute; top: 0; bottom: 0; width: 1px; background: var(--muted); opacity: 0.5; }
.chip { position: absolute; top: 22px; height: 48px; padding: 0 10px; text-align: left; font-weight: 700; font-size: 1.1rem; border-radius: 8px; border: 1px solid var(--line); background: var(--surface-2); white-space: nowrap; overflow: hidden; }
.chip.past { opacity: 0.45; }
.chip.active { border-color: var(--accent); }
.chip.low { text-decoration: underline dotted var(--muted); }
.chip.edited { box-shadow: inset 0 -3px 0 var(--accent); }

.tracker-bottom { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.4fr); gap: 16px; }
@media (max-width: 800px) { .tracker-bottom { grid-template-columns: 1fr; } }
.diagrams, .controls { background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); padding: 16px; }
.tabs { display: flex; gap: 8px; margin-bottom: 12px; }
.piano .white { fill: #f4f4f4; stroke: #888; }
.piano .black { fill: #222; }
.piano [data-state="tone"] { fill: var(--accent); }
.piano [data-state="bass"] { fill: #4fa3ff; }
.guitar { width: 160px; }
.guitar line { stroke: var(--muted); }
.guitar .fret-dot { fill: var(--accent); }
.guitar .open { fill: none; stroke: var(--text); }
.guitar text { fill: var(--text); font-size: 10px; }

.controls { display: flex; flex-wrap: wrap; gap: 16px; align-items: center; }
.control { display: flex; align-items: center; gap: 8px; }
.control output { min-width: 2.5ch; text-align: center; font-weight: 700; }

.modal-backdrop { position: fixed; inset: 0; background: rgb(0 0 0 / 0.55); display: grid; place-items: center; padding: 16px; z-index: 10; }
.modal { width: min(560px, 100%); background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); padding: 20px; display: grid; gap: 14px; }
.formats { display: grid; gap: 8px; }
.formats label { display: flex; gap: 10px; padding: 10px; border: 1px solid var(--line); border-radius: 10px; }
.root-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 6px; }
.suggestions { display: flex; gap: 8px; flex-wrap: wrap; }
.suggestions .button { font-size: 1.3rem; font-weight: 800; }
```

- [ ] **Step 3: Implement pages and shell**

`client/src/pages/HomePage.tsx`:
```tsx
import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { formatKey } from '../theory/chord'
import type { SongSummary } from '../types'

export function HomePage() {
  const navigate = useNavigate()
  const [url, setUrl] = useState('')
  const [mode, setMode] = useState<'fast' | 'accurate'>('fast')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [songs, setSongs] = useState<SongSummary[] | null>(null)

  useEffect(() => {
    api.songs().then(setSongs).catch(() => setSongs([]))
  }, [])

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const r = await api.analyze(url.trim(), mode)
      navigate(r.song_id ? `/songs/${r.song_id}` : `/jobs/${r.job_id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setBusy(false)
    }
  }

  return (
    <main className="page">
      <h1>Paste a YouTube link</h1>
      <form className="analyze-form" onSubmit={submit}>
        <label htmlFor="url">YouTube link</label>
        <input id="url" type="text" inputMode="url" required placeholder="https://www.youtube.com/watch?v=…"
          value={url} onChange={(e) => setUrl(e.target.value)} />
        <fieldset className="mode">
          <legend className="muted">Mode</legend>
          <label><input type="radio" name="mode" checked={mode === 'fast'} onChange={() => setMode('fast')} /> Fast (~30 s)</label>
          <label><input type="radio" name="mode" checked={mode === 'accurate'} onChange={() => setMode('accurate')} /> Accurate (separates vocals &amp; drums, several minutes)</label>
        </fieldset>
        <div><button className="button primary" type="submit" disabled={busy}>{busy ? 'Starting…' : 'Analyze'}</button></div>
        {error && <p role="alert" className="error">{error}</p>}
      </form>

      <h2>Recent songs</h2>
      {songs === null ? <p className="muted">Loading…</p> : songs.length === 0 ? (
        <p className="muted">No songs yet — analyze your first link above.</p>
      ) : (
        <div className="library">
          {songs.map((s) => (
            <Link key={s.id} to={`/songs/${s.id}`} className="song-card" aria-label={s.title}>
              <img src={`https://i.ytimg.com/vi/${s.video_id}/mqdefault.jpg`} alt="" loading="lazy" />
              <div>
                <strong>{s.title}</strong>
                <div className="muted">{formatKey(s.key)} · {Math.round(s.tempo)} BPM</div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </main>
  )
}
```

Placeholders (replaced in Tasks 6 and 12):

`client/src/pages/AnalyzingPage.tsx`:
```tsx
export function AnalyzingPage(_props: { pollMs?: number }) {
  return <main className="page" />
}
```

`client/src/pages/TrackerPage.tsx`:
```tsx
export function TrackerPage() {
  return <main className="page" />
}
```

`client/src/App.tsx`:
```tsx
import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import { AnalyzingPage } from './pages/AnalyzingPage'
import { HomePage } from './pages/HomePage'
import { TrackerPage } from './pages/TrackerPage'

export function AppRoutes() {
  return (
    <>
      <header className="topbar">
        <Link to="/" className="brand">Chordarium</Link>
        <span className="soon" title="Publishing chord sheets arrives in Phase 2">Public library · coming soon</span>
      </header>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/jobs/:jobId" element={<AnalyzingPage />} />
        <Route path="/songs/:songId" element={<TrackerPage />} />
      </Routes>
    </>
  )
}

export function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  )
}
```

`client/src/main.tsx`:
```tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App } from './App'
import './styles.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

In `client/index.html` set `<title>Chordarium</title>` and remove the `vite.svg` favicon link. Delete `client/src/App.css`, `client/src/index.css`, `client/src/assets/react.svg`, `client/public/vite.svg`.

- [ ] **Step 4: Run tests and build**

Run: `npm test`
Expected: all PASS.
Run: `npm run build`
Expected: succeeds.

- [ ] **Step 5: Commit**

```bash
git add -A client/src client/index.html client/public
git commit -m "feat: add app shell, dark studio theme and home page"
```

---

### Task 6: Analyzing page

**Files:**
- Modify: `client/src/pages/AnalyzingPage.tsx` (replace placeholder)
- Test: `client/src/pages/AnalyzingPage.test.tsx`

**Interfaces:**
- Consumes: `api.job`, `api.cancelJob`, `Job`, `JobState`
- Produces: `AnalyzingPage({ pollMs = 1000 })` — polls until `done` (navigates to `/songs/<song_id>` with replace), `failed` or `cancelled` (stops, shows reason).

- [ ] **Step 1: Write the failing tests**

`client/src/pages/AnalyzingPage.test.tsx`:
```tsx
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Job } from '../types'
import { renderAt } from '../test/router'
import { AnalyzingPage } from './AnalyzingPage'

vi.mock('../api', () => ({ api: { job: vi.fn(), cancelJob: vi.fn() } }))
import { api } from '../api'
const mocked = vi.mocked(api)

const base: Job = {
  id: 'j1', video_id: 'abcdefghijk', mode: 'fast', state: 'queued', progress: 0,
  message: 'Waiting to start', error: null, song_id: null, created_at: '',
}

function renderPage() {
  return renderAt('/jobs/j1', (
    <>
      <Route path="/jobs/:jobId" element={<AnalyzingPage pollMs={5} />} />
      <Route path="/songs/:songId" element={<p>SONG PAGE</p>} />
    </>
  ))
}

beforeEach(() => vi.resetAllMocks())

describe('AnalyzingPage', () => {
  it('shows live steps and opens the song when done', async () => {
    mocked.job
      .mockResolvedValueOnce({ ...base, state: 'chords', progress: 60, message: 'Recognizing chords' })
      .mockResolvedValue({ ...base, state: 'done', progress: 100, song_id: 's1' })
    renderPage()
    expect(await screen.findByText('Recognizing chords', { selector: 'li' })).toHaveAttribute('data-status', 'active')
    expect(screen.queryByText(/separating stems/i)).not.toBeInTheDocument()
    expect(await screen.findByText('SONG PAGE')).toBeInTheDocument()
  })

  it('lists the separation step for accurate jobs', async () => {
    mocked.job.mockResolvedValue({ ...base, mode: 'accurate', state: 'separating', progress: 15 })
    renderPage()
    expect(await screen.findByText(/separating stems/i)).toHaveAttribute('data-status', 'active')
  })

  it('shows failure and stops polling', async () => {
    mocked.job.mockResolvedValue({ ...base, state: 'failed', error: 'This video is private.' })
    renderPage()
    expect(await screen.findByRole('alert')).toHaveTextContent('This video is private.')
    const calls = mocked.job.mock.calls.length
    await new Promise((r) => setTimeout(r, 40))
    expect(mocked.job.mock.calls.length).toBe(calls)
    expect(screen.getByRole('link', { name: /try another link/i })).toHaveAttribute('href', '/')
  })

  it('cancels the job', async () => {
    mocked.job.mockResolvedValue({ ...base, state: 'beats', progress: 45 })
    mocked.cancelJob.mockResolvedValue({ cancelled: true })
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByRole('button', { name: /cancel/i }))
    await waitFor(() => expect(mocked.cancelJob).toHaveBeenCalledWith('j1'))
  })

  it('shows a cancelled message', async () => {
    mocked.job.mockResolvedValue({ ...base, state: 'cancelled' })
    renderPage()
    expect(await screen.findByText(/analysis cancelled/i)).toBeInTheDocument()
  })
})
```

Run: `npm test -- src/pages/AnalyzingPage`
Expected: FAIL (placeholder renders nothing).

- [ ] **Step 2: Implement `client/src/pages/AnalyzingPage.tsx`**

```tsx
import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import type { Job, JobState } from '../types'

const STEPS: [JobState, string][] = [
  ['downloading', 'Downloading audio'],
  ['separating', 'Separating stems (vocals, drums, bass)'],
  ['beats', 'Detecting beats'],
  ['chords', 'Recognizing chords'],
  ['bass', 'Detecting bass notes and inversions'],
  ['key', 'Estimating key'],
]
const FINAL: JobState[] = ['done', 'failed', 'cancelled']

export function AnalyzingPage({ pollMs = 1000 }: { pollMs?: number }) {
  const { jobId = '' } = useParams()
  const navigate = useNavigate()
  const [job, setJob] = useState<Job | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let stopped = false
    let timer: ReturnType<typeof setTimeout> | undefined
    const tick = async () => {
      try {
        const j = await api.job(jobId)
        if (stopped) return
        setJob(j)
        if (j.state === 'done' && j.song_id) {
          navigate(`/songs/${j.song_id}`, { replace: true })
          return
        }
        if (FINAL.includes(j.state)) return
      } catch (e) {
        if (!stopped) setError(e instanceof Error ? e.message : String(e))
        return
      }
      timer = setTimeout(tick, pollMs)
    }
    tick()
    return () => {
      stopped = true
      clearTimeout(timer)
    }
  }, [jobId, pollMs, navigate])

  const steps = STEPS.filter(([s]) => s !== 'separating' || job?.mode === 'accurate')
  const current = job ? steps.findIndex(([s]) => s === job.state) : -1
  const status = (i: number) => (job?.state === 'done' || i < current ? 'done' : i === current ? 'active' : 'pending')
  const finished = job !== null && FINAL.includes(job.state)

  return (
    <main className="page">
      <h1>Analyzing…</h1>
      {job && (
        <img src={`https://i.ytimg.com/vi/${job.video_id}/mqdefault.jpg`} alt="" width={320}
          style={{ borderRadius: 12, maxWidth: '100%' }} />
      )}
      <progress value={job?.progress ?? 0} max={100} aria-label="Analysis progress" />
      <ol className="steps">
        {steps.map(([state, label], i) => (
          <li key={state} data-status={status(i)}>{label}</li>
        ))}
      </ol>
      {job?.message && !finished && <p className="muted">{job.message}</p>}
      {job && !finished && (
        <button className="button" type="button" onClick={() => api.cancelJob(job.id).catch(() => undefined)}>
          Cancel
        </button>
      )}
      {job?.state === 'failed' && <p role="alert" className="error">{job.error ?? 'Analysis failed.'}</p>}
      {job?.state === 'cancelled' && <p>Analysis cancelled.</p>}
      {error && <p role="alert" className="error">{error}</p>}
      {(finished || error) && job?.state !== 'done' && <p><Link to="/" className="button">Try another link</Link></p>}
    </main>
  )
}
```

Note: the step `li` text for the chords state is `Recognizing chords`, matching the test's `findByText('Recognizing chords', { selector: 'li' })`; the job message paragraph uses the same words but is a `p`.

- [ ] **Step 3: Run tests to verify they pass**

Run: `npm test -- src/pages/AnalyzingPage`
Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add client/src/pages/AnalyzingPage.tsx client/src/pages/AnalyzingPage.test.tsx
git commit -m "feat: add analysis progress page with polling and cancel"
```

---

### Task 7: YouTube player hook

**Files:**
- Create: `client/src/hooks/useYouTubePlayer.ts`
- Test: `client/src/hooks/useYouTubePlayer.test.ts`

**Interfaces:**
- Produces: `loadYouTubeApi(): Promise<YTNamespace>`, `interface PlayerControls { ready: boolean; time: number; playing: boolean; seek(t: number): void; setRate(r: number): void }`, `useYouTubePlayer(elementId: string, videoId: string): PlayerControls`

- [ ] **Step 1: Write the failing test**

`client/src/hooks/useYouTubePlayer.test.ts`:
```ts
import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useYouTubePlayer } from './useYouTubePlayer'

class FakePlayer {
  static last: FakePlayer
  time = 0
  seekTo = vi.fn()
  setPlaybackRate = vi.fn()
  destroy = vi.fn()
  constructor(public elementId: string, public opts: any) {
    FakePlayer.last = this
  }
  getCurrentTime() {
    return this.time
  }
}

beforeEach(() => {
  ;(window as any).YT = { Player: FakePlayer, PlayerState: { PLAYING: 1, PAUSED: 2 } }
})
afterEach(() => {
  delete (window as any).YT
})

describe('useYouTubePlayer', () => {
  it('creates the player for the element and video', async () => {
    renderHook(() => useYouTubePlayer('yt', 'abcdefghijk'))
    await waitFor(() => expect(FakePlayer.last?.opts.videoId).toBe('abcdefghijk'))
    expect(FakePlayer.last.elementId).toBe('yt')
  })

  it('reports ready, playing state and current time', async () => {
    const { result } = renderHook(() => useYouTubePlayer('yt', 'abcdefghijk'))
    await waitFor(() => expect(FakePlayer.last).toBeDefined())
    act(() => FakePlayer.last.opts.events.onReady())
    expect(result.current.ready).toBe(true)
    act(() => FakePlayer.last.opts.events.onStateChange({ data: 1 }))
    expect(result.current.playing).toBe(true)
    FakePlayer.last.time = 5.25
    await waitFor(() => expect(result.current.time).toBe(5.25))
  })

  it('seeks, sets rate and destroys on unmount', async () => {
    const { result, unmount } = renderHook(() => useYouTubePlayer('yt', 'abcdefghijk'))
    await waitFor(() => expect(FakePlayer.last).toBeDefined())
    const player = FakePlayer.last
    act(() => result.current.seek(12))
    expect(player.seekTo).toHaveBeenCalledWith(12, true)
    expect(result.current.time).toBe(12)
    act(() => result.current.setRate(0.75))
    expect(player.setPlaybackRate).toHaveBeenCalledWith(0.75)
    unmount()
    expect(player.destroy).toHaveBeenCalled()
  })
})
```

Run: `npm test -- src/hooks/useYouTubePlayer`
Expected: FAIL — cannot resolve `./useYouTubePlayer`.

- [ ] **Step 2: Implement `client/src/hooks/useYouTubePlayer.ts`**

```ts
import { useCallback, useEffect, useRef, useState } from 'react'

interface YTPlayer {
  getCurrentTime?: () => number
  seekTo(seconds: number, allowSeekAhead: boolean): void
  setPlaybackRate(rate: number): void
  destroy(): void
}

interface YTNamespace {
  Player: new (elementId: string, opts: unknown) => YTPlayer
  PlayerState: { PLAYING: number }
}

declare global {
  interface Window {
    YT?: YTNamespace
    onYouTubeIframeAPIReady?: () => void
  }
}

let apiPromise: Promise<YTNamespace> | null = null

export function loadYouTubeApi(): Promise<YTNamespace> {
  if (window.YT?.Player) return Promise.resolve(window.YT)
  if (!apiPromise) {
    apiPromise = new Promise((resolve) => {
      const previous = window.onYouTubeIframeAPIReady
      window.onYouTubeIframeAPIReady = () => {
        previous?.()
        resolve(window.YT as YTNamespace)
      }
      const script = document.createElement('script')
      script.src = 'https://www.youtube.com/iframe_api'
      document.head.appendChild(script)
    })
  }
  return apiPromise
}

export interface PlayerControls {
  ready: boolean
  time: number
  playing: boolean
  seek(t: number): void
  setRate(r: number): void
}

export function useYouTubePlayer(elementId: string, videoId: string): PlayerControls {
  const playerRef = useRef<YTPlayer | null>(null)
  const [ready, setReady] = useState(false)
  const [time, setTime] = useState(0)
  const [playing, setPlaying] = useState(false)

  useEffect(() => {
    let cancelled = false
    let frame = 0
    let last = -1
    loadYouTubeApi().then((YT) => {
      if (cancelled) return
      playerRef.current = new YT.Player(elementId, {
        videoId,
        playerVars: { rel: 0, playsinline: 1, modestbranding: 1 },
        events: {
          onReady: () => !cancelled && setReady(true),
          onStateChange: (e: { data: number }) => !cancelled && setPlaying(e.data === YT.PlayerState.PLAYING),
        },
      })
      const loop = () => {
        const t = playerRef.current?.getCurrentTime?.() ?? 0
        if (Math.abs(t - last) > 0.02) {
          last = t
          setTime(t)
        }
        frame = requestAnimationFrame(loop)
      }
      frame = requestAnimationFrame(loop)
    })
    return () => {
      cancelled = true
      cancelAnimationFrame(frame)
      playerRef.current?.destroy()
      playerRef.current = null
      setReady(false)
    }
  }, [elementId, videoId])

  const seek = useCallback((t: number) => {
    playerRef.current?.seekTo(t, true)
    setTime(t)
  }, [])
  const setRate = useCallback((r: number) => playerRef.current?.setPlaybackRate(r), [])

  return { ready, time, playing, seek, setRate }
}
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `npm test -- src/hooks/useYouTubePlayer`
Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add client/src/hooks/useYouTubePlayer.ts client/src/hooks/useYouTubePlayer.test.ts
git commit -m "feat: add youtube iframe player hook with playhead polling"
```

---

### Task 8: Chord hero and chord lane

**Files:**
- Create: `client/src/components/ChordHero.tsx`, `client/src/components/ChordLane.tsx`
- Test: `client/src/components/ChordHero.test.tsx`, `client/src/components/ChordLane.test.tsx`

**Interfaces:**
- Consumes: `PX_PER_SECOND`, `laneOffset`, `Segment`
- Produces: `ChordHero({ current: string | null; next: string | null; beatsToNext: number })`; `ChordLane({ segments; symbols: string[]; beats; downbeats; duration; time; editMode; onSeek(t); onEdit(i); width? })`

- [ ] **Step 1: Write the failing tests**

`client/src/components/ChordHero.test.tsx`:
```tsx
import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import { ChordHero } from './ChordHero'

it('shows current, next and a beat countdown capped at 4', () => {
  const { rerender } = render(<ChordHero current="Cm7" next="F7" beatsToNext={2} />)
  expect(screen.getByTestId('current-chord')).toHaveTextContent('Cm7')
  expect(screen.getByTestId('next-chord')).toHaveTextContent('F7')
  expect(screen.getByLabelText('2 beats to next chord')).toBeInTheDocument()
  rerender(<ChordHero current={null} next={null} beatsToNext={9} />)
  expect(screen.getByTestId('current-chord')).toHaveTextContent('—')
  expect(screen.getByLabelText('4 beats to next chord')).toBeInTheDocument()
})
```

`client/src/components/ChordLane.test.tsx`:
```tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { TIMELINE } from '../test/fixtures'
import { ChordLane } from './ChordLane'

const symbols = ['Cm7', 'F7', 'Bbmaj7', 'Ebmaj7', 'D7/F#']

function renderLane(props: Partial<Parameters<typeof ChordLane>[0]> = {}) {
  const onSeek = vi.fn()
  const onEdit = vi.fn()
  render(
    <ChordLane segments={TIMELINE.segments} symbols={symbols} beats={TIMELINE.beats} downbeats={TIMELINE.downbeats}
      duration={TIMELINE.duration} time={2.5} width={800} editMode={false} onSeek={onSeek} onEdit={onEdit} {...props} />,
  )
  return { onSeek, onEdit }
}

describe('ChordLane', () => {
  it('positions the track so the playhead sits at the centre', () => {
    renderLane()
    expect(screen.getByTestId('lane-track')).toHaveStyle({ transform: 'translateX(100px)' })
  })

  it('marks past, active and low-confidence chords', () => {
    renderLane()
    expect(screen.getByRole('button', { name: 'Cm7' })).toHaveClass('past')
    expect(screen.getByRole('button', { name: 'F7' })).toHaveClass('active')
    expect(screen.getByRole('button', { name: 'D7/F#' })).toHaveClass('low')
  })

  it('seeks on click, or opens the editor in edit mode', async () => {
    const user = userEvent.setup()
    const { onSeek } = renderLane()
    await user.click(screen.getByRole('button', { name: 'Bbmaj7' }))
    expect(onSeek).toHaveBeenCalledWith(4)
  })

  it('edits in edit mode', async () => {
    const user = userEvent.setup()
    const { onEdit, onSeek } = renderLane({ editMode: true })
    await user.click(screen.getByRole('button', { name: 'Bbmaj7' }))
    expect(onEdit).toHaveBeenCalledWith(2)
    expect(onSeek).not.toHaveBeenCalled()
  })
})
```

Run: `npm test -- src/components/ChordHero src/components/ChordLane`
Expected: FAIL — cannot resolve components.

- [ ] **Step 2: Implement the components**

`client/src/components/ChordHero.tsx`:
```tsx
interface Props {
  current: string | null
  next: string | null
  beatsToNext: number
}

export function ChordHero({ current, next, beatsToNext }: Props) {
  const dots = Math.min(Math.max(beatsToNext, 0), 4)
  return (
    <section className="hero" aria-label="Current chord">
      <div className="hero-current" data-testid="current-chord">{current ?? '—'}</div>
      <div className="hero-next">
        <span className="hero-next-label">Next</span>
        <span data-testid="next-chord">{next ?? '—'}</span>
        <span className="beat-dots" aria-label={`${dots} beats to next chord`}>
          {Array.from({ length: 4 }, (_, i) => (
            <span key={i} className={i < dots ? 'dot on' : 'dot'} />
          ))}
        </span>
      </div>
    </section>
  )
}
```

`client/src/components/ChordLane.tsx`:
```tsx
import { useEffect, useRef, useState } from 'react'
import { PX_PER_SECOND, laneOffset } from '../sync'
import type { Segment } from '../types'

interface Props {
  segments: Segment[]
  symbols: string[]
  beats: number[]
  downbeats: number[]
  duration: number
  time: number
  editMode: boolean
  onSeek(t: number): void
  onEdit(index: number): void
  width?: number
}

export function ChordLane({ segments, symbols, beats, downbeats, duration, time, editMode, onSeek, onEdit, width }: Props) {
  const ref = useRef<HTMLDivElement>(null)
  const [measured, setMeasured] = useState(800)

  useEffect(() => {
    if (width !== undefined) return
    const el = ref.current
    if (!el) return
    const update = () => setMeasured(el.clientWidth || 800)
    update()
    const observer = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(update) : null
    observer?.observe(el)
    return () => observer?.disconnect()
  }, [width])

  const offset = laneOffset(time, width ?? measured)
  return (
    <div className="lane" ref={ref} aria-label="Chord timeline">
      <div className="lane-playhead" />
      <div className="lane-track" data-testid="lane-track"
        style={{ transform: `translateX(${offset}px)`, width: duration * PX_PER_SECOND }}>
        {beats.map((b) => <span key={`b${b}`} className="beat-tick" style={{ left: b * PX_PER_SECOND }} />)}
        {downbeats.map((d) => <span key={`d${d}`} className="bar-line" style={{ left: d * PX_PER_SECOND }} />)}
        {segments.map((s, i) => {
          if (s.label === 'N') return null
          const classes = ['chip']
          if (s.end <= time) classes.push('past')
          if (s.start <= time && time < s.end) classes.push('active')
          if (s.confidence < 0.5) classes.push('low')
          if (s.edited) classes.push('edited')
          return (
            <button key={i} type="button" className={classes.join(' ')}
              style={{ left: s.start * PX_PER_SECOND, width: Math.max((s.end - s.start) * PX_PER_SECOND - 4, 28) }}
              title={editMode ? 'Edit this chord' : 'Jump here'}
              onClick={() => (editMode ? onEdit(i) : onSeek(s.start))}>
              {symbols[i]}
            </button>
          )
        })}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `npm test -- src/components/ChordHero src/components/ChordLane`
Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add client/src/components/ChordHero.tsx client/src/components/ChordHero.test.tsx client/src/components/ChordLane.tsx client/src/components/ChordLane.test.tsx
git commit -m "feat: add chord hero display and scrolling chord lane"
```

---

### Task 9: Piano and guitar diagrams

**Files:**
- Create: `client/src/theory/voicings.ts`, `client/src/components/PianoDiagram.tsx`, `client/src/components/GuitarDiagram.tsx`, `client/src/components/DiagramPanel.tsx`
- Test: `client/src/theory/voicings.test.ts`, `client/src/components/DiagramPanel.test.tsx`

**Interfaces:**
- Consumes: `Chord`, `QUALITY_INTERVALS`, `SHARPS`
- Produces (`voicings.ts`): `interface GuitarPosition { frets: number[]; fingers?: number[]; baseFret: number; barres?: number[] }`, `interface ChordsDb { chords: Record<string, { key: string; suffix: string; positions: GuitarPosition[] }[]> }`, `pianoKeys(c: Chord): { tones: number[]; bass: number }` (offsets 0–23 over two octaves), `guitarShape(db: ChordsDb, c: Chord): GuitarPosition | null`
- Produces: `PianoDiagram({ chord, label })`, `GuitarDiagram({ position, label })`, `DiagramPanel({ chord: Chord | null; label: string; db?: ChordsDb })`

chords-db facts (verified from the 0.5.1 package): `guitar.json` has `chords` keyed `C, Csharp, D, Eb, E, F, Fsharp, G, Ab, A, Bb, B`; entries `{key, suffix, positions}`; suffixes used here: `major, minor, dim, dim7, aug, 6, m6, 7, maj7, m7, m7b5, mmaj7, sus2, sus4`, slash suffixes `/E, /F, /F#, /G, /G#, /A, /Bb, /B, /C, /C#, /D, /D#` (major) and `m/B, m/C, …` (minor); `frets` use `-1` = muted, `0` = open, relative to `baseFret`.

- [ ] **Step 1: Write the failing tests**

`client/src/theory/voicings.test.ts`:
```ts
import { describe, expect, it } from 'vitest'
import { parse } from './chord'
import { guitarShape, pianoKeys, type ChordsDb } from './voicings'

const db: ChordsDb = {
  chords: {
    C: [
      { key: 'C', suffix: 'major', positions: [{ frets: [-1, 3, 2, 0, 1, 0], baseFret: 1 }] },
      { key: 'C', suffix: '/E', positions: [{ frets: [0, 3, 2, 0, 1, 0], baseFret: 1 }] },
      { key: 'C', suffix: 'm7b5', positions: [{ frets: [-1, 3, 4, 3, 4, -1], baseFret: 1 }] },
    ],
    Fsharp: [{ key: 'F#', suffix: 'minor', positions: [{ frets: [1, 3, 3, 1, 1, 1], baseFret: 2 }] }],
  },
}

describe('pianoKeys', () => {
  it('puts chord tones in the upper octave and the bass in the lower one', () => {
    expect(pianoKeys(parse('C:maj')!)).toEqual({ tones: [12, 16, 19], bass: 0 })
    expect(pianoKeys(parse('G:maj/3')!)).toEqual({ tones: [19, 23, 14], bass: 11 })
  })
})

describe('guitarShape', () => {
  it('maps qualities and sharps to chords-db names', () => {
    expect(guitarShape(db, parse('C:maj')!)?.frets).toEqual([-1, 3, 2, 0, 1, 0])
    expect(guitarShape(db, parse('C:hdim7')!)?.frets).toEqual([-1, 3, 4, 3, 4, -1])
    expect(guitarShape(db, parse('F#:min')!)?.baseFret).toBe(2)
  })
  it('prefers a real slash shape and falls back to the plain chord', () => {
    expect(guitarShape(db, parse('C:maj/3')!)?.frets).toEqual([0, 3, 2, 0, 1, 0])
    expect(guitarShape(db, parse('C:maj/5')!)?.frets).toEqual([-1, 3, 2, 0, 1, 0])
  })
  it('returns null when the chord is missing', () => {
    expect(guitarShape(db, parse('D:sus2')!)).toBeNull()
  })
})
```

`client/src/components/DiagramPanel.test.tsx`:
```tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { parse } from '../theory/chord'
import type { ChordsDb } from '../theory/voicings'
import { DiagramPanel } from './DiagramPanel'

const db: ChordsDb = {
  chords: { C: [{ key: 'C', suffix: 'major', positions: [{ frets: [-1, 3, 2, 0, 1, 0], baseFret: 1 }] }] },
}

describe('DiagramPanel', () => {
  it('shows the piano with highlighted tones and bass', () => {
    const { container } = render(<DiagramPanel chord={parse('C:maj/3')} label="C/E" db={db} />)
    expect(screen.getByRole('img', { name: 'Piano keys for C/E' })).toBeInTheDocument()
    expect(container.querySelectorAll('[data-state="tone"]')).toHaveLength(3)
    expect(container.querySelector('[data-state="bass"]')).toHaveAttribute('data-offset', '4')
  })

  it('switches to guitar and draws muted, open and fretted strings', async () => {
    const user = userEvent.setup()
    const { container } = render(<DiagramPanel chord={parse('C:maj')} label="C" db={db} />)
    await user.click(screen.getByRole('tab', { name: 'Guitar' }))
    expect(screen.getByRole('img', { name: 'Guitar shape for C' })).toBeInTheDocument()
    expect(screen.getAllByText('×')).toHaveLength(1)
    expect(container.querySelectorAll('circle.open')).toHaveLength(2)
    expect(container.querySelectorAll('circle.fret-dot')).toHaveLength(3)
  })

  it('explains when no guitar shape exists', async () => {
    const user = userEvent.setup()
    render(<DiagramPanel chord={parse('D:sus2')} label="Dsus2" db={db} />)
    await user.click(screen.getByRole('tab', { name: 'Guitar' }))
    expect(screen.getByText(/no guitar shape for dsus2/i)).toBeInTheDocument()
  })

  it('handles no chord', () => {
    render(<DiagramPanel chord={null} label="N.C." db={db} />)
    expect(screen.getByText(/no chord/i)).toBeInTheDocument()
  })
})
```

Run: `npm test -- src/theory/voicings src/components/DiagramPanel`
Expected: FAIL — cannot resolve modules.

- [ ] **Step 2: Implement `client/src/theory/voicings.ts`**

```ts
import { QUALITY_INTERVALS, type Chord } from './chord'

export interface GuitarPosition {
  frets: number[]
  fingers?: number[]
  baseFret: number
  barres?: number[]
}

export interface ChordsDb {
  chords: Record<string, { key: string; suffix: string; positions: GuitarPosition[] }[]>
}

const DB_KEYS = ['C', 'Csharp', 'D', 'Eb', 'E', 'F', 'Fsharp', 'G', 'Ab', 'A', 'Bb', 'B']
const DB_BASS_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'Bb', 'B']
const SUFFIX: Record<string, string> = {
  maj: 'major', min: 'minor', dim: 'dim', aug: 'aug', min6: 'm6', maj6: '6', min7: 'm7', minmaj7: 'mmaj7',
  maj7: 'maj7', '7': '7', dim7: 'dim7', hdim7: 'm7b5', sus2: 'sus2', sus4: 'sus4',
}

export function pianoKeys(c: Chord): { tones: number[]; bass: number } {
  const tones = QUALITY_INTERVALS[c.quality].map((i) => {
    let t = 12 + c.root + i
    while (t > 23) t -= 12
    return t
  })
  return { tones, bass: c.bass ?? c.root }
}

export function guitarShape(db: ChordsDb, c: Chord): GuitarPosition | null {
  const list = db.chords[DB_KEYS[c.root]]
  if (!list) return null
  const find = (suffix: string) => list.find((e) => e.suffix === suffix)?.positions[0] ?? null
  if (c.bass !== null && (c.quality === 'maj' || c.quality === 'min')) {
    const slash = find(`${c.quality === 'min' ? 'm' : ''}/${DB_BASS_NAMES[c.bass]}`)
    if (slash) return slash
  }
  return find(SUFFIX[c.quality])
}
```

- [ ] **Step 3: Implement the diagram components**

`client/src/components/PianoDiagram.tsx`:
```tsx
import type { Chord } from '../theory/chord'
import { pianoKeys } from '../theory/voicings'

const WHITE = [0, 2, 4, 5, 7, 9, 11]
const BLACK_SLOT: Record<number, number> = { 1: 1, 3: 2, 6: 4, 8: 5, 10: 6 }
const WW = 14
const WH = 60
const BW = 9
const BH = 38

export function PianoDiagram({ chord, label }: { chord: Chord; label: string }) {
  const { tones, bass } = pianoKeys(chord)
  const toneSet = new Set(tones)
  const state = (offset: number) => (offset === bass ? 'bass' : toneSet.has(offset) ? 'tone' : 'off')
  const whites = []
  const blacks = []
  for (let octave = 0; octave < 2; octave++) {
    for (const [k, pc] of WHITE.entries()) {
      const offset = octave * 12 + pc
      whites.push(<rect key={`w${offset}`} className="white" x={(octave * 7 + k) * WW} y={0} width={WW} height={WH}
        data-offset={offset} data-state={state(offset)} />)
    }
    for (const pc of [1, 3, 6, 8, 10]) {
      const offset = octave * 12 + pc
      blacks.push(<rect key={`b${offset}`} className="black" x={(octave * 7 + BLACK_SLOT[pc]) * WW - BW / 2} y={0}
        width={BW} height={BH} data-offset={offset} data-state={state(offset)} />)
    }
  }
  return (
    <svg className="piano" viewBox={`0 0 ${14 * WW} ${WH}`} role="img" aria-label={`Piano keys for ${label}`}>
      {whites}
      {blacks}
    </svg>
  )
}
```

`client/src/components/GuitarDiagram.tsx`:
```tsx
import type { GuitarPosition } from '../theory/voicings'

const LEFT = 20
const TOP = 30
const STRING_GAP = 16
const FRET_GAP = 22

export function GuitarDiagram({ position, label }: { position: GuitarPosition; label: string }) {
  return (
    <svg className="guitar" viewBox="0 0 120 150" role="img" aria-label={`Guitar shape for ${label}`}>
      {position.baseFret > 1 && <text x={2} y={TOP + FRET_GAP / 2 + 4}>{position.baseFret}fr</text>}
      {Array.from({ length: 6 }, (_, i) => (
        <line key={`s${i}`} x1={LEFT + i * STRING_GAP} y1={TOP} x2={LEFT + i * STRING_GAP} y2={TOP + 4 * FRET_GAP} />
      ))}
      {Array.from({ length: 5 }, (_, i) => (
        <line key={`f${i}`} x1={LEFT} y1={TOP + i * FRET_GAP} x2={LEFT + 5 * STRING_GAP} y2={TOP + i * FRET_GAP}
          strokeWidth={i === 0 && position.baseFret === 1 ? 3 : 1} />
      ))}
      {position.frets.map((fret, i) => {
        const x = LEFT + i * STRING_GAP
        if (fret === -1) return <text key={i} x={x} y={TOP - 8} textAnchor="middle">×</text>
        if (fret === 0) return <circle key={i} className="open" cx={x} cy={TOP - 12} r={4} />
        return <circle key={i} className="fret-dot" cx={x} cy={TOP + (fret - 0.5) * FRET_GAP} r={6} />
      })}
    </svg>
  )
}
```

`client/src/components/DiagramPanel.tsx`:
```tsx
import { useState } from 'react'
import guitarDb from '@tombatossals/chords-db/lib/guitar.json'
import type { Chord } from '../theory/chord'
import { guitarShape, type ChordsDb } from '../theory/voicings'
import { GuitarDiagram } from './GuitarDiagram'
import { PianoDiagram } from './PianoDiagram'

interface Props {
  chord: Chord | null
  label: string
  db?: ChordsDb
}

export function DiagramPanel({ chord, label, db = guitarDb as unknown as ChordsDb }: Props) {
  const [tab, setTab] = useState<'piano' | 'guitar'>('piano')
  if (!chord) {
    return <section className="diagrams" aria-label="Chord diagram"><p className="muted">No chord right now.</p></section>
  }
  const shape = tab === 'guitar' ? guitarShape(db, chord) : null
  return (
    <section className="diagrams" aria-label="Chord diagram">
      <div className="tabs" role="tablist">
        <button type="button" role="tab" className="button" aria-selected={tab === 'piano'} onClick={() => setTab('piano')}>Piano</button>
        <button type="button" role="tab" className="button" aria-selected={tab === 'guitar'} onClick={() => setTab('guitar')}>Guitar</button>
      </div>
      {tab === 'piano' ? (
        <PianoDiagram chord={chord} label={label} />
      ) : shape ? (
        <GuitarDiagram position={shape} label={label} />
      ) : (
        <p className="muted">No guitar shape for {label} — see the piano view.</p>
      )}
    </section>
  )
}
```

- [ ] **Step 4: Run tests and build**

Run: `npm test -- src/theory/voicings src/components/DiagramPanel`
Expected: all PASS.
Run: `npm run build`
Expected: succeeds (if TypeScript cannot find types for the JSON import, `resolveJsonModule` from Task 1 is missing — add it).

- [ ] **Step 5: Commit**

```bash
git add client/src/theory/voicings.ts client/src/theory/voicings.test.ts client/src/components/PianoDiagram.tsx client/src/components/GuitarDiagram.tsx client/src/components/DiagramPanel.tsx client/src/components/DiagramPanel.test.tsx
git commit -m "feat: add piano and guitar chord diagrams"
```

---

### Task 10: Controls and export modal

**Files:**
- Create: `client/src/components/Controls.tsx`, `client/src/components/ExportModal.tsx`
- Test: `client/src/components/Controls.test.tsx`, `client/src/components/ExportModal.test.tsx`

**Interfaces:**
- Consumes: `ViewSettings`, `RATES`, `exportUrl`, `ExportFormat`
- Produces: `interface LoopRange { a: number | null; b: number | null }`; `Controls({ settings, onChange, loop, onSetA, onSetB, onClearLoop, editMode, onToggleEdit, onReset, onExport })`; `ExportModal({ songId, settings, onClose })`

- [ ] **Step 1: Write the failing tests**

`client/src/components/Controls.test.tsx`:
```tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { DEFAULT_VIEW } from '../hooks/useViewSettings'
import { Controls } from './Controls'

function setup(overrides = {}) {
  const props = {
    settings: DEFAULT_VIEW, onChange: vi.fn(), loop: { a: null, b: null }, onSetA: vi.fn(), onSetB: vi.fn(),
    onClearLoop: vi.fn(), editMode: false, onToggleEdit: vi.fn(), onReset: vi.fn(), onExport: vi.fn(), ...overrides,
  }
  render(<Controls {...props} />)
  return props
}

describe('Controls', () => {
  it('steps transpose and capo', async () => {
    const user = userEvent.setup()
    const p = setup({ settings: { ...DEFAULT_VIEW, transpose: 2, capo: 1 } })
    expect(screen.getByLabelText('Transpose value')).toHaveTextContent('+2')
    await user.click(screen.getByRole('button', { name: 'Transpose up' }))
    expect(p.onChange).toHaveBeenCalledWith({ transpose: 3 })
    await user.click(screen.getByRole('button', { name: 'Capo down' }))
    expect(p.onChange).toHaveBeenCalledWith({ capo: 0 })
  })

  it('changes speed and simplify', async () => {
    const user = userEvent.setup()
    const p = setup()
    await user.selectOptions(screen.getByLabelText('Speed'), '0.75')
    expect(p.onChange).toHaveBeenCalledWith({ rate: 0.75 })
    await user.click(screen.getByLabelText('Simplify chords'))
    expect(p.onChange).toHaveBeenCalledWith({ simplify: true })
  })

  it('drives loop, edit, reset and export actions', async () => {
    const user = userEvent.setup()
    const p = setup({ loop: { a: 12.5, b: null }, editMode: true })
    expect(screen.getByRole('button', { name: /set a/i })).toHaveTextContent('0:12')
    await user.click(screen.getByRole('button', { name: /set b/i }))
    expect(p.onSetB).toHaveBeenCalled()
    expect(screen.getByRole('button', { name: /edit chords/i })).toHaveAttribute('aria-pressed', 'true')
    await user.click(screen.getByRole('button', { name: /reset edits/i }))
    expect(p.onReset).toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: /export/i }))
    expect(p.onExport).toHaveBeenCalled()
  })
})
```

`client/src/components/ExportModal.test.tsx`:
```tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { DEFAULT_VIEW } from '../hooks/useViewSettings'
import { ExportModal } from './ExportModal'

describe('ExportModal', () => {
  it('defaults to a PDF with the current view settings', () => {
    render(<ExportModal songId="s1" settings={{ ...DEFAULT_VIEW, transpose: 2, capo: 1 }} onClose={vi.fn()} />)
    expect(screen.getByRole('link', { name: /download/i }))
      .toHaveAttribute('href', '/api/songs/s1/export?fmt=pdf&transpose=2&capo=1&simplify=0&bars_per_row=4')
  })

  it('changes format, drops view settings, simplifies and widens rows', async () => {
    const user = userEvent.setup()
    render(<ExportModal songId="s1" settings={{ ...DEFAULT_VIEW, transpose: 2, capo: 1 }} onClose={vi.fn()} />)
    await user.click(screen.getByLabelText(/chordpro/i))
    await user.click(screen.getByLabelText(/apply current transpose/i))
    await user.click(screen.getByLabelText(/simplified chords/i))
    await user.selectOptions(screen.getByLabelText(/bars per row/i), '8')
    expect(screen.getByRole('link', { name: /download/i }))
      .toHaveAttribute('href', '/api/songs/s1/export?fmt=chordpro&transpose=0&capo=0&simplify=1&bars_per_row=8')
  })

  it('closes', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    render(<ExportModal songId="s1" settings={DEFAULT_VIEW} onClose={onClose} />)
    await user.click(screen.getByRole('button', { name: /close/i }))
    expect(onClose).toHaveBeenCalled()
  })
})
```

Run: `npm test -- src/components/Controls src/components/ExportModal`
Expected: FAIL — cannot resolve components.

- [ ] **Step 2: Implement `client/src/components/Controls.tsx`**

```tsx
import { RATES, type ViewSettings } from '../hooks/useViewSettings'

export interface LoopRange {
  a: number | null
  b: number | null
}

interface Props {
  settings: ViewSettings
  onChange(patch: Partial<ViewSettings>): void
  loop: LoopRange
  onSetA(): void
  onSetB(): void
  onClearLoop(): void
  editMode: boolean
  onToggleEdit(): void
  onReset(): void
  onExport(): void
}

const signed = (n: number) => (n > 0 ? `+${n}` : String(n))
const clock = (t: number) => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, '0')}`

export function Controls(p: Props) {
  const { settings, onChange } = p
  return (
    <section className="controls" aria-label="Playback and chord controls">
      <div className="control">
        <span>Transpose</span>
        <button type="button" className="button" aria-label="Transpose down" onClick={() => onChange({ transpose: settings.transpose - 1 })}>−</button>
        <output aria-label="Transpose value">{signed(settings.transpose)}</output>
        <button type="button" className="button" aria-label="Transpose up" onClick={() => onChange({ transpose: settings.transpose + 1 })}>+</button>
      </div>
      <div className="control">
        <span>Capo</span>
        <button type="button" className="button" aria-label="Capo down" onClick={() => onChange({ capo: settings.capo - 1 })}>−</button>
        <output aria-label="Capo value">{settings.capo}</output>
        <button type="button" className="button" aria-label="Capo up" onClick={() => onChange({ capo: settings.capo + 1 })}>+</button>
      </div>
      <label className="control">
        Speed
        <select aria-label="Speed" value={settings.rate} onChange={(e) => onChange({ rate: Number(e.target.value) })}>
          {RATES.map((r) => <option key={r} value={r}>{r}×</option>)}
        </select>
      </label>
      <label className="control">
        <input type="checkbox" aria-label="Simplify chords" checked={settings.simplify}
          onChange={(e) => onChange({ simplify: e.target.checked })} />
        Simplify
      </label>
      <div className="control">
        <button type="button" className="button" onClick={p.onSetA}>Set A{p.loop.a !== null ? ` ${clock(p.loop.a)}` : ''}</button>
        <button type="button" className="button" onClick={p.onSetB}>Set B{p.loop.b !== null ? ` ${clock(p.loop.b)}` : ''}</button>
        {(p.loop.a !== null || p.loop.b !== null) && (
          <button type="button" className="button" onClick={p.onClearLoop}>Clear loop</button>
        )}
      </div>
      <div className="control">
        <button type="button" className="button" aria-pressed={p.editMode} onClick={p.onToggleEdit}>Edit chords</button>
        <button type="button" className="button" onClick={p.onReset}>Reset edits</button>
        <button type="button" className="button primary" onClick={p.onExport}>Export</button>
      </div>
    </section>
  )
}
```

- [ ] **Step 3: Implement `client/src/components/ExportModal.tsx`**

```tsx
import { useState } from 'react'
import { exportUrl } from '../api'
import type { ViewSettings } from '../hooks/useViewSettings'
import type { ExportFormat } from '../types'

const FORMATS: { fmt: ExportFormat; label: string; hint: string }[] = [
  { fmt: 'pdf', label: 'PDF chord sheet', hint: 'Printable bar grid with a chord legend' },
  { fmt: 'chordpro', label: 'ChordPro (.cho)', hint: 'Open in OnSong, SongbookPro, ChordPro tools' },
  { fmt: 'txt', label: 'Plain text', hint: 'Bar grid as text' },
  { fmt: 'midi', label: 'MIDI', hint: 'Block chords at the song tempo, for your DAW or keyboard' },
  { fmt: 'json', label: 'JSON', hint: 'The raw chord timeline' },
]

interface Props {
  songId: string
  settings: ViewSettings
  onClose(): void
}

export function ExportModal({ songId, settings, onClose }: Props) {
  const [fmt, setFmt] = useState<ExportFormat>('pdf')
  const [includeView, setIncludeView] = useState(true)
  const [simplify, setSimplify] = useState(settings.simplify)
  const [barsPerRow, setBarsPerRow] = useState<4 | 8>(4)
  const href = exportUrl(songId, {
    fmt,
    transpose: includeView ? settings.transpose : 0,
    capo: includeView ? settings.capo : 0,
    simplify,
    barsPerRow,
  })
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" role="dialog" aria-modal="true" aria-label="Export chord sheet" onClick={(e) => e.stopPropagation()}>
        <h2>Export</h2>
        <div className="formats" role="radiogroup" aria-label="Format">
          {FORMATS.map((f) => (
            <label key={f.fmt}>
              <input type="radio" name="fmt" checked={fmt === f.fmt} onChange={() => setFmt(f.fmt)} />
              <span><strong>{f.label}</strong><br /><span className="muted">{f.hint}</span></span>
            </label>
          ))}
        </div>
        <label><input type="checkbox" checked={includeView} onChange={(e) => setIncludeView(e.target.checked)} /> Apply current transpose &amp; capo</label>
        <label><input type="checkbox" checked={simplify} onChange={(e) => setSimplify(e.target.checked)} /> Simplified chords</label>
        <label>
          Bars per row{' '}
          <select value={barsPerRow} onChange={(e) => setBarsPerRow(Number(e.target.value) as 4 | 8)}>
            <option value={4}>4</option>
            <option value={8}>8</option>
          </select>
        </label>
        <div className="control">
          <a className="button primary" href={href} download>Download</a>
          <button type="button" className="button" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- src/components/Controls src/components/ExportModal`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add client/src/components/Controls.tsx client/src/components/Controls.test.tsx client/src/components/ExportModal.tsx client/src/components/ExportModal.test.tsx
git commit -m "feat: add playback controls and export dialog"
```

---

### Task 11: Chord editor

**Files:**
- Create: `client/src/components/ChordEditor.tsx`
- Test: `client/src/components/ChordEditor.test.tsx`

**Interfaces:**
- Consumes: `parse`, `toHarte`, `transpose`, `simplify`, `formatSymbol`, `rootNameInKey`, `QUALITIES`, `QUALITY_SYMBOL`, `Segment`
- Produces: `ChordEditor({ segment: Segment; shift: number; tonic: string; onApply(label: string, applyToAll: boolean): void; onClose(): void })` — `shift = transpose − capo`; everything shown is in displayed pitch; `onApply` always receives a **concert-pitch** Harte label.

- [ ] **Step 1: Write the failing tests**

`client/src/components/ChordEditor.test.tsx`:
```tsx
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { Segment } from '../types'
import { ChordEditor } from './ChordEditor'

const rootButton = (name: string) => within(screen.getByRole('group', { name: 'Root' })).getByRole('button', { name })

const seg: Segment = { start: 6, end: 8, label: 'D:7/3', alt: 'D:7', confidence: 0.4, bass: 'F#', edited: false }

describe('ChordEditor', () => {
  it('offers the model alternative and a simpler chord', async () => {
    const user = userEvent.setup()
    const onApply = vi.fn()
    render(<ChordEditor segment={seg} shift={0} tonic="G" onApply={onApply} onClose={vi.fn()} />)
    expect(screen.getByRole('heading')).toHaveTextContent('D7/F#')
    const suggestions = screen.getByRole('group', { name: /suggestions/i })
    expect(suggestions).toHaveTextContent('D7')
    expect(suggestions).toHaveTextContent('D')
    await user.click(within(suggestions).getByRole('button', { name: 'D7' }))
    expect(onApply).toHaveBeenCalledWith('D:7', false)
  })

  it('saves manual picks in concert pitch', async () => {
    const user = userEvent.setup()
    const onApply = vi.fn()
    // transpose +2: D7/F# is displayed as E7/G#
    render(<ChordEditor segment={seg} shift={2} tonic="A" onApply={onApply} onClose={vi.fn()} />)
    expect(screen.getByRole('heading')).toHaveTextContent('E7/G#')
    expect(rootButton('E')).toHaveAttribute('aria-pressed', 'true')
    await user.selectOptions(screen.getByLabelText('Chord type'), 'maj7')
    await user.click(screen.getByRole('button', { name: /^apply$/i }))
    expect(onApply).toHaveBeenCalledWith('D:maj7/3', false)
  })

  it('picks a new root and bass', async () => {
    const user = userEvent.setup()
    const onApply = vi.fn()
    render(<ChordEditor segment={seg} shift={0} tonic="G" onApply={onApply} onClose={vi.fn()} />)
    await user.click(rootButton('C'))
    await user.selectOptions(screen.getByLabelText('Chord type'), 'maj')
    await user.selectOptions(screen.getByLabelText('Bass'), '')
    await user.click(screen.getByRole('button', { name: /^apply$/i }))
    expect(onApply).toHaveBeenCalledWith('C:maj', false)
  })

  it('can mark no chord for every matching chord', async () => {
    const user = userEvent.setup()
    const onApply = vi.fn()
    render(<ChordEditor segment={seg} shift={0} tonic="G" onApply={onApply} onClose={vi.fn()} />)
    await user.click(screen.getByLabelText(/apply to every matching chord/i))
    await user.click(screen.getByRole('button', { name: /no chord/i }))
    expect(onApply).toHaveBeenCalledWith('N', true)
  })
})
```

Run: `npm test -- src/components/ChordEditor`
Expected: FAIL — cannot resolve `./ChordEditor`.

- [ ] **Step 2: Implement `client/src/components/ChordEditor.tsx`**

```tsx
import { useState } from 'react'
import {
  QUALITIES, QUALITY_SYMBOL, formatSymbol, parse, rootNameInKey, simplify, toHarte, transpose,
} from '../theory/chord'
import type { Segment } from '../types'

interface Props {
  segment: Segment
  shift: number
  tonic: string
  onApply(label: string, applyToAll: boolean): void
  onClose(): void
}

export function ChordEditor({ segment, shift, tonic, onApply, onClose }: Props) {
  const shown = transpose(parse(segment.label), shift)
  const [root, setRoot] = useState(shown?.root ?? 0)
  const [quality, setQuality] = useState(shown?.quality ?? 'maj')
  const [bass, setBass] = useState<number | null>(shown?.bass ?? null)
  const [applyToAll, setApplyToAll] = useState(false)

  const display = (label: string) => formatSymbol(transpose(parse(label), shift), { tonic })
  const simpler = toHarte(simplify(parse(segment.label)))
  const suggestions = [segment.alt, simpler].filter(
    (l, i, all): l is string => !!l && l !== 'N' && l !== segment.label && all.indexOf(l) === i,
  )

  function applyManual() {
    const picked = { root, quality, bass: bass === null || bass === root ? null : bass }
    onApply(toHarte(transpose(picked, -shift)), applyToAll)
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" role="dialog" aria-modal="true" aria-label="Edit chord" onClick={(e) => e.stopPropagation()}>
        <h2>{display(segment.label)}</h2>
        {suggestions.length > 0 && (
          <div className="suggestions" role="group" aria-label="Suggestions">
            {suggestions.map((l) => (
              <button key={l} type="button" className="button" onClick={() => onApply(l, applyToAll)}>{display(l)}</button>
            ))}
          </div>
        )}
        <div className="root-grid" role="group" aria-label="Root">
          {Array.from({ length: 12 }, (_, pc) => (
            <button key={pc} type="button" className="button" aria-pressed={root === pc} onClick={() => setRoot(pc)}>
              {rootNameInKey(pc, tonic)}
            </button>
          ))}
        </div>
        <label>
          Chord type{' '}
          <select aria-label="Chord type" value={quality} onChange={(e) => setQuality(e.target.value)}>
            {QUALITIES.map((q) => <option key={q} value={q}>{QUALITY_SYMBOL[q] || 'major'}</option>)}
          </select>
        </label>
        <label>
          Bass{' '}
          <select aria-label="Bass" value={bass ?? ''} onChange={(e) => setBass(e.target.value === '' ? null : Number(e.target.value))}>
            <option value="">Root position</option>
            {Array.from({ length: 12 }, (_, pc) => <option key={pc} value={pc}>{rootNameInKey(pc, tonic)}</option>)}
          </select>
        </label>
        <label>
          <input type="checkbox" checked={applyToAll} onChange={(e) => setApplyToAll(e.target.checked)} />
          {' '}Apply to every matching chord
        </label>
        <div className="control">
          <button type="button" className="button primary" onClick={applyManual}>Apply</button>
          <button type="button" className="button" onClick={() => onApply('N', applyToAll)}>No chord</button>
          <button type="button" className="button" onClick={onClose}>Cancel</button>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `npm test -- src/components/ChordEditor`
Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add client/src/components/ChordEditor.tsx client/src/components/ChordEditor.test.tsx
git commit -m "feat: add chord editor with suggestions and concert-pitch saving"
```

---

### Task 12: Tracker page

**Files:**
- Modify: `client/src/pages/TrackerPage.tsx` (replace placeholder)
- Test: `client/src/pages/TrackerPage.test.tsx`

**Interfaces:**
- Consumes: everything from Tasks 2–11: `api.song/editSegment/reset`, `useViewSettings`, `useYouTubePlayer`, `activeIndex`, `upcomingIndex`, `beatsUntil`, `render`, `keySpelling`, `formatKey`, `parse`, `simplify`, `transpose`, `ChordHero`, `ChordLane`, `DiagramPanel`, `Controls`, `ChordEditor`, `ExportModal`
- Produces: `TrackerPage` (route `/songs/:songId`)

- [ ] **Step 1: Write the failing tests**

`client/src/pages/TrackerPage.test.tsx`:
```tsx
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { makeSong } from '../test/fixtures'
import { renderAt } from '../test/router'
import { TrackerPage } from './TrackerPage'

const player = vi.hoisted(() => ({ ready: true, time: 1.0, playing: false, seek: vi.fn(), setRate: vi.fn() }))
vi.mock('../hooks/useYouTubePlayer', () => ({ useYouTubePlayer: () => player }))
vi.mock('../api', () => ({
  api: { song: vi.fn(), editSegment: vi.fn(), reset: vi.fn() },
  exportUrl: () => '/api/export',
}))
import { api } from '../api'
const mocked = vi.mocked(api)

function renderTracker() {
  return renderAt('/songs/s1', <Route path="/songs/:songId" element={<TrackerPage />} />)
}

beforeEach(() => {
  vi.clearAllMocks()
  player.time = 1.0
  mocked.song.mockResolvedValue(makeSong())
})

describe('TrackerPage', () => {
  it('shows the song header and the chord at the playhead', async () => {
    renderTracker()
    expect(await screen.findByRole('heading', { name: 'Test Song' })).toBeInTheDocument()
    expect(screen.getByText('G minor')).toBeInTheDocument()
    expect(screen.getByTestId('current-chord')).toHaveTextContent('Cm7')
    expect(screen.getByTestId('next-chord')).toHaveTextContent('F7')
    expect(screen.getByLabelText('2 beats to next chord')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'Piano keys for Cm7' })).toBeInTheDocument()
  })

  it('re-spells chords when transposing', async () => {
    const user = userEvent.setup()
    renderTracker()
    await screen.findByTestId('current-chord')
    await user.click(screen.getByRole('button', { name: 'Transpose up' }))
    expect(screen.getByTestId('current-chord')).toHaveTextContent('C#m7')
    expect(screen.getByText('G# minor')).toBeInTheDocument()
  })

  it('edits a chord through the editor', async () => {
    const edited = makeSong()
    edited.timeline.segments[1] = { ...edited.timeline.segments[1], label: 'F:maj', edited: true }
    mocked.editSegment.mockResolvedValue(edited.timeline)
    const user = userEvent.setup()
    renderTracker()
    await screen.findByTestId('current-chord')
    await user.click(screen.getByRole('button', { name: /edit chords/i }))
    await user.click(screen.getByRole('button', { name: 'F7' }))
    await user.click(within(screen.getByRole('group', { name: /suggestions/i })).getByRole('button', { name: 'F' }))
    expect(mocked.editSegment).toHaveBeenCalledWith('s1', 1, 'F:maj', false)
    await waitFor(() => expect(screen.queryByRole('dialog', { name: /edit chord/i })).not.toBeInTheDocument())
    expect(screen.getByRole('button', { name: 'F' })).toHaveClass('edited')
  })

  it('loops between A and B', async () => {
    const user = userEvent.setup()
    const view = renderTracker()
    await screen.findByTestId('current-chord')
    player.time = 0.5
    view.rerender(view.ui())
    await user.click(screen.getByRole('button', { name: /set a/i }))
    player.time = 2.4
    view.rerender(view.ui())
    await user.click(screen.getByRole('button', { name: /set b/i }))
    expect(player.seek).not.toHaveBeenCalled()
    player.time = 2.6
    view.rerender(view.ui())
    await waitFor(() => expect(player.seek).toHaveBeenCalledWith(0.5))
  })

  it('shows analysis warnings', async () => {
    mocked.song.mockResolvedValue(makeSong({ warnings: ['BTC model weights not found.'] }))
    renderTracker()
    expect(await screen.findByRole('status')).toHaveTextContent('BTC model weights not found.')
  })

  it('shows an error for unknown songs', async () => {
    mocked.song.mockRejectedValue(new Error('Song not found'))
    renderTracker()
    expect(await screen.findByRole('alert')).toHaveTextContent('Song not found')
  })
})
```

(`view.ui()` comes from `renderAt` in Task 5 and builds a fresh element each call.)

Run: `npm test -- src/pages/TrackerPage`
Expected: FAIL (placeholder renders nothing).

- [ ] **Step 2: Implement `client/src/pages/TrackerPage.tsx`**

```tsx
import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import { ChordEditor } from '../components/ChordEditor'
import { ChordHero } from '../components/ChordHero'
import { ChordLane } from '../components/ChordLane'
import { Controls, type LoopRange } from '../components/Controls'
import { DiagramPanel } from '../components/DiagramPanel'
import { ExportModal } from '../components/ExportModal'
import { useViewSettings } from '../hooks/useViewSettings'
import { useYouTubePlayer } from '../hooks/useYouTubePlayer'
import { activeIndex, beatsUntil, upcomingIndex } from '../sync'
import { formatKey, keySpelling, parse, render, simplify, transpose } from '../theory/chord'
import type { Song, Timeline } from '../types'

export function TrackerPage() {
  const { songId = '' } = useParams()
  const [song, setSong] = useState<Song | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.song(songId).then(setSong).catch((e) => setError(e instanceof Error ? e.message : String(e)))
  }, [songId])

  if (error) {
    return (
      <main className="page">
        <p role="alert" className="error">{error}</p>
        <Link to="/" className="button">Back to home</Link>
      </main>
    )
  }
  if (!song) return <main className="page"><p className="muted">Loading…</p></main>
  return <Tracker song={song} onTimeline={(timeline) => setSong({ ...song, timeline })} />
}

function Tracker({ song, onTimeline }: { song: Song; onTimeline(t: Timeline): void }) {
  const t = song.timeline
  const [settings, update] = useViewSettings(song.id)
  const player = useYouTubePlayer('yt-player', t.video_id)
  const [loop, setLoop] = useState<LoopRange>({ a: null, b: null })
  const [editMode, setEditMode] = useState(false)
  const [editing, setEditing] = useState<number | null>(null)
  const [exporting, setExporting] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  const shift = settings.transpose - settings.capo
  const tonic = keySpelling(t.key, shift)
  const symbols = useMemo(
    () => t.segments.map((s) => render(s.label, { transpose: settings.transpose, capo: settings.capo, simplify: settings.simplify, tonic })),
    [t.segments, settings.transpose, settings.capo, settings.simplify, tonic],
  )

  const idx = activeIndex(t.segments, player.time)
  const next = upcomingIndex(t.segments, player.time)
  const beatsToNext = next >= 0 ? beatsUntil(t.beats, player.time, t.segments[next].start) : 0
  const currentChord = useMemo(() => {
    if (idx < 0) return null
    let c = parse(t.segments[idx].label)
    if (settings.simplify) c = simplify(c)
    return transpose(c, shift)
  }, [idx, t.segments, settings.simplify, shift])

  const { setRate, ready, seek, time } = player
  useEffect(() => {
    if (ready) setRate(settings.rate)
  }, [ready, setRate, settings.rate])

  useEffect(() => {
    if (loop.a !== null && loop.b !== null && loop.b > loop.a && time >= loop.b) seek(loop.a)
  }, [time, loop, seek])

  async function applyEdit(label: string, applyToAll: boolean) {
    if (editing === null) return
    try {
      onTimeline(await api.editSegment(song.id, editing, label, applyToAll))
      setEditing(null)
      setActionError(null)
    } catch (e) {
      setActionError(e instanceof Error ? e.message : String(e))
    }
  }

  async function resetEdits() {
    try {
      onTimeline(await api.reset(song.id))
    } catch (e) {
      setActionError(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <main className="page tracker">
      <div>
        <h1>{t.title}</h1>
        <div className="chips">
          <span className="chip-meta">{formatKey(t.key, settings.transpose)}</span>
          <span className="chip-meta">{Math.round(t.tempo)} BPM</span>
          <span className="chip-meta">{t.time_signature}/4</span>
          {settings.capo > 0 && <span className="chip-meta">Capo {settings.capo}</span>}
          <span className="chip-meta muted">{t.engine.chords === 'btc-large' ? 'BTC model' : 'Template model'}{t.engine.separated ? ' · stems' : ''}</span>
        </div>
      </div>
      {t.warnings.length > 0 && (
        <div role="status" className="banner">{t.warnings.map((w) => <p key={w}>{w}</p>)}</div>
      )}
      {actionError && <p role="alert" className="error">{actionError}</p>}
      <div className="tracker-top">
        <div className="player"><div id="yt-player" /></div>
        <ChordHero current={idx >= 0 ? symbols[idx] : null} next={next >= 0 ? symbols[next] : null} beatsToNext={beatsToNext} />
      </div>
      <ChordLane segments={t.segments} symbols={symbols} beats={t.beats} downbeats={t.downbeats} duration={t.duration}
        time={player.time} editMode={editMode} onSeek={seek} onEdit={setEditing} />
      <div className="tracker-bottom">
        <DiagramPanel chord={currentChord} label={idx >= 0 ? symbols[idx] : 'N.C.'} />
        <Controls settings={settings} onChange={update} loop={loop}
          onSetA={() => setLoop((l) => ({ ...l, a: time }))} onSetB={() => setLoop((l) => ({ ...l, b: time }))}
          onClearLoop={() => setLoop({ a: null, b: null })} editMode={editMode} onToggleEdit={() => setEditMode((m) => !m)}
          onReset={resetEdits} onExport={() => setExporting(true)} />
      </div>
      {editing !== null && (
        <ChordEditor segment={t.segments[editing]} shift={shift} tonic={tonic} onApply={applyEdit} onClose={() => setEditing(null)} />
      )}
      {exporting && <ExportModal songId={song.id} settings={settings} onClose={() => setExporting(false)} />}
    </main>
  )
}
```

- [ ] **Step 3: Run the whole client suite and build**

Run: `npm test`
Expected: all PASS.
Run: `npm run build`
Expected: succeeds.

- [ ] **Step 4: Commit**

```bash
git add client/src/pages/TrackerPage.tsx client/src/pages/TrackerPage.test.tsx client/src/test/router.tsx
git commit -m "feat: add tracker page with synced player, editing, loop and export"
```

---

### Task 13: Dev launch config, browser verification, README

**Files:**
- Create: `.claude/launch.json`
- Modify: `README.md`, `.gitignore` (confirm `client/node_modules/`, `client/dist/` ignored)

- [ ] **Step 1: Launch configuration**

`.claude/launch.json`:
```json
{
  "version": "0.0.1",
  "configurations": [
    {
      "name": "chordarium-api",
      "runtimeExecutable": ".venv/Scripts/python.exe",
      "runtimeArgs": ["-m", "server.app"],
      "port": 5000
    },
    {
      "name": "chordarium-client",
      "runtimeExecutable": "npm",
      "runtimeArgs": ["--prefix", "client", "run", "dev"],
      "port": 5173
    }
  ]
}
```

- [ ] **Step 2: Manual browser verification (golden path + edge cases)**

Start both servers (API first), open `http://localhost:5173`, and check each item, fixing any failure test-first before continuing:
1. Home shows the library with the two songs analyzed in Plan 1; cards open the tracker.
2. Tracker: video plays; big chord and next chord change in time with the music; lane scrolls under the centre playhead; clicking a chip seeks.
3. Transpose +2 / capo 2 change the displayed chords and key chip; reload the page — settings persist.
4. Speed 0.75× slows the video.
5. Set A/B loops the section; Clear loop stops it.
6. Edit mode: click a chip, pick a suggestion — lane updates with the edited marker; Reset edits restores it.
7. Export: download PDF and ChordPro; open both and confirm chords match the lane with the chosen transpose/capo.
8. Guitar tab shows a shape for common chords and the fallback text for a chord without one.
9. Paste an invalid link on Home → inline error; paste a new valid link in Fast mode → progress page → tracker.
10. Narrow the window to phone width (375 px): no horizontal scroll; layout stacks.

- [ ] **Step 3: README**

Append to `README.md`:
````markdown
## Run the app (Phase 1)

Terminal 1 — API:
```powershell
.venv\Scripts\activate
python -m server.app
```

Terminal 2 — web client:
```powershell
cd client
npm install
npm run dev          # http://localhost:5173
npm test             # client tests
```
````
and change the Status line to: `**Status:** Phase 1 complete — local Flask API + React client.`

- [ ] **Step 4: Full verification and commit**

Run (repo root): `.venv\Scripts\python -m pytest -m "slow or not slow" -q` → all PASS.
Run (client): `npm test` and `npm run build` → PASS / succeeds.

```bash
git add .claude/launch.json README.md .gitignore
git commit -m "docs: add dev launch config and client run instructions"
```
