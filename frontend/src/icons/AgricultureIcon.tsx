interface Props { size?: number; color?: string }
export default function AgricultureIcon({ size = 24, color = '#7e986b' }: Props) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M7 22V12c0-4 5-6 5-6s5 2 5 6v10" stroke={color} strokeWidth="1.5" fill="none"/>
      <path d="M12 6V2M12 6c-3 0-5 2-5 2M12 6c3 0 5 2 5 2" stroke={color} strokeWidth="1.2" fill="none" opacity="0.5"/>
      <ellipse cx="12" cy="8" rx="1.5" ry="1" fill={color} opacity="0.4"/>
      <path d="M5 14h14M5 18h14" stroke={color} strokeWidth="0.8" opacity="0.3"/>
      <line x1="9" y1="18" x2="9" y2="22" stroke={color} strokeWidth="1.5" strokeLinecap="round"/>
      <line x1="15" y1="18" x2="15" y2="22" stroke={color} strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  )
}
