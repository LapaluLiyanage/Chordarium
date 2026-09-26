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
