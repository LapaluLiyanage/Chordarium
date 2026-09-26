import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useYouTubePlayer } from './useYouTubePlayer'

class FakePlayer {
  static last: FakePlayer
  time = 0
  seekTo = vi.fn()
  setPlaybackRate = vi.fn()
  destroy = vi.fn()
  constructor(public elementId: string, public opts: any) {
    FakePlayer.last = this
  }
  getCurrentTime() {
    return this.time
  }
}

beforeEach(() => {
  ;(window as any).YT = { Player: FakePlayer, PlayerState: { PLAYING: 1, PAUSED: 2 } }
})
afterEach(() => {
  delete (window as any).YT
})

describe('useYouTubePlayer', () => {
  it('creates the player for the element and video', async () => {
    renderHook(() => useYouTubePlayer('yt', 'abcdefghijk'))
    await waitFor(() => expect(FakePlayer.last?.opts.videoId).toBe('abcdefghijk'))
    expect(FakePlayer.last.elementId).toBe('yt')
  })

  it('reports ready, playing state and current time', async () => {
    const { result } = renderHook(() => useYouTubePlayer('yt', 'abcdefghijk'))
    await waitFor(() => expect(FakePlayer.last).toBeDefined())
    act(() => FakePlayer.last.opts.events.onReady())
    expect(result.current.ready).toBe(true)
    act(() => FakePlayer.last.opts.events.onStateChange({ data: 1 }))
    expect(result.current.playing).toBe(true)
    FakePlayer.last.time = 5.25
    await waitFor(() => expect(result.current.time).toBe(5.25))
  })

  it('seeks, sets rate and destroys on unmount', async () => {
    const { result, unmount } = renderHook(() => useYouTubePlayer('yt', 'abcdefghijk'))
    await waitFor(() => expect(FakePlayer.last).toBeDefined())
    const player = FakePlayer.last
    act(() => result.current.seek(12))
    expect(player.seekTo).toHaveBeenCalledWith(12, true)
    expect(result.current.time).toBe(12)
    act(() => result.current.setRate(0.75))
    expect(player.setPlaybackRate).toHaveBeenCalledWith(0.75)
    unmount()
    expect(player.destroy).toHaveBeenCalled()
  })
})
