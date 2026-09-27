import React from 'react'
import { GitBranch, ArrowDownRight } from 'lucide-react'
import type { SubsetCertificate } from '../api/client'

interface SubsetCertificateViewProps {
  certificate: SubsetCertificate
}

const certificateTypeLabel: Record<string, string> = {
  reducible: 'Traced to a smaller combination',
  entangled: 'Risk spread across the regimen',
  higher_order: 'Requires all drugs together',
}

export const SubsetCertificateView: React.FC<SubsetCertificateViewProps> = ({ certificate }) => {
  if (!certificate.applicable) {
    return null
  }

  const { certificate_type, summary, minimal_elevated_subsets, total_minimal_subsets_found, removal_impact, caveat, full_regimen_probability } = certificate

  return (
    <div className="rounded-lg border border-indigo-200 bg-indigo-50/60 p-4 shadow-2xs">
      <div className="flex items-center gap-1.5 font-bold text-indigo-900 text-xs tracking-wide uppercase mb-2">
        <GitBranch className="h-4 w-4 text-indigo-700 shrink-0" />
        <span>Minimal Unsafe Subset Certificate</span>
        {certificate_type && (
          <span className="ml-1 font-bold px-2 py-0.5 rounded-full bg-indigo-200 text-indigo-900 text-[10px] normal-case tracking-normal">
            {certificateTypeLabel[certificate_type]}
          </span>
        )}
      </div>

      {summary && <p className="text-sm text-slate-900 font-medium leading-relaxed">{summary}</p>}

      {full_regimen_probability !== undefined && (
        <p className="mt-1 text-xs text-slate-600">
          Full-regimen combination-signal probability: <span className="font-semibold">{Math.round(full_regimen_probability * 100)}%</span>
        </p>
      )}

      {minimal_elevated_subsets && minimal_elevated_subsets.length > 0 && (
        <div className="mt-3 space-y-1.5">
          <div className="text-[11px] font-bold text-indigo-800 uppercase tracking-wider">
            {certificate_type === 'entangled' ? 'Strongest combinations' : 'Responsible combination'}
          </div>
          {minimal_elevated_subsets.map((s, i) => (
            <div key={i} className="flex items-center justify-between text-xs bg-white/70 rounded-md px-2.5 py-1.5 border border-indigo-100">
              <span className="font-medium text-slate-800">{s.drugs.join(' + ')}</span>
              <span className="font-bold text-indigo-700">{Math.round(s.probability * 100)}%</span>
            </div>
          ))}
          {total_minimal_subsets_found !== undefined && total_minimal_subsets_found > minimal_elevated_subsets.length && (
            <p className="text-[11px] text-slate-500 italic">
              +{total_minimal_subsets_found - minimal_elevated_subsets.length} more combination
              {total_minimal_subsets_found - minimal_elevated_subsets.length > 1 ? 's' : ''} from this regimen also independently trigger the signal.
            </p>
          )}
        </div>
      )}

      {removal_impact && removal_impact.length > 0 && (
        <div className="mt-3 space-y-1">
          <div className="flex items-center gap-1 text-[11px] font-bold text-indigo-800 uppercase tracking-wider">
            <ArrowDownRight className="h-3 w-3" />
            <span>If one drug were removed</span>
          </div>
          {removal_impact.map((r, i) => (
            <div key={i} className="flex items-center justify-between text-xs text-slate-700">
              <span>Without <span className="font-medium">{r.drug}</span>:</span>
              <span className={r.still_elevated_without_it ? 'text-slate-600' : 'text-emerald-700 font-semibold'}>
                {Math.round(r.probability_without_this_drug * 100)}%
                {!r.still_elevated_without_it && ' — no longer elevated'}
              </span>
            </div>
          ))}
        </div>
      )}

      {caveat && (
        <div className="mt-3 pt-2 border-t border-indigo-100 text-[11px] text-slate-500 italic">
          {caveat}
        </div>
      )}
    </div>
  )
}
