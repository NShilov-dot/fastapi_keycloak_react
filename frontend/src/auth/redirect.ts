// Loop-breaker: a session that keeps coming back 401 would otherwise ping-pong
// /login → Keycloak → /callback → 401 → /login forever. Cap redirects per window.
const LOG_KEY = 'auth:redirects'
const WINDOW_MS = 10_000
const MAX_REDIRECTS = 3

// Parallel 401s on one page load are a single expiry, not a loop.
let redirecting = false

function recentRedirects(now: number): number[] {
  try {
    const raw = sessionStorage.getItem(LOG_KEY)
    const arr: number[] = raw ? JSON.parse(raw) : []
    return arr.filter((t) => now - t < WINDOW_MS)
  } catch {
    return []
  }
}

export function clearRedirectLoopState(): void {
  try {
    sessionStorage.removeItem(LOG_KEY)
  } catch {
    /* sessionStorage unavailable */
  }
}

/** Send the browser through the OIDC login, returning here. False if we appear to be looping. */
export function redirectToLogin(): boolean {
  if (redirecting) return true
  const now = Date.now()
  const recent = recentRedirects(now)
  if (recent.length >= MAX_REDIRECTS) return false
  try {
    sessionStorage.setItem(LOG_KEY, JSON.stringify([...recent, now]))
  } catch {
    /* sessionStorage unavailable — proceed without loop tracking */
  }
  redirecting = true
  const returnTo = window.location.pathname + window.location.search
  window.location.assign(`/v1/auth/login?return_to=${encodeURIComponent(returnTo)}`)
  return true
}
