import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useModalA11y } from './useModalA11y'

function Modal({ onClose }: { onClose: () => void }) {
  const ref = useModalA11y(onClose)
  return (
    <div ref={ref} role="dialog">
      <button>First</button>
      <button>Middle</button>
      <button>Last</button>
    </div>
  )
}

function Harness({ onClose }: { onClose: () => void }) {
  return (
    <div>
      <button>Opener</button>
      <Modal onClose={onClose} />
    </div>
  )
}

function ToggleHarness() {
  const [open, setOpen] = useState(false)
  return (
    <div>
      <button onClick={() => setOpen(true)}>Opener</button>
      {open && <Modal onClose={() => setOpen(false)} />}
    </div>
  )
}

afterEach(() => { document.body.innerHTML = '' })

describe('useModalA11y', () => {
  it('focuses the first focusable element on mount', () => {
    render(<Harness onClose={vi.fn()} />)
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'First' }))
  })

  it('calls onClose on Escape', () => {
    const onClose = vi.fn()
    render(<Harness onClose={onClose} />)
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalled()
  })

  it('traps Tab: wraps last -> first and Shift+Tab wraps first -> last', () => {
    render(<Harness onClose={vi.fn()} />)
    const first = screen.getByRole('button', { name: 'First' })
    const last = screen.getByRole('button', { name: 'Last' })

    last.focus()
    fireEvent.keyDown(document, { key: 'Tab' })
    expect(document.activeElement).toBe(first)

    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true })
    expect(document.activeElement).toBe(last)
  })

  it('restores focus to the opener once the modal closes', async () => {
    const user = userEvent.setup()
    render(<ToggleHarness />)
    const opener = screen.getByRole('button', { name: 'Opener' })
    await user.click(opener)
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'First' }))
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(document.activeElement).toBe(opener)
  })
})
