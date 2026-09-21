import { useRef, useState } from 'react'
import { api } from './api.js'
import { Scorecard, VerdictBadge } from './Criterion.jsx'
import { PageHeader, Alert } from './ui.jsx'

const STEPS = ['Upload', 'Review PII', 'Score', 'Decision']

const SAMPLE = `FICTIONAL SAMPLE - not a real applicant
Amina Example
AI Engineer at Example Studio
Built automated invoice review with a human approval step.
Built a Python FastAPI service with validated requests and helpful errors.
Created document search that returned exact source quotes with each answer.
Designed a database with separate customer access and tested access checks.
Added 32 automated tests and deployed the service with failure alerts.`

function StepBar({ current }) {
  return (
    <div className="flex items-center gap-1 mb-6">
      {STEPS.map((label, i) => {
        const n = i + 1
        const active = n === current
        const done = n < current
        return (
          <div key={label} className="flex items-center gap-1">
            <span className={`inline-flex items-center justify-center w-7 h-7 rounded-full text-xs font-semibold border ${
              done ? 'bg-emerald-600 text-white border-emerald-600' :
              active ? 'bg-brand-600 text-white border-brand-600' :
              'bg-white text-slate-400 border-slate-200'
            }`}>{done ? '\u2713' : n}</span>
            <span className={`text-xs font-medium ${active ? 'text-slate-900' : 'text-slate-400'}`}>{label}</span>
            {i < STEPS.length - 1 && <span className="w-6 h-px bg-slate-200 mx-1" />}
          </div>
        )
      })}
    </div>
  )
}

