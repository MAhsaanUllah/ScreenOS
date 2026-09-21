import { loadSession, clearSession } from './session.js'

export async function api(path, options = {}) {
  const session = loadSession()
  const response = await fetch(path, {
    ...options,
    headers: {
      'X-Screenos': '1',
      ...(session && session.token ? { Authorization: `Bearer ${session.token}` } : {}),
      ...(options.headers || {})
    }
  })
  if (response.status === 401) {
    clearSession()
    window.location.reload()
    throw new Error('Session expired. Sign in again.')
  }
  const data = await response.json()
  if (!response.ok) {
    throw new Error(typeof data.detail === 'string' ? data.detail : 'Request failed. Please check inputs.')
  }
  return data
}