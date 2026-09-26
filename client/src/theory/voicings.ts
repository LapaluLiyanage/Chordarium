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
