export const VERDICT_CLASS = {
  STRONG_MATCH: 'verdict-strong',
  POSSIBLE_MATCH: 'verdict-possible',
  WEAK_MATCH: 'verdict-weak'
}

export function VerdictBadge({ verdict }) {
  return (
    <span className={`verdict-badge ${VERDICT_CLASS[verdict] || 'verdict-weak'}`}>
      {verdict.replaceAll('_', ' ')}
    </span>
  )
}

export function CriterionCard({ c }) {
  const isMet = c.status === 'MET'
  const isPartial = c.status === 'PARTIALLY_MET'
  return (
    <article className={`criterion-card ${isMet ? 'met' : isPartial ? 'partial' : 'notfound'}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-semibold text-slate-900">{c.criterion}</span>
        <span className={`text-[11px] font-semibold px-2 py-0.5 rounded ${
          isMet ? 'pill-green' : isPartial ? 'verdict-possible' : 'verdict-weak'
        }`}>
          {c.status.replaceAll('_', ' ')} · {c.score}/{c.weight} Pts
        </span>
      </div>
      <div className="quote-block">
        {c.evidence_quote ? `\u201C${c.evidence_quote}\u201D` : '— No direct evidence found in candidate text.'}
      </div>
    </article>
  )
}

export function Scorecard({ card }) {
  return card ? (
    <div>
      <div className="flex items-end justify-between pb-5 border-b border-slate-200 mb-5">
        <div>
          <div className="text-[11px] uppercase font-semibold tracking-wider text-slate-400">Total Evaluation Score</div>
          <div className="font-mono text-4xl font-bold tracking-tight text-slate-900">
            {card.overall_score}<small className="text-xl text-slate-400 font-medium">/100</small>
          </div>
        </div>
        <VerdictBadge verdict={card.verdict} />
      </div>
      <div className="flex flex-col gap-3.5">
        {card.criteria.map(c => <CriterionCard key={c.criterion} c={c} />)}
      </div>
      <div className="mt-5 p-3.5 bg-slate-50 border border-slate-200 rounded-md">
        <strong className="text-xs text-slate-500 uppercase block mb-1">Scoring Summary & Notes</strong>
        <p className="text-[13px] text-slate-900">{card.notes || 'Automated rubric evaluation completed.'}</p>
      </div>
    </div>
  ) : null
}