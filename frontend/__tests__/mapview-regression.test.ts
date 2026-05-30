import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

const MAPVIEW_PATH = resolve(__dirname, '../src/components/MapView.tsx')
const content = readFileSync(MAPVIEW_PATH, 'utf-8')

describe('MapView.tsx — MapLibre paint validation', () => {
  // BUG-R1: MapLibre GL paint and layout properties do NOT support CSS var(--...) syntax.
  // They require concrete hex/rgba values. Using CSS variables silently fails at runtime:
  //   Error: layers.clusters.paint.circle-color: color expected, "var(--bg-panel)" found
  it('paint properties use concrete hex values, not CSS variables (BUG-R1 regression)', () => {
    // Extract all paint property values (string literals inside paint: { ... })
    // Look for 'circle-color', 'circle-stroke-color', 'text-color', 'text-halo-color' etc.
    const paintVars = content.match(/'circle-color':\s*'[^']+'/g) || []
    const strokeVars = content.match(/'circle-stroke-color':\s*'[^']+'/g) || []
    const textColors = content.match(/'text-color':\s*'[^']+'/g) || []
    const haloColors = content.match(/'text-halo-color':\s*'[^']+'/g) || []

    const allPaintProps = [...paintVars, ...strokeVars, ...textColors, ...haloColors]

    // Each paint property value must NOT contain var(--...
    for (const prop of allPaintProps) {
      expect(prop).not.toMatch(/var\(--/)
    }
  })

  it('all MapLibre paint color values are valid hex (BUG-R1 regression)', () => {
    const hexPattern = /'(?:circle-color|circle-stroke-color|text-color|text-halo-color)':\s*'([^']+)'/g
    let match
    while ((match = hexPattern.exec(content)) !== null) {
      const value = match[1]
      // Must be hex: #xxx or #xxxxxx
      expect(value).toMatch(/^#[0-9a-fA-F]{3,8}$/)
    }
  })
})
