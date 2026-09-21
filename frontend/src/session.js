const KEY = 'screenos_session'

export function loadSession() {
  try { return JSON.parse(localStorage.getItem(KEY)) } catch { return null }
}

export function saveSession(session) {
  localStorage.setItem(KEY, JSON.stringify(session))
}

export function clearSession() {
  // Capture token before removal for server revocation
  let token = null
  try {
    const s = JSON.parse(localStorage.getItem(KEY) || 'null')
    token = s?.token || null
  } catch { /* ignore */ }
  localStorage.removeItem(KEY)
  // Best-effort server revocation (fire-and-forget)
  if (token) {
    try {
      fetch('/api/auth/logout', {
        method: 'POST',
        headers: { 'X-Screenos': '1', Authorization: `Bearer ${token}` }
      }).catch(() => {})
    } catch { /* ignore */ }
  }
}