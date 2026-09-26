import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { expect, it, vi } from 'vitest'
import { AppRoutes } from './App'

vi.mock('./api', () => ({ api: { analyze: vi.fn(), songs: vi.fn().mockResolvedValue([]) } }))

it('renders the brand and the home page at /', async () => {
  render(<MemoryRouter initialEntries={['/']}><AppRoutes /></MemoryRouter>)
  expect(screen.getByRole('link', { name: 'Chordarium' })).toHaveAttribute('href', '/')
  expect(await screen.findByRole('heading', { name: /paste a song/i })).toBeInTheDocument()
})
