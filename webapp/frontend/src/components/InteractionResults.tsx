import { useState } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  AlertOctagon,
  ChevronDown,
  ChevronUp,
  Info,
  HelpCircle,
} from 'lucide-react'
import type { CheckResponse, InteractionPair } from '../api/client'
import { PairExplanationView } from './PairExplanationView'

interface InteractionResultsProps {
  result: CheckResponse
  onReset?: () => void
}

export const InteractionResults: React.FC<InteractionResultsProps> = ({
  result,
  onReset,
}) => {
  const [showAllPairs, setShowAllPairs] = useState(false)
  const [expandedPairs, setExpandedPairs] = useState<Record<number, boolean>>({})

  const togglePairExplanation = (index: number) => {
    setExpandedPairs((prev) => ({
      ...prev,
      [index]: !prev[index],
    }))
  }

  const { matched, unmatched, regimen, combination_signal } = result
  const pairs = regimen.pairs || []
  const overallSeverity = regimen.overall_severity

  // Determine Banner Variant: Red, Amber, Green, or Gray
  const isMajor = overallSeverity === 'Major'
  const isModerate = overallSeverity === 'Moderate'
  const isMinor = overallSeverity === 'Minor'
  const isIncomplete = matched.length < 2 || overallSeverity === null

  // Find highest risk pair (backend already sorts worst-first: pairs[0])
  const highestRiskPair: InteractionPair | undefined = pairs.length > 0 ? pairs[0] : undefined

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* 1. Primary Dominant Severity Banner */}
      <div
        role="alert"
        className={`rounded-xl border-2 p-6 sm:p-7 shadow-xs transition-all ${
          isIncomplete
            ? 'bg-slate-50 border-slate-300 text-slate-900'
            : isMajor
            ? 'bg-rose-50 border-rose-500 text-rose-950'
            : isModerate
            ? 'bg-amber-50 border-amber-500 text-amber-950'
            : 'bg-emerald-50 border-emerald-500 text-emerald-950'
        }`}
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-start gap-4">
            {/* Status Icon */}
            <div
              className={`p-3 rounded-lg shrink-0 ${
                isIncomplete
                  ? 'bg-slate-200 text-slate-700'
                  : isMajor
                  ? 'bg-rose-600 text-white'
                  : isModerate
                  ? 'bg-amber-600 text-white'
                  : 'bg-emerald-600 text-white'
              }`}
            >
              {isIncomplete && <HelpCircle className="h-7 w-7" />}
              {isMajor && <AlertOctagon className="h-7 w-7" />}
              {isModerate && <AlertTriangle className="h-7 w-7" />}
              {isMinor && <CheckCircle2 className="h-7 w-7" />}
            </div>

            <div>
              <div className="text-xs font-bold uppercase tracking-wider opacity-75">
                Interaction Screening Result
              </div>
              <h2 className="text-2xl sm:text-3xl font-extrabold tracking-tight mt-0.5">
                {isIncomplete && 'Incomplete Check'}
                {isMajor && 'Major Interaction Risk'}
                {isModerate && 'Moderate Interaction Risk'}
                {isMinor && 'Minor Interaction Risk'}
              </h2>
            </div>
          </div>

          {onReset && (
            <button
              type="button"
              onClick={onReset}
              className="self-start sm:self-center px-4 py-2 text-sm font-semibold rounded-lg bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 shadow-2xs transition-colors"
            >
              Check another regimen
            </button>
          )}
        </div>

        {/* Highest-risk interaction callout */}
        <div className="mt-5 pt-4 border-t border-black/10">
          {highestRiskPair ? (
            <div>
              <p className="text-base sm:text-lg font-semibold">
                Highest-risk interaction:{' '}
                <span className="underline decoration-2 underline-offset-2">
                  {highestRiskPair.drug_a} + {highestRiskPair.drug_b}
                </span>
                <span
                  className={`ml-2 text-xs font-bold uppercase px-2.5 py-1 rounded-full ${
                    highestRiskPair.severity === 'Major'
                      ? 'bg-rose-600 text-white'
                      : highestRiskPair.severity === 'Moderate'
                      ? 'bg-amber-600 text-white'
                      : 'bg-emerald-700 text-white'
                  }`}
                >
                  {highestRiskPair.severity}
                </span>
              </p>

              {/* Undocumented-pair caution - shown regardless of severity, since a
                  confident-looking result on an unlabeled pair is the case that
                  most needs a warning, not silence */}
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

              {/* Explainability Display for Highest-Risk Pair directly under callout */}
              {highestRiskPair.explanation && (
                <PairExplanationView explanation={highestRiskPair.explanation} />
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

      {/* 3. Secondary Combination Signal Note (ONLY shown when combination_signal is present AND elevated === true) */}
      {combination_signal && combination_signal.elevated && (
        <div
          role="note"
          className="rounded-lg bg-indigo-50/80 border border-indigo-200 p-4 text-indigo-950 shadow-2xs"
        >
          <div className="flex items-start gap-3">
            <Info className="h-5 w-5 text-indigo-700 shrink-0 mt-0.5" />
            <div className="text-sm space-y-1">
              <p className="font-bold text-indigo-900 text-xs uppercase tracking-wider">
                Multi-Drug Pattern Review
              </p>
              <p className="font-medium text-slate-800 text-sm leading-relaxed">
                Combination pattern check: this combination resembles known higher-risk medication patterns. Use this as a review prompt, not a confirmed interaction.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* 4. Collapsible "Show all interactions" Section */}
      {pairs.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white overflow-hidden shadow-2xs">
          <button
            type="button"
            onClick={() => setShowAllPairs(!showAllPairs)}
            className="w-full px-5 py-3.5 bg-slate-50/80 hover:bg-slate-100 flex items-center justify-between text-left transition-colors border-b border-slate-200"
          >
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold text-slate-900">
                {showAllPairs ? 'Hide all interactions' : 'Show all interactions'}
              </span>
              <span className="text-xs font-semibold px-2 py-0.5 rounded bg-slate-200 text-slate-700">
                {pairs.length} {pairs.length === 1 ? 'pair' : 'pairs'} evaluated
              </span>
            </div>
            {showAllPairs ? (
              <ChevronUp className="h-5 w-5 text-slate-500" />
            ) : (
              <ChevronDown className="h-5 w-5 text-slate-500" />
            )}
          </button>

          {showAllPairs && (
            <div className="p-4 sm:p-5">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm border-collapse">
                  <thead>
                    <tr className="border-b border-slate-200 text-xs font-bold uppercase tracking-wider text-slate-500">
                      <th className="py-2.5 px-3">Medicine Pair</th>
                      <th className="py-2.5 px-3 text-right">Severity Level</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {pairs.map((pair, index) => {
                      const pairSeverity = pair.severity
                      const badgeClass =
                        pairSeverity === 'Major'
                          ? 'bg-rose-100 text-rose-800 border-rose-300'
                          : pairSeverity === 'Moderate'
                          ? 'bg-amber-100 text-amber-800 border-amber-300'
                          : 'bg-emerald-100 text-emerald-800 border-emerald-300'

                      const isExpanded = !!expandedPairs[index]
                      const hasExplanation = !!pair.explanation

                      return (
                        <tr
                          key={`${pair.drug_a}-${pair.drug_b}-${index}`}
                          className="hover:bg-slate-50/75 transition-colors group"
                        >
                          <td className="py-3 px-3 align-top">
                            <div className="font-semibold text-slate-900">
                              {pair.drug_a}{' '}
                              <span className="text-slate-400 font-normal">+</span>{' '}
                              {pair.drug_b}
                            </div>

                            {pair.is_documented === false && (
                              <div className="mt-1 flex items-center gap-1 text-[11px] font-semibold text-amber-800">
                                <AlertTriangle className="h-3 w-3 shrink-0" />
                                <span>No documented record for this exact pair</span>
                              </div>
                            )}

                            {/* Inline reason toggle button if explanation exists */}
                            {hasExplanation && (
                              <button
                                type="button"
                                onClick={() => togglePairExplanation(index)}
                                className="mt-1 text-xs text-blue-700 hover:text-blue-900 font-semibold flex items-center gap-1 transition-colors"
                              >
                                <span>{isExpanded ? 'Hide mechanism' : 'Why this may be risky'}</span>
                                {isExpanded ? (
                                  <ChevronUp className="h-3.5 w-3.5" />
                                ) : (
                                  <ChevronDown className="h-3.5 w-3.5" />
                                )}
                              </button>
                            )}

                            {/* Expanded Inline Explanation */}
                            {hasExplanation && isExpanded && pair.explanation && (
                              <PairExplanationView explanation={pair.explanation} compact />
                            )}
                          </td>
                          <td className="py-3 px-3 text-right align-top">
                            <span
                              className={`inline-block text-xs font-bold px-2.5 py-1 rounded-full border ${badgeClass}`}
                            >
                              {pairSeverity}
                            </span>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
