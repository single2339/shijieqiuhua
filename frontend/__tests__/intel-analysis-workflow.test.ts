import { describe, expect, test } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

const PANEL_PATH = resolve(__dirname, '../src/components/IntelAnalysisPanel.tsx')
const content = readFileSync(PANEL_PATH, 'utf-8')

describe('IntelAnalysisPanel workflow navigation', () => {
  test('uses an intelligence-cycle workflow instead of standalone chart modules', () => {
    for (const label of ['研判范围', '事件核查', '证据评估', '态势研判', '预警指标']) {
      expect(content).toContain(`label: '${label}'`)
    }

    for (const removedLabel of ['时间线', '关联网络', '交叉信源', '异常检测', '风险热力', '情报缺口']) {
      expect(content).not.toContain(`label: '${removedLabel}'`)
    }
  })
})
