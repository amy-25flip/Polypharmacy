import React from 'react'
import { HelpCircle, Network, Layers } from 'lucide-react'
import type { PairExplanation } from '../api/client'

interface PairExplanationViewProps {
  explanation: PairExplanation
  compact?: boolean
}

export const formatEvidenceType = (type: string): string => {
  switch (type.toLowerCase()) {
    case 'class':
      return 'Shared drug class'
    case 'side_effect':
      return 'Shared adverse-effect'
    case 'gene':
      return 'Shared biological target'
    case 'structural_resemblance':
      return 'Structural similarity'
    default:
      return type.charAt(0).toUpperCase() + type.slice(1)
  }
}

export const PairExplanationView: React.FC<PairExplanationViewProps> = ({
  explanation,
  compact = false,
}) => {
  const { has_explanation, primary_reason, supporting_evidence, coverage, caveat } = explanation

  const hasLimitedCoverage = !coverage.drug_a_has_kg_data || !coverage.drug_b_has_kg_data

  return (
    <div
      className={`rounded-lg border bg-white/90 text-slate-800 shadow-2xs ${
        compact
          ? 'p-3 text-xs border-slate-200 mt-2 bg-slate-50/60'
          : 'p-4 sm:p-5 border-slate-200/80 mt-3.5 space-y-3'
      }`}
    >
      {/* Section Header */}
      <div className="flex items-center gap-1.5 font-bold text-slate-900 text-xs tracking-wide uppercase">
        <Network className="h-3.5 w-3.5 text-blue-700 shrink-0" />
        <span>Why this may be risky</span>
      </div>

      {has_explanation && primary_reason ? (
        <div className="space-y-2.5">
          {/* Main sentence in plain language */}
          <p className="text-sm font-medium text-slate-900 leading-relaxed">
            {primary_reason.plain_text}
          </p>

          {/* Primary Evidence Items */}
          {primary_reason.evidence && primary_reason.evidence.length > 0 && (
            <div className="text-xs text-slate-700 bg-slate-100/80 rounded-md p-2.5 border border-slate-200/60">
              <span className="font-semibold text-slate-800">
                {primary_reason.title || 'Evidence'}:{' '}
              </span>
              <span className="text-slate-700">
                {primary_reason.evidence.join(', ')}
              </span>
            </div>
          )}

          {/* Supporting Evidence (if any) */}
          {supporting_evidence && supporting_evidence.length > 0 && (
            <div className="pt-1 space-y-1.5">
              <div className="flex items-center gap-1 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                <Layers className="h-3 w-3 text-slate-400" />
                <span>Additional evidence</span>
              </div>
              <div className="space-y-1">
                {supporting_evidence.map((item, idx) => (
                  <div
                    key={idx}
                    className="text-xs text-slate-700 flex items-start gap-1.5"
                  >
                    <span className="font-semibold text-slate-800 shrink-0">
                      {formatEvidenceType(item.type)}:
                    </span>
                    <span>{item.items.join(', ')}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        /* No Knowledge Graph Overlap Found */
        <div className="space-y-1.5 text-xs text-slate-700">
          <div className="flex items-start gap-2">
            <HelpCircle className="h-4 w-4 text-slate-400 shrink-0 mt-0.5" />
            <p className="leading-relaxed">
              No specific shared-mechanism evidence was found in the current knowledge base for this pair. This may reflect incomplete data coverage rather than an absence of risk.
            </p>
          </div>
          {hasLimitedCoverage && (
            <p className="text-[11px] text-slate-500 italic pl-6">
              Limited reference data available for one of these medicines.
            </p>
          )}
        </div>
      )}

      {/* Mandatory Caveat Line */}
      {caveat && (
        <div className="pt-2 border-t border-slate-100 text-[11px] text-slate-500 font-medium italic">
          {caveat}
        </div>
      )}
    </div>
  )
}
