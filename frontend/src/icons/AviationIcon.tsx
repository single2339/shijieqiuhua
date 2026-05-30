interface Props { size?: number; color?: string }
export default function AviationIcon({ size = 24, color = '#00bcd4' }: Props) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M12 2C12 2 6 8 6 14c0 3.3 2.7 6 6 6s6-2.7 6-6c0-6-6-12-6-12z" fill={color} opacity="0.9"/>
      <circle cx="12" cy="14" r="3" fill="#fff" opacity="0.3"/>
      <circle cx="12" cy="14" r="1.5" fill="#fff" opacity="0.6"/>
      <path d="M7 14h10" stroke="#fff" strokeWidth="1" strokeLinecap="round" opacity="0.4"/>
      <path d="M12 9v10" stroke="#fff" strokeWidth="1" strokeLinecap="round" opacity="0.4"/>
    </svg>
  )
}
