import { motion } from 'framer-motion'
import type { IntelLayer, LayerSummary } from '../types'
import { LAYER_META } from '../types'
import NatureIcon from '../icons/NatureIcon'
import EconomyIcon from '../icons/EconomyIcon'
import FinanceIcon from '../icons/FinanceIcon'
import PoliticsIcon from '../icons/PoliticsIcon'
import MilitaryIcon from '../icons/MilitaryIcon'
import AviationIcon from '../icons/AviationIcon'
import TechnologyIcon from '../icons/TechnologyIcon'
import SocietyIcon from '../icons/SocietyIcon'
import EnergyIcon from '../icons/EnergyIcon'
import AgricultureIcon from '../icons/AgricultureIcon'
import HealthIcon from '../icons/HealthIcon'
import CyberIcon from '../icons/CyberIcon'

interface Props {
  layers: LayerSummary[]
  activeLayers: Set<IntelLayer>
  onToggle: (layer: IntelLayer) => void
}

const iconMap: Record<IntelLayer, typeof NatureIcon> = {
  nature: NatureIcon, economy: EconomyIcon, finance: FinanceIcon, politics: PoliticsIcon,
  military: MilitaryIcon, aviation: AviationIcon, technology: TechnologyIcon, society: SocietyIcon,
  energy: EnergyIcon, agriculture: AgricultureIcon, health: HealthIcon, cyber: CyberIcon,
}

export default function LayerPanel({ layers, activeLayers, onToggle }: Props) {
  return (
    <motion.div
      style={{
        display: 'flex', flexDirection: 'column', gap: 2,
        background: 'var(--glass-bg)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        borderRadius: 'var(--radius-lg)',
        border: '1px solid var(--glass-border)',
        boxShadow: 'var(--shadow-diffuse), var(--glass-inner-shadow)',
        padding: '6px 4px',
      }}
    >
      {layers.map((l, i) => {
        const isActive = activeLayers.has(l.layer)
        const Icon = iconMap[l.layer]
        const meta = LAYER_META[l.layer]
        return (
          <motion.button
            key={l.layer}
            initial={{ x: -20, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            transition={{ type: 'spring', stiffness: 120, damping: 18, delay: 0.2 + i * 0.03 }}
            whileHover={{ scale: 1.06 }}
            whileTap={{ scale: 0.94 }}
            onClick={() => onToggle(l.layer)}
            style={{
              position: 'relative',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              width: 36, height: 36,
              border: 'none',
              borderRadius: 'var(--radius-md)',
              background: isActive
                ? `${meta.color}18`
                : 'transparent',
              cursor: 'pointer',
              transition: 'background 0.2s ease',
            }}
            title={`${meta.label} (${l.count})`}
          >
            {isActive && (
              <motion.div
                layoutId="layer-indicator"
                style={{
                  position: 'absolute', left: 0, top: '50%',
                  width: 3, height: 16, borderRadius: 2,
                  background: meta.color,
                  transform: 'translateY(-50%)',
                }}
                transition={{ type: 'spring', stiffness: 200, damping: 24 }}
              />
            )}
            <Icon size={16} color={isActive ? meta.color : 'var(--text-tertiary)'} />
            {l.count > 0 && (
              <span style={{
                position: 'absolute', top: 2, right: 2,
                background: isActive ? meta.color : 'var(--border-active)',
                color: isActive ? '#fff' : 'var(--text-tertiary)',
                fontSize: 7, fontWeight: 700, lineHeight: '12px',
                minWidth: 12, height: 12,
                textAlign: 'center', borderRadius: 'var(--radius-full)',
                padding: '0 2px',
                opacity: isActive ? 1 : 0.4,
                transition: 'opacity 0.2s ease',
              }}>
                {l.count > 99 ? '99+' : l.count}
              </span>
            )}
          </motion.button>
        )
      })}
    </motion.div>
  )
}
