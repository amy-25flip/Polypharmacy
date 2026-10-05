import {
  AlertTriangle,
  CheckCircle2,
  AlertOctagon,
  Info,
  HelpCircle,
  ShieldCheck,
  Network,
  FileWarning,
  Printer,
} from 'lucide-react'
import { severityName } from '../severity'
import type { CheckResponse, InteractionPair } from '../api/client'
import { PairExplanationView } from './PairExplanationView'
import { AbstainCard, EvidencePassportView } from './EvidencePassportView'
import { SubsetCertificateView } from './SubsetCertificateView'

interface InteractionResultsProps {
  result: CheckResponse
  onReset?: () => void
  diagnoses?: { name: string; medicines: string[] }[]
}

const severityBadgeClass = (severity: InteractionPair['severity']) =>
  severity === 'Major'
    ? 'bg-rose-100 text-rose-800 border-rose-300'
    : severity === 'Moderate'
    ? 'bg-amber-100 text-amber-800 border-amber-300'
    : severity === 'None'
    ? 'bg-sky-100 text-sky-800 border-sky-300'
    : 'bg-emerald-100 text-emerald-800 border-emerald-300'

const severityPillClass = (severity: InteractionPair['severity']) =>
  severity === 'Major'
    ? 'bg-rose-600 text-white'
    : severity === 'Moderate'
    ? 'bg-amber-600 text-white'
    : severity === 'None'
    ? 'bg-sky-700 text-white'
    : 'bg-emerald-700 text-white'

