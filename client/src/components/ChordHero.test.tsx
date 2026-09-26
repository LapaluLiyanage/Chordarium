import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import { ChordHero } from './ChordHero'

it('shows current, next and a beat countdown capped at 4', () => {
  const { rerender } = render(<ChordHero current="Cm7" next="F7" beatsToNext={2} />)
  expect(screen.getByTestId('current-chord')).toHaveTextContent('Cm7')
  expect(screen.getByTestId('next-chord')).toHaveTextContent('F7')
  expect(screen.getByLabelText('2 beats to next chord')).toBeInTheDocument()
  rerender(<ChordHero current={null} next={null} beatsToNext={9} />)
  expect(screen.getByTestId('current-chord')).toHaveTextContent('—')
  expect(screen.getByLabelText('4 beats to next chord')).toBeInTheDocument()
})

it('marks a low-confidence current chord with the dotted underline', () => {
  render(<ChordHero current="G7" next="C" beatsToNext={1} lowConfidence />)
  expect(screen.getByTestId('current-chord').querySelector('.cs')).toHaveClass('low-confidence')
})
