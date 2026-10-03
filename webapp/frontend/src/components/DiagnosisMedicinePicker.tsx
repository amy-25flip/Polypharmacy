import { useEffect, useMemo, useState } from 'react'
import { Loader2, RefreshCw } from 'lucide-react'
import { fetchDiseaseMedicines } from '../api/client'
import type { CandidateScreenResponse, DiseaseMedicine } from '../api/client'
import type { CombinedMedication } from './MedicationTimingTable'
import { pairAsFlag, ScreeningFlag } from './ScreeningFlag'

interface Props {
  id: string
  diseaseId: string
  diseaseName: string
  selected: string[]
  combined: CombinedMedication[]
  screening: CandidateScreenResponse | null
  screeningLoading: boolean
  screeningError: boolean
  onVisibleChange: (id: string, names: string[]) => void
  onToggle: (name: string, checked: boolean) => void
}

// Evidence provenance shown to the doctor so a surprising entry (e.g. an ARB under diabetes)
// can be judged by where it came from. Hetionet CtD = disease-modifying treatment,
// CpD = symptom relief; guideline citations are shortened to their list name.
function sourceLabels(sources: string[]): string {
  const labels = sources.map((source) => {
    if (source === 'hetionet:CtD') return 'Hetionet (treats)'
    if (source === 'hetionet:CpD') return 'Hetionet (symptom relief)'
    if (source === 'fda-label:indicated') return 'FDA label (approved use)'
    return source.split(':')[0].trim()
  })
  return [...new Set(labels)].join(' · ')
}

