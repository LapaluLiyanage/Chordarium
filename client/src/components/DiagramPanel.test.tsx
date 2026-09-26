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
