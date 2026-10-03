import { AlertTriangle, CheckCircle2, Info } from 'lucide-react'
import type { CandidateFlag, ScreenedPair, Severity } from '../api/client'

const classes: Record<string, string> = {
  Major: 'border-rose-300 bg-rose-50 text-rose-900',
  Moderate: 'border-amber-300 bg-amber-50 text-amber-900',
  Minor: 'border-emerald-300 bg-emerald-50 text-emerald-900',
}

export function SeverityLabel({ severity, uncertain }: { severity: Severity | string; uncertain?: boolean }) {
  if (!severity) return <span className="inline-flex items-center gap-1 text-xs text-slate-500"><CheckCircle2 className="h-3.5 w-3.5" /> No interaction found with current plan</span>
  return <span className={`inline-flex flex-wrap items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-semibold ${uncertain ? 'border-slate-300 bg-slate-100 text-slate-800' : classes[severity] || classes.Minor}`}>
    {uncertain ? <Info className="h-3.5 w-3.5" /> : <AlertTriangle className="h-3.5 w-3.5" />}
    {severity}{uncertain && ' · low-confidence estimate'}
  </span>
}

export function ScreeningFlag({ flags, severity, basis }: { flags: CandidateFlag[]; severity: Severity; basis: string }) {
  const worst = flags.find((flag) => flag.severity === severity) || flags[0]
  return <div className="min-w-0 text-xs">
    <SeverityLabel severity={severity} uncertain={worst?.uncertain} />
    {worst && <span className="ml-1 text-slate-600">with {worst.with}</span>}
    {flags.length > 0 && <details className="mt-1 text-slate-700">
      <summary className="w-fit cursor-pointer font-semibold text-blue-800">Interaction details</summary>
      <ul className="mt-2 space-y-2">
        {flags.map((flag, index) => <li key={`${flag.with}-${index}`} className="break-words rounded-md bg-slate-50 p-2">
          <span className="font-semibold">With {flag.with}: </span><SeverityLabel severity={flag.severity} uncertain={flag.uncertain} />
          <span className="ml-1">{flag.is_documented ? 'Documented' : 'Inferred'}</span>
          {flag.adverse_effects.length > 0 && <div className="mt-1 flex flex-wrap gap-1">{flag.adverse_effects.map((effect) => <span key={effect} className="rounded bg-white px-1.5 py-0.5 text-slate-700">{effect}</span>)}</div>}
        </li>)}
      </ul>
      <p className="mt-2 text-[11px] text-slate-600">{basis}</p>
    </details>}
  </div>
}

export function pairAsFlag(pair: ScreenedPair, medicine: string): CandidateFlag {
  return {
    with: pair.drug_a.toLowerCase() === medicine.toLowerCase() ? pair.drug_b : pair.drug_a,
    severity: pair.severity,
    is_documented: pair.is_documented,
    uncertain: pair.uncertain,
    adverse_effects: pair.adverse_effects,
  }
}
