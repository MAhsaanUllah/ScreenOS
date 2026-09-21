const KEY = 'screenos_session'

export function loadSession() {
  try { return JSON.parse(localStorage.getItem(KEY)) } catch { return null }
}

export function saveSession(session) {
  localStorage.setItem(KEY, JSON.stringify(session))
}

export function clearSession() {
  localStorage.removeItem(KEY)
}