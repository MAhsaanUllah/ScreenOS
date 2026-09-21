import { useRef, useState } from 'react'
import { api } from './api.js'
import { Scorecard } from './Criterion.jsx'

const SAMPLE = `FICTIONAL SAMPLE - not a real applicant
Amina Example
AI Engineer at Example Studio
Built automated invoice review with a human approval step.
Built a Python FastAPI service with validated requests and helpful errors.
Created document search that returned exact source quotes with each answer.
Designed a database with separate customer access and tested access checks.
Added 32 automated tests and deployed the service with failure alerts.`

export default function Screening() {
  const fileInput = useRef(null)
  const [token, setToken] = useState(null)
  const [busy, setBusy] = useState(false)
  const [fileName, setFileName] = useState('No file selected')
  const [cleaned, setCleaned] = useState('')
  const [consent, setConsent] = useState(false)
  const [notice, setNotice] = useState({ text: 'Upload a CV (PDF, DOCX, or TXT) to begin local intake.', error: false })
  const [card, setCard] = useState(null)
  const [record, setRecord] = useState(null)
  const [notes, setNotes] = useState('')

  function status(text, error) { setNotice({ text, error: !!error }) }

  function loadSample() {
    const file = new File([SAMPLE], '01_strong.txt', { type: 'text/plain' })
    if (fileInput.current) fileInput.current.files = [file]
    setFileName('Selected: 01_strong.txt')
    document.getElementById('name-input').value = 'Amina Example'
    status('Sample CV loaded: 01_strong.txt. Click "Prepare & Clean Resume".')
  }

  async function prepare(e) {
    e.preventDefault()
    const form = new FormData(e.target)
    setBusy(true); setToken(null); setCard(null); setRecord(null); setNotes('')
    status('Extracting text and applying PII guardrails...')
    try {
      const data = await api('/api/preview', { method: 'POST', body: form })
      setToken(data.review_id)
      setCleaned(data.cleaned_text)
      setConsent(false)
      status('PII sanitized and candidate hash generated. Review text and authorize scoring.')
    } catch (err) {
      status(err.message, true)
    } finally {
      setBusy(false)
    }
  }

  async function score() {
    if (!token || !consent || busy) return
    setBusy(true)
    status('Evaluating candidate against job rubric... Please wait a few moments.')
    try {
      const d = await api(`/api/reviews/${token}/score`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cleaned_text: cleaned })
      })
      setCard(d)
      status('Evidence card ready. Review supporting quotes and make your screening decision.')
    } catch (err) {
      status(err.message, true)
    } finally {
      setBusy(false)
    }
  }

  async function decide(decision) {
    try {
      const rec = await api(`/api/reviews/${token}/decision`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision, notes })
      })
      setRecord(rec)
      status(`Decision recorded. You may download the audit JSON or screen another candidate.`)
    } catch (err) {
      status(err.message, true)
    }
  }

  function download() {
    if (!record) return
    const blob = new Blob([JSON.stringify(record, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `screenos-review-${token.slice(0, 8)}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="max-w-[1400px] mx-auto">
      <div className="mb-5">
        <p className="text-[11px] font-bold tracking-widest uppercase text-blue-600 mb-1">High-Trust Recruiter Workspace</p>
        <h1 className="text-2xl font-bold tracking-tight">Evidence First. Human Decision.</h1>
        <p className="text-sm text-slate-600 mt-0.5">Screen CVs against verifiable requirements. Positive points require direct quotes.</p>
      </div>

      <div
        role="status"
        aria-live="polite"
        className={`px-4 py-3 rounded-md text-[13px] font-medium mb-5 flex items-center gap-2 ${
          notice.error ? 'bg-rose-50 border border-rose-200 text-rose-700' : 'bg-blue-50 border border-blue-200 text-blue-800'
        }`}
      >{notice.text}</div>

      <div className="grid grid-cols-[460px_1fr] gap-6 items-start max-lg:grid-cols-1">
        <section className="panel">
          <h2 className="text-[15px] font-semibold mb-4">1. Intake & Safety Redaction</h2>

          <form onSubmit={prepare}>
            <div
              className="border-2 border-dashed border-slate-300 rounded-lg p-6 text-center bg-slate-50 cursor-pointer hover:border-blue-500 hover:bg-blue-50 transition-colors"
              onClick={() => fileInput.current?.click()}
            >
              <div className="text-2xl mb-1">📄</div>
              <strong className="block text-sm">Choose a resume file or drag here</strong>
              <p className="text-xs text-slate-400 mt-1">Supported: PDF, DOCX, TXT (up to 10 MB)</p>
              <input ref={fileInput} name="file" id="file-input" type="file" accept=".pdf,.docx,.txt" required className="hidden" />
            </div>

            <div className="flex items-center justify-between mt-2">
              <span className="text-xs text-slate-400">{fileName}</span>
              <button type="button" onClick={loadSample} className="text-xs text-blue-600 underline">Load Sample CV (01_strong.txt)</button>
            </div>

            <label className="block text-[13px] font-semibold mt-4 mb-1">Candidate Full Name (to redact)</label>
            <input id="name-input" name="name" required placeholder="e.g. Amina Example" maxLength={200}
              className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm" />
            <p className="text-xs text-slate-400 mt-1">Required to strip name references and prevent demographic bias.</p>

            <details className="mt-4 mb-3 p-2.5 bg-slate-50 border border-slate-200 rounded-md">
              <summary className="cursor-pointer text-xs font-medium text-slate-600">Additional Identity Redaction (Optional)</summary>
              <label className="block text-[13px] font-semibold mt-3 mb-1">Address to redact</label>
              <input name="address" placeholder="e.g. Gujranwala, Pakistan" maxLength={500}
                className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm" />
              <label className="block text-[13px] font-semibold mt-3 mb-1">Graduation years to redact</label>
              <input name="years" placeholder="e.g. 2022, 2026"
                className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm" />
            </details>

            <button type="submit" disabled={busy} className="btn-primary mt-3">Prepare & Clean Resume</button>
          </form>

          {token && (
            <div className="mt-6">
              <div className="flex gap-2 mb-4">
                <span className="pill-green">✓ PII Sanitized</span>
                <span className="pill-blue">✓ Anti-Injection Boundary Active</span>
              </div>
              <label className="block text-[13px] font-semibold mb-1">Sanitized Candidate Text (Auditable & Editable)</label>
              <p className="text-xs text-slate-400 mb-1">Review the sanitized text below before scoring.</p>
              <textarea
                value={cleaned}
                onChange={e => { setCleaned(e.target.value); setConsent(false) }}
                rows={12}
                maxLength={100000}
                disabled={busy}
                className="w-full px-3 py-2 border border-slate-300 rounded-md font-mono text-xs leading-relaxed resize-y"
              />
              <label className="flex items-start gap-2.5 mt-4 mb-1 text-xs text-slate-600 font-normal">
                <input type="checkbox" checked={consent} disabled={busy} onChange={e => setConsent(e.target.checked)} className="mt-1" />
                <span>I have verified the sanitized text and authorize evaluation.</span>
              </label>
              <button className="btn-primary" disabled={!consent || busy} onClick={score}>Score Candidate with AI Scorer</button>
            </div>
          )}
        </section>

        <section className="panel">
          <h2 className="text-[15px] font-semibold mb-4">2. Verified Evidence Card</h2>

          {!card ? (
            <div className="text-center py-16 text-slate-400">
              <div className="text-3xl mb-3 text-slate-300">📊</div>
              <h3 className="text-sm font-medium text-slate-500">Scorecard will generate here</h3>
              <p className="text-xs mt-2 max-w-[320px] mx-auto">Every awarded score includes the exact verbatim quote from the candidate CV.</p>
            </div>
          ) : (
            <Scorecard card={card} />
          )}
        </section>
      </div>

      {card && (
        <div className="fixed bottom-0 left-52 right-0 bg-white/95 backdrop-blur border-t border-slate-200 px-6 py-3 flex items-center justify-between shadow-[0_-4px_12px_rgba(0,0,0,0.03)] z-50 max-lg:left-0 max-lg:flex-col max-lg:gap-2.5 max-lg:items-stretch">
          <div className="flex items-center gap-4 flex-1">
            <div className="shrink-0">
              <strong className="text-[13px] block">3. Human Recruiter Decision</strong>
              <span className="text-xs text-slate-400">AI recommendations require human review under NYC LL144 & EU AI Act.</span>
            </div>
            <input
              value={notes}
              onChange={e => setNotes(e.target.value)}
              disabled={!!record}
              placeholder="Add recruiter review notes (optional)..."
              maxLength={2000}
              className="flex-1 min-w-[200px] px-3 py-2 border border-slate-200 rounded-md text-sm"
            />
          </div>
          <div className="flex items-center gap-2.5">
            {record && <span className="text-xs text-emerald-600 font-medium">✓ {record.decision === 'APPROVE' ? 'Approved for Interview' : 'Rejected'} (Saved)</span>}
            <button className="btn-approve" disabled={!!record} onClick={() => decide('APPROVE')}>Approve (Interview)</button>
            <button className="btn-reject" disabled={!!record} onClick={() => decide('REJECT')}>Reject</button>
            {record && <button className="bg-white text-slate-600 border border-slate-200 px-3.5 py-2 rounded-md text-sm font-medium hover:bg-slate-50" onClick={download}>Download Review JSON</button>}
          </div>
        </div>
      )}
    </div>
  )
}