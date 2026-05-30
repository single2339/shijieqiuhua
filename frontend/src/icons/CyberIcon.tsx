interface Props { size?: number; color?: string }
export default function CyberIcon({ size = 24, color = '#1a237e' }: Props) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M12 2L3 7v5c0 4.4 3.6 8 9 10 5.4-2 9-5.6 9-10V7l-9-5z" stroke={color} strokeWidth="1.5" fill={color} opacity="0.15"/>
      <path d="M12 8v4M12 16h.01" stroke={color} strokeWidth="2" strokeLinecap="round"/>
      <circle cx="12" cy="12" r="7" stroke={color} strokeWidth="0.8" fill="none" opacity="0.25"/>
    </svg>
  )
}
