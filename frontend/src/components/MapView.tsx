import { useEffect, useRef, useState, useCallback } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import type { IntelItem } from '../types'
import { LAYER_META } from '../types'
import { safeExternalUrl } from '../utils/safeUrl'

const TIANDITU_KEY = import.meta.env.VITE_TIANDITU_KEY as string | undefined
const HAS_TIANDITU = Boolean(TIANDITU_KEY)
const TIANDITU_URL = safeExternalUrl('https://www.tianditu.gov.cn/') ?? ''
const TIANDITU_ATTRIBUTION = `&copy; <a href="${TIANDITU_URL}">天地图</a>`

type TileSource = 'carto' | 'tianditu'

const CARTODB_STYLE = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json'

function tiandituStyle(key: string) {
  const tileUrl = (sub: number, layer: string) =>
    `https://t${sub}.tianditu.gov.cn/${layer}_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=${layer}&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&tk=${key}`
  return {
    version: 8,
    sources: {
      tdt: {
        type: 'raster' as const,
        tiles: Array.from({ length: 8 }, (_, i) => tileUrl(i, 'vec')),
        tileSize: 256,
        attribution: TIANDITU_ATTRIBUTION,
      },
      tdt_label: {
        type: 'raster' as const,
        tiles: Array.from({ length: 8 }, (_, i) => tileUrl(i, 'cva')),
        tileSize: 256,
        attribution: TIANDITU_ATTRIBUTION,
      },
    },
    layers: [
      { id: 'tdt-base', type: 'raster' as const, source: 'tdt', minzoom: 0, maxzoom: 18 },
      { id: 'tdt-label', type: 'raster' as const, source: 'tdt_label', minzoom: 4, maxzoom: 18 },
    ],
    glyphs: 'https://fonts.openmaptiles.org/{fontstack}/{range}.pbf',
  }
}

interface Props { items: IntelItem[]; onSelect: (item: IntelItem) => void }

/** Spread items at the same (lat,lng) with natural-looking random scatter so every pin is visible and clickable. */
function spiderfy(items: IntelItem[]): Array<{ id: string; layer: string; lng: number; lat: number }> {
  // Deterministic seed per item so positions are stable across re-renders
  let seed = 42
  function nextRand(): number {
    seed = (seed * 1664525 + 1013904223) & 0x7fffffff
    return seed / 0x7fffffff
  }

  const groups = new Map<string, IntelItem[]>()
  for (const item of items) {
    const key = `${item.location.lat.toFixed(4)}:${item.location.lng.toFixed(4)}`
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key)!.push(item)
  }

  const out: Array<{ id: string; layer: string; lng: number; lat: number }> = []
  for (const [, group] of groups) {
    const count = group.length
    if (count === 1) {
      const { lat, lng } = group[0].location
      out.push({ id: group[0].id, layer: group[0].layer, lng, lat })
    } else {
      // Perturb seed per group for variance across groups
      seed = count * 7919 + group[0].location.lat * 100
      for (const item of group) {
        const { lat: baseLat, lng: baseLng } = item.location
        const angle = nextRand() * Math.PI * 2
        // Use larger radius for more items so they don't overlap each other
        const radius = 0.02 + nextRand() * Math.min(0.08, 0.02 + count * 0.008)
        const latOffset = radius * Math.cos(angle)
        const lngOffset = radius * Math.sin(angle) / Math.cos((baseLat * Math.PI) / 180)
        out.push({ id: item.id, layer: item.layer, lng: baseLng + lngOffset, lat: baseLat + latOffset })
      }
    }
  }
  return out
}

function createPinImage(color: string): ImageData {
  const c = document.createElement('canvas')
  c.width = 34; c.height = 44
  const ctx = c.getContext('2d')!
  ctx.beginPath()
  ctx.arc(17, 14, 14, 0, Math.PI * 2)
  ctx.fillStyle = color + '30'
  ctx.fill()
  ctx.beginPath()
  ctx.arc(17, 12, 9, 0, Math.PI, false)
  ctx.lineTo(17, 38)
  ctx.closePath()
  ctx.fillStyle = color
  ctx.fill()
  ctx.strokeStyle = '#121416'
  ctx.lineWidth = 1.5
  ctx.stroke()
  ctx.beginPath()
  ctx.arc(17, 12, 2.5, 0, Math.PI * 2)
  ctx.fillStyle = '#f2eee6'
  ctx.fill()
  return ctx.getImageData(0, 0, 34, 44)
}

