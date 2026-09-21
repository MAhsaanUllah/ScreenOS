import { loadSession, clearSession } from './session.js'

const OFFLINE = 'Cannot reach the server. Please check your connection and try again.'

export async function api(path, options = {}) {
  const session = loadSession()
  let response
  try {
    response = await fetch(path, {
      ...options,
      headers: {
        'X-Screenos': '1',
        ...(session && session.token ? { Authorization: `Bearer ${session.token}` } : {}),
        ...(options.headers || {})
      }
    })
  } catch {
    throw new Error(OFFLINE)
  }
  if (response.status === 401) {
    clearSession()
    window.location.reload()
    throw new Error('Session expired. Sign in again.')
  }
  // A proxy failure or a crash can return an empty body, which is not JSON.
  const text = await response.text()
  let data = {}
  if (text) {
    try { data = JSON.parse(text) } catch { data = {} }
  }
  if (!response.ok) {
    throw new Error(typeof data.detail === 'string' ? data.detail : `Server error (HTTP ${response.status}). Please try again.`)
  }
  if (!text) {
    throw new Error(OFFLINE)
  }
  return data
}
