import { CheckCircle, Circle, MagnifyingGlass, SpinnerGap } from '@phosphor-icons/react'
import { motion } from 'framer-motion'
import type { FootballOsintJob } from '../types'

// ── mapping from backend phase to visual step index ──
const PHASE_ORDER = ['queued', 'verify', 'collect', 'normalize', 'score', 'report', 'done']
const VISUAL_STEPS = [
  { key: 'verify',    label: '核验', desc: '确认比赛主体、时间、场地' },
  { key: 'collect',   label: '采集', desc: '多源情报抓取与去重' },
  { key: 'normalize', label: '归一', desc: '翻译、结构化、时效评分' },
  { key: 'score',     label: '打分', desc: '因子加权、贝叶斯更新' },
  { key: 'report',    label: '研判', desc: '生成结论与置信度' },
]

function activeStepIdx(phase: string): number {
  if (phase === 'done') return VISUAL_STEPS.length
  const idx = PHASE_ORDER.indexOf(phase)
  if (idx < 0) return 0
  // Map backend phases to visual steps
  if (phase === 'queued') return 0
  if (phase === 'verify') return 0   // same visual step as verify
  if (phase === 'collect') return 1
  if (phase === 'normalize') return 2
  if (phase === 'score') return 3
  if (phase === 'report') return 4
  return idx > 0 ? Math.min(idx - 1, VISUAL_STEPS.length) : 0
}

// ── public API ──

const SRC_STATUS: Record<string, { label: string; cls: string }> = {
  ok:      { label: '命中', cls: 'sqh-tag--ok' },
  skipped: { label: '跳过', cls: 'sqh-tag--mute' },
  failed:  { label: '失败', cls: 'sqh-tag--warn' },
}

interface PhaseTrackerProps {
  phase: string
  progress: number
  sources?: FootballOsintJob['sources']
}

export default function PhaseTracker({ phase, progress, sources }: PhaseTrackerProps) {
  const stepIdx = activeStepIdx(phase)
  const isDone = phase === 'done'

  return (
    <motion.div
      className="sqh-tracker"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.2, 0.7, 0.3, 1] }}
    >
      {/* head */}
      <div className="sqh-tracker-head">
        <div className="sqh-section-title">
          <MagnifyingGlass size={15} weight="duotone" />
          <span>{isDone ? '一轮研判完成，输出结果' : '情报研判进行中'}</span>
        </div>
        <span className="sqh-tracker-pct">{progress}%</span>
      </div>

      {/* phase rail */}
      <div className="sqh-phase-rail">
        {VISUAL_STEPS.map((step, i) => {
          const state = i < stepIdx ? 'done' : i === stepIdx ? 'active' : 'todo'
          return (
            <div className={`sqh-phase sqh-phase--${state}`} key={step.key}>
              <div className="sqh-phase-node">
                <span className="sqh-phase-bead">
                  {state === 'done' ? <CheckCircle size={14} weight="fill" />
                    : state === 'active' ? <SpinnerGap size={14} weight="bold" className="sqh-phase-spin" />
                    : <span className="sqh-phase-no">{i + 1}</span>}
                </span>
                <span className="sqh-phase-label">{step.label}</span>
                {i < VISUAL_STEPS.length - 1 && (
                  <span className={`sqh-phase-line sqh-phase-line--${state}`} />
                )}
              </div>
            </div>
          )
        })}
      </div>

      {/* progress bar */}
      <div className="sqh-tracker-bar">
        <i style={{ width: `${progress}%` }} />
      </div>

      {/* source feed */}
      {sources && sources.length > 0 && (
        <div className="sqh-tracker-feed">
          {sources.map((s, i) => {
            const meta = SRC_STATUS[s.status] || SRC_STATUS.failed
            return (
              <motion.div
                className="sqh-tracker-item"
                key={s.adapter + i}
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.06, duration: 0.22 }}
              >
                {s.status === 'ok' ? <CheckCircle size={13} weight="fill" />
                  : <Circle size={13} weight="bold" />}
                <span className="sqh-tracker-src">{s.label}</span>
                <span className="sqh-tracker-why">{s.reason}</span>
                <span className={`sqh-tag ${meta.cls}`}>{meta.label}</span>
              </motion.div>
            )
          })}
        </div>
      )}
    </motion.div>
  )
}
