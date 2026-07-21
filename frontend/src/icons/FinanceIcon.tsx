interface Props { size?: number; color?: string }
export default function FinanceIcon({ size = 24, color = '#c8a45d' }: Props) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <polyline points="2,18 7,13 12,15 18,6 22,8" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
      <path d="M2 18L7 13L12 15L18 6L22 8V22H2Z" fill={color} opacity="0.15"/>
      <circle cx="18" cy="6" r="2" fill={color}/>
      <line x1="2" y1="20" x2="22" y2="20" stroke={color} strokeWidth="1" opacity="0.3"/>
    </svg>
  )
}
