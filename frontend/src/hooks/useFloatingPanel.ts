import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { CSSProperties, PointerEvent as ReactPointerEvent } from 'react'

interface FloatingPanelOptions {
  enabled: boolean
  width: number
  height: number
  margin?: number
  anchor?: 'bottom-center' | 'right'
}

interface Position {
  x: number
  y: number
}

interface DragState {
  pointerId: number
  offsetX: number
  offsetY: number
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
}

function clampPosition(pos: Position, width: number, height: number, margin: number): Position {
  if (typeof window === 'undefined') return pos
  const effectiveWidth = Math.min(width, window.innerWidth - margin * 2)
  const effectiveHeight = Math.min(height, window.innerHeight - margin * 2)
  return {
    x: clamp(pos.x, margin, Math.max(margin, window.innerWidth - effectiveWidth - margin)),
    y: clamp(pos.y, margin, Math.max(margin, window.innerHeight - effectiveHeight - margin)),
  }
}

export function useFloatingPanel({
  enabled,
  width,
  height,
  margin = 16,
  anchor = 'bottom-center',
}: FloatingPanelOptions) {
  const dragRef = useRef<DragState | null>(null)
  const [position, setPosition] = useState<Position | null>(null)

  const initialPosition = useCallback((): Position => {
    if (typeof window === 'undefined') return { x: margin, y: margin }
    const x = anchor === 'right'
      ? window.innerWidth - width - Math.max(20, window.innerWidth * 0.04)
      : (window.innerWidth - width) / 2
    const y = anchor === 'right' ? 56 : window.innerHeight - height - margin
    return clampPosition({ x, y }, width, height, margin)
  }, [anchor, height, margin, width])

  useEffect(() => {
    if (!enabled) return
    setPosition(initialPosition())

    const handleResize = () => {
      setPosition(prev => clampPosition(prev ?? initialPosition(), width, height, margin))
    }
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [enabled, height, initialPosition, margin, width])

  const onPointerDown = useCallback((event: ReactPointerEvent<HTMLElement>) => {
    if (!enabled || event.button !== 0) return
    const target = event.target as HTMLElement
    if (target.closest('button, input, select, textarea, a')) return

    const current = position ?? initialPosition()
    dragRef.current = {
      pointerId: event.pointerId,
      offsetX: event.clientX - current.x,
      offsetY: event.clientY - current.y,
    }
    event.currentTarget.setPointerCapture(event.pointerId)
    event.preventDefault()
  }, [enabled, initialPosition, position])

  const onPointerMove = useCallback((event: ReactPointerEvent<HTMLElement>) => {
    const drag = dragRef.current
    if (!drag || drag.pointerId !== event.pointerId) return
    setPosition(clampPosition({
      x: event.clientX - drag.offsetX,
      y: event.clientY - drag.offsetY,
    }, width, height, margin))
  }, [height, margin, width])

  const onPointerUp = useCallback((event: ReactPointerEvent<HTMLElement>) => {
    const drag = dragRef.current
    if (!drag || drag.pointerId !== event.pointerId) return
    dragRef.current = null
    event.currentTarget.releasePointerCapture(event.pointerId)
  }, [])

  const panelStyle = useMemo<CSSProperties>(() => {
    if (!enabled || !position) return {}
    return {
      left: position.x,
      top: position.y,
      right: 'auto',
      bottom: 'auto',
      transform: 'none',
    }
  }, [enabled, position])

  const dragHandleProps = enabled ? {
    onPointerDown,
    onPointerMove,
    onPointerUp,
    onPointerCancel: onPointerUp,
  } : {}

  const dragHandleStyle = enabled ? {
    cursor: dragRef.current ? 'grabbing' : 'grab',
    touchAction: 'none',
    userSelect: 'none',
  } satisfies CSSProperties : {}

  return { panelStyle, dragHandleProps, dragHandleStyle }
}
