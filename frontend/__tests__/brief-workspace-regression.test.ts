import { describe, expect, test } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

const reportPanelContent = readFileSync(resolve(__dirname, '../src/components/ReportPanel.tsx'), 'utf-8')
const typesContent = readFileSync(resolve(__dirname, '../src/types.ts'), 'utf-8')

describe('brief workspace integration', () => {
  test('report panel is a workspace, not a standalone generator', () => {
    expect(reportPanelContent).toContain('简报工作台')
    expect(reportPanelContent).toContain('候选材料')
    expect(reportPanelContent).toContain('草稿')
    expect(reportPanelContent).toContain('历史')
    expect(reportPanelContent).toContain('导出 Markdown')
    expect(reportPanelContent).toContain('导出 HTML')
  })

  test('brief workspace material is part of the shared type contract', () => {
    expect(typesContent).toContain('BriefWorkspaceMaterial')
    expect(typesContent).toContain('BriefWorkspace')
    expect(typesContent).toContain('source_materials?: BriefWorkspaceMaterial[]')
  })
})
