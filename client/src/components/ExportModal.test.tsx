import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { DEFAULT_VIEW } from '../hooks/useViewSettings'
import { ExportModal } from './ExportModal'

describe('ExportModal', () => {
  it('defaults to a PDF with the current view settings', () => {
    render(<ExportModal songId="s1" settings={{ ...DEFAULT_VIEW, transpose: 2, capo: 1 }} onClose={vi.fn()} />)
    expect(screen.getByRole('link', { name: /download/i }))
      .toHaveAttribute('href', '/api/songs/s1/export?fmt=pdf&transpose=2&capo=1&simplify=0&bars_per_row=4')
  })

  it('changes format, drops view settings, simplifies and widens rows', async () => {
    const user = userEvent.setup()
    render(<ExportModal songId="s1" settings={{ ...DEFAULT_VIEW, transpose: 2, capo: 1 }} onClose={vi.fn()} />)
    await user.click(screen.getByLabelText(/chordpro/i))
    await user.click(screen.getByLabelText(/apply current transpose/i))
    await user.click(screen.getByLabelText(/simplified chords/i))
    await user.selectOptions(screen.getByLabelText(/bars per row/i), '8')
    expect(screen.getByRole('link', { name: /download/i }))
      .toHaveAttribute('href', '/api/songs/s1/export?fmt=chordpro&transpose=0&capo=0&simplify=1&bars_per_row=8')
  })

  it('closes on Escape', () => {
    const onClose = vi.fn()
    render(<ExportModal songId="s1" settings={DEFAULT_VIEW} onClose={onClose} />)
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalled()
  })

  it('closes', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    render(<ExportModal songId="s1" settings={DEFAULT_VIEW} onClose={onClose} />)
    await user.click(screen.getByRole('button', { name: /close/i }))
    expect(onClose).toHaveBeenCalled()
  })
})
