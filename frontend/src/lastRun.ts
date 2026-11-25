const KEY = 'axiom.lastRunId'

export function rememberRun(id: number): void {
  try {
    window.localStorage.setItem(KEY, String(id))
  } catch {
    // Storage can be unavailable; the nav link then falls back to disabled.
  }
}

export function lastRunId(): string | null {
  try {
    return window.localStorage.getItem(KEY)
  } catch {
    return null
  }
}
