export const BRIEF_WORKSPACE_STORAGE_KEY = 'osint.briefWorkspace.v1'
export const BRIEF_REPORT_HISTORY_STORAGE_KEY = 'osint.briefReportHistory.v1'

const USER_SCOPED_KEYS = [BRIEF_WORKSPACE_STORAGE_KEY, BRIEF_REPORT_HISTORY_STORAGE_KEY]

export function getUserStorageKey(baseKey: string, userId: number | string | null | undefined): string | null {
  if (userId === null || userId === undefined || userId === '') return null
  return `${baseKey}.user.${encodeURIComponent(String(userId))}`
}

export function clearUserScopedStorage(userId: number | string | null | undefined): void {
  if (typeof window === 'undefined') return

  for (const baseKey of USER_SCOPED_KEYS) {
    const scopedKey = getUserStorageKey(baseKey, userId)
    try {
      if (scopedKey) window.localStorage.removeItem(scopedKey)
      // Remove pre-isolation keys so data written by older builds cannot leak.
      window.localStorage.removeItem(baseKey)
    } catch {
      // Storage can be unavailable in private browsing or locked-down contexts.
    }
  }
}
