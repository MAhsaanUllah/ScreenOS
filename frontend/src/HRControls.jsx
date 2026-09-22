import { useEffect, useState } from 'react'
import { api } from './api.js'
import { PageHeader, Alert, HelpTip } from './ui.jsx'

export default function HRControls() {
  // PII custom (moved from Settings — separate page per HR request)
  const [rules, setRules] = useState([])
  const [type, setType] = useState('location')
  const [value, setValue] = useState('')
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)

  // Rubric points editor (single default rubric, HR-friendly)
  const [rubric, setRubric] = useState(null)
  const [rows, setRows] = useState([])
  const [rMsg, setRMsg] = useState('')
  const [rBusy, setRBusy] = useState(false)
  const [archive, setArchive] = useState([])

  useEffect(() => {
    api('/api/settings/pii').then(setRules).catch(() => {})
    api('/api/rubric').then(r => { setRubric(r); setRows(r.rows.map(x => ({ ...x }))) }).catch(() => {})
    api('/api/rubrics/archive').then(setArchive).catch(() => {})
  }, [])

  async function addRule(e) {
    e.preventDefault()
    setBusy(true); setMsg('')
    try {
      const next = await api('/api/settings/pii', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ type, value }) })
      setRules(next); setValue(''); setMsg('Added — will auto-remove on every new CV.')
    } catch (err) { setMsg(err.message) }
    finally { setBusy(false) }
  }
  async function delRule(id) {
    setBusy(true)
    try { setRules(await api(`/api/settings/pii/${id}`, { method: 'DELETE' })) } catch (err) { alert(err.message) }
    finally { setBusy(false) }
  }

  function setPoint(i, v) {
    const n = Number(v)
    setRows(prev => prev.map((r, idx) => idx === i ? { ...r, points: v === '' ? '' : n } : r))
  }
  const total = rows.reduce((s, r) => s + (Number(r.points) || 0), 0)
  async function saveRubric() {
    setRBusy(true); setRMsg('')
    try {
      const next = await api('/api/rubric', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ rows }) })
      setRubric(next); setRows(next.rows.map(x => ({ ...x }))); setRMsg('Rubric saved — total 100. New scores will use this.')
      api('/api/rubrics/archive').then(setArchive).catch(() => {})
    } catch (err) { setRMsg(err.message) }
    finally { setRBusy(false) }
  }
  async function restoreRubric(file) {
    setRBusy(true)
    try {
      const next = await api(`/api/rubrics/restore/${file}`, { method: 'POST' })
      setRubric(next); setRows(next.rows.map(x => ({ ...x }))); setRMsg(`Restored ${file}`)
      api('/api/rubrics/archive').then(setArchive).catch(() => {})
    } catch (err) { setRMsg(err.message) }
    finally { setRBusy(false) }
  }

  return (
    <div className="max-w-[900px] mx-auto">
      <PageHeader eyebrow="HR Controls" title="One place to change filters & scores" description="Add PII words to always hide, or adjust rubric points. Settings stays clean (org/keys only) — this page is your HR toolkit." />

      <div className="flex flex-col gap-6">
        <section className="bg-white border border-slate-200 rounded-lg p-5">
          <div className="flex items-center justify-between mb-2">
            <h2 className="panel-title mb-0">PII Filters <HelpTip text="Add any word to always redact — e.g. location Lahore, university PU. Shows auto in Review PII." /></h2>
            <span className="text-[11px] font-semibold px-2 py-1 rounded bg-slate-100 text-slate-600">{rules.length} rules</span>
          </div>
          <p className="text-xs text-slate-500 mb-3">Example: <em>location</em> = <code className="px-1 bg-slate-100 rounded">Lahore</code>, <em>university</em> = <code className="px-1 bg-slate-100 rounded">University of Punjab</code>. Every new CV hides these automatically.</p>
          {msg && <Alert tone={msg.startsWith('Added') ? 'success' : 'error'}>{msg}</Alert>}
          <form onSubmit={addRule} className="flex gap-2 mb-3 max-sm:flex-col">
            <select value={type} onChange={e => setType(e.target.value)} className="input max-w-[150px] max-sm:max-w-none">
              <option value="location">location</option>
              <option value="university">university</option>
              <option value="custom">custom</option>
              <option value="address">address</option>
              <option value="other">other</option>
            </select>
            <input value={value} onChange={e => setValue(e.target.value)} placeholder="Value to redact e.g. Lahore" maxLength={120} required className="input flex-1" />
            <button type="submit" disabled={busy || !value.trim()} className="btn-primary whitespace-nowrap">+ Add</button>
          </form>
          <div className="border border-slate-200 rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-[11px] uppercase tracking-wide text-slate-500"><tr><th className="px-3 py-2">Type</th><th className="px-3 py-2">Value</th><th className="px-3 py-2 text-right">Action</th></tr></thead>
              <tbody className="divide-y divide-slate-100">
                {rules.length === 0 ? (
                  <tr><td colSpan={3} className="px-3 py-6 text-center text-xs text-slate-400">No custom filters yet. Add location/university above — they’ll appear in Review PII pre-checked.</td></tr>
                ) : rules.map(r => (
                  <tr key={r.id}><td className="px-3 py-2 text-xs font-medium text-slate-600">{r.type}</td><td className="px-3 py-2 font-mono text-xs text-slate-800">{r.value}</td><td className="px-3 py-2 text-right"><button onClick={() => delRule(r.id)} disabled={busy} className="text-xs text-red-600 hover:text-red-700">Delete</button></td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="bg-white border border-slate-200 rounded-lg p-5">
          <div className="flex items-center justify-between mb-2">
            <h2 className="panel-title mb-0">Rubric Scores <HelpTip text="Change points per requirement. Must total 100. Only admin can save." /></h2>
            {rubric && <span className="text-[11px] font-semibold px-2 py-1 rounded bg-slate-100 text-slate-600">{rubric.job}</span>}
          </div>
          <p className="text-xs text-slate-500 mb-3">Adjust points (e.g. give more weight to Python). Requirement names stay same — only points & evidence editable here. Total must be 100.</p>
          {rMsg && <Alert tone={rMsg.startsWith('Rubric saved') ? 'success' : 'error'}>{rMsg}</Alert>}
          {rows.length > 0 && (
            <>
              <div className="border border-slate-200 rounded-lg overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-left text-[11px] uppercase tracking-wide text-slate-500"><tr><th className="px-3 py-2 w-24">Points</th><th className="px-3 py-2">Requirement</th><th className="px-3 py-2">Evidence to look for</th></tr></thead>
                  <tbody className="divide-y divide-slate-100">
                    {rows.map((r, i) => (
                      <tr key={r.requirement}>
                        <td className="px-3 py-2"><input type="number" min={1} max={100} step={1} value={r.points} onChange={e => setPoint(i, e.target.value)} className="input w-20" /></td>
                        <td className="px-3 py-2 text-xs font-medium text-slate-700">{r.requirement}</td>
                        <td className="px-3 py-2 text-xs text-slate-500">{r.evidence}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="flex items-center justify-between mt-3">
                <span className={`text-xs font-semibold ${total === 100 ? 'text-emerald-600' : 'text-amber-600'}`}>Total: {total}/100 {total !== 100 && '(must be 100 to save)'}</span>
                <button onClick={saveRubric} disabled={rBusy || total !== 100} className="btn-primary">Save rubric</button>
              </div>
              {archive.length > 0 && (
                <div className="mt-4 border-t border-slate-200 pt-3">
                  <p className="text-xs font-semibold text-slate-600 mb-2">Previous versions</p>
                  <div className="flex flex-wrap gap-2">
                    {archive.map(a => (
                      <button key={a.file} onClick={() => restoreRubric(a.file)} disabled={rBusy} className="text-xs border border-slate-200 rounded px-2 py-1 bg-slate-50 hover:bg-white">{a.file.replace('ai-engineer_','').replace('.md','')} — {a.points}pts</button>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </section>

        <section className="bg-slate-50 border border-slate-200 rounded-lg p-4">
          <h3 className="text-sm font-bold text-slate-900">How it works for HR</h3>
          <ul className="text-xs text-slate-600 list-disc list-inside mt-1 space-y-1">
            <li><strong>PII Filters</strong> live here — not during CV check. Review PII will auto-check them.</li>
            <li><strong>Rubric</strong> changes apply to new scores only — old scorecards keep old points.</li>
            <li>Need more rules? Add multiple location/university values — all are redacted.</li>
          </ul>
        </section>
      </div>
    </div>
  )
}
