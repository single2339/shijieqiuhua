import DOMPurify from 'dompurify'
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

// ── HTML generation (download) ──

function renderBlockToHTML(block: Block): string {
  switch (block.type) {
    case 'h2':
      return `<h2 style="font-size:18px;font-weight:700;color:#0d9488;margin:28px 0 12px;padding-bottom:8px;border-bottom:1px solid #e5e7eb;font-family:-apple-system,BlinkMacSystemFont,sans-serif;letter-spacing:-0.01em;">${esc(block.text)}</h2>`
    case 'h3':
      return `<h3 style="font-size:14px;font-weight:600;color:#1f2937;margin:18px 0 8px;padding-left:12px;border-left:3px solid #0d9488;">${esc(block.text)}</h3>`
    case 'list':
      return `<div style="font-size:13px;line-height:1.9;color:#4b5563;margin-bottom:4px;padding-left:4px;display:flex;gap:8px;"><span style="color:#9ca3af;flex-shrink:0;">${/^\d+\./.test(block.text) ? (block.text.match(/^\d+\./)![0]) : '—'}</span><span>${highlightHTML(block.text.replace(/^[-*\d+\.]\s*/, ''))}</span></div>`
    case 'code':
      return `<pre style="margin:10px 0;padding:14px 18px;background:#f3f4f6;border-radius:6px;border:1px solid #e5e7eb;font-family:'JetBrains Mono',monospace;font-size:12px;line-height:1.7;color:#374151;white-space:pre-wrap;word-break:break-word;">${esc(block.text)}</pre>`
    case 'table':
      const headerRow = `<tr style="background:#f9fafb;">${block.headers.map(h => `<th style="padding:8px 14px;text-align:left;font-weight:600;color:#1f2937;font-size:12px;border-bottom:1px solid #e5e7eb;">${esc(h)}</th>`).join('')}</tr>`
      const bodyRows = block.rows.map(row =>
        `<tr>${row.map(cell => `<td style="padding:7px 14px;color:#4b5563;font-size:12px;border-bottom:1px solid #f3f4f6;">${esc(cell)}</td>`).join('')}</tr>`
      ).join('')
      return `<table style="width:100%;border-collapse:collapse;margin:12px 0;border:1px solid #e5e7eb;border-radius:6px;overflow:hidden;font-family:'JetBrains Mono',monospace;font-size:12px;">${headerRow}${bodyRows}</table>`
    default:
      return `<p style="font-size:13px;line-height:2;color:#4b5563;margin-bottom:10px;">${highlightHTML(block.text)}</p>`
  }
}

