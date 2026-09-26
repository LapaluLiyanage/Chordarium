import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError, exportUrl } from './api'

function reply(status: number, body?: unknown) {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status, headers: { 'Content-Type': 'application/json' },
  })
}

afterEach(() => vi.unstubAllGlobals())

describe('api', () => {
  it('posts analyze requests as JSON', async () => {
    const fetchMock = vi.fn().mockResolvedValue(reply(202, { job_id: 'j1' }))
    vi.stubGlobal('fetch', fetchMock)
    await expect(api.analyze('https://youtu.be/x', 'accurate')).resolves.toEqual({ job_id: 'j1' })
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/analyze')
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body)).toEqual({ url: 'https://youtu.be/x', mode: 'accurate' })
  })

  it('turns error responses into ApiError with the server message', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(reply(400, { error: 'Not a YouTube link' })))
    const err = await api.analyze('nope', 'fast').catch((e) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect(err.message).toBe('Not a YouTube link')
    expect(err.status).toBe(400)
  })

  it('returns undefined for 204 responses', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(reply(204)))
    await expect(api.deleteSong('s1')).resolves.toBeUndefined()
  })

  it('sends segment edits with apply_to_all', async () => {
    const fetchMock = vi.fn().mockResolvedValue(reply(200, { segments: [] }))
    vi.stubGlobal('fetch', fetchMock)
    await api.editSegment('s1', 3, 'G:maj', true)
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/songs/s1/segments/3')
    expect(init.method).toBe('PUT')
    expect(JSON.parse(init.body)).toEqual({ label: 'G:maj', apply_to_all: true })
  })
})

describe('exportUrl', () => {
  it('encodes every export option', () => {
    expect(exportUrl('s1', { fmt: 'chordpro', transpose: -2, capo: 3, simplify: true, barsPerRow: 8 }))
      .toBe('/api/songs/s1/export?fmt=chordpro&transpose=-2&capo=3&simplify=1&bars_per_row=8')
  })
})
