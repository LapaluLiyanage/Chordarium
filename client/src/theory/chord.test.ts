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
