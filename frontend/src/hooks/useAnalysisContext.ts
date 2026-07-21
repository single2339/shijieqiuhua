import { useEffect, useMemo, useRef, useState } from 'react'
import { fetchEventClusters, fetchWarningIndicators } from '../api'
import type { EventClusterResult, IntelLayer, WarningIndicatorResult } from '../types'
import { buildAnalysisWindow } from '../utils/analysisWindow'
import { buildItemAnalysisContext } from '../utils/intelDisplay'
import { isAbortError } from '../utils/request'

export function useAnalysisContext(
  selectedDate: string,
  startDate: string,
  endDate: string,
  activeLayers: IntelLayer[],
  enabled = true,
  focusDate = '',
) {
  const [events, setEvents] = useState<EventClusterResult | null>(null)
  const [warnings, setWarnings] = useState<WarningIndicatorResult | null>(null)
  const [loading, setLoading] = useState(false)
  const requestGenerationRef = useRef(0)
  const layersKey = activeLayers.join(',')
  const analysisWindow = buildAnalysisWindow({ selectedDate, startDate, endDate, focusDate })

  useEffect(() => {
    const requestGeneration = ++requestGenerationRef.current
    const controller = new AbortController()
    if (!enabled) {
      setLoading(false)
      return () => controller.abort()
    }
    setLoading(true)
    Promise.all([
      fetchEventClusters({ startDate: analysisWindow.startDate, endDate: analysisWindow.endDate, layers: activeLayers }, controller.signal),
      fetchWarningIndicators({ startDate: analysisWindow.startDate, endDate: analysisWindow.endDate, layers: activeLayers }, controller.signal),
    ])
      .then(([eventData, warningData]) => {
        if (controller.signal.aborted || requestGeneration !== requestGenerationRef.current) return
        setEvents(eventData)
        setWarnings(warningData)
      })
      .catch(error => {
        if (isAbortError(error) || requestGeneration !== requestGenerationRef.current) return
        setEvents(null)
        setWarnings(null)
      })
      .finally(() => {
        if (!controller.signal.aborted && requestGeneration === requestGenerationRef.current) setLoading(false)
      })
    return () => controller.abort()
  }, [analysisWindow.startDate, analysisWindow.endDate, layersKey, enabled])

  const itemContext = useMemo(() => buildItemAnalysisContext(events, warnings), [events, warnings])

  return {
    events,
    warnings,
    itemContext,
    loading,
  }
}