function esc(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function highlightHTML(text: string): string {
  return text.replace(/\*\*([^*]+)\*\*/g, '<strong style="color:#0d9488;font-weight:700;">$1</strong>')
}

export function generateMarkdown(result: SuperAnalysisResponse): string {
  const lines: string[] = []

  lines.push(`# 超级分析报告`)
  lines.push('')
  lines.push(`**问题**: ${result.question}`)
  if (result.model) lines.push(`**模型**: ${result.model}`)
  lines.push('')

  lines.push(result.analysis)
  lines.push('')

  if (result.web_results.length > 0) {
    lines.push('## 网络搜索参考')
    lines.push('')
    result.web_results.forEach((wr, i) => {
      const label = wr.title || `来源 ${i + 1}`
      lines.push(`- [${label}](${wr.url}): ${wr.snippet}`)
    })
    lines.push('')
  }

  if (result.relevant_items.length > 0) {
    lines.push('## 相关情报项')
    lines.push('')
    result.relevant_items.forEach((item, idx) => {
      lines.push(`### ${idx + 1}. ${item.title}`)
      lines.push('')
      lines.push(`- 来源: ${item.source} | 日期: ${item.date} | 层级: ${item.layer}`)
      lines.push(`- 置信度: ${(item.confidence * 100).toFixed(0)}% | 判定: ${VERDICT_LABELS[item.verdict] ?? item.verdict}`)
      lines.push(`- 先验类别: ${PRIOR_LABELS[item.prior_class] ?? item.prior_class} (${(item.prior_probability * 100).toFixed(0)}%)`)
      if (item.evidence_items.length > 0) {
        lines.push(`- 证据项: ${item.evidence_items.map(e => `${e.name} (LR=${e.lr}, ${e.direction})`).join('; ')}`)
      }
      lines.push(`- 置信度追踪: ${item.bayesian_trace.map(t => t.toFixed(2)).join(' → ')}`)
      lines.push(`- 内容: ${item.content_snippet}`)
      lines.push('')
    })
  }

  return lines.join('\n')
}

export function generateHTML(result: SuperAnalysisResponse): string {
  const blocks = parseAnalysis(result.analysis)
  const bodyBlocks = blocks.map(b => renderBlockToHTML(b)).join('\n')

  const now = new Date().toISOString().slice(0, 19).replace('T', ' ')

  const webResultsHTML = result.web_results.length > 0 ? `
    <h2 style="font-size:18px;font-weight:700;color:#0d9488;margin:32px 0 12px;padding-bottom:8px;border-bottom:1px solid #e5e7eb;font-family:-apple-system,BlinkMacSystemFont,sans-serif;">网络搜索参考</h2>
    ${result.web_results.map(wr => `
      <div style="margin-bottom:8px;font-size:12px;">
        <a href="${esc(wr.url)}" style="color:#0d9488;font-weight:600;text-decoration:none;">${esc(wr.title || '来源')}</a>
        <span style="color:#6b7280;margin-left:4px;">${esc(wr.snippet)}</span>
      </div>
    `).join('\n')}
  ` : ''

  const itemsHTML = result.relevant_items.length > 0 ? `
    <h2 style="font-size:18px;font-weight:700;color:#0d9488;margin:32px 0 12px;padding-bottom:8px;border-bottom:1px solid #e5e7eb;font-family:-apple-system,BlinkMacSystemFont,sans-serif;">相关情报项</h2>
    ${result.relevant_items.map((item, idx) => `
      <div style="margin-bottom:18px;padding:14px 16px;background:#f9fafb;border-radius:8px;border:1px solid #e5e7eb;">
        <h3 style="font-size:14px;font-weight:600;color:#1f2937;margin:0 0 8px;">${idx + 1}. ${esc(item.title)}</h3>
        <div style="font-size:12px;color:#6b7280;margin-bottom:6px;">
          来源: ${esc(item.source)} | 日期: ${esc(item.date)} | 层级: ${esc(item.layer)}
        </div>
        <div style="font-size:12px;color:#6b7280;margin-bottom:6px;">
          置信度: ${(item.confidence * 100).toFixed(0)}% | 判定: ${VERDICT_LABELS[item.verdict] ?? item.verdict}
        </div>
        <div style="font-size:12px;color:#6b7280;margin-bottom:6px;">
          先验类别: ${PRIOR_LABELS[item.prior_class] ?? item.prior_class} (${(item.prior_probability * 100).toFixed(0)}%)
        </div>
        ${item.evidence_items.length > 0 ? `
          <div style="font-size:12px;color:#6b7280;margin-bottom:6px;">
            证据项: ${item.evidence_items.map(e => esc(`${e.name} (LR=${e.lr}, ${e.direction})`)).join('; ')}
          </div>
        ` : ''}
        <div style="font-size:12px;color:#6b7280;margin-bottom:6px;">
          置信度追踪: ${item.bayesian_trace.map(t => t.toFixed(2)).join(' → ')}
        </div>
        <div style="font-size:12px;color:#4b5563;line-height:1.6;">${esc(item.content_snippet)}</div>
      </div>
    `).join('\n')}
  ` : ''

  const modelSuffix = result.model ? ` &middot; ${esc(result.model)}` : ''
  const raw = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>超级分析报告 — ${esc(result.question.slice(0, 60))}</title>
<style>
  body {
    max-width: 860px; margin: 0 auto; padding: 40px 24px 60px;
    background: #faf9f6; color: #1f2937;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  }
  @media (max-width: 640px) { body { padding: 20px 16px 40px; } }
</style>
</head>
<body>
<h1 style="font-size:22px;font-weight:700;color:#0d9488;margin:0 0 4px;letter-spacing:-0.01em;">超级分析报告</h1>
<div style="font-size:12px;color:#9ca3af;margin-bottom:24px;">
  问题: ${esc(result.question)} &middot; ${now}${modelSuffix}
</div>
<hr style="border:none;border-top:1px solid #e5e7eb;margin-bottom:24px;">
${bodyBlocks}
<hr style="border:none;border-top:1px solid #e5e7eb;margin-top:28px;">
${webResultsHTML}
${itemsHTML}
</body>
</html>`
  return DOMPurify.sanitize(raw)
}
