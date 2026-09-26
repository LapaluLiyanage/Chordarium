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
