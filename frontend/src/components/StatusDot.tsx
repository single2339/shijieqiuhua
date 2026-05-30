import { motion } from 'framer-motion'

interface Props {
  loading: boolean
  error: boolean
  label?: string
}

export default function StatusDot({ loading, error, label }: Props) {
  const color = error ? 'var(--danger)' : loading ? 'var(--warning)' : 'var(--success)'

  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
      <motion.span
        animate={
          loading
            ? { opacity: [0.4, 1, 0.4], scale: [1, 1.2, 1] }
            : error
              ? { opacity: [0.6, 1, 0.6] }
              : {}
        }
        transition={{ duration: loading ? 1.2 : 2, repeat: Infinity, ease: 'easeInOut' }}
        style={{
          width: 6, height: 6, borderRadius: '50%',
          background: color,
          boxShadow: `0 0 6px ${color}40`,
          display: 'inline-block',
        }}
      />
      {label && (
        <span style={{ fontSize: 9, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
          {label}
        </span>
      )}
    </span>
  )
}
