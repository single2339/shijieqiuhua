import { describe, expect, test } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

const appContent = readFileSync(resolve(__dirname, '../src/App.tsx'), 'utf-8')
const cardContent = readFileSync(resolve(__dirname, '../src/components/IntelCard.tsx'), 'utf-8')
const panelContent = readFileSync(resolve(__dirname, '../src/components/IntelAnalysisPanel.tsx'), 'utf-8')
const situationBriefContent = readFileSync(resolve(__dirname, '../src/components/analysis/SituationBriefView.tsx'), 'utf-8')
const warningContent = readFileSync(resolve(__dirname, '../src/components/analysis/WarningIndicatorsView.tsx'), 'utf-8')

describe('single intel item to analysis workflow linkage', () => {
  test('intel card exposes an action to analyze this item', () => {
    expect(cardContent).toContain('onAnalyzeItem')
    expect(cardContent).toContain('按此情报分析')
  })

  test('intel card exposes an action to add this item to brief candidates', () => {
    expect(cardContent).toContain('onAddToBrief')
    expect(cardContent).toContain('加入简报候选')
  })

  test('app stores item analysis focus and passes it to the analysis panel', () => {
    expect(appContent).toContain('analysisFocus')
    expect(appContent).toContain('setAnalysisFocus')
    expect(appContent).toContain('focusItem={analysisFocus?.item ?? null}')
  })

  test('app stores a brief workspace and passes it through card analysis and report panels', () => {
    expect(appContent).toContain('briefWorkspace')
    expect(appContent).toContain('addBriefMaterial')
    expect(appContent).toContain('workspace={briefWorkspace}')
    expect(appContent).toContain('onAddToBrief={addBriefMaterial}')
  })

  test('analysis panel accepts a focused item and renders single-item scope text', () => {
    expect(panelContent).toContain('focusItem')
    expect(panelContent).toContain('单条情报')
    expect(panelContent).toContain('focusEventId')
  })

  test('analysis panel can send selected workflow material to the brief workspace', () => {
    expect(panelContent).toContain('onAddToBrief')
    expect(panelContent).toContain('将该事件加入简报')
    expect(situationBriefContent).toContain('将判断加入简报')
    expect(warningContent).toContain('将预警加入简报')
  })
})
