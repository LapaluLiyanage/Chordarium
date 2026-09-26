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
