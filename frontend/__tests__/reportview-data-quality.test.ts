import { describe, expect, it } from 'vitest'
import { dataQualityReasonLabel } from '../src/shijieqiuhua/components/ReportView'

describe('dataQualityReasonLabel', () => {
  it('maps insufficient reason codes to user-facing Chinese copy', () => {
    expect(dataQualityReasonLabel('detail_fixture_unmatched')).toBe('赛前分析源暂未匹配到该场')
    expect(dataQualityReasonLabel('structured_stats_unresolved')).toBe('结构化战绩源未解析到双方近期数据')
  })
})
