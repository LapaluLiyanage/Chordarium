import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ChordSymbol, splitChordSymbol } from './ChordSymbol'

describe('splitChordSymbol', () => {
  it('splits root, quality letters and raised extension', () => {
    expect(splitChordSymbol('Cmaj7')).toEqual({ root: 'C', quality: 'maj', ext: '7', bass: null })
    expect(splitChordSymbol('Am7b5')).toEqual({ root: 'A', quality: 'm', ext: '7b5', bass: null })
    expect(splitChordSymbol('G7b9')).toEqual({ root: 'G', quality: '', ext: '7b9', bass: null })
  })
  it('splits a slash bass at 60%', () => {
    expect(splitChordSymbol('C/E')).toEqual({ root: 'C', quality: '', ext: '', bass: 'E' })
    expect(splitChordSymbol('D7/F#')).toEqual({ root: 'D', quality: '', ext: '7', bass: 'F#' })
  })
  it('leaves a plain major chord as just a root', () => {
    expect(splitChordSymbol('C')).toEqual({ root: 'C', quality: '', ext: '', bass: null })
  })
  it('passes N.C. through untouched', () => {
    expect(splitChordSymbol('N.C.')).toEqual({ root: 'N.C.', quality: '', ext: '', bass: null })
  })
})

describe('ChordSymbol', () => {
  it('renders each part in its own styled span', () => {
    const { container } = render(<ChordSymbol symbol="Am7b5" />)
    expect(container.querySelector('.cs-root')).toHaveTextContent('A')
    expect(container.querySelector('.cs-quality')).toHaveTextContent('m')
    expect(container.querySelector('.cs-ext')).toHaveTextContent('7b5')
    expect(screen.getByText((_, el) => el?.className === 'cs')).toHaveTextContent('Am7b5')
  })
  it('marks low-confidence chords for the dotted underline', () => {
    const { container } = render(<ChordSymbol symbol="G7" lowConfidence />)
    expect(container.querySelector('.cs')).toHaveClass('low-confidence')
  })
})
