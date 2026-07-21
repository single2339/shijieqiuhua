interface Props { size?: number; color?: string }
export default function PoliticsIcon({ size = 24, color = '#b88a5a' }: Props) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <circle cx="9" cy="7" r="3" stroke={color} strokeWidth="1.5" fill={color} opacity="0.2"/>
      <path d="M3 22c0-5 3-8 6-8s6 3 6 8" stroke={color} strokeWidth="1.5" fill="none"/>
      <circle cx="17" cy="9" r="2.5" stroke={color} strokeWidth="1.5" fill={color} opacity="0.2"/>
      <path d="M14 22c0-4 1.5-6.5 3-6.5s3 2.5 3 6.5" stroke={color} strokeWidth="1.5" fill="none"/>
      <path d="M2 3l4 1-4 1z" fill={color} opacity="0.4"/>
      <path d="M19 3l4 1-4 1z" fill={color} opacity="0.4"/>
    </svg>
  )
}
