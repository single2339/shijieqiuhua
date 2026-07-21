import { describe, expect, it } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

const PANEL_PATH = resolve(__dirname, '../src/components/IntelAnalysisPanel.tsx')
const content = readFileSync(PANEL_PATH, 'utf-8')
const eventsContent = readFileSync(resolve(__dirname, '../src/components/analysis/EventClustersView.tsx'), 'utf-8')
const corroborationContent = readFileSync(resolve(__dirname, '../src/components/analysis/CorroborationView.tsx'), 'utf-8')

describe('professional intelligence workflow', () => {
  it('opens on the persisted event view instead of the raw scope overview', () => {
    expect(content).toContain("useState<StepKey>('events')")
  })

  it('uses Chinese terminology for verifiable claims', () => {
    expect(eventsContent).toContain('可验证主张')
    expect(corroborationContent).toContain('可验证主张')
    expect(eventsContent).not.toContain('title="Claim"')
    expect(corroborationContent).not.toContain('label="Claim"')
  })
})
