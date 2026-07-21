export function safeExternalUrl(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined

  const candidate = value.trim()
  if (!candidate) return undefined

  try {
    const url = new URL(candidate)
    return url.protocol === 'http:' || url.protocol === 'https:' ? candidate : undefined
  } catch {
    return undefined
  }
}
