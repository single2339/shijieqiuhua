import type { SuperAnalysisResponse } from '../types'
import { safeExternalUrl } from '../utils/safeUrl'


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
      while (i < lines.length && !lines[i].startsWith('```') && codeLines.length < 50) {
        if (/^(#{2,3})\s/.test(lines[i]) || /^\*\*第\d+步/.test(lines[i])) {
          break
        }
        codeLines.push(lines[i])
        i++
      }
      if (i < lines.length && lines[i].startsWith('```')) {
        i++
      }
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
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function highlightHTML(text: string): string {
  return text
    .split(/(\*\*[^*]+\*\*)/g)
    .map(part => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return `<strong style="color:#0d9488;font-weight:700;">${esc(part.slice(2, -2))}</strong>`
      }
      return esc(part)
    })
    .join('')
}

export function generateMarkdown(result: SuperAnalysisResponse): string {
  const lines: string[] = []

  lines.push(`# 超级分析报告`)
  lines.push('')
  lines.push(`**问题**: ${result.question}`)
  if (result.model) lines.push(`**模型**: ${result.model}`)
  lines.push('')
  lines.push('## 执行状态')
  lines.push('')
  lines.push(`- 采集状态: ${result.collection_status}`)
  lines.push(`- 分析状态: ${result.analysis_status}`)
  lines.push(`- 降级: ${result.degraded ? '是' : '否'}`)
  const providers = Object.entries(result.provider_statuses)
    .map(([provider, status]) => `${provider}=${status}`)
    .join(', ')
  if (providers) lines.push(`- 数据源: ${providers}`)
  result.errors.forEach(error => lines.push(`- 错误: ${error}`))
  lines.push('')

  if (result.hypothesis_assessment) {
    const assessment = result.hypothesis_assessment
    lines.push('## 结构化假设评估')
    lines.push('')
    lines.push(`- 假设: ${assessment.hypothesis}`)
    lines.push(`- 先验概率: ${Math.round(assessment.prior_probability * 100)}%`)
    lines.push(`- 后验概率: ${Math.round(assessment.posterior_probability * 100)}%`)
    lines.push(`- 判定: ${assessment.verdict}`)
    lines.push(`- 置信等级: ${assessment.confidence_level}`)
    lines.push(`- 独立证据源: ${assessment.independent_source_count}`)
    lines.push('')
    if (assessment.evidence.length > 0) {
      lines.push('| 证据ID | 来源 | 关系 | 强度 | LR | 后验 | 理由 |')
      lines.push('|---|---|---|---|---:|---:|---|')
      assessment.evidence.forEach(evidence => {
        lines.push(
          `| ${evidence.evidence_id} | ${evidence.source} | ${evidence.relation} | ${evidence.strength} | ${evidence.likelihood_ratio} | ${Math.round(evidence.posterior_probability * 100)}% | ${evidence.rationale} |`,
        )
      })
      lines.push('')
    }
  }

  lines.push(result.analysis)
  lines.push('')

  if (result.web_results.length > 0) {
    lines.push('## 网络搜索摘要（未验证）')
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
      lines.push(`- 聚合独立来源: ${item.independent_source_count} | 文档质量: ${Math.round(item.quality_score * 100)}%`)
      lines.push(`- 来源类别: ${item.source_class}`)
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
  const providerSummary = Object.entries(result.provider_statuses)
    .map(([provider, status]) => `${provider}=${status}`)
    .join(', ')
  const statusHTML = `
    <h2 style="font-size:18px;font-weight:700;color:#0d9488;margin:24px 0 12px;">执行状态</h2>
    <div style="font-size:12px;color:#6b7280;line-height:1.7;">
      采集状态: ${esc(result.collection_status)}<br>
      分析状态: ${esc(result.analysis_status)}<br>
      降级: ${result.degraded ? '是' : '否'}
      ${providerSummary ? `<br>数据源: ${esc(providerSummary)}` : ''}
      ${result.errors.map(error => `<br>错误: ${esc(error)}`).join('')}
    </div>
  `
  const hypothesisHTML = result.hypothesis_assessment ? (() => {
    const assessment = result.hypothesis_assessment
    const rows = assessment.evidence.map(evidence => `
      <tr>
        <td>${esc(evidence.evidence_id)}</td>
        <td>${esc(evidence.source)}</td>
        <td>${esc(evidence.relation)}</td>
        <td>${esc(evidence.strength)}</td>
        <td>${evidence.likelihood_ratio}</td>
        <td>${Math.round(evidence.posterior_probability * 100)}%</td>
        <td>${esc(evidence.rationale)}</td>
      </tr>
    `).join('')
    return `
      <h2 style="font-size:18px;font-weight:700;color:#0d9488;margin:32px 0 12px;">结构化假设评估</h2>
      <div style="font-size:12px;color:#4b5563;line-height:1.7;">
        <strong>假设:</strong> ${esc(assessment.hypothesis)}<br>
        <strong>先验:</strong> ${Math.round(assessment.prior_probability * 100)}% &middot;
        <strong>后验:</strong> ${Math.round(assessment.posterior_probability * 100)}% &middot;
        <strong>判定:</strong> ${esc(assessment.verdict)} &middot;
        <strong>置信等级:</strong> ${esc(assessment.confidence_level)} &middot;
        <strong>独立证据源:</strong> ${assessment.independent_source_count}
      </div>
      ${rows ? `
        <table style="width:100%;border-collapse:collapse;margin-top:12px;font-size:11px;">
          <thead><tr><th>证据ID</th><th>来源</th><th>关系</th><th>强度</th><th>LR</th><th>后验</th><th>理由</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      ` : ''}
    `
  })() : ''

  const webResultsHTML = result.web_results.length > 0 ? `
    <h2 style="font-size:18px;font-weight:700;color:#0d9488;margin:32px 0 12px;padding-bottom:8px;border-bottom:1px solid #e5e7eb;font-family:-apple-system,BlinkMacSystemFont,sans-serif;">网络搜索摘要（未验证）</h2>
    ${result.web_results.map(wr => `
      <div style="margin-bottom:8px;font-size:12px;">
        <a href="${esc(safeExternalUrl(wr.url) ?? '')}" style="color:#0d9488;font-weight:600;text-decoration:none;">${esc(wr.title || '来源')}</a>
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
          聚合独立来源: ${item.independent_source_count} | 文档质量: ${Math.round(item.quality_score * 100)}%
        </div>
        <div style="font-size:12px;color:#6b7280;margin-bottom:6px;">
          来源类别: ${esc(item.source_class)}
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
${statusHTML}
${hypothesisHTML}
${bodyBlocks}
<hr style="border:none;border-top:1px solid #e5e7eb;margin-top:28px;">
${webResultsHTML}
${itemsHTML}
</body>
</html>`
  return raw
}