export const InteractionResults: React.FC<InteractionResultsProps> = ({
  result,
  onReset,
  diagnoses = [],
}) => {
  const { matched, unmatched, regimen, combination_signal, subset_certificate } = result
  const pairs = regimen.pairs || []
  const overallSeverity = regimen.overall_severity

  // Find highest risk pair (backend already sorts worst-first: pairs[0])
  const highestRiskPair: InteractionPair | undefined = pairs.length > 0 ? pairs[0] : undefined
  const hasMultiDrugRegimen = matched.length >= 3

  // Determine Banner Variant: Red, Amber, Green, Gray (incomplete), or Uncertain (abstained).
  // If the worst-looking pair doesn't clear the reliability bar, the banner must not
  // proclaim a confident severity headline - that would contradict the pair-by-pair
  // review directly below it.
  // A "no reaction on record" pair is a result in its own right, whatever the model's own confidence.
  const isUncertain = highestRiskPair?.severity !== 'None' && !!highestRiskPair?.evidence_passport?.abstain
  const isNone = !isUncertain && overallSeverity === 'None'
  const noDataPairs = pairs.filter((pair) => pair.severity_basis === 'no_data')
  const allNotChecked = pairs.length > 0 && noDataPairs.length === pairs.length
  const isMajor = !isUncertain && overallSeverity === 'Major'
  const isModerate = !isUncertain && overallSeverity === 'Moderate'
  const isMinor = !isUncertain && overallSeverity === 'Minor'
  const isIncomplete = matched.length < 2 || overallSeverity === null

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Print-only report header - hidden on screen, shown only in the printed/exported report */}
      <div className="hidden print:block mb-4 pb-4 border-b-2 border-slate-900">
        <h1 className="text-2xl font-extrabold text-slate-950">PolyGuard — Medication Interaction Screening Report</h1>
        <p className="text-sm text-slate-600 mt-1">Generated {new Date().toLocaleString()}</p>
        <p className="text-xs text-slate-600 mt-2 leading-relaxed">
          This is an AI-based clinical decision-support output, not a substitute for clinical judgment,
          prescribing guidelines, or pharmacist review. Verify all findings independently before acting on them.
        </p>
        {diagnoses.length > 0 && <div className="mt-3 border-t border-slate-300 pt-2">
          <h2 className="text-sm font-bold">Medication plan by diagnosis</h2>
          <ul className="mt-1 space-y-1 text-xs">{diagnoses.map((diagnosis) => <li key={diagnosis.name} className="break-words"><strong>{diagnosis.name}:</strong> {diagnosis.medicines.join(', ') || 'No medicines selected'}</li>)}</ul>
        </div>}
      </div>

      {/* Print/export control - screen only */}
      <div className="print:hidden flex justify-end">
        <button
          type="button"
          onClick={() => window.print()}
          className="inline-flex items-center gap-1.5 px-3.5 py-2 text-sm font-semibold rounded-lg bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 shadow-2xs transition-colors"
        >
          <Printer className="h-4 w-4" />
          Print / Export Report
        </button>
      </div>

      {/* 1. Primary Dominant Severity Banner */}
      <div
        role="alert"
        className={`rounded-xl border-2 p-6 sm:p-7 shadow-xs transition-all ${
          isIncomplete || isUncertain
            ? 'bg-slate-50 border-slate-300 text-slate-900'
            : isMajor
            ? 'bg-rose-50 border-rose-500 text-rose-950'
            : isModerate
            ? 'bg-amber-50 border-amber-500 text-amber-950'
            : isNone
            ? 'bg-sky-50 border-sky-500 text-sky-950'
            : 'bg-emerald-50 border-emerald-500 text-emerald-950'
        }`}
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-start gap-4">
            {/* Status Icon */}
            <div
              className={`p-3 rounded-lg shrink-0 ${
                isIncomplete || isUncertain
                  ? 'bg-slate-200 text-slate-700'
                  : isMajor
                  ? 'bg-rose-600 text-white'
                  : isModerate
                  ? 'bg-amber-600 text-white'
                  : isNone
                  ? 'bg-sky-700 text-white'
                  : 'bg-emerald-600 text-white'
              }`}
            >
              {isIncomplete && <HelpCircle className="h-7 w-7" />}
              {isUncertain && <FileWarning className="h-7 w-7" />}
              {isMajor && <AlertOctagon className="h-7 w-7" />}
              {isModerate && <AlertTriangle className="h-7 w-7" />}
              {isMinor && <CheckCircle2 className="h-7 w-7" />}
              {isNone && <ShieldCheck className="h-7 w-7" />}
            </div>

            <div>
              <div className="text-xs font-bold uppercase tracking-wider opacity-75">
                Interaction Screening Result
              </div>
              <h2 className="text-2xl sm:text-3xl font-extrabold tracking-tight mt-0.5">
                {isIncomplete && 'Incomplete Check'}
                {isUncertain && 'Uncertain — Review Needed'}
                {isMajor && 'Major Interaction Risk'}
                {isModerate && 'Moderate Interaction Risk'}
                {isMinor && 'Minor Interaction Risk'}
                {isNone && (allNotChecked ? 'Not Checked — No Interaction Data' : 'No Reaction on Record')}
              </h2>
              {pairs.length > 0 && (
                <p className="mt-2 text-sm font-semibold opacity-85">
                  {matched.length} recognized medicine{matched.length === 1 ? '' : 's'} checked across{' '}
                  {pairs.length} pair{pairs.length === 1 ? '' : 's'}.
                </p>
              )}
            </div>
          </div>

          {onReset && (
            <button
              type="button"
              onClick={onReset}
              className="print:hidden self-start sm:self-center px-4 py-2 text-sm font-semibold rounded-lg bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 shadow-2xs transition-colors"
            >
              Check another regimen
            </button>
          )}
        </div>

        {/* Highest-risk interaction callout */}
        <div className="mt-5 pt-4 border-t border-black/10">
          {isUncertain ? (
            <div>
              <p className="text-base sm:text-lg font-semibold">
                Highest-scoring pair:{' '}
                <span className="underline decoration-2 underline-offset-2">
                  {highestRiskPair.drug_a} + {highestRiskPair.drug_b}
                </span>
                <span className="ml-2 text-xs font-bold uppercase px-2.5 py-1 rounded-full bg-slate-300 text-slate-800">
                  Insufficient evidence
                </span>
              </p>
              <p className="mt-2 text-sm font-medium opacity-85">
                This pair's model output isn't reliable enough to headline as a severity result - see the pair-by-pair review below for why.
              </p>
            </div>
          ) : isNone ? (
            <p className="text-base font-semibold">
              {allNotChecked
                ? 'None of these pairs could be checked because the medicines have no interaction data in the reference database.'
                : 'No interaction is recorded for any pair in this regimen. This means no recorded reaction, not proof that the combination is safe.'}
              {!allNotChecked && noDataPairs.length > 0 && ' Pairs with a medicine that has no interaction data were not checked.'}
            </p>
          ) : highestRiskPair ? (
            <div>
              <p className="text-base sm:text-lg font-semibold">
                Highest-risk pair:{' '}
                <span className="underline decoration-2 underline-offset-2">
                  {highestRiskPair.drug_a} + {highestRiskPair.drug_b}
                </span>
                <span
                  className={`ml-2 text-xs font-bold uppercase px-2.5 py-1 rounded-full ${severityPillClass(
                    highestRiskPair.severity
                  )}`}
                >
                  {severityName(highestRiskPair.severity)}
                </span>
              </p>
              {hasMultiDrugRegimen && (
                <p className="mt-2 text-sm font-medium opacity-85">
                  The remaining medicine{matched.length > 3 ? 's are' : ' is'} reviewed in the pair-by-pair section below and, when supported, in the multi-drug pattern review.
                </p>
              )}

              {highestRiskPair.severity_notice && highestRiskPair.severity_basis !== 'no_record' && (
                <div className="mt-3 p-3 rounded-lg bg-sky-50 border border-sky-300 text-sky-950 shadow-2xs">
                  <div className="flex items-start gap-2.5">
                    <Info className="h-4 w-4 shrink-0 mt-0.5 text-sky-700" />
                    <p className="text-sm font-medium leading-relaxed">{highestRiskPair.severity_notice}</p>
                  </div>
                </div>
              )}

              {highestRiskPair.is_documented === false && highestRiskPair.undocumented_pair_notice && (
                <div className="mt-3 p-3 rounded-lg bg-amber-100/80 border border-amber-300 text-amber-950 shadow-2xs">
                  <div className="flex items-start gap-2.5">
                    <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5 text-amber-700" />
                    <p className="text-sm font-medium leading-relaxed">
                      {highestRiskPair.undocumented_pair_notice}
                    </p>
                  </div>
                </div>
              )}
            </div>
          ) : isIncomplete ? (
            <p className="text-sm font-medium text-slate-700">
              Fewer than 2 recognized medicines were provided. Interaction analysis requires at least 2 database-indexed medicines.
            </p>
          ) : (
            <p className="text-base font-semibold">
              No significant interaction risks identified between these medicines.
            </p>
          )}

          {/* Action-oriented line for Major severity specifically */}
          {isMajor && (
            <div className="mt-3 p-3 rounded-lg bg-rose-100/80 border border-rose-300 text-rose-950 font-semibold text-sm">
              Action recommended: Review therapy, dose, alternatives, or monitoring needs before continuing.
            </div>
          )}
        </div>
      </div>

      {/* 2. Unmatched Medicines Notice (if any) - Framed as limitation, not error */}
      {unmatched.length > 0 && (
        <div
          role="note"
          className="rounded-lg bg-slate-100 border border-slate-300 p-4 text-slate-800"
        >
          <div className="flex items-start gap-3">
            <Info className="h-5 w-5 text-slate-600 shrink-0 mt-0.5" />
            <div className="text-sm">
              <p className="font-semibold text-slate-900">
                {unmatched.length} medicine{unmatched.length > 1 ? 's' : ''} could not be checked:{' '}
                <span className="font-normal italic">{unmatched.join(', ')}</span>
              </p>
              <p className="text-xs text-slate-600 mt-1">
                These items are not present in the reference interaction database and were excluded from this analysis.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* 3. Combination Signal Note */}
      {combination_signal && (
        <div
          role="note"
          className={`rounded-lg border p-4 shadow-2xs ${
            combination_signal.elevated
              ? 'bg-indigo-50/80 border-indigo-200 text-indigo-950'
              : 'bg-emerald-50/80 border-emerald-200 text-emerald-950'
          }`}
        >
          <div className="flex items-start gap-3">
            {combination_signal.elevated ? (
              <Network className="h-5 w-5 text-indigo-700 shrink-0 mt-0.5" />
            ) : (
              <ShieldCheck className="h-5 w-5 text-emerald-700 shrink-0 mt-0.5" />
            )}
            <div className="text-sm space-y-1">
              <p className="font-bold text-xs uppercase tracking-wider">
                Multi-Drug Pattern Review
              </p>
              <p className="font-medium text-slate-800 text-sm leading-relaxed">
                The set-level model reviewed {combination_signal.drugs_used} of {combination_signal.drugs_total} recognized medicines together.
                {' '}
                {combination_signal.elevated
                  ? 'This combination resembles known higher-risk medication patterns; use it as a regimen-level review prompt, not a confirmed interaction.'
                  : 'No elevated regimen-level pattern was flagged for this medicine set.'}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* 3b. Minimal Unsafe Subset Certificate - only meaningful when the combination signal above is elevated */}
      {subset_certificate && <SubsetCertificateView certificate={subset_certificate} />}

      {/* 4. Always-visible pair-by-pair review */}
      {pairs.length > 0 && (
        <section className="rounded-xl border border-slate-200 bg-white shadow-2xs overflow-hidden">
          <div className="px-5 py-4 bg-slate-50/90 border-b border-slate-200">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
              <div>
                <h3 className="text-base font-extrabold text-slate-950">
                  Pair-by-Pair Interaction Review
                </h3>
                <p className="text-sm text-slate-600 mt-1">
                  Every medicine is checked against every other medicine in this regimen.
                </p>
              </div>
              <span className="self-start sm:self-center text-xs font-bold px-2.5 py-1 rounded-full bg-slate-200 text-slate-700">
                {pairs.length} {pairs.length === 1 ? 'pair' : 'pairs'} evaluated
              </span>
            </div>
          </div>

          <div className="divide-y divide-slate-100">
            {pairs.map((pair, index) => {
              const hasExplanation = !!pair.explanation
              const passport = pair.evidence_passport

              if (passport?.abstain && pair.severity !== 'None') {
                return (
                  <article
                    key={`${pair.drug_a}-${pair.drug_b}-${index}`}
                    className="p-4 sm:p-5"
                  >
                    <div className="text-sm font-bold uppercase tracking-wide text-slate-500 mb-2">
                      Pair {index + 1}
                    </div>
                    <AbstainCard drugA={pair.drug_a} drugB={pair.drug_b} reason={passport.abstain_reason} />
                  </article>
                )
              }

              return (
                <article
                  key={`${pair.drug_a}-${pair.drug_b}-${index}`}
                  className="p-4 sm:p-5"
                >
                  <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
                    <div className="min-w-0">
                      <div className="text-sm font-bold uppercase tracking-wide text-slate-500">
                        Pair {index + 1}
                      </div>
                      <h4 className="mt-1 text-lg font-extrabold text-slate-950 break-words">
                        {pair.drug_a}{' '}
                        <span className="text-slate-400 font-semibold">+</span>{' '}
                        {pair.drug_b}
                      </h4>
                    </div>
                    <span
                      className={`self-start inline-block text-xs font-bold px-2.5 py-1 rounded-full border ${severityBadgeClass(
                        pair.severity
                      )}`}
                    >
                      {pair.severity_basis === 'no_data' ? 'Not checked' : severityName(pair.severity)}
                    </span>
                  </div>

                  {pair.severity_notice && (
                    <div className="mt-3 flex items-start gap-2 rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-xs font-semibold text-sky-900">
                      <Info className="h-4 w-4 shrink-0 mt-0.5 text-sky-700" />
                      <span>{pair.severity_notice}</span>
                    </div>
                  )}

                  {pair.is_documented === false && (!pair.severity_basis || pair.severity_basis === 'inferred') && (
                    <div className="mt-3 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-900">
                      <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5 text-amber-700" />
                      <span>
                        No documented record for this exact pair. Treat this as an inferred screening result and verify independently.
                      </span>
                    </div>
                  )}

                  {pair.label_evidence && pair.label_evidence.length > 0 && (
                    <div className="mt-3 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-800">
                      <div className="font-bold uppercase tracking-wide text-[11px] text-slate-600">What the FDA label says about this combination</div>
                      {pair.label_effects && pair.label_effects.length > 0 && (
                        <div className="mt-1 flex flex-wrap gap-1">
                          {pair.label_effects.map((effect) => <span key={effect} className="rounded-full border border-slate-300 bg-slate-50 px-2 py-0.5 font-semibold">{effect}</span>)}
                        </div>
                      )}
                      <ul className="mt-1.5 space-y-1">
                        {pair.label_evidence.map((entry, entryIndex) => (
                          <li key={entryIndex} className="italic text-slate-700">From the label for {entry.from}: “{entry.text}”</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {pair.severity === 'None' || pair.severity_basis === 'duplicate_class' ? null : hasExplanation && pair.explanation ? (
                    <PairExplanationView explanation={pair.explanation} compact />
                  ) : (
                    <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
                      No separate knowledge-graph mechanism was found for this pair in the current reference data.
                    </div>
                  )}

                  {passport && pair.severity !== 'None' && pair.severity_basis !== 'duplicate_class' && (
                    <EvidencePassportView
                      passport={passport}
                      drugA={pair.drug_a}
                      drugB={pair.drug_b}
                      conformalSets={pair.conformal_sets}
                      modelBased={!pair.severity_basis || pair.severity_basis === 'inferred'}
                    />
                  )}
                </article>
              )
            })}
          </div>
        </section>
      )}
    </div>
  )
}
