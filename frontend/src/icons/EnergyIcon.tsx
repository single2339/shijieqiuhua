interface Props { size?: number; color?: string }
export default function EnergyIcon({ size = 24, color = '#bd835f' }: Props) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M13 2L4 14h6l-2 8 10-12h-6l2-8z" stroke={color} strokeWidth="1.5" strokeLinejoin="round" fill={color} opacity="0.3"/>
      <circle cx="18" cy="5" r="2" stroke={color} strokeWidth="1" fill="none" opacity="0.5"/>
      <circle cx="18" cy="18" r="2" stroke={color} strokeWidth="1" fill="none" opacity="0.5"/>
    </svg>
  )
}
