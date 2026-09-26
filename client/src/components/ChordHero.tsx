import { ChordSymbol } from './ChordSymbol'

interface Props {
  current: string | null
  next: string | null
  beatsToNext: number
  lowConfidence?: boolean
}

export function ChordHero({ current, next, beatsToNext, lowConfidence = false }: Props) {
  const dots = Math.min(Math.max(beatsToNext, 0), 4)
  return (
    <section className="hero" aria-label="Current chord">
      <div className="hero-current" data-testid="current-chord">
        {current ? <ChordSymbol symbol={current} lowConfidence={lowConfidence} /> : '—'}
      </div>
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
