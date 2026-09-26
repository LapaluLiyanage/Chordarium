import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { DEFAULT_VIEW } from '../hooks/useViewSettings'
import { Controls } from './Controls'

function setup(overrides = {}) {
  const props = {
    settings: DEFAULT_VIEW, onChange: vi.fn(), loop: { a: null, b: null }, onSetA: vi.fn(), onSetB: vi.fn(),
    onClearLoop: vi.fn(), editMode: false, onToggleEdit: vi.fn(), onReset: vi.fn(), onExport: vi.fn(), ...overrides,
  }
  render(<Controls {...props} />)
  return props
}

describe('Controls', () => {
  it('steps transpose and capo', async () => {
    const user = userEvent.setup()
    const p = setup({ settings: { ...DEFAULT_VIEW, transpose: 2, capo: 1 } })
    expect(screen.getByLabelText('Transpose value')).toHaveTextContent('+2')
    await user.click(screen.getByRole('button', { name: 'Transpose up' }))
    expect(p.onChange).toHaveBeenCalledWith({ transpose: 3 })
    await user.click(screen.getByRole('button', { name: 'Capo down' }))
    expect(p.onChange).toHaveBeenCalledWith({ capo: 0 })
  })

  it('changes speed and simplify', async () => {
    const user = userEvent.setup()
    const p = setup()
    await user.selectOptions(screen.getByLabelText('Speed'), '0.75')
    expect(p.onChange).toHaveBeenCalledWith({ rate: 0.75 })
    await user.click(screen.getByLabelText('Simplify chords'))
    expect(p.onChange).toHaveBeenCalledWith({ simplify: true })
  })

  it('drives loop, edit, reset and export actions', async () => {
    const user = userEvent.setup()
    const p = setup({ loop: { a: 12.5, b: null }, editMode: true })
    expect(screen.getByRole('button', { name: /set a/i })).toHaveTextContent('0:12')
    await user.click(screen.getByRole('button', { name: /set b/i }))
    expect(p.onSetB).toHaveBeenCalled()
    expect(screen.getByRole('button', { name: /edit chords/i })).toHaveAttribute('aria-pressed', 'true')
    await user.click(screen.getByRole('button', { name: /reset edits/i }))
    expect(p.onReset).toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: /export/i }))
    expect(p.onExport).toHaveBeenCalled()
  })
})