export function DiagnosisMedicinePicker({ id, diseaseId, diseaseName, selected, combined, screening, screeningLoading, screeningError, onVisibleChange, onToggle }: Props) {
  const [medicines, setMedicines] = useState<DiseaseMedicine[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [retry, setRetry] = useState(0)
  const [query, setQuery] = useState('')
  const [hideMajor, setHideMajor] = useState(false)
  const [safestFirst, setSafestFirst] = useState(false)
  const planIsEmpty = combined.length === 0

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError(false)
    setMedicines([])
    void fetchDiseaseMedicines(diseaseId, controller.signal).then((items) => {
      if (!controller.signal.aborted) setMedicines(items)
    }).catch((caught) => {
      if (!controller.signal.aborted && !(caught instanceof Error && caught.name === 'AbortError')) setError(true)
    }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [diseaseId, retry])

  const filtered = useMemo(() => medicines.filter((item) => item.name.toLowerCase().includes(query.trim().toLowerCase())).sort((a, b) => a.name.localeCompare(b.name)), [medicines, query])
  const unselected = filtered.filter((item) => !selected.some((name) => name.toLowerCase() === item.name.toLowerCase()))
  const candidateNames = unselected.map((item) => item.name)
  const candidateKey = candidateNames.join('\u0000')
  useEffect(() => {
    onVisibleChange(id, candidateKey ? candidateKey.split('\u0000') : [])
    return () => onVisibleChange(id, [])
  }, [id, candidateKey, onVisibleChange])

  const rank = (name: string) => {
    const severity = screening?.results.find((item) => item.candidate.toLowerCase() === name.toLowerCase())?.worst_severity
    return severity === 'Major' ? 3 : severity === 'Moderate' ? 2 : severity === 'Minor' ? 1 : 0
  }
  const displayed = [...filtered].filter((item) => !hideMajor || screeningError || !screening || selected.some((name) => name.toLowerCase() === item.name.toLowerCase()) || rank(item.name) !== 3)
    .sort((a, b) => safestFirst && screening ? rank(a.name) - rank(b.name) || a.name.localeCompare(b.name) : a.name.localeCompare(b.name))

  return <div className="rounded-lg border border-blue-200 bg-white p-3 sm:p-4">
    <h4 className="break-words text-sm font-bold text-slate-900">Medicines for {diseaseName}</h4>
    <p className="mt-1 text-xs text-slate-600">Reference list of medicines commonly associated with this condition - not a prescribing recommendation. Flags are screening estimates; verify clinically.</p>
    {loading ? <p role="status" className="mt-3 flex items-center gap-2 text-xs text-slate-600"><Loader2 className="h-4 w-4 animate-spin" /> Loading reference medicines…</p> : error ? <div role="alert" className="mt-3 rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-900">
      <p className="font-semibold">Medicine reference list unavailable. This does not mean no medicines are associated with this diagnosis.</p>
      <button type="button" onClick={() => setRetry((value) => value + 1)} className="mt-2 inline-flex items-center gap-1 font-bold"><RefreshCw className="h-3.5 w-3.5" /> Retry medicines</button>
    </div> : <>
      <div className="mt-3 flex flex-wrap items-end gap-3">
        <label className="min-w-0 flex-1 text-xs font-semibold text-slate-700">Filter medicines
          <input aria-label={`Filter medicines for ${diseaseName}`} value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search or browse medicines" className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
        </label>
        <label className="text-xs font-semibold text-slate-700">Order
          <select aria-label={`Order medicines for ${diseaseName}`} value={safestFirst ? 'safest' : 'alphabetical'} onChange={(event) => setSafestFirst(event.target.value === 'safest')} className="mt-1 block rounded-lg border border-slate-300 px-2 py-2 text-xs">
            <option value="alphabetical">Alphabetical</option><option value="safest">Safest first</option>
          </select>
        </label>
        <label className="flex items-center gap-1 text-xs font-medium text-slate-700"><input type="checkbox" checked={hideMajor} onChange={(event) => setHideMajor(event.target.checked)} /> Hide Major interactions</label>
      </div>
      <div className="mt-3 max-h-80 divide-y divide-slate-100 overflow-y-auto rounded-lg border border-slate-200" aria-label={`Reference medicines for ${diseaseName}`}>
        {displayed.length ? displayed.map((item) => {
          const checked = selected.some((name) => name.toLowerCase() === item.name.toLowerCase())
          const other = combined.find((med) => med.name.toLowerCase() === item.name.toLowerCase())?.sources.filter((source) => source !== diseaseName) || []
          const flag = screening?.results.find((entry) => entry.candidate.toLowerCase() === item.name.toLowerCase())
          const selectedPairs = screening?.selected_summary.pairs.filter((pair) => pair.drug_a.toLowerCase() === item.name.toLowerCase() || pair.drug_b.toLowerCase() === item.name.toLowerCase()) || []
          const selectedFlags = selectedPairs.map((pair) => pairAsFlag(pair, item.name))
          const selectedSeverity = selectedFlags.some((entry) => entry.severity === 'Major') ? 'Major' : selectedFlags.some((entry) => entry.severity === 'Moderate') ? 'Moderate' : selectedFlags.some((entry) => entry.severity === 'Minor') ? 'Minor' : selectedFlags.some((entry) => entry.severity === 'None') ? 'None' : null
          const inPlan = combined.some((med) => med.name.toLowerCase() === item.name.toLowerCase())
          const unmatched = screening?.unmatched.some((name) => name.toLowerCase() === item.name.toLowerCase())
          return <div key={item.name.toLowerCase()} className="min-w-0 px-3 py-2">
            <label className="flex cursor-pointer items-start gap-2 text-sm font-semibold text-slate-900">
              <input type="checkbox" checked={checked} onChange={(event) => onToggle(item.name, event.target.checked)} className="mt-0.5 shrink-0" />
              <span className="min-w-0 break-words">{item.name}</span>
            </label>
            {other.length > 0 && <p className="ml-5 break-words text-[11px] text-slate-500">Already in plan (from {other.join(', ')})</p>}
            <p className="ml-5 break-words text-[11px] text-slate-500" title={item.sources.join(' | ')}>Listed by: {sourceLabels(item.sources)}</p>
            <div className="ml-5 mt-1">{planIsEmpty ? null : screeningLoading ?<span className="flex items-center gap-1 text-xs text-slate-500"><Loader2 className="h-3 w-3 animate-spin" /> Screening…</span> : !screeningError && unmatched ? <span className="text-xs text-amber-800">Not matched to screening reference data; interaction status unknown</span> : !screeningError && screening && inPlan ? <ScreeningFlag flags={selectedFlags} severity={selectedSeverity} basis={screening.adverse_effect_basis} /> : !screeningError && flag ? <ScreeningFlag flags={flag.flags} severity={flag.worst_severity} basis={screening?.adverse_effect_basis || ''} /> : !screeningError && screening && !flag ? <span className="text-xs text-slate-500">No screening estimate returned for this medicine</span> : null}</div>
          </div>
        }) : <p className="p-3 text-xs text-slate-500">No medicines match this filter.</p>}
      </div>
      <p className="mt-2 text-[11px] text-slate-500">{filtered.length} visible · {medicines.length} reference medicines{candidateNames.length > 100 && '; screening limited to the first 100 visible unselected medicines across diagnosis pickers'}</p>
    </>}
  </div>
}
