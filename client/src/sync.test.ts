import { describe, expect, it } from 'vitest'
import { activeIndex, beatsUntil, laneOffset, upcomingIndex } from './sync'
import { TIMELINE } from './test/fixtures'

const segs = TIMELINE.segments
const withGap = [
  { ...segs[0], start: 1, end: 2 },
  { ...segs[0], start: 2, end: 3, label: 'N' },
  { ...segs[1], start: 3, end: 5 },
]

describe('activeIndex', () => {
  it('finds the segment containing t', () => {
    expect(activeIndex(segs, 0)).toBe(0)
    expect(activeIndex(segs, 2)).toBe(1)
    expect(activeIndex(segs, 5.5)).toBe(3)
  })
  it('returns -1 before the first and after the last segment', () => {
    expect(activeIndex(withGap, 0.5)).toBe(-1)
    expect(activeIndex(segs, 8)).toBe(-1)
  })
})

describe('upcomingIndex', () => {
  it('is the next segment after t', () => {
    expect(upcomingIndex(segs, 1)).toBe(1)
    expect(upcomingIndex(segs, 7)).toBe(-1)
  })
  it('skips no-chord segments', () => {
    expect(upcomingIndex(withGap, 1.5)).toBe(2)
    expect(upcomingIndex(withGap, 0)).toBe(0)
  })
})

describe('beatsUntil / laneOffset', () => {
  it('counts beats after t up to and including the target', () => {
    expect(beatsUntil(TIMELINE.beats, 1.0, 2.0)).toBe(2)
    expect(beatsUntil(TIMELINE.beats, 1.9, 2.0)).toBe(1)
    expect(beatsUntil(TIMELINE.beats, 2.0, 2.0)).toBe(0)
  })
  it('centres the playhead', () => {
    expect(laneOffset(0, 800)).toBe(400)
    expect(laneOffset(2, 800)).toBe(160)
  })
})
