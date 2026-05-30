interface Props { size?: number; color?: string }
export default function TechnologyIcon({ size = 24, color = '#ff4081' }: Props) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M12 3v2M12 19v2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M3 12h2M19 12h2M5.6 18.4l1.4-1.4M17 7l1.4-1.4" stroke={color} strokeWidth="1.2" strokeLinecap="round" opacity="0.4"/>
      <rect x="8" y="8" width="8" height="8" rx="2" fill={color} opacity="0.8"/>
      <path d="M10.5 12h3M12 10.5v3" stroke="#fff" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  )
}
