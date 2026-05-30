import { describe, test, expect } from 'vitest'
import { LAYER_META } from '../src/types'
import type { IntelLayer } from '../src/types'

const ALL_LAYERS: IntelLayer[] = ['nature', 'economy', 'finance', 'politics', 'military', 'aviation', 'technology', 'society', 'energy', 'agriculture', 'health', 'cyber']

describe('LAYER_META', () => {
  test('has all 12 IntelLayer entries', () => {
    expect(Object.keys(LAYER_META)).toHaveLength(12)
  })

  test('every layer has a non-empty label and valid hex color', () => {
    for (const layer of ALL_LAYERS) {
      const meta = LAYER_META[layer]
      expect(meta, `missing meta for ${layer}`).toBeDefined()
      expect(meta.label.length, `label empty for ${layer}`).toBeGreaterThan(0)
      expect(meta.color, `color invalid for ${layer}`).toMatch(/^#[0-9a-fA-F]{6}$/)
    }
  })

  test('all colors are unique across layers', () => {
    const colors = ALL_LAYERS.map(l => LAYER_META[l].color)
    expect(new Set(colors).size).toBe(colors.length)
  })

  test('all labels are unique across layers', () => {
    const labels = ALL_LAYERS.map(l => LAYER_META[l].label)
    expect(new Set(labels).size).toBe(labels.length)
  })

  test('TypeScript IntelLayer union matches LAYER_META keys exactly', () => {
    const metaKeys = Object.keys(LAYER_META) as IntelLayer[]
    metaKeys.sort()
    const sorted = [...ALL_LAYERS].sort()
    expect(metaKeys).toEqual(sorted)
  })
})