export default function MapView({ items, onSelect }: Props) {
  const container = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const itemsRef = useRef(items)
  itemsRef.current = items
  const onSelectRef = useRef(onSelect)
  onSelectRef.current = onSelect
  const initDone = useRef(false)
  const handlersBound = useRef(false)
  const [styleKey, setStyleKey] = useState<TileSource>(HAS_TIANDITU ? 'tianditu' : 'carto')

  function setupIntelLayers(map: maplibregl.Map) {
    // Register pin images (persist across setStyle but check anyway)
    for (const [layer, meta] of Object.entries(LAYER_META)) {
      if (!map.hasImage(`pin-${layer}`)) {
        map.addImage(`pin-${layer}`, createPinImage(meta.color))
      }
    }

    // Add source if fresh (first load or after setStyle clears it)
    if (!map.getSource('intel-points')) {
      map.addSource('intel-points', {
        type: 'geojson', cluster: true, clusterMaxZoom: 8, clusterRadius: 45,
        data: { type: 'FeatureCollection', features: [] },
      })
    }

    // Add layers idempotently
    const layers: Array<maplibregl.AddLayerObject> = [
      {
        id: 'point-glow', type: 'circle', source: 'intel-points',
        filter: ['!', ['has', 'point_count']],
        paint: {
          'circle-radius': 14,
          'circle-color': ['match', ['get', 'layer'],
            'nature', LAYER_META.nature.color, 'economy', LAYER_META.economy.color,
            'finance', LAYER_META.finance.color, 'politics', LAYER_META.politics.color,
            'military', LAYER_META.military.color, 'aviation', LAYER_META.aviation.color,
            'technology', LAYER_META.technology.color, 'society', LAYER_META.society.color,
            'energy', LAYER_META.energy.color, 'agriculture', LAYER_META.agriculture.color,
            'health', LAYER_META.health.color, 'cyber', LAYER_META.cyber.color, '#c8a45d'],
          'circle-opacity': 0.18, 'circle-blur': 1.8,
        },
      },
      {
        id: 'clusters', type: 'circle', source: 'intel-points',
        filter: ['has', 'point_count'],
        paint: {
          'circle-color': '#202428',
          'circle-radius': ['step', ['get', 'point_count'], 18, 10, 22, 50, 30],
          'circle-stroke-width': 1.5, 'circle-stroke-color': '#c8a45d', 'circle-opacity': 0.94,
        },
      },
      {
        id: 'cluster-count', type: 'symbol', source: 'intel-points',
        filter: ['has', 'point_count'],
        layout: {
          'text-field': ['get', 'point_count_abbreviated'],
          'text-size': 11,
          'text-font': ['Open Sans Regular', 'Arial Unicode MS Regular'],
        },
        paint: { 'text-color': '#f2eee6', 'text-halo-color': '#121416', 'text-halo-width': 1.5 },
      },
      {
        id: 'unclustered-point', type: 'symbol', source: 'intel-points',
        filter: ['!', ['has', 'point_count']],
        layout: {
          'icon-image': ['concat', 'pin-', ['get', 'layer']],
          'icon-size': 0.7, 'icon-allow-overlap': true,
          'icon-ignore-placement': true, 'icon-anchor': 'bottom',
        },
      },
    ]
    for (const layer of layers) {
      if (!map.getLayer(layer.id)) map.addLayer(layer)
    }

    // Bind event handlers once (they survive setStyle on the map object)
    if (!handlersBound.current) {
      handlersBound.current = true
      map.on('click', 'clusters', async (e) => {
        const f = map.queryRenderedFeatures(e.point, { layers: ['clusters'] })
        const id = f[0]?.properties?.cluster_id
        if (!id) return
        const src = map.getSource('intel-points') as maplibregl.GeoJSONSource | undefined
        if (!src) return
        try {
          const z = await src.getClusterExpansionZoom(id)
          if (!f[0]) return
          const coords = (f[0].geometry as GeoJSON.Point).coordinates as [number, number]
          map.flyTo({ center: coords, zoom: z + 1 })
        } catch { /* ignore */ }
      })
      map.on('click', 'unclustered-point', (e) => {
        const id = e.features?.[0]?.properties?.id as string | undefined
        if (!id) return
        const item = itemsRef.current.find(i => i.id === id)
        if (item) onSelectRef.current(item)
      })
      map.on('mouseenter', 'clusters', () => { map.getCanvas().style.cursor = 'pointer' })
      map.on('mouseleave', 'clusters', () => { map.getCanvas().style.cursor = '' })
      map.on('mouseenter', 'unclustered-point', () => { map.getCanvas().style.cursor = 'pointer' })
      map.on('mouseleave', 'unclustered-point', () => { map.getCanvas().style.cursor = '' })
    }

    // Populate data with current items
    const points = spiderfy(itemsRef.current)
    const src = map.getSource('intel-points') as maplibregl.GeoJSONSource | undefined
    if (src) {
      src.setData({
        type: 'FeatureCollection',
        features: points.map(p => ({
          type: 'Feature' as const,
          geometry: { type: 'Point' as const, coordinates: [p.lng, p.lat] },
          properties: { id: p.id, layer: p.layer },
        })),
      })
    }
  }

  // Initialize map once
  useEffect(() => {
    if (!container.current || initDone.current) return
    initDone.current = true
    handlersBound.current = false

    const map = new maplibregl.Map({
      container: container.current,
      style: HAS_TIANDITU ? tiandituStyle(TIANDITU_KEY!) : CARTODB_STYLE,
      center: [0, 20], zoom: 2,
      attributionControl: false,
    })
    map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-right')
    map.addControl(new maplibregl.NavigationControl(), 'top-right')
    mapRef.current = map

    map.on('style.load', () => setupIntelLayers(map))

    return () => { map.remove(); mapRef.current = null; initDone.current = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Style switch
  const handleStyleSwitch = useCallback((key: TileSource) => {
    const map = mapRef.current
    if (!map || key === styleKey) return
    setStyleKey(key)
    map.setStyle(key === 'tianditu' ? tiandituStyle(TIANDITU_KEY!) : CARTODB_STYLE)
  }, [styleKey])

  // Update GeoJSON when items change
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    const tryUpdate = () => {
      const src = map.getSource('intel-points') as maplibregl.GeoJSONSource | undefined
      if (!src) {
        map.once('idle', tryUpdate)
        return
      }
      const points = spiderfy(items)
      src.setData({
        type: 'FeatureCollection',
        features: points.map(p => ({
          type: 'Feature' as const,
          geometry: { type: 'Point' as const, coordinates: [p.lng, p.lat] },
          properties: { id: p.id, layer: p.layer },
        })),
      })
    }
    tryUpdate()
  }, [items])

  return (
    <div style={{ position: 'absolute', inset: 0 }}>
      <div ref={container} style={{ width: '100%', height: '100%' }} />
      {HAS_TIANDITU && (
        <div className="tile-source-switcher" style={{
          position: 'absolute', top: 54, right: 12, zIndex: 'var(--z-map-controls)',
          display: 'flex', gap: 2,
          background: 'var(--glass-bg)', backdropFilter: 'blur(12px)',
          border: '1px solid var(--glass-border)', borderRadius: 'var(--radius-sm)',
          padding: 2, boxShadow: 'var(--shadow-diffuse)',
        }}>
          {(['carto', 'tianditu'] as TileSource[]).map(k => (
            <button key={k} onClick={() => handleStyleSwitch(k)}
              style={{
                padding: '4px 8px', fontSize: 9, fontFamily: 'var(--font-mono)',
                background: styleKey === k ? 'var(--accent)' : 'transparent',
                color: styleKey === k ? 'var(--bg-deep)' : 'var(--text-secondary)',
                border: 'none', borderRadius: 3, cursor: 'pointer',
                fontWeight: 600, letterSpacing: 0.5,
                transition: 'all 0.15s ease', whiteSpace: 'nowrap',
              }}
            >
              {k === 'carto' ? 'CartoDB' : '天地图'}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
