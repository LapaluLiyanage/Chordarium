/** Splits a rendered chord symbol ("Cmaj7", "G7b9", "Am7b5", "C/E", "N.C.") into
 * root / quality-letters / raised-extension / bass parts for the studio typography
 * (root full size, quality at 64% on the baseline, extensions raised 44%, bass 60% + lighter). */

export interface ChordParts {
  root: string
  quality: string
  ext: string
  bass: string | null
}

const ROOT_RE = /^[A-G](#|b)?/

export function splitChordSymbol(symbol: string): ChordParts {
  if (symbol === 'N.C.' || symbol === '') return { root: symbol, quality: '', ext: '', bass: null }
  const rootMatch = symbol.match(ROOT_RE)
  const root = rootMatch ? rootMatch[0] : symbol
  const rest = symbol.slice(root.length)
  const slash = rest.indexOf('/')
  const qualityPart = slash === -1 ? rest : rest.slice(0, slash)
  const bass = slash === -1 ? null : rest.slice(slash + 1)
  const letters = qualityPart.match(/^[A-Za-z]*/)?.[0] ?? ''
  const ext = qualityPart.slice(letters.length)
  return { root, quality: letters, ext, bass }
}

export function ChordSymbol({ symbol, lowConfidence = false }: { symbol: string; lowConfidence?: boolean }) {
  const parts = splitChordSymbol(symbol)
  if (!parts.quality && !parts.ext && !parts.bass) {
    return <span className={lowConfidence ? 'cs low-confidence' : 'cs'}><span className="cs-root">{parts.root}</span></span>
  }
  return (
    <span className={lowConfidence ? 'cs low-confidence' : 'cs'}>
      <span className="cs-root">{parts.root}</span>
      {parts.quality && <span className="cs-quality">{parts.quality}</span>}
      {parts.ext && <span className="cs-ext">{parts.ext}</span>}
      {parts.bass !== null && <span className="cs-bass">/{parts.bass}</span>}
    </span>
  )
}
