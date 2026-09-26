import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import { AnalyzingPage } from './pages/AnalyzingPage'
import { HomePage } from './pages/HomePage'
import { TrackerPage } from './pages/TrackerPage'

export function AppRoutes() {
  return (
    <>
      <header className="topbar">
        <Link to="/" className="brand">Chordarium</Link>
        <span className="soon" title="Publishing chord sheets arrives in Phase 2">Public library · coming soon</span>
      </header>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/jobs/:jobId" element={<AnalyzingPage />} />
        <Route path="/songs/:songId" element={<TrackerPage />} />
      </Routes>
    </>
  )
}

export function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  )
}
