import React from 'react'
import { ShieldAlert, ShieldCheck, ShieldQuestion, FileWarning } from 'lucide-react'
import type { EvidencePassport, EvidenceTier, ReliabilityBand, SupportTier } from '../api/client'

interface EvidencePassportViewProps {
  passport: EvidencePassport
  drugA: string
  drugB: string
}

const evidenceTierLabel: Record<EvidenceTier, string> = {
  documented: 'Documented pair',
  mechanism_evidence: 'Mechanism evidence found',
  indirect_evidence: 'Indirect evidence only',
  no_evidence: 'No supporting evidence found',
}

const evidenceTierClass: Record<EvidenceTier, string> = {
  documented: 'bg-emerald-100 text-emerald-800 border-emerald-300',
  mechanism_evidence: 'bg-blue-100 text-blue-800 border-blue-300',
  indirect_evidence: 'bg-amber-100 text-amber-800 border-amber-300',
  no_evidence: 'bg-slate-100 text-slate-700 border-slate-300',
}

const reliabilityClass: Record<ReliabilityBand, string> = {
  High: 'text-emerald-700',
  Moderate: 'text-amber-700',
  Low: 'text-rose-700',
}

const supportLabel: Record<SupportTier, string> = {
  sparse: 'Sparse data',
  limited: 'Limited data',
  well_represented: 'Well represented',
}

/** Abstain state: shown instead of a severity badge when the model's evidence
 * doesn't clear the empirically-measured reliability bar for this pair. */
export const AbstainCard: React.FC<{ drugA: string; drugB: string; reason: string | null }> = ({
  drugA,
  drugB,
  reason,
}) => (
  <div className="rounded-lg border-2 border-slate-300 bg-slate-50 p-4">
    <div className="flex items-start gap-3">
      <FileWarning className="h-5 w-5 text-slate-500 shrink-0 mt-0.5" />
      <div>
        <p className="text-sm font-bold text-slate-900">
          {drugA} + {drugB}: insufficient evidence for a reliable estimate
        </p>
        <p className="mt-1 text-xs text-slate-600 leading-relaxed">
          {reason || 'PolyGuard cannot support a reliable severity estimate for this pair.'}
        </p>
        <p className="mt-1 text-[11px] text-slate-500 italic">
          Do not infer low risk from this - verify this combination independently.
        </p>
      </div>
    </div>
  </div>
)

export const EvidencePassportView: React.FC<EvidencePassportViewProps> = ({ passport }) => {
  const { evidence_tier, drug_a_support, drug_b_support, reliability } = passport

  const Icon =
    evidence_tier === 'documented'
      ? ShieldCheck
      : evidence_tier === 'no_evidence'
      ? ShieldQuestion
      : ShieldAlert

  return (
    <div className="mt-3 rounded-lg border border-slate-200 bg-white/70 p-3">
      <div className="flex items-center gap-1.5 font-bold text-slate-900 text-[11px] tracking-wide uppercase mb-2">
        <Icon className="h-3.5 w-3.5 text-slate-500 shrink-0" />
        <span>Evidence Passport</span>
      </div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs">
        <span
          className={`inline-block font-bold px-2 py-0.5 rounded-full border ${evidenceTierClass[evidence_tier]}`}
        >
          {evidenceTierLabel[evidence_tier]}
        </span>
        <span className="text-slate-600">
          Model reliability at this confidence:{' '}
          <span className={`font-bold ${reliabilityClass[reliability.band]}`}>
            {reliability.band} ({Math.round(reliability.empirical_accuracy * 100)}% historically, held-out test)
          </span>
        </span>
      </div>
      <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-slate-500">
        <span>Drug A data: {supportLabel[drug_a_support.tier]} ({drug_a_support.documented_pair_count} documented pairs)</span>
        <span>Drug B data: {supportLabel[drug_b_support.tier]} ({drug_b_support.documented_pair_count} documented pairs)</span>
      </div>
    </div>
  )
}
