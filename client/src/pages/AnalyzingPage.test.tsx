import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Job } from '../types'
import { renderAt } from '../test/router'
import { AnalyzingPage } from './AnalyzingPage'

vi.mock('../api', () => ({ api: { job: vi.fn(), cancelJob: vi.fn() } }))
import { api } from '../api'
const mocked = vi.mocked(api)

const base: Job = {
  id: 'j1', video_id: 'abcdefghijk', mode: 'fast', state: 'queued', progress: 0,
  message: 'Waiting to start', error: null, song_id: null, created_at: '',
}

function renderPage() {
  return renderAt('/jobs/j1', (
    <>
      <Route path="/jobs/:jobId" element={<AnalyzingPage pollMs={5} />} />
      <Route path="/songs/:songId" element={<p>SONG PAGE</p>} />
    </>
  ))
}

beforeEach(() => vi.resetAllMocks())

describe('AnalyzingPage', () => {
  it('shows live steps and opens the song when done', async () => {
    mocked.job
      .mockResolvedValueOnce({ ...base, state: 'chords', progress: 60, message: 'Recognizing chords' })
      .mockResolvedValue({ ...base, state: 'done', progress: 100, song_id: 's1' })
    renderPage()
    expect(await screen.findByText('Recognizing chords', { selector: 'li' })).toHaveAttribute('data-status', 'active')
    expect(screen.queryByText(/separating stems/i)).not.toBeInTheDocument()
    expect(await screen.findByText('SONG PAGE')).toBeInTheDocument()
  })

  it('lists the separation step for accurate jobs', async () => {
    mocked.job.mockResolvedValue({ ...base, mode: 'accurate', state: 'separating', progress: 15 })
    renderPage()
    expect(await screen.findByText(/separating stems/i)).toHaveAttribute('data-status', 'active')
  })

  it('shows failure and stops polling', async () => {
    mocked.job.mockResolvedValue({ ...base, state: 'failed', error: 'This video is private.' })
    renderPage()
    expect(await screen.findByRole('alert')).toHaveTextContent('This video is private.')
    const calls = mocked.job.mock.calls.length
    await new Promise((r) => setTimeout(r, 40))
    expect(mocked.job.mock.calls.length).toBe(calls)
    expect(screen.getByRole('link', { name: /try another link/i })).toHaveAttribute('href', '/')
  })

  it('cancels the job', async () => {
    mocked.job.mockResolvedValue({ ...base, state: 'beats', progress: 45 })
    mocked.cancelJob.mockResolvedValue({ cancelled: true })
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByRole('button', { name: /cancel/i }))
    await waitFor(() => expect(mocked.cancelJob).toHaveBeenCalledWith('j1'))
  })

  it('shows a cancelled message', async () => {
    mocked.job.mockResolvedValue({ ...base, state: 'cancelled' })
    renderPage()
    expect(await screen.findByText(/analysis cancelled/i)).toBeInTheDocument()
  })
})
