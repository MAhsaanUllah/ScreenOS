import { useEffect, useState } from 'react'
import { api } from './api.js'
import { PageHeader } from './ui.jsx'

export default function Rubrics() {
  const [rubric, setRubric] = useState(null)

  useEffect(() => {
    api('/api/rubric').then(setRubric).catch(err => alert(err.message))
  }, [])

  return (
    <div className="max-w-[1400px] mx-auto">
      <PageHeader eyebrow="Scoring Criteria" title="Active Rubric"
        description={rubric ? rubric.job : 'Loading rubric...'} />

      {rubric && (
        <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[11px] uppercase tracking-wider text-slate-400 border-b border-slate-200">
                <th className="px-4 py-3 font-semibold w-16">Points</th>
                <th className="px-4 py-3 font-semibold">Requirement</th>
                <th className="px-4 py-3 font-semibold">Evidence to look for</th>
              </tr>
            </thead>
            <tbody>
              {rubric.rows.map(r => (
                <tr key={r.requirement} className="border-b border-slate-100 last:border-0">
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center justify-center w-10 h-10 rounded-lg bg-blue-50 text-blue-700 font-mono font-semibold text-sm">{r.points}</span>
                  </td>
                  <td className="px-4 py-3 font-semibold text-slate-900">{r.requirement}</td>
                  <td className="px-4 py-3 text-[13px] text-slate-600">{r.evidence}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="px-4 py-3 bg-slate-50 border-t border-slate-200 text-xs text-slate-500">
            Total 100 points · Scores must be backed by verbatim quotes · MET = full, PARTIALLY_MET = half, NOT_FOUND = zero.
          </div>
        </div>
      )}
    </div>
  )
}