export default function Screening() {
  const fileInput = useRef(null)
  const [step, setStep] = useState(1)
  const [rawText, setRawText] = useState('')
  const [detectedPii, setDetectedPii] = useState([])
  const [selectedPii, setSelectedPii] = useState(new Set())
  const [reviewId, setReviewId] = useState(null)
  const [cleanedText, setCleanedText] = useState('')
  const [card, setCard] = useState(null)
  const [record, setRecord] = useState(null)
  const [notes, setNotes] = useState('')
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState({ text: 'Upload one or more CVs (PDF, DOCX, or TXT) to begin.', error: false })
  const [picked, setPicked] = useState([])
  const [batch, setBatch] = useState(null)

  const MAX_FILES = 50

  function status(text, error) { setNotice({ text, error: !!error }) }

  function onFilesSelected(files) {
    const list = [...files].filter(f => /\.(pdf|docx|txt)$/i.test(f.name))
    if (list.length === 0) { status('Only PDF, DOCX or TXT files are accepted.', true); return }
    if (list.length > MAX_FILES) { status(`Maximum ${MAX_FILES} files per upload. You selected ${list.length}.`, true); return }
    setPicked(list)
    setBatch(null)
    status(`${list.length} file${list.length === 1 ? '' : 's'} selected. Click "Scan".`)
  }

  function loadSample() {
    setPicked([new File([SAMPLE], '01_strong.txt', { type: 'text/plain' })])
    setBatch(null)
    status('Sample CV loaded. Click "Scan".')
  }

  // Step 1: single file → PII review, multiple → batch results
  async function handleUpload(e) {
    e.preventDefault()
    if (!picked.length) return
    setBusy(true)
    try {
      if (picked.length === 1) {
        status('Extracting text and scanning for personal information...')
        const form = new FormData()
        form.append('file', picked[0])
        const data = await api('/api/preview', { method: 'POST', body: form })
        setRawText(data.raw_text)
        setDetectedPii(data.detected_pii)
        setSelectedPii(new Set(data.detected_pii.map((_, i) => i)))
        setCard(null); setRecord(null); setNotes(''); setReviewId(null); setCleanedText('')
        setStep(2)
        status(`Found ${data.detected_pii.length} personal detail${data.detected_pii.length === 1 ? '' : 's'}. Review and confirm what to remove.`)
      } else {
        status(`Uploading ${picked.length} files and scanning...`)
        const form = new FormData()
        picked.forEach(f => form.append('file', f))
        const result = await api('/api/preview/batch', { method: 'POST', body: form })
        setBatch(result)
        status(`Batch processed: ${result.accepted} accepted, ${result.skipped.length} skipped.`)
      }
    } catch (err) {
      status(err.message, true)
    } finally {
      setBusy(false)
    }
  }

  // Step 2: confirm PII removals → store review
  async function handleConfirmPii() {
    setBusy(true)
    status('Applying redactions and preparing candidate record...')
    try {
      const items = [...selectedPii].map(i => detectedPii[i])
      const form = new FormData()
      form.append('raw_text', rawText)
      form.append('remove_pii', JSON.stringify(items))
      const data = await api('/api/preview/confirm', { method: 'POST', body: form })
      setReviewId(data.review_id)
      setCleanedText(data.cleaned_text)
      setStep(3)
      status('Redactions applied. Review the sanitized text and score the candidate.')
    } catch (err) {
      status(err.message, true)
    } finally {
      setBusy(false)
    }
  }

  // Step 3: score candidate
  async function handleScore() {
    if (!reviewId || busy) return
    setBusy(true)
    status('Evaluating candidate against job rubric...')
    try {
      const d = await api(`/api/reviews/${reviewId}/score`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cleaned_text: cleanedText })
      })
      setCard(d)
      setStep(4)
      status('Evidence card ready. Review quotes and make your decision.')
    } catch (err) {
      status(err.message, true)
    } finally {
      setBusy(false)
    }
  }

  // Step 4: decide
  async function handleDecide(decision) {
    try {
      const rec = await api(`/api/reviews/${reviewId}/decision`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision, notes })
      })
      setRecord(rec)
      status('Decision recorded.')
    } catch (err) {
      status(err.message, true)
    }
  }

  function download() {
    if (!record) return
    const blob = new Blob([JSON.stringify(record, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = `screenos-review-${reviewId.slice(0, 8)}.json`; a.click()
    URL.revokeObjectURL(url)
  }

  function togglePii(idx) {
    setSelectedPii(prev => {
      const next = new Set(prev)
      next.has(idx) ? next.delete(idx) : next.add(idx)
      return next
    })
  }

  async function openBatchReview(row) {
    try {
      const detail = await api(`/api/reviews/${row.review_id}`)
      setRawText(detail.cleaned_text)
      setDetectedPii(row.detected_pii || [])
      const allIdx = new Set((row.detected_pii || []).map((_, i) => i))
      setSelectedPii(allIdx)
      setReviewId(row.review_id)
      setCleanedText(detail.cleaned_text)
      setCard(null); setRecord(null); setNotes('')
      setStep(3)
      status(`Loaded ${row.filename}. Review the sanitized text and score.`)
    } catch (err) {
      status(err.message, true)
    }
  }

  const piiTypeLabel = { name: 'Candidate name', email: 'Email address', phone: 'Phone number', year: 'Graduation year' }

  return (
    <div className="max-w-[1400px] mx-auto">
      <PageHeader
        eyebrow="High-trust recruiter workspace"
        title="Evidence first. Human decision."
        description="Screen CVs against verifiable requirements. Positive points require direct quotes."
      />

      <Alert tone={notice.error ? 'error' : 'info'}>{notice.text}</Alert>

      <StepBar current={step} />

      {/* Step 1: Upload */}
      {step === 1 && (
        <div className="grid grid-cols-[460px_1fr] gap-6 items-start max-lg:grid-cols-1">
          <section className="panel">
            <h2 className="panel-title">Upload CVs</h2>
            <form onSubmit={handleUpload}>
              <div
                className="border-2 border-dashed border-slate-300 rounded-lg p-6 text-center bg-slate-50 cursor-pointer hover:border-brand-400 hover:bg-brand-50 transition-colors"
                onDragOver={e => { e.preventDefault(); e.currentTarget.classList.add('border-brand-400', 'bg-brand-50') }}
                onDragLeave={e => { e.currentTarget.classList.remove('border-brand-400', 'bg-brand-50') }}
                onDrop={e => { e.preventDefault(); e.currentTarget.classList.remove('border-brand-400', 'bg-brand-50'); onFilesSelected(e.dataTransfer.files) }}
                onClick={() => fileInput.current?.click()}
              >
                <strong className="block text-sm">{picked.length ? `${picked.length} file${picked.length === 1 ? '' : 's'} selected` : 'Choose files or drag them here'}</strong>
                <p className="text-xs text-slate-400 mt-1">PDF, DOCX or TXT, up to {MAX_FILES} files</p>
                <input ref={fileInput} type="file" accept=".pdf,.docx,.txt" multiple className="hidden" onChange={e => onFilesSelected(e.target.files)} />
              </div>
              <div className="flex items-center justify-between mt-2">
                <span className="text-xs text-slate-400">{picked.length ? picked.map(f => f.name).join(', ') : 'No file selected'}</span>
                <button type="button" onClick={loadSample} className="link-btn text-xs">Load sample CV</button>
              </div>
              <button type="submit" disabled={busy || !picked.length} className="btn-primary mt-4">
                {busy ? 'Scanning...' : `Scan ${picked.length > 1 ? `${picked.length} files` : 'file'}`}
              </button>
            </form>

            {batch && batch.reviews.length > 0 && (
              <div className="mt-4 border border-slate-200 rounded-md overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-left text-[11px] uppercase tracking-wide text-slate-500">
                    <tr>
                      <th className="px-3 py-2">File</th>
                      <th className="px-3 py-2">Guessed name</th>
                      <th className="px-3 py-2 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {batch.reviews.map(r => (
                      <tr key={r.review_id}>
                        <td className="px-3 py-2 text-slate-700">{r.filename}</td>
                        <td className="px-3 py-2 text-slate-500">{r.name_guess || '—'}</td>
                        <td className="px-3 py-2 text-right">
                          <button onClick={() => openBatchReview(r)} className="link-btn text-xs">Open review</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {batch && batch.skipped.length > 0 && (
              <div className="mt-2">
                {batch.skipped.map(s => (
                  <p key={s.filename} className="text-xs text-red-600">Skipped: {s.filename}. {s.reason}</p>
                ))}
              </div>
            )}
          </section>
          <section className="panel">
            <h2 className="panel-title">How it works</h2>
            <ol className="text-sm text-slate-600 space-y-3 list-decimal list-inside">
              <li>Upload one or more CVs. The system extracts text and finds personal details automatically.</li>
              <li>Review detected PII and confirm what to remove.</li>
              <li>AI scores the candidate against the job rubric with verbatim evidence.</li>
              <li>You make the final hiring decision. Every score includes the exact quote from the CV.</li>
            </ol>
          </section>
        </div>
      )}

      {/* Step 2: Review PII */}
      {step === 2 && (
        <div className="max-w-3xl">
          <section className="panel">
            <div className="flex items-center justify-between mb-4">
              <h2 className="panel-title mb-0">Detected personal information</h2>
              <span className="text-xs text-slate-400">{selectedPii.size} of {detectedPii.length} selected</span>
            </div>
            {detectedPii.length === 0 ? (
              <p className="text-sm text-slate-500">No personal details detected. You can continue to scoring.</p>
            ) : (
              <div className="border border-slate-200 rounded-lg overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-[11px] uppercase tracking-wider text-slate-400 border-b border-slate-200 bg-slate-50">
                      <th className="px-4 py-3 w-10">Remove</th>
                      <th className="px-4 py-3">Type</th>
                      <th className="px-4 py-3">Value</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detectedPii.map((item, i) => (
                      <tr key={i} className="border-b border-slate-100 last:border-0">
                        <td className="px-4 py-3">
                          <input
                            type="checkbox"
                            checked={selectedPii.has(i)}
                            onChange={() => togglePii(i)}
                            className="rounded"
                          />
                        </td>
                        <td className="px-4 py-3 text-xs font-medium text-slate-600">{piiTypeLabel[item.type] || item.type}</td>
                        <td className="px-4 py-3 font-mono text-xs text-slate-800">{item.value}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <div className="flex items-center gap-3 mt-4">
              <button onClick={handleConfirmPii} disabled={busy} className="btn-primary">
                {busy ? 'Processing...' : 'Remove selected and continue'}
              </button>
              <button onClick={() => setStep(1)} className="btn-ghost">Back to upload</button>
            </div>
          </section>
        </div>
      )}

      {/* Step 3: Score */}
      {step === 3 && (
        <div className="grid grid-cols-[460px_1fr] gap-6 items-start max-lg:grid-cols-1">
          <section className="panel">
            <h2 className="panel-title">Sanitized candidate text</h2>
            <p className="text-xs text-slate-400 mb-2">Review the text below. Edit if needed, then score.</p>
            <textarea
              value={cleanedText}
              onChange={e => setCleanedText(e.target.value)}
              rows={14}
              maxLength={100000}
              className="w-full px-3 py-2 border border-slate-300 rounded-md font-mono text-xs leading-relaxed resize-y"
            />
            <div className="flex items-center gap-3 mt-4">
              <button className="btn-primary" disabled={busy} onClick={handleScore}>
                {busy ? 'Scoring...' : 'Score candidate'}
              </button>
              <button onClick={() => setStep(2)} className="btn-ghost">Back to PII review</button>
            </div>
          </section>
          <section className="panel">
            <h2 className="panel-title">Evidence card</h2>
            <p className="text-xs text-slate-400">The scorecard will appear here after scoring.</p>
          </section>
        </div>
      )}

      {/* Step 4: Decide */}
      {step === 4 && (
        <div className="grid grid-cols-[1fr_360px] gap-6 items-start max-lg:grid-cols-1">
          <section className="panel">
            <h2 className="panel-title">Evidence card</h2>
            {card && <Scorecard card={card} />}
          </section>
          <section className="panel">
            <h2 className="panel-title">Your decision</h2>
            <p className="text-xs text-slate-400 mb-4">AI recommendations require human review under NYC LL144 and EU AI Act.</p>
            <textarea
              value={notes}
              onChange={e => setNotes(e.target.value)}
              disabled={!!record}
              placeholder="Add recruiter review notes (optional)..."
              maxLength={2000}
              rows={4}
              className="input resize-y mb-4"
            />
            <div className="flex flex-col gap-2">
              <button className="btn-approve" disabled={!!record} onClick={() => handleDecide('APPROVE')}>Approve for interview</button>
              <button className="btn-reject" disabled={!!record} onClick={() => handleDecide('REJECT')}>Reject</button>
            </div>
            {record && (
              <div className="mt-4 pt-4 border-t border-slate-200">
                <p className="text-xs text-emerald-600 font-medium mb-3">
                  {record.decision === 'APPROVE' ? 'Approved for interview' : 'Rejected'} and saved.
                </p>
                <div className="flex gap-2">
                  <button className="btn-ghost" onClick={download}>Download review JSON</button>
                  <button className="btn-ghost" onClick={() => { setStep(1); setCard(null); setRecord(null); setNotes(''); setFileName('No file selected'); status('Upload a CV to begin.'); }}>Screen another</button>
                </div>
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  )
}
