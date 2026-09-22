import { useEffect, useState } from 'react'
import { api } from './api.js'
import { PageHeader, Alert, HelpTip } from './ui.jsx'

export default function HRControls() {
  // Jobs (Chunk 1) — org-scoped openings
  const [jobs, setJobs] = useState([])
  const [jobTitle, setJobTitle] = useState('')
  const [jobJd, setJobJd] = useState('')
  const [jobMsg, setJobMsg] = useState('')
  // Agency vs Internal (minimal flag)
  const [org, setOrg] = useState(null)
  const [orgMsg, setOrgMsg] = useState('')
  // PII custom
  const [rules, setRules] = useState([])
  const [type, setType] = useState('location')
  const [value, setValue] = useState('')
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)

  // Rubric (global, will become per-job in later chunk)
  const [rubric, setRubric] = useState(null)
  const [rows, setRows] = useState([])
  const [rMsg, setRMsg] = useState('')
  const [rBusy, setRBusy] = useState(false)
  const [archive, setArchive] = useState([])

  useEffect(() => {
    api('/api/jobs').then(setJobs).catch(() => {})
    api('/api/settings').then(setOrg).catch(() => {})
    api('/api/settings/pii').then(setRules).catch(() => {})
    api('/api/rubric').then(r => { setRubric(r); setRows(r.rows.map(x => ({ ...x }))) }).catch(() => {})
    api('/api/rubrics/archive').then(setArchive).catch(() => {})
  }, [])
  async function createJob(e) {
    e.preventDefault()
    setBusy(true); setJobMsg('')
    try {
      const j = await api('/api/jobs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title: jobTitle, jd_text: jobJd }) })
      setJobs(prev => [j, ...prev]); setJobTitle(''); setJobJd(''); setJobMsg('Job created — DRAFT. Add rubric then OPEN to screen.')
    } catch (err) { setJobMsg(err.message) }
    finally { setBusy(false) }
  }
  async function closeJob(id) {
    setBusy(true)
    try { const j = await api(`/api/jobs/${id}/close`, { method: 'POST' }); setJobs(prev => prev.map(x => x.id === id ? j : x)) } catch (err) { alert(err.message) }
    finally { setBusy(false) }
  }
  async function setOrgType(t) {
    setBusy(true); setOrgMsg('')
    try { const next = await api('/api/settings/org-type', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ org_type: t }) }); setOrg(next); setOrgMsg(`Organization is now ${t}`) } catch (err) { setOrgMsg(err.message) }
    finally { setBusy(false) }
  }

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
      <PageHeader eyebrow="HR Controls" title="One place to change filters & scores" description="Add Jobs, PII words to always hide, or adjust rubric points. Settings stays clean (org/keys only) — this page is your HR toolkit." />

      <div className="flex flex-col gap-6">
        <section className="bg-white border border-slate-200 rounded-lg p-5">
          <h2 className="panel-title">Job Openings <HelpTip text="Create a Job with title + JD. DRAFT → add rubric → OPEN to screen. Reviews can reference a Job (nullable for compat)." /></h2>
          {jobMsg && <Alert tone={jobMsg.startsWith('Job created') ? 'success' : 'error'}>{jobMsg}</Alert>}
          <form onSubmit={createJob} className="flex flex-col gap-2 mb-3">
            <input value={jobTitle} onChange={e => setJobTitle(e.target.value)} placeholder="Job title e.g. Backend Engineer" maxLength={120} required className="input" />
            <textarea value={jobJd} onChange={e => setJobJd(e.target.value)} placeholder="Job description (paste JD, max 8000)" maxLength={8000} rows={3} className="input resize-y" />
            <button type="submit" disabled={busy || !jobTitle.trim()} className="btn-primary w-fit">Create Job</button>
          </form>
          <div className="border border-slate-200 rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-[11px] uppercase tracking-wide text-slate-500"><tr><th className="px-3 py-2">Title</th><th className="px-3 py-2">Status</th><th className="px-3 py-2">Rubric</th><th className="px-3 py-2">Job ID</th><th className="px-3 py-2 text-right">Action</th></tr></thead>
              <tbody className="divide-y divide-slate-100">
                {jobs.length === 0 ? (
                  <tr><td colSpan={5} className="px-3 py-6 text-center text-xs text-slate-400">No jobs yet. Create one above — existing reviews without a Job remain valid.</td></tr>
                ) : jobs.map(j => (
                  <tr key={j.id}>
                    <td className="px-3 py-2 text-xs font-medium text-slate-700">{j.title}</td>
                    <td className="px-3 py-2"><span className="text-[11px] px-2 py-1 rounded bg-slate-100">{j.status}</span></td>
                    <td className="px-3 py-2"><span className={`text-[11px] px-2 py-1 rounded ${j.rubric_approved ? 'bg-emerald-50 text-emerald-700' : j.rubric ? 'bg-amber-50 text-amber-700' : 'bg-slate-100 text-slate-500'}`}>{j.rubric_approved ? 'APPROVED' : j.rubric ? 'DRAFT' : '—'}</span></td>
                    <td className="px-3 py-2 font-mono text-[11px] text-slate-500">{j.id.slice(0, 8)}</td>
                    <td className="px-3 py-2 text-right flex gap-1 justify-end flex-wrap">
                      {j.rubric && <button onClick={() => alert(JSON.stringify(j.rubric, null, 2))} className="text-xs text-slate-500">View</button>}
                      <button onClick={async () => { setBusy(true); try { const nj = await api(`/api/jobs/${j.id}/rubric/draft`, { method: 'POST' }); setJobs(prev => prev.map(x => x.id === j.id ? nj : x)) } catch(e){alert(e.message)} finally{setBusy(false)} }} disabled={busy || !j.jd_text} className="text-xs text-brand-600 hover:text-brand-700 disabled:text-slate-300" title={!j.jd_text ? 'Add JD first' : 'Generate'}>Draft</button>
                      <button onClick={async () => { const cur = JSON.stringify(j.rubric || []); const ed = prompt('Edit rubric JSON array [{requirement,points,evidence}]:', cur); if(ed===null) return; try { const arr = JSON.parse(ed); const nj = await api(`/api/jobs/${j.id}`, { method: 'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ rubric: arr }) }); setJobs(prev => prev.map(x => x.id===j.id?nj:x)) } catch(e){alert(e.message)} }} disabled={busy} className="text-xs text-slate-500">Edit</button>
                      <button onClick={async () => { setBusy(true); try { const nj = await api(`/api/jobs/${j.id}/rubric/approve`, { method: 'POST' }); setJobs(prev => prev.map(x => x.id===j.id?nj:x)) } catch(e){alert(e.message)} finally{setBusy(false)} }} disabled={busy || !j.rubric || j.rubric_approved} className="text-xs text-emerald-600 disabled:text-slate-300">Approve</button>
                      {j.status !== 'CLOSED' && <button onClick={() => closeJob(j.id)} disabled={busy} className="text-xs text-slate-400">Close</button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-[11px] text-slate-400 mt-2">JD → Draft (AI, BYOK) → Edit (add/remove/points) → Approve (100pts) → OPEN. Old scorecards keep old rubric.</p>
        </section>

        <section className="bg-white border border-slate-200 rounded-lg p-5">
          <h2 className="panel-title">Organization Type <HelpTip text="Agency = external recruiting agency, Internal = your company. Just a label for now." /></h2>
          {org && (
            <div className="flex items-center gap-3">
              <span className="text-xs text-slate-500">Current: <strong className="text-slate-700">{org.org_type || 'internal'}</strong></span>
              <button onClick={() => setOrgType('internal')} disabled={busy || org.org_type === 'internal'} className="btn-ghost text-xs">Internal</button>
              <button onClick={() => setOrgType('agency')} disabled={busy || org.org_type === 'agency'} className="btn-primary text-xs px-3 py-1">Agency</button>
            </div>
          )}
          {orgMsg && <Alert tone={orgMsg.startsWith('Organization is now') ? 'success' : 'error'}>{orgMsg}</Alert>}
          <p className="text-[11px] text-slate-400 mt-2">Ponytail: flag only — no extra agency logic until you need it. Add when workflow differs.</p>
        </section>
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
