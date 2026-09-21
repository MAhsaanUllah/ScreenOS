import { useEffect, useState } from 'react'
import { api } from './api.js'
import { saveSession } from './session.js'
import { PageHeader, Alert, HelpTip } from './ui.jsx'

export default function Settings({ session, onSessionChange }) {
  const [org, setOrg] = useState(null)
  const [name, setName] = useState('')
  const [catalog, setCatalog] = useState([])
  const [configured, setConfigured] = useState([])
  const [drafts, setDrafts] = useState({})
  const [busy, setBusy] = useState(false)
  const [pass, setPass] = useState({ current: '', next: '' })
  const [passMsg, setPassMsg] = useState('')
  const isAdmin = session.role === 'ADMIN'

  useEffect(() => {
    api('/api/settings')
      .then(o => { setOrg(o); setName(o.name) })
      .catch(err => alert(err.message))
    api('/api/providers').then(setCatalog).catch(err => alert(err.message))
    api('/api/settings/llm').then(setConfigured).catch(err => alert(err.message))
  }, [])

  async function rename(e) {
    e.preventDefault(); setBusy(true)
    try {
      const next = await api('/api/settings/org', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name })
      })
      setOrg(next)
      const nextSession = { ...session, org: { ...session.org, name } }
      saveSession(nextSession)
      onSessionChange(nextSession)
    } catch (err) {
      alert(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function changePassword(e) {
    e.preventDefault(); setBusy(true); setPassMsg('')
    try {
      await api('/api/settings/password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ current_password: pass.current, new_password: pass.next })
      })
      setPass({ current: '', next: '' })
      setPassMsg('Password changed. Other devices signed out. This one stays signed in.')
    } catch (err) {
      setPassMsg(err.message)
    } finally {
      setBusy(false)
    }
  }

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
      // Clear key from memory immediately after save to reduce exposure
      setDrafts(prev => ({ ...prev, [providerId]: { ...prev[providerId], key: '' } }))
      alert(`Saved ${providerId} provider settings.`)
    } catch (err) {
      alert(err.message)
    } finally {
      setBusy(false)
    }
  }

  const known = Object.fromEntries(configured.map(c => [c.provider, c]))

  // Custom PII rules (HR can add location/university etc) — stored in Settings, not during CV check
  const [piiRules, setPiiRules] = useState([])
  const [newType, setNewType] = useState('location')
  const [newValue, setNewValue] = useState('')
  const [piiMsg, setPiiMsg] = useState('')

  useEffect(() => {
    api('/api/settings/pii').then(setPiiRules).catch(() => {})
  }, [])

  async function addPii(e) {
    e.preventDefault()
    setBusy(true); setPiiMsg('')
    try {
      const next = await api('/api/settings/pii', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type: newType, value: newValue })
      })
      setPiiRules(next); setNewValue('')
      setPiiMsg('Added. This value will be auto-removed on every CV.')
    } catch (err) { setPiiMsg(err.message) }
    finally { setBusy(false) }
  }
  async function delPii(id) {
    setBusy(true)
    try { setPiiRules(await api(`/api/settings/pii/${id}`, { method: 'DELETE' })) } catch (err) { alert(err.message) }
    finally { setBusy(false) }
  }

  return (
    <div className="max-w-[1400px] mx-auto">
      <PageHeader eyebrow="Workspace Configuration" title="Settings"
        description={isAdmin
          ? 'Manage organization profile, password and bring-your-own-key provider credentials.'
          : 'Only admins can change organization and provider settings. Your own password can always be changed.'} />

      <div className="flex flex-col gap-6 max-w-3xl">
        <section className="bg-white border border-slate-200 rounded-lg p-5">
          <h2 className="panel-title">Organization</h2>
          {org && (
            <div className="flex flex-col gap-4">
              {isAdmin && (
                <form onSubmit={rename} className="flex gap-3 items-end">
                  <label className="flex-1 block">
                    <span className="label">Organization name</span>
                    <input value={name} onChange={e => setName(e.target.value)} maxLength={80} required
                      className="input" />
                  </label>
                  <button className="btn-primary" disabled={busy}>Rename</button>
                </form>
              )}
              <p className="text-xs text-slate-500">
                Created {new Date(org.created_at).toLocaleDateString()} · {org.members} member{org.members === 1 ? '' : 's'} · your role: {org.role}
              </p>
            </div>
          )}
        </section>

        <section className="bg-white border border-slate-200 rounded-lg p-5">
          <h2 className="panel-title">Password</h2>
          {passMsg && <Alert tone={passMsg.startsWith('Password changed') ? 'success' : 'error'}>{passMsg}</Alert>}
          <form onSubmit={changePassword} className="flex flex-col gap-3">
            <input type="password" placeholder="Current password" minLength={8} required
              value={pass.current} onChange={e => setPass({ ...pass, current: e.target.value })}
              className="input" />
            <input type="password" placeholder="New password (min 8 characters)" minLength={8} required
              value={pass.next} onChange={e => setPass({ ...pass, next: e.target.value })}
              className="input" />
            <div className="flex items-center gap-3">
              <button className="btn-primary" disabled={busy}>Change password</button>
            </div>
          </form>
        </section>

        <section className="bg-white border border-slate-200 rounded-lg p-5">
          <h2 className="panel-title">AI Provider Keys <HelpTip text="Like a password that lets the app talk to AI. If you don't have one, use Ollama (local) — no key needed. Ask IT for a key if needed." /></h2>
          <p className="text-xs text-slate-500 mb-1">
            Keys are masked after saving (…last4 only) and stored encrypted. Two keys = fallback if one is down.
          </p>
          <p className="text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 rounded px-2 py-1.5 mb-3">
            Non-technical? You don’t need to buy anything. Use <strong>Ollama (local)</strong> below — no key, works offline. For DeepSeek/Gemini, ask IT to paste the key.
          </p>
          <div className="flex flex-col gap-3">
            {catalog.map(spec => {
              const entry = known[spec.id]
              return (
                <div key={spec.id} className="border border-slate-200 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <strong className="text-sm text-slate-900">{spec.label}</strong>
                    {entry ? (
                      <span className="text-[11px] font-semibold px-2 py-1 rounded bg-emerald-50 text-emerald-700">
                        {spec.needs_key ? `Key saved (${entry.hint})` : 'No key needed'} · {entry.model || spec.default_model}
                      </span>
                    ) : (
                      <span className="text-[11px] font-semibold px-2 py-1 rounded bg-slate-100 text-slate-500">Not configured</span>
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
                        className="input flex-1 max-sm:flex-none"
                      />
                      <input
                        placeholder="Model name (default if blank)"
                        value={drafts[spec.id]?.model || ''}
                        onChange={e => setDraft(spec.id, 'model', e.target.value)}
                        className="input flex-1 max-sm:flex-none"
                      />
                      <button className="btn-primary" disabled={busy || (spec.needs_key && !drafts[spec.id]?.key)}
                        onClick={() => save(spec.id, spec.needs_key)}>Save</button>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </section>

        <section className="bg-white border border-slate-200 rounded-lg p-5">
          <div className="flex items-center justify-between mb-2">
            <h2 className="panel-title mb-0">Custom Redaction <HelpTip text="HR can add any word to always redact — e.g. location Lahore, university PU. Added here in Settings, not during CV check. Appears auto in Review PII." /></h2>
            <span className="text-[11px] font-semibold px-2 py-1 rounded bg-slate-100 text-slate-600">{piiRules.length} rules</span>
          </div>
          <p className="text-xs text-slate-500 mb-3">Add a word/phrase to always remove — e.g. <em>location</em> = <code className="px-1 bg-slate-100 rounded">Lahore</code>, <em>university</em> = <code className="px-1 bg-slate-100 rounded">University of Punjab</code>. Works on every CV automatically.</p>
          {piiMsg && <Alert tone={piiMsg.startsWith('Added') ? 'success' : 'error'}>{piiMsg}</Alert>}
          <form onSubmit={addPii} className="flex gap-2 mb-3 max-sm:flex-col">
            <select value={newType} onChange={e => setNewType(e.target.value)} className="input max-w-[150px] max-sm:max-w-none">
              <option value="location">location</option>
              <option value="university">university</option>
              <option value="custom">custom</option>
              <option value="address">address</option>
              <option value="other">other</option>
            </select>
            <input value={newValue} onChange={e => setNewValue(e.target.value)} placeholder="Value to redact e.g. Lahore" maxLength={120} required className="input flex-1" />
            <button type="submit" disabled={busy || !newValue.trim()} className="btn-primary whitespace-nowrap">+ Add</button>
          </form>
          <div className="border border-slate-200 rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-[11px] uppercase tracking-wide text-slate-500">
                <tr><th className="px-3 py-2">Type</th><th className="px-3 py-2">Value</th><th className="px-3 py-2 text-right">Action</th></tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {piiRules.length === 0 ? (
                  <tr><td colSpan={3} className="px-3 py-6 text-center text-xs text-slate-400">No custom rules yet. Add location or university above — they’ll show in Review PII and be auto-removed.</td></tr>
                ) : piiRules.map(r => (
                  <tr key={r.id}>
                    <td className="px-3 py-2 text-xs font-medium text-slate-600">{r.type}</td>
                    <td className="px-3 py-2 font-mono text-xs text-slate-800">{r.value}</td>
                    <td className="px-3 py-2 text-right"><button onClick={() => delPii(r.id)} disabled={busy} className="text-xs text-red-600 hover:text-red-700">Delete</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-[11px] text-slate-400 mt-2">These are not shown during CV upload — they live here in Settings. Every new CV will auto-hide these values.</p>
        </section>
      </div>
    </div>
  )
}