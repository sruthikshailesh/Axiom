/** The signed-in token. One localStorage key, and only the token inside it. */

const TOKEN_KEY = 'axiom.token'

export const UNAUTHORIZED_EVENT = 'axiom:unauthorized'

export function getToken(): string | null {
  try {
    return window.localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setToken(token: string): void {
  try {
    window.localStorage.setItem(TOKEN_KEY, token)
  } catch {
    // Storage can be unavailable (private mode); the next request then 401s.
  }
}

export function clearToken(): void {
  try {
    window.localStorage.removeItem(TOKEN_KEY)
  } catch {
    // Nothing to clear.
  }
}

/** Tell the app a request came back 401 so it can send the user to sign-in. */
export function notifyUnauthorized(): void {
  window.dispatchEvent(new Event(UNAUTHORIZED_EVENT))
}
