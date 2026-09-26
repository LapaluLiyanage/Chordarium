import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter, Routes } from 'react-router-dom'

export function renderAt(path: string, routes: ReactElement) {
  const ui = () => (
    <MemoryRouter initialEntries={[path]}>
      <Routes>{routes}</Routes>
    </MemoryRouter>
  )
  return { ...render(ui()), ui }
}
