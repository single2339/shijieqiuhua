interface Props { size?: number; color?: string }
export default function MilitaryIcon({ size = 24, color = '#bf6f63' }: Props) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M12 2l-3 7h6l-3-7z" fill={color} opacity="0.9"/>
      <rect x="10" y="9" width="4" height="4" rx="1" fill={color} opacity="0.7"/>
      <path d="M7 13l5 3 5-3" stroke={color} strokeWidth="1.5" fill="none" opacity="0.6"/>
      <path d="M12 16v4" stroke={color} strokeWidth="1.5" strokeLinecap="round" opacity="0.7"/>
      <circle cx="12" cy="21" r="1" fill={color} opacity="0.5"/>
      <rect x="8" y="19" width="8" height="1.5" rx="0.5" fill={color} opacity="0.3"/>
    </svg>
  )
}
