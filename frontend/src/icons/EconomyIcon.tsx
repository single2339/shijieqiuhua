interface Props { size?: number; color?: string }
export default function EconomyIcon({ size = 24, color = '#3498db' }: Props) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <rect x="4" y="10" width="16" height="12" rx="1" stroke={color} strokeWidth="1.5" fill={color} opacity="0.15"/>
      <rect x="7" y="6" width="2" height="6" rx="1" fill={color} opacity="0.8"/>
      <rect x="12" y="4" width="2" height="8" rx="1" fill={color} opacity="0.8"/>
      <rect x="17" y="7" width="2" height="5" rx="1" fill={color} opacity="0.8"/>
      <circle cx="8" cy="5" r="1.2" fill={color} opacity="0.4"/>
      <circle cx="13" cy="3" r="1.5" fill={color} opacity="0.4"/>
      <circle cx="18" cy="6" r="1" fill={color} opacity="0.4"/>
      <rect x="6" y="17" width="12" height="1.5" rx="0.5" fill={color} opacity="0.5"/>
    </svg>
  )
}
