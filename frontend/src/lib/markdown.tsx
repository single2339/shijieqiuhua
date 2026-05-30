import type { SuperAnalysisResponse } from '../types'

// ── Shared constants ──

export const PRIOR_LABELS: Record<string, string> = {
  'high-credibility': '高可信',
  'medium-credibility': '中可信',
  'low-credibility': '低可信',
  kol: 'KOL',
  unknown: '未知',
}

export const PRIOR_COLORS: Record<string, string> = {
  'high-credibility': '#10b981',
  'medium-credibility': '#3b82f6',
  'low-credibility': '#f59e0b',
  kol: '#8b5cf6',
  unknown: '#6b7280',
}

export const VERDICT_COLORS: Record<string, string> = {
  verified: '#10b981',
  false: '#f87171',
  uncertain: '#fbbf24',
}

export const VERDICT_LABELS: Record<string, string> = {
  verified: '已核实',
  false: '不实',
  uncertain: '不确定',
}

// ── Types ──

export type Block =
  | { type: 'h2'; text: string }
  | { type: 'h3'; text: string }
  | { type: 'p'; text: string }
  | { type: 'list'; text: string }
  | { type: 'code'; text: string }
  | { type: 'table'; headers: string[]; rows: string[][] }

// ── Markdown parsing ──

export function parseAnalysis(md: string): Block[] {
  const blocks: Block[] = []
  const lines = md.split('\n')
  let i = 0

  while (i < lines.length) {
    const line = lines[i]

    if (line.startsWith('```')) {
      const codeLines: string[] = []
      i++
      while (i < lines.length && !lines[i].startsWith('```')) {
        codeLines.push(lines[i])
        i++
      }
      i++
      if (codeLines.length > 0) {
        blocks.push({ type: 'code', text: codeLines.join('\n') })
      }
      continue
    }

    if (line.includes('|') && line.trim().startsWith('|')) {
      const headerLine = line
      if (i + 1 < lines.length && lines[i + 1].includes('---') && lines[i + 1].includes('|')) {
        const headers = headerLine.split('|').map(h => h.trim()).filter(Boolean)
        const rows: string[][] = []
        i += 2
        while (i < lines.length && lines[i].includes('|') && lines[i].trim().startsWith('|')) {
          rows.push(lines[i].split('|').map(c => c.trim()).filter(Boolean))
          i++
        }
        if (headers.length > 0) {
          blocks.push({ type: 'table', headers, rows })
        }
        continue
      }
    }

    if (/^##\s/.test(line)) {
      blocks.push({ type: 'h2', text: line.replace(/^##\s+/, '') })
    } else if (/^###\s/.test(line)) {
      blocks.push({ type: 'h3', text: line.replace(/^###\s+/, '') })
    } else if (/^[-*]\s/.test(line) || /^\d+\.\s/.test(line)) {
      blocks.push({ type: 'list', text: line })
    } else if (line.trim()) {
      blocks.push({ type: 'p', text: line })
    }
    i++
  }

  return blocks
}

export function highlightText(text: string): React.ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*)/g)
  return parts.map((part, idx) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={idx} style={{ color: 'var(--accent)', fontWeight: 700 }}>{part.slice(2, -2)}</strong>
    }
    return <span key={idx}>{part}</span>
  })
}

// ── Markdown generation (download) ──

export function generateMarkdown(result: SuperAnalysisResponse): string {
  const lines: string[] = []
  lines.push('# 超级分析报告')
  lines.push(`\n**问题**: ${result.question}`)
  lines.push(`**生成时间**: ${new Date().toISOString().slice(0, 19).replace('T', ' ')}`)
  lines.push(`**模型**: ${result.model}`)
  lines.push('\n---\n')
  lines.push(result.analysis)
  lines.push('\n---\n')

  if (result.web_results.length > 0) {
    lines.push('## 网络搜索参考\n')
    result.web_results.forEach((wr, idx) => {
      lines.push(`- [${wr.title || `来源 ${idx + 1}`}](${wr.url}): ${wr.snippet}`)
    })
    lines.push('')
  }

  if (result.relevant_items.length > 0) {
    lines.push('## 相关情报项\n')
    result.relevant_items.forEach((item, idx) => {
      const traceDisplay = item.bayesian_trace.map(t => t.toFixed(2)).join(' → ')
      lines.push(`### ${idx + 1}. ${item.title}`)
      lines.push(`- **来源**: ${item.source} | **日期**: ${item.date} | **层级**: ${item.layer}`)
      lines.push(`- **置信度**: ${(item.confidence * 100).toFixed(0)}% | **判定**: ${VERDICT_LABELS[item.verdict] ?? item.verdict}`)
      lines.push(`- **先验类别**: ${PRIOR_LABELS[item.prior_class] ?? item.prior_class} (${(item.prior_probability * 100).toFixed(0)}%)`)
      if (item.evidence_items.length > 0) {
        lines.push(`- **证据项**: ${item.evidence_items.map(e => `${e.name} (LR=${e.lr}, ${e.direction})`).join('; ')}`)
      }
      lines.push(`- **置信度追踪**: ${traceDisplay}`)
      lines.push(`- **内容摘要**: ${item.content_snippet}`)
      lines.push('')
    })
  }

  return lines.join('\n')
}
