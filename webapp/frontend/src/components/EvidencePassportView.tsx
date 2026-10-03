import React from 'react'
import { ShieldAlert, ShieldCheck, ShieldQuestion, FileWarning, Braces } from 'lucide-react'
import type { ConformalSet, ConformalSets, EvidencePassport, EvidenceTier, ReliabilityBand, SupportTier } from '../api/client'

interface EvidencePassportViewProps {
  passport: EvidencePassport
  drugA: string
  drugB: string
  conformalSets?: ConformalSets
  /** False when the severity comes from a database record, so the model's reliability does not apply. */
  modelBased?: boolean
}

const severityDotClass: Record<string, string> = {
  Minor: 'bg-emerald-500',
  Moderate: 'bg-amber-500',
  Major: 'bg-rose-500',
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

const disagreementClass: Record<'Low' | 'Moderate' | 'High', string> = {
  Low: 'text-emerald-700',
  Moderate: 'text-amber-700',
  High: 'text-rose-700',
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

const CONFORMAL_LEVELS = ['0.8', '0.9', '0.95']

export const EvidencePassportView: React.FC<EvidencePassportViewProps> = ({ passport, conformalSets, modelBased = true }) => {
  const { evidence_tier, drug_a_support, drug_b_support, reliability, cross_model_agreement } = passport
  const conformalLevels: { level: string; entry: ConformalSet }[] = CONFORMAL_LEVELS
    .map((level) => ({ level, entry: conformalSets?.[level] }))
    .filter((row): row is { level: string; entry: ConformalSet } => !!row.entry)

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
        {modelBased ? (
          <span className="text-slate-600">
            Model reliability at this confidence:{' '}
            <span className={`font-bold ${reliabilityClass[reliability.band]}`}>
              {reliability.band} ({Math.round(reliability.empirical_accuracy * 100)}% historically, held-out test)
            </span>
          </span>
        ) : (
          <span className="text-slate-600">Severity is taken from the reference database record, not predicted.</span>
        )}
      </div>
      <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-slate-500">
        <span>Drug A data: {supportLabel[drug_a_support.tier]} ({drug_a_support.documented_pair_count} documented pairs)</span>
        <span>Drug B data: {supportLabel[drug_b_support.tier]} ({drug_b_support.documented_pair_count} documented pairs)</span>
      </div>
      {conformalLevels.length > 0 && (
        <div className="mt-2 pt-2 border-t border-slate-100 text-xs">
          <div className="flex items-center gap-1.5 font-semibold text-slate-700 mb-1.5">
            <Braces className="h-3.5 w-3.5 text-slate-400 shrink-0" />
            <span>Conformal severity set — statistically guaranteed coverage, not a single guess</span>
          </div>
          <div className="space-y-1">
            {conformalLevels.map(({ level, entry }) => (
              <div key={level} className="flex items-center gap-2">
                <span className="w-16 shrink-0 font-mono font-bold text-slate-500">
                  {Math.round(Number(level) * 100)}%
                </span>
                <div className="flex items-center gap-1.5 flex-wrap">
                  {entry.set.map((s) => (
                    <span
                      key={s}
                      className="inline-flex items-center gap-1 font-bold text-slate-800 bg-slate-100 border border-slate-200 rounded-full px-2 py-0.5"
                    >
                      <span className={`h-1.5 w-1.5 rounded-full ${severityDotClass[s]}`} />
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
          <p className="mt-1.5 text-[11px] text-slate-500 italic">
            As target coverage rises, the guaranteed set widens — a mathematically calibrated way of saying how sure PolyGuard really is, not just a confidence number.
          </p>
        </div>
      )}

      {modelBased && cross_model_agreement && (
        <div className="mt-2 pt-2 border-t border-slate-100 text-xs">
          <span className="font-semibold text-slate-700">Independent second opinion (chemistry model): </span>
          <span className={`font-bold ${disagreementClass[cross_model_agreement.disagreement_level]}`}>
            {cross_model_agreement.disagreement_level} disagreement
          </span>
          <span className="text-slate-500">
            {' '}(chemistry model says {cross_model_agreement.chemistry_model_severity}
            {cross_model_agreement.disagreement_level !== 'Low' && (
              <> — historically {Math.round(cross_model_agreement.model1_empirical_accuracy_at_this_disagreement * 100)}% accurate at this disagreement level</>
            )}
            )
          </span>
        </div>
      )}
    </div>
  )
}
