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
