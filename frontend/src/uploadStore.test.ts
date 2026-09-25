import { describe, expect, it } from 'vitest'
import { UPLOAD_TTL_MS, isFresh } from './uploadStore'

describe('isFresh', () => {
  const saved = 1_000_000

  it('keeps a file for 24 hours', () => {
    expect(isFresh(saved, saved)).toBe(true)
    expect(isFresh(saved, saved + UPLOAD_TTL_MS - 1)).toBe(true)
  })

  it('forgets it after that', () => {
    expect(isFresh(saved, saved + UPLOAD_TTL_MS)).toBe(false)
  })

  it('does not trust a timestamp from the future', () => {
    expect(isFresh(saved, saved - 1)).toBe(false)
  })
})
