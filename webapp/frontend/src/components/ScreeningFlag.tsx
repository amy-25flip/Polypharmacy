import { AlertTriangle, CheckCircle2, HelpCircle, Info } from 'lucide-react'
import type { CandidateFlag, ScreenedPair, Severity } from '../api/client'
import { basisLabel, severityName } from '../severity'

const classes: Record<string, string> = {
  Major: 'border-rose-300 bg-rose-50 text-rose-900',
  Moderate: 'border-amber-300 bg-amber-50 text-amber-900',
  Minor: 'border-emerald-300 bg-emerald-50 text-emerald-900',
  None: 'border-slate-300 bg-slate-100 text-slate-800',
}

export function SeverityLabel({ severity, uncertain, notChecked }: { severity: Severity | string; uncertain?: boolean; notChecked?: boolean }) {
  if (notChecked) return <span className="inline-flex items-center gap-1 rounded-full border border-slate-300 bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-800"><Info className="h-3.5 w-3.5" /> Not checked (no interaction data)</span>
  if (!severity) return <span className="inline-flex items-center gap-1 text-xs text-slate-500"><CheckCircle2 className="h-3.5 w-3.5" /> No interaction found with current plan</span>
  return <span className={`inline-flex flex-wrap items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-semibold ${uncertain ? 'border-slate-300 bg-slate-100 text-slate-800' : classes[severity] || classes.Minor}`}>
    {uncertain ? <Info className="h-3.5 w-3.5" /> : severity === 'None' ? <HelpCircle className="h-3.5 w-3.5" /> : <AlertTriangle className="h-3.5 w-3.5" />}
    {severityName(severity)}{uncertain && ' · low-confidence estimate'}
  </span>
}

export function ScreeningFlag({ flags, severity, basis }: { flags: CandidateFlag[]; severity: Severity; basis: string }) {
  const worst = flags.find((flag) => flag.severity === severity) || flags[0]
  const estimates = flags.flatMap((flag) => flag.estimated_from ?? [])
  const estimateNotes = [...new Map(estimates.map((note) => [`${note.drug}|${note.proxy}`, note])).values()]
  return <div className="min-w-0 text-xs">
    <SeverityLabel severity={severity} uncertain={worst?.uncertain} notChecked={severity === 'None' && worst?.severity_basis === 'no_data'} />
    {worst && <span className="ml-1 text-slate-600">with {worst.with}</span>}
    {flags.length > 0 && <details className="mt-1 text-slate-700">
      <summary className="w-fit cursor-pointer font-semibold text-blue-800">Interaction details</summary>
      <ul className="mt-2 space-y-2">
        {flags.map((flag, index) => <li key={`${flag.with}-${index}`} className="break-words rounded-md bg-slate-50 p-2">
          <span className="font-semibold">With {flag.with}: </span><SeverityLabel severity={flag.severity} uncertain={flag.uncertain} notChecked={flag.severity_basis === 'no_data'} />
          <span className="ml-1">{basisLabel(flag.severity_basis, flag.is_documented)}</span>
          {flag.adverse_effects.length > 0 && <div className="mt-1 flex flex-wrap gap-1">{flag.adverse_effects.map((effect) => <span key={effect} className="rounded bg-white px-1.5 py-0.5 text-slate-700">{effect}</span>)}</div>}
          {flag.adverse_effect_source === 'label' && <p className="mt-1 text-[11px] text-slate-600">Effects named in the FDA label for this combination.</p>}
          {flag.adverse_effect_source === 'overlap' && flag.adverse_effects.length > 0 && <p className="mt-1 text-[11px] text-slate-600">Side effects both medicines are reported to cause on their own; not specific to this combination.</p>}
          {(flag.label_evidence ?? []).map((entry, entryIndex) => <p key={entryIndex} className="mt-1 text-[11px] italic text-slate-700">FDA label for {entry.from}: “{entry.text}”</p>)}
        </li>)}
      </ul>
      {severity === 'None' && worst?.severity_basis !== 'no_data' && <p className="mt-2 text-[11px] text-slate-600">No interaction is recorded for this combination in the reference database. Risk is not excluded: this is not proof that it is safe.</p>}
      {[...new Set(flags.map((flag) => flag.severity_notice).filter((notice): notice is string => !!notice && !!flags.find((f) => f.severity_notice === notice && f.severity_basis === 'no_data')))].map((notice) => <p key={notice} className="mt-2 text-[11px] text-slate-700">{notice}</p>)}
      {estimateNotes.map((note) => <p key={`${note.drug}-${note.proxy}`} className="mt-2 text-[11px] text-amber-900">{note.drug} has no interaction records of its own, so it is checked as {note.proxy} (estimate). {note.reason}</p>)}
      {flags.some((flag) => flag.adverse_effect_source !== 'label' && flag.adverse_effects.length > 0) && <p className="mt-2 text-[11px] text-slate-600">{basis}</p>}
    </details>}
  </div>
}

export function pairAsFlag(pair: ScreenedPair, medicine: string): CandidateFlag {
  return {
    with: pair.drug_a.toLowerCase() === medicine.toLowerCase() ? pair.drug_b : pair.drug_a,
    severity: pair.severity,
    severity_basis: pair.severity_basis,
    severity_notice: pair.severity_notice,
    estimated_from: pair.estimated_from,
    label_evidence: pair.label_evidence,
    adverse_effect_source: pair.adverse_effect_source,
    is_documented: pair.is_documented,
    uncertain: pair.uncertain,
    adverse_effects: pair.adverse_effects,
  }
}
