interface Props { size?: number; color?: string }
export default function HealthIcon({ size = 24, color = '#00bcd4' }: Props) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <rect x="6" y="3" width="12" height="18" rx="3" stroke={color} strokeWidth="1.5" fill={color} opacity="0.1"/>
      <path d="M12 8v8M8 12h8" stroke={color} strokeWidth="2" strokeLinecap="round" opacity="0.8"/>
      <circle cx="12" cy="12" r="4.5" stroke={color} strokeWidth="1" fill="none" opacity="0.3"/>
    </svg>
  )
}
