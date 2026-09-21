import { loadSession, clearSession } from './session.js'

const OFFLINE = 'Cannot reach the server. Please check your connection and try again.'

export async function api(path, options = {}) {
  const session = loadSession()
  const isForm = options.body instanceof FormData
  const h = new Headers()
  h.set('X-Screenos', '1')
  if (session && session.token) h.set('Authorization', `Bearer ${session.token}`)
  if (options.headers) {
    for (const [k, v] of Object.entries(options.headers)) h.set(k, v)
  }
  let response
  try {
    response = await fetch(path, { ...options, headers: h })
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
    let msg = `Server error (HTTP ${response.status}). Please try again.`
    if (typeof data.detail === 'string' && data.detail) msg = data.detail
    else if (Array.isArray(data.detail) && data.detail[0]) {
      const first = data.detail[0]
      msg = typeof first.msg === 'string' ? first.msg : JSON.stringify(first)
    } else if (data.detail && typeof data.detail.msg === 'string') msg = data.detail.msg
    throw new Error(msg)
  }
  if (!text) {
    throw new Error(OFFLINE)
  }
  return data
}
