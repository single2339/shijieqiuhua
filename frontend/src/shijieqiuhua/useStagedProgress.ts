import { useCallback, useEffect, useRef, useState } from 'react'

// The backend runs the prediction synchronously and returns an already-done job,
// so there is no server-side incremental progress to poll. This hook animates the
// five real pipeline stages (核验→采集→归一→打分→研判) on a timer while we wait,
// capping below 100% until the server actually responds — then `finish()` snaps to
// done. The stages are genuine pipeline work; only their timing is estimated.

export interface StagedProgress {
  active: boolean
  phase: string
  progress: number
}

const IDLE: StagedProgress = { active: false, phase: 'queued', progress: 0 }

// phase → target progress %, fired at `at` ms after start. Capped at 92 so the
// bar never claims completion before the real result arrives.
const STAGES: { phase: string; target: number; at: number }[] = [
  { phase: 'verify',    target: 16, at: 0 },
  { phase: 'collect',   target: 52, at: 800 },
  { phase: 'normalize', target: 70, at: 2400 },
  { phase: 'score',     target: 84, at: 3600 },
  { phase: 'report',    target: 92, at: 5000 },
]

export function useStagedProgress() {
  const [staged, setStaged] = useState<StagedProgress>(IDLE)
  const timers = useRef<ReturnType<typeof setTimeout>[]>([])

  const clear = useCallback(() => {
    timers.current.forEach(clearTimeout)
    timers.current = []
  }, [])

  const start = useCallback(() => {
    clear()
    setStaged({ active: true, phase: 'verify', progress: 6 })
    for (const s of STAGES) {
      timers.current.push(setTimeout(() => {
        setStaged(prev => (prev.active ? { active: true, phase: s.phase, progress: s.target } : prev))
      }, s.at))
    }
  }, [clear])

  const finish = useCallback(() => {
    clear()
    setStaged({ active: false, phase: 'done', progress: 100 })
  }, [clear])

  const reset = useCallback(() => { clear(); setStaged(IDLE) }, [clear])

  useEffect(() => clear, [clear])

  return { staged, start, finish, reset }
}
