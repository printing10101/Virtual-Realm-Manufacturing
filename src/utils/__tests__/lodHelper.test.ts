import { describe, it, expect } from 'vitest'
import {
  getDefaultConfig,
  updateLODConfig,
  type LODConfig,
} from '@/utils/lodHelper'

describe('lodHelper', () => {
  describe('getDefaultConfig', () => {
    it('returns config with enabled=true', () => {
      const config = getDefaultConfig()
      expect(config.enabled).toBe(true)
    })

    it('returns config with three LOD levels', () => {
      const config = getDefaultConfig()
      expect(config.levels).toHaveLength(3)
    })

    it('has distances in ascending order', () => {
      const config = getDefaultConfig()
      const [a, b, c] = config.levels
      expect(a.distance).toBeLessThan(b.distance)
      expect(b.distance).toBeLessThan(c.distance)
    })

    it('highest LOD has zero simplification', () => {
      const config = getDefaultConfig()
      expect(config.levels[0].simplificationRatio).toBe(0)
    })

    it('lowest LOD has higher simplification', () => {
      const config = getDefaultConfig()
      expect(config.levels[2].simplificationRatio).toBeGreaterThan(config.levels[1].simplificationRatio)
    })

    it('uses edge collapse by default', () => {
      const config = getDefaultConfig()
      expect(config.useEdgeCollapse).toBe(true)
    })

    it('preserves materials by default', () => {
      const config = getDefaultConfig()
      expect(config.preserveMaterials).toBe(true)
    })
  })

  describe('updateLODConfig', () => {
    it('updates enabled flag', () => {
      const config = getDefaultConfig()
      const updated = updateLODConfig(config, { enabled: false })
      expect(updated.enabled).toBe(false)
    })

    it('preserves levels when not provided', () => {
      const config = getDefaultConfig()
      const updated = updateLODConfig(config, { useEdgeCollapse: false })
      expect(updated.levels).toEqual(config.levels)
      expect(updated.useEdgeCollapse).toBe(false)
    })

    it('replaces levels when provided', () => {
      const config = getDefaultConfig()
      const newLevels = [{ distance: 100, simplificationRatio: 0.3 }]
      const updated = updateLODConfig(config, { levels: newLevels })
      expect(updated.levels).toEqual(newLevels)
    })

    it('returns a new object (immutable)', () => {
      const config = getDefaultConfig()
      const updated = updateLODConfig(config, { enabled: false })
      expect(updated).not.toBe(config)
    })
  })
})
