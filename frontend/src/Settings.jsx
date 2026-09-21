import { useEffect, useState } from 'react'
import { api } from './api.js'

export default function Settings({ session }) {
  const [catalog, setCatalog] = useState([])
  const [configured, setConfigured] = useState([])
  const [drafts, setDrafts] = useState({})
  const [busy, setBusy] = useState(false)
  const isAdmin = session.role === 'ADMIN'

  useEffect(() => {
    api('/api/providers').then(setCatalog).catch(err => alert(err.message))
    api('/api/settings/llm').then(setConfigured).catch(err => alert(err.message))
  }, [])

  function setDraft(provider, field, value) {
    setDrafts(prev => ({ ...prev, [provider]: { ...prev[provider], [field]: value } }))
  }

  async function save(providerId, needsKey) {
    setBusy(true)
    const d = drafts[providerId] || {}
    try {
      setConfigured(await api('/api/settings/llm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider: providerId, api_key: needsKey ? d.key || '' : '', model: d.model || '' })
      }))
      alert(`Saved ${providerId} provider settings.`)
    } catch (err) {
      alert(err.message)
    } finally {
      setBusy(false)
    }
  }

  const known = Object.fromEntries(configured.map(c => [c.provider, c]))

  return (
    <div className="max-w-[1400px] mx-auto">
      <div className="mb-5">
        <p className="text-[11px] font-bold tracking-widest uppercase text-blue-600 mb-1">Workspace Configuration</p>
        <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
        <p className="text-sm text-slate-600 mt-0.5">
          {isAdmin
            ? 'Bring-your-own-key provider credentials used for AI scoring. Keys are masked after saving.'
            : 'Only admins can configure provider keys. Here is what is currently active.'}
        </p>
      </div>

      <div className="flex flex-col gap-3">
        {catalog.map(spec => {
          const entry = known[spec.id]
          return (
            <div key={spec.id} className="bg-white border border-slate-200 rounded-xl p-4">
              <div className="flex items-center justify-between mb-2">
                <strong className="text-sm text-slate-900">{spec.label}</strong>
                {entry ? (
                  <span className="text-[11px] font-semibold px-2 py-0.5 rounded bg-emerald-50 text-emerald-700">
                    {spec.needs_key ? `Key saved (${entry.hint})` : 'No key needed'} · {entry.model || spec.default_model}
                  </span>
                ) : (
                  <span className="text-[11px] font-semibold px-2 py-0.5 rounded bg-slate-100 text-slate-500">Not configured</span>
                )}
              </div>
              <p className="text-xs text-slate-500 mb-3">Default model: {spec.default_model}</p>
              {isAdmin && (
                <div className="flex gap-3 max-sm:flex-col">
                  <input
                    type="password"
                    placeholder={spec.needs_key ? 'API key' : 'No key needed (local model)'}
                    disabled={!spec.needs_key}
                    value={drafts[spec.id]?.key || ''}
                    onChange={e => setDraft(spec.id, 'key', e.target.value)}
                    className="flex-1 px-3 py-2 border border-slate-300 rounded-md text-sm"
                  />
                  <input
                    placeholder="Model name (default if blank)"
                    value={drafts[spec.id]?.model || ''}
                    onChange={e => setDraft(spec.id, 'model', e.target.value)}
                    className="flex-1 px-3 py-2 border border-slate-300 rounded-md text-sm"
                  />
                  <button className="btn-primary" disabled={busy || (spec.needs_key && !drafts[spec.id]?.key)}
                    onClick={() => save(spec.id, spec.needs_key)}>Save</button>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}