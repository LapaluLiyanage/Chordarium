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
