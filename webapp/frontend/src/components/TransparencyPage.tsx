import { useEffect, useState } from 'react'
import { ArrowLeft, Loader2, BarChart3 } from 'lucide-react'
import { fetchTransparency } from '../api/client'
import type { TransparencyData, ModelComparisonRow } from '../api/client'

interface TransparencyPageProps {
  onBack: () => void
}

const statusBadge: Record<ModelComparisonRow['status'], string> = {
  baseline: 'bg-slate-200 text-slate-700',
  shipped: 'bg-emerald-100 text-emerald-800 border border-emerald-300',
  negative_result: 'bg-amber-100 text-amber-800 border border-amber-300',
}

const statusLabel: Record<ModelComparisonRow['status'], string> = {
  baseline: 'Baseline',
  shipped: 'Deployed',
  negative_result: 'Negative result',
}

export const TransparencyPage: React.FC<TransparencyPageProps> = ({ onBack }) => {
  const [data, setData] = useState<TransparencyData | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchTransparency()
      .then(setData)
      .catch(() => setError('Could not load transparency data. Please verify backend connection.'))
  }, [])

  return (
    <div className="min-h-screen bg-slate-100/70 text-slate-900 py-6 sm:py-10 px-4 sm:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onBack}
            className="flex items-center gap-1.5 text-sm font-semibold text-slate-600 hover:text-slate-900 transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to checker
          </button>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 sm:p-7">
          <div className="flex items-center gap-2.5 mb-1">
            <BarChart3 className="h-6 w-6 text-blue-700" />
            <h1 className="text-2xl font-extrabold text-slate-950">Model Transparency</h1>
          </div>
          <p className="text-sm text-slate-600">
            PolyGuard's real, held-out evaluation numbers - not marketing claims. Every figure below
            comes from data the relevant model was never trained on. Negative results are shown here
            exactly as honestly as positive ones.
          </p>
        </div>

        {error && (
          <div className="bg-rose-50 border border-rose-200 rounded-lg p-4 text-rose-900 text-sm">{error}</div>
        )}

        {!data && !error && (
          <div className="flex items-center justify-center py-16 text-slate-500">
            <Loader2 className="h-6 w-6 animate-spin mr-2" />
            Loading transparency data...
          </div>
        )}

        {data && (
          <>
            {/* Model comparison */}
            <section className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 sm:p-7">
              <h2 className="text-lg font-bold text-slate-950 mb-1">Model comparison</h2>
              <p className="text-xs text-slate-500 mb-4">{data.model_comparison.note}</p>
              <div className="overflow-x-auto">
                <table className="w-full text-xs sm:text-sm">
                  <thead>
                    <tr className="text-left text-slate-500 border-b border-slate-200">
                      <th className="py-2 pr-3 font-semibold">Model</th>
                      <th className="py-2 px-3 font-semibold text-right">Standard acc.</th>
                      <th className="py-2 px-3 font-semibold text-right">Standard F1</th>
                      <th className="py-2 px-3 font-semibold text-right">Cold-start acc.</th>
                      <th className="py-2 px-3 font-semibold text-right">Cold-start F1</th>
                      <th className="py-2 pl-3 font-semibold">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.model_comparison.rows.map((r) => (
                      <tr key={r.model} className="border-b border-slate-100">
                        <td className="py-2 pr-3 font-medium text-slate-800">{r.model}</td>
                        <td className="py-2 px-3 text-right text-slate-700">{(r.standard_accuracy * 100).toFixed(1)}%</td>
                        <td className="py-2 px-3 text-right text-slate-700">{r.standard_macro_f1.toFixed(3)}</td>
                        <td className="py-2 px-3 text-right text-slate-700">{(r.cold_start_accuracy * 100).toFixed(1)}%</td>
                        <td className="py-2 px-3 text-right text-slate-700">{r.cold_start_macro_f1.toFixed(3)}</td>
                        <td className="py-2 pl-3">
                          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${statusBadge[r.status]}`}>
                            {statusLabel[r.status]}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="mt-4 text-sm text-slate-700 leading-relaxed bg-slate-50 rounded-lg p-3 border border-slate-200">
                {data.model_comparison.finding}
              </p>
            </section>

            {/* Model 1 calibration */}
            <section className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 sm:p-7">
              <h2 className="text-lg font-bold text-slate-950 mb-1">Model 1 calibration</h2>
              <p className="text-xs text-slate-500 mb-4">{data.model1_calibration.method}</p>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {data.model1_calibration.bins.map((b) => (
                  <div key={b.confidence_low} className="bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-center">
                    <div className="text-[10px] text-slate-500 font-medium">
                      {(b.confidence_low * 100).toFixed(0)}–{(b.confidence_high * 100).toFixed(0)}% conf.
                    </div>
                    <div className="text-lg font-extrabold text-slate-900">{(b.empirical_accuracy * 100).toFixed(0)}%</div>
                    <div className="text-[10px] text-slate-400">accurate, n={b.n.toLocaleString()}</div>
                  </div>
                ))}
              </div>
            </section>

            {/* Conformal sets */}
            <section className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 sm:p-7">
              <h2 className="text-lg font-bold text-slate-950 mb-1">Conformal severity sets</h2>
              <p className="text-xs text-slate-500 mb-4">{data.conformal_sets.method}</p>
              <div className="grid sm:grid-cols-2 gap-4">
                {(['standard_split', 'cold_start_split'] as const).map((splitKey) => (
                  <div key={splitKey}>
                    <div className="text-xs font-bold uppercase tracking-wide text-slate-500 mb-2">
                      {splitKey === 'standard_split' ? 'Standard split' : 'Cold-start split (unseen drugs)'}
                    </div>
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="text-left text-slate-400">
                          <th className="pb-1">Target</th>
                          <th className="pb-1 text-right">Observed</th>
                          <th className="pb-1 text-right">Avg. set size</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(data.conformal_sets.eval[splitKey]).map(([target, m]) => (
                          <tr key={target} className="border-t border-slate-100">
                            <td className="py-1 font-medium text-slate-700">{(Number(target) * 100).toFixed(0)}%</td>
                            <td className="py-1 text-right text-slate-700">{(m.overall_coverage * 100).toFixed(1)}%</td>
                            <td className="py-1 text-right text-slate-700">{m.overall_avg_set_size.toFixed(2)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ))}
              </div>
              <p className="mt-3 text-[11px] text-slate-500 italic">
                Coverage held almost exactly at target even under the harder cold-start split - the sets
                just grew wider, which is the correct, honest behavior for this technique.
              </p>
            </section>

            {/* Disagreement sentinel */}
            <section className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 sm:p-7">
              <h2 className="text-lg font-bold text-slate-950 mb-1">Model Disagreement Sentinel</h2>
              <p className="text-xs text-slate-500 mb-4">{data.disagreement_sentinel.method}</p>
              <p className="text-sm text-slate-700 mb-3">
                Correlation between model disagreement and Model 1 error:{' '}
                <span className="font-bold">{data.disagreement_sentinel.calibration.correlation_disagreement_vs_error.toFixed(3)}</span>
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {data.disagreement_sentinel.calibration.bins.map((b) => (
                  <div key={b.js_divergence_low} className="bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-center">
                    <div className="text-[10px] text-slate-500 font-medium">
                      JS {b.js_divergence_low.toFixed(2)}–{b.js_divergence_high.toFixed(2)}
                    </div>
                    <div className="text-lg font-extrabold text-slate-900">{(b.model1_empirical_accuracy * 100).toFixed(0)}%</div>
                    <div className="text-[10px] text-slate-400">Model 1 accurate, n={b.n.toLocaleString()}</div>
                  </div>
                ))}
              </div>
            </section>

            {/* Dataset stats */}
            <section className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 sm:p-7">
              <h2 className="text-lg font-bold text-slate-950 mb-1">Dataset coverage</h2>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mt-3 text-sm">
                <div><span className="font-bold text-slate-900">{data.dataset.total_drugs.toLocaleString()}</span><div className="text-xs text-slate-500">indexed drugs</div></div>
                <div><span className="font-bold text-slate-900">{data.dataset.total_documented_pairs.toLocaleString()}</span><div className="text-xs text-slate-500">documented pairs</div></div>
                <div><span className="font-bold text-slate-900">{data.dataset.drugs_with_drugbank_id.toLocaleString()}</span><div className="text-xs text-slate-500">with DrugBank ID / HODDI support</div></div>
              </div>
            </section>
          </>
        )}

        <footer className="text-center text-xs text-slate-400 pt-4">
          PolyGuard v1.0 • Clinical Drug Interaction Screening System
        </footer>
      </div>
    </div>
  )
}
