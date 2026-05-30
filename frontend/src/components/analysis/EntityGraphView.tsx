import { useEffect, useState, useRef, useCallback } from 'react'
import { motion } from 'framer-motion'
import type { EntityGraphResult, EntityNode } from '../../types'
import { fetchEntityGraph } from '../../api'
import AIInterpretBadge from './AIInterpretBadge'

const COLORS: Record<string, string> = {
  person: '#c084fc',
  org: '#60a5fa',
  location: '#34d399',
}

export default function EntityGraphView() {
  const [data, setData] = useState<EntityGraphResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedNode, setSelectedNode] = useState<EntityNode | null>(null)
  const svgRef = useRef<SVGSVGElement>(null)

  useEffect(() => {
    fetchEntityGraph()
      .then(d => { setData(d); setLoading(false) })
      .catch(e => { setError(e instanceof Error ? e.message : '加载失败'); setLoading(false) })
  }, [])

  const nodePositions = useCallback(() => {
    if (!data) return { positions: new Map(), w: 600, h: 400 }
    const positions = new Map<string, { x: number; y: number }>()
    const { nodes } = data
    const cx = 400
    const cy = 300
    const rx = 350
    const ry = 260
    nodes.forEach((n, i) => {
      const angle = (2 * Math.PI * i) / nodes.length - Math.PI / 2
      positions.set(n.id, {
        x: cx + rx * Math.cos(angle),
        y: cy + ry * Math.sin(angle),
      })
    })
    return { positions, w: 800, h: 600 }
  }, [data])

  const { positions, w, h } = nodePositions()

  const maxCount = data ? Math.max(...data.nodes.map(n => n.count), 1) : 1

  if (loading) {
    return (
      <div style={{ padding: 40, textAlign: 'center' }}>
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 1.2, repeat: Infinity, ease: 'linear' }}
          style={{
            width: 20, height: 20, borderRadius: '50%', margin: '0 auto',
            border: '2px solid var(--border-subtle)', borderTopColor: 'var(--accent)',
          }}
        />
      </div>
    )
  }

  if (error) {
    return <div style={{ color: 'var(--danger)', fontSize: 11, textAlign: 'center', padding: 20 }}>{error}</div>
  }

  if (!data || data.nodes.length === 0) {
    return <div style={{ color: 'var(--text-tertiary)', fontSize: 11, textAlign: 'center', padding: 30 }}>暂无实体数据</div>
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10 }}>
        {Object.entries(COLORS).map(([type, color]) => (
          <div key={type} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 9, color: 'var(--text-tertiary)' }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: color }} />
            {{ person: '人物', org: '组织', location: '地点' }[type] ?? type}
          </div>
        ))}
      </div>

      <div style={{ overflow: 'auto', borderRadius: 'var(--radius-md)', background: 'var(--bg-deep)' }}>
        <svg ref={svgRef} width={w} height={h} style={{ display: 'block', minWidth: '100%' }}>
          {/* Edges */}
          {data.edges.map((e, i) => {
            const a = positions.get(e.source)
            const b = positions.get(e.target)
            if (!a || !b) return null
            const opacity = Math.min(0.6, 0.1 + e.weight * 0.05)
            return (
              <line
                key={`e-${i}`}
                x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                stroke="var(--border-subtle)"
                strokeWidth={Math.max(0.5, e.weight * 0.3)}
                opacity={opacity}
              />
            )
          })}
          {/* Nodes */}
          {data.nodes.map((n, i) => {
            const pos = positions.get(n.id)
            if (!pos) return null
            const color = COLORS[n.type] ?? 'var(--text-tertiary)'
            const r = 6 + (n.count / maxCount) * 18
            const isSelected = selectedNode?.id === n.id
            return (
              <motion.g
                key={n.id}
                initial={{ opacity: 0, scale: 0 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: i * 0.02, type: 'spring', stiffness: 100 }}
                style={{ cursor: 'pointer' }}
                onClick={() => setSelectedNode(isSelected ? null : n)}
              >
                <circle cx={pos.x} cy={pos.y} r={r} fill={color} opacity={isSelected ? 0.9 : 0.5} />
                {isSelected && (
                  <circle cx={pos.x} cy={pos.y} r={r + 3} fill="none" stroke={color} strokeWidth={1.5} opacity={0.6} />
                )}
                <text
                  x={pos.x} y={pos.y + r + 11}
                  textAnchor="middle"
                  fill="var(--text-secondary)"
                  fontSize={8}
                  fontFamily="'JetBrains Mono', monospace"
                >
                  {n.label.length > 8 ? n.label.slice(0, 8) + '…' : n.label}
                </text>
              </motion.g>
            )
          })}
        </svg>
      </div>

      {selectedNode && (
        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          style={{
            marginTop: 10, padding: '10px 14px',
            background: 'rgba(0,0,0,0.2)', borderRadius: 'var(--radius-md)',
            border: '1px solid var(--glass-border)',
            fontSize: 11, color: 'var(--text-secondary)',
            display: 'flex', alignItems: 'center', gap: 10,
          }}
        >
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: COLORS[selectedNode.type] ?? 'gray' }} />
          <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{selectedNode.label}</span>
          <span style={{ color: 'var(--text-tertiary)' }}>{{ person: '人物', org: '组织', location: '地点' }[selectedNode.type] ?? selectedNode.type}</span>
          <span style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>提及 {selectedNode.count} 次</span>
        </motion.div>
      )}

      <AIInterpretBadge
        analysisType="entity_graph"
        context={{ node_count: data.nodes.length, edge_count: data.edges.length, top_entities: data.nodes.slice(0, 10).map(n => n.label) }}
      />
    </div>
  )
}
