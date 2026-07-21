const DEFAULT_ANALYSIS_WINDOW_DAYS = 14

function shiftDate(date: string, deltaDays: number): string {
  const parsed = new Date(`${date}T00:00:00Z`)
  parsed.setUTCDate(parsed.getUTCDate() + deltaDays)
  return parsed.toISOString().slice(0, 10)
}

export interface AnalysisWindow {
  startDate: string
  endDate: string
  label: string
  isExplicit: boolean
}

export function buildAnalysisWindow(params: {
  selectedDate: string
  startDate?: string
  endDate?: string
  focusDate?: string
  days?: number
}): AnalysisWindow {
  const explicitStart = params.startDate || ''
  const explicitEnd = params.endDate || ''
  const endDate = explicitEnd || params.focusDate || params.selectedDate
  const days = params.days ?? DEFAULT_ANALYSIS_WINDOW_DAYS
  const startDate = explicitStart || shiftDate(endDate, -(days - 1))
  const isExplicit = Boolean(explicitStart || explicitEnd)

  return {
    startDate,
    endDate,
    label: `${startDate} → ${endDate}`,
    isExplicit,
  }
}
