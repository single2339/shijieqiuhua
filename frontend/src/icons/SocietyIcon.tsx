interface Props { size?: number; color?: string }
export default function SocietyIcon({ size = 24, color = '#b47670' }: Props) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <circle cx="7" cy="7" r="2.5" stroke={color} strokeWidth="1.5" fill={color} opacity="0.15"/>
      <circle cx="17" cy="7" r="2.5" stroke={color} strokeWidth="1.5" fill={color} opacity="0.15"/>
      <circle cx="12" cy="14" r="2.5" stroke={color} strokeWidth="1.5" fill={color} opacity="0.15"/>
      <path d="M5 10c-1.5 2-2 4-1 6M19 10c1.5 2 2 4 1 6M7 12c-1 2-1 4 0 6M17 12c1 2 1 4 0 6" stroke={color} strokeWidth="1" opacity="0.35"/>
      <line x1="12" y1="16.5" x2="12" y2="20" stroke={color} strokeWidth="1.5" strokeLinecap="round" opacity="0.5"/>
    </svg>
  )
}
