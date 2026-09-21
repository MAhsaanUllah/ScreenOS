import { PageHeader, Alert } from './ui.jsx'

export default function Help() {
  return (
    <div className="max-w-[900px] mx-auto">
      <PageHeader
        eyebrow="For HR — 3 minute guide"
        title="How to use SCREENOS"
        description="No technical knowledge needed. SCREENOS helps you screen CVs fairly — AI checks the CV, you make the final decision."
      />

      <Alert tone="info">
        <span><strong>Tip for first time:</strong> Try the sample CV — no upload needed. Click Upload → Load sample CV → Scan. You will see every step without risk.</span>
      </Alert>

      <div className="grid gap-6 mt-6">
        <section className="bg-white border border-slate-200 rounded-lg p-6">
          <h2 className="panel-title text-base">4 easy steps</h2>
          <ol className="space-y-4 mt-4">
            <li className="flex gap-4">
              <span className="w-8 h-8 rounded-full bg-brand-600 text-white text-sm font-bold flex items-center justify-center shrink-0">1</span>
              <div>
                <strong className="text-sm text-slate-900">Upload CVs</strong>
                <p className="text-sm text-slate-600 mt-1">Go to <em>Upload & Screening</em>. Drag PDFs/DOCXs or click to choose. You can upload 1 or up to 50 at once. Click <strong>Scan</strong>.</p>
                <p className="text-xs text-slate-500 mt-1">No file? Click <strong>Load sample CV</strong> to try.</p>
              </div>
            </li>
            <li className="flex gap-4">
              <span className="w-8 h-8 rounded-full bg-brand-600 text-white text-sm font-bold flex items-center justify-center shrink-0">2</span>
              <div>
                <strong className="text-sm text-slate-900">Check personal info (PII)</strong>
                <p className="text-sm text-slate-600 mt-1">System finds names, emails, phones automatically. Keep all checked to remove them (fair screening), then <strong>Remove selected and continue</strong>. Bias reduces, compliance stays.</p>
              </div>
            </li>
            <li className="flex gap-4">
              <span className="w-8 h-8 rounded-full bg-brand-600 text-white text-sm font-bold flex items-center justify-center shrink-0">3</span>
              <div>
                <strong className="text-sm text-slate-900">Score</strong>
                <p className="text-sm text-slate-600 mt-1">Click <strong>Score candidate</strong>. AI matches CV against the job rubric. Every point has an <strong>exact quote</strong> from the CV — no guess. If no key is set, ask admin or use <em>Ollama (local)</em>.</p>
              </div>
            </li>
            <li className="flex gap-4">
              <span className="w-8 h-8 rounded-full bg-emerald-600 text-white text-sm font-bold flex items-center justify-center shrink-0">4</span>
              <div>
                <strong className="text-sm text-slate-900">You decide</strong>
                <p className="text-sm text-slate-600 mt-1">Review evidence card. Add notes (optional) → <strong>Approve for interview</strong> or <strong>Reject</strong>. Your decision is final and saved. AI never auto-hires.</p>
              </div>
            </li>
          </ol>
        </section>

        <section className="bg-white border border-slate-200 rounded-lg p-6">
          <h2 className="panel-title">What is an AI key? Do I need it?</h2>
          <p className="text-sm text-slate-600 mt-2">
            Think of it like a password that lets SCREENOS talk to DeepSeek / Gemini / OpenAI. <strong>You don’t need to buy one immediately:</strong> choose <em>Ollama (local)</em> in Settings — it runs on your own computer and needs no key. If your company already has a key, admin pastes it in <em>Settings → AI Provider Keys</em> and it stays encrypted (<code className="px-1 py-0.5 bg-slate-100 rounded text-xs">…last4</code> only shown).
          </p>
          <p className="text-xs text-slate-500 mt-2">Keys are never shown again after saving. Two keys = automatic fallback if one is down.</p>
        </section>

        <section className="bg-white border border-slate-200 rounded-lg p-6">
          <h2 className="panel-title">Where to find everything</h2>
          <ul className="text-sm text-slate-600 list-disc list-inside space-y-1 mt-2">
            <li><strong>Candidate Queue</strong> — all CVs, filter by Pending / Scored / Approved / Rejected</li>
            <li><strong>Analytics</strong> — how many approved vs rejected, where AI & human disagreed</li>
            <li><strong>Rubrics</strong> — what the job requires (points must total 100)</li>
            <li><strong>Team & Roles</strong> — admin can add teammates (RECRUITER vs ADMIN)</li>
            <li><strong>Settings</strong> — change org name, password, AI keys</li>
          </ul>
        </section>

        <section className="bg-white border border-amber-200 rounded-lg p-6">
          <h2 className="panel-title">Trouble uploading PDF? (Scanned / blank pages)</h2>
          <p className="text-sm text-slate-600 mt-2">If you see <em>“A PDF page has no readable text”</em>: that PDF is a scanned image, not real text. Fix in 30 seconds:</p>
          <ul className="text-sm text-slate-600 list-disc list-inside space-y-1 mt-2">
            <li><strong>Easiest:</strong> Open the CV in Word → Save As <strong>DOCX</strong> or <strong>TXT</strong> and upload that.</li>
            <li><strong>Bulk:</strong> Select 50 PDFs directly (no ZIP needed) or upload one ZIP with up to 50 files — both work now.</li>
            <li><strong>OCR option (advanced):</strong> Install Tesseract on server + <code className="px-1 py-0.5 bg-slate-100 rounded text-xs">pip install pytesseract Pillow</code> → scanned PDFs will auto-OCR. Local HR doesn’t need this — just use DOCX.</li>
          </ul>
        </section>

        <section className="bg-slate-50 border border-slate-200 rounded-lg p-6">
          <h3 className="text-sm font-bold text-slate-900">Need help?</h3>
          <p className="text-sm text-slate-600 mt-1">Ask your workspace admin, or use the sample CV first. For compliance, every score keeps the exact CV quote and a document hash — auditable anytime under <em>Compliance</em>.</p>
        </section>
      </div>
    </div>
  )
}
