import type { Segment } from './types'

export const PX_PER_SECOND = 120

function firstStartAfter(segments: Segment[], t: number): number {
  let lo = 0
  let hi = segments.length
  while (lo < hi) {
    const mid = (lo + hi) >> 1
    if (segments[mid].start <= t) lo = mid + 1
    else hi = mid
  }
  return lo
}

export function activeIndex(segments: Segment[], t: number): number {
  const i = firstStartAfter(segments, t) - 1
  return i >= 0 && t < segments[i].end ? i : -1
}

export function upcomingIndex(segments: Segment[], t: number): number {
  for (let j = firstStartAfter(segments, t); j < segments.length; j++) {
    if (segments[j].label !== 'N') return j
  }
  return -1
}

export function beatsUntil(beats: number[], t: number, target: number): number {
  return beats.filter((b) => b > t + 1e-6 && b <= target + 1e-6).length
}

export function laneOffset(t: number, width: number): number {
  return width / 2 - t * PX_PER_SECOND
}
