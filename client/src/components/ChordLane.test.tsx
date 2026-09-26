import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { TIMELINE } from '../test/fixtures'
import { ChordLane } from './ChordLane'

const symbols = ['Cm7', 'F7', 'Bbmaj7', 'Ebmaj7', 'D7/F#']

function renderLane(props: Partial<Parameters<typeof ChordLane>[0]> = {}) {
  const onSeek = vi.fn()
  const onEdit = vi.fn()
  render(
    <ChordLane segments={TIMELINE.segments} symbols={symbols} beats={TIMELINE.beats} downbeats={TIMELINE.downbeats}
      duration={TIMELINE.duration} time={2.5} width={800} editMode={false} onSeek={onSeek} onEdit={onEdit} {...props} />,
  )
  return { onSeek, onEdit }
}

describe('ChordLane', () => {
  it('positions the track so the playhead sits at the centre', () => {
    renderLane()
    expect(screen.getByTestId('lane-track')).toHaveStyle({ transform: 'translateX(100px)' })
  })

  it('marks past, active and low-confidence chords', () => {
    renderLane()
    expect(screen.getByRole('button', { name: 'Cm7' })).toHaveClass('past')
    expect(screen.getByRole('button', { name: 'F7' })).toHaveClass('active')
    expect(screen.getByRole('button', { name: 'D7/F#' })).toHaveClass('low')
  })

  it('marks chords below the spec 70% threshold as low, not just below 50%', () => {
    // TIMELINE's Bbmaj7 segment has confidence 0.6 — under 70% (spec), not under 50%.
    renderLane()
    expect(screen.getByRole('button', { name: 'Bbmaj7' })).toHaveClass('low')
  })

  it('seeks on click, or opens the editor in edit mode', async () => {
    const user = userEvent.setup()
    const { onSeek } = renderLane()
    await user.click(screen.getByRole('button', { name: 'Bbmaj7' }))
    expect(onSeek).toHaveBeenCalledWith(4)
  })

  it('edits in edit mode', async () => {
    const user = userEvent.setup()
    const { onEdit, onSeek } = renderLane({ editMode: true })
    await user.click(screen.getByRole('button', { name: 'Bbmaj7' }))
    expect(onEdit).toHaveBeenCalledWith(2)
    expect(onSeek).not.toHaveBeenCalled()
  })

  it('lets edit mode add a chord where the model found none', async () => {
    const user = userEvent.setup()
    const noChordSegments = [
      { start: 0, end: 2, label: 'N', alt: null, confidence: 1, bass: null, edited: false },
      ...TIMELINE.segments.slice(1),
    ]
    const noChordSymbols = ['N.C.', ...symbols.slice(1)]
    const { onEdit } = renderLane({ segments: noChordSegments, symbols: noChordSymbols, editMode: true })
    const placeholder = screen.getByRole('button', { name: /add a chord/i })
    expect(placeholder).toHaveClass('empty')
    await user.click(placeholder)
    expect(onEdit).toHaveBeenCalledWith(0)
  })

  it('does not render a no-chord placeholder outside edit mode', () => {
    const noChordSegments = [
      { start: 0, end: 2, label: 'N', alt: null, confidence: 1, bass: null, edited: false },
      ...TIMELINE.segments.slice(1),
    ]
    renderLane({ segments: noChordSegments, editMode: false })
    expect(screen.queryByRole('button', { name: /add a chord/i })).not.toBeInTheDocument()
  })
})
