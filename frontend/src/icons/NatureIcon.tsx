interface Props { size?: number; color?: string }
export default function NatureIcon({ size = 24, color = '#2ecc71' }: Props) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M12 2C12 2 6 8 6 14c0 3.3 2.7 6 6 6s6-2.7 6-6c0-6-6-12-6-12z" fill={color} opacity="0.9"/>
      <path d="M12 8c-2 3-2 6 0 8" stroke="#fff" strokeWidth="1.5" strokeLinecap="round" fill="none" opacity="0.6"/>
      <path d="M4 20h16" stroke={color} strokeWidth="1.5" strokeLinecap="round" opacity="0.5"/>
    </svg>
  )
}
