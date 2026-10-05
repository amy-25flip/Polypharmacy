import { useEffect, useMemo, useState } from 'react'
import { Loader2, RefreshCw } from 'lucide-react'
import { fetchDiseaseMedicines } from '../api/client'
import type { CandidateScreenResponse, DiseaseMedicine, PatientCaution } from '../api/client'
import type { CombinedMedication } from './MedicationTimingTable'
import { pairAsFlag, ScreeningFlag } from './ScreeningFlag'

interface Props {
  id: string
  diseaseId: string
  diseaseName: string
  note?: string
  routeNote?: string
  // Age, kidney and pregnancy cautions for the medicines on this list (empty until the doctor enters patient facts).
  cautions?: PatientCaution[]
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
    if (source === 'hetionet:CtD') return 'Research link, role in care not reviewed'
    if (source === 'hetionet:CpD') return 'Research link (symptom relief), role not reviewed'
    if (source === 'fda-label:indicated') return 'FDA label lists this use (place in therapy not reviewed)'
    return source.split(':')[0].trim()
  })
  return [...new Set(labels)].join(' · ')
}

export function DiagnosisMedicinePicker({ id, diseaseId, diseaseName, note, routeNote, cautions = [], selected, combined, screening, screeningLoading, screeningError, onVisibleChange, onToggle }: Props) {
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

  // Fewest flagged interactions first. This says nothing about suitability for the patient, and a medicine
  // that could not be screened goes last so it never looks like the safe choice.
  const rank = (name: string) => {
    const result = screening?.results.find((item) => item.candidate.toLowerCase() === name.toLowerCase())
    if (!result) return 4
    if (result.flags.length > 0 && result.flags.every((flag) => flag.severity_basis === 'no_data')) return 5
    const severity = result.worst_severity
    return severity === 'Major' ? 3 : severity === 'Moderate' ? 2 : severity === 'Minor' ? 1 : 0
  }
  const isSelected = (name: string) => selected.some((picked) => picked.toLowerCase() === name.toLowerCase())
  const matchesHide = (item: DiseaseMedicine) => hideMajor && !screeningError && !!screening && !isSelected(item.name) && rank(item.name) === 3
  const hiddenByMajor = filtered.filter(matchesHide)
  const displayed = [...filtered].filter((item) => !matchesHide(item))
    .sort((a, b) => safestFirst && screening ? rank(a.name) - rank(b.name) || a.name.localeCompare(b.name) : a.name.localeCompare(b.name))

  const renderRow = (item: DiseaseMedicine) => {
    const checked = isSelected(item.name)
    const other = combined.find((med) => med.name.toLowerCase() === item.name.toLowerCase())?.sources.filter((source) => source !== diseaseName) || []
    const flag = screening?.results.find((entry) => entry.candidate.toLowerCase() === item.name.toLowerCase())
    const selectedPairs = screening?.selected_summary.pairs.filter((pair) => pair.drug_a.toLowerCase() === item.name.toLowerCase() || pair.drug_b.toLowerCase() === item.name.toLowerCase()) || []
    const selectedFlags = selectedPairs.map((pair) => pairAsFlag(pair, item.name))
    const selectedSeverity = selectedFlags.some((entry) => entry.severity === 'Major') ? 'Major' : selectedFlags.some((entry) => entry.severity === 'Moderate') ? 'Moderate' : selectedFlags.some((entry) => entry.severity === 'Minor') ? 'Minor' : selectedFlags.some((entry) => entry.severity === 'None') ? 'None' : null
    const inPlan = combined.some((med) => med.name.toLowerCase() === item.name.toLowerCase())
    const unmatched = screening?.unmatched.some((name) => name.toLowerCase() === item.name.toLowerCase())
    const itemCautions = cautions.filter((caution) => caution.drug.toLowerCase() === item.name.toLowerCase())
    return <div key={item.name.toLowerCase()} className="min-w-0 px-3 py-2">
      <label className="flex cursor-pointer items-start gap-2 text-sm font-semibold text-slate-900">
        <input type="checkbox" checked={checked} onChange={(event) => onToggle(item.name, event.target.checked)} className="mt-0.5 shrink-0" />
        <span className="min-w-0 break-words">{item.name}</span>
      </label>
      {item.label && <p className="ml-5 break-words text-[11px] font-medium text-slate-700">{item.label}</p>}
      {itemCautions.map((caution) => <p key={`${caution.drug}-${caution.factor}`} className="ml-5 mt-0.5 break-words rounded border border-rose-200 bg-rose-50 px-1.5 py-0.5 text-[11px] font-semibold text-rose-900">{caution.level} ({caution.trigger}): {caution.text}</p>)}
      {other.length > 0 && <p className="ml-5 break-words text-[11px] text-slate-500">Already in plan (from {other.join(', ')})</p>}
      <p className="ml-5 break-words text-[11px] text-slate-500" title={item.sources.join(' | ')}>Listed by: {sourceLabels(item.sources)}</p>
      <div className="ml-5 mt-1">{planIsEmpty ? null : screeningLoading ?<span className="flex items-center gap-1 text-xs text-slate-500"><Loader2 className="h-3 w-3 animate-spin" /> Screening…</span> : !screeningError && unmatched ? <span className="text-xs text-amber-800">Not matched to screening reference data; interaction status unknown</span> : !screeningError && screening && inPlan ? <ScreeningFlag flags={selectedFlags} severity={selectedSeverity} basis={screening.adverse_effect_basis} /> : !screeningError && flag ? <ScreeningFlag flags={flag.flags} severity={flag.worst_severity} basis={screening?.adverse_effect_basis || ''} /> : !screeningError && screening && !flag ? <span className="text-xs text-slate-500">No screening estimate returned for this medicine</span> : null}</div>
    </div>
  }

  // Curated lists come in clinical groups (first choices, add-ons, specialist use); other lists stay flat.
  const grouped = displayed.some((item) => item.group)
  const groups: { label: string; order: number; collapsed: boolean; items: DiseaseMedicine[] }[] = []
  if (grouped) {
    for (const item of displayed) {
      const label = item.group ?? 'Other'
      let group = groups.find((entry) => entry.label === label)
      if (!group) { group = { label, order: item.group_order ?? 99, collapsed: !!item.group_collapsed, items: [] }; groups.push(group) }
      group.items.push(item)
    }
    groups.sort((a, b) => a.order - b.order)
  }

  return <div className="rounded-lg border border-blue-200 bg-white p-3 sm:p-4">
    <h4 className="break-words text-sm font-bold text-slate-900">Medicines for {diseaseName}</h4>
    <p className="mt-1 text-xs text-slate-600">Reference list of medicines commonly associated with this condition - not a prescribing recommendation. Flags are screening estimates; verify clinically.</p>
    <p className="mt-1 text-[11px] font-semibold text-amber-900">These lists have not yet been reviewed by an Indian clinician or pharmacist.</p>
    {(note || routeNote) && <div className="mt-2 space-y-1 rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-xs text-sky-950">
      {note && <p><span className="font-semibold">Note: </span>{note}</p>}
      {routeNote && <p><span className="font-semibold">About these medicines: </span>{routeNote}</p>}
    </div>}
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
            <option value="alphabetical">Alphabetical</option><option value="safest">Fewest flagged interactions</option>
          </select>
        </label>
        <label className="flex items-center gap-1 text-xs font-medium text-slate-700"><input type="checkbox" checked={hideMajor} onChange={(event) => setHideMajor(event.target.checked)} /> Hide medicines with Major alerts</label>
      </div>
      {safestFirst && <p className="mt-1 text-[11px] text-slate-600">This order counts flagged interactions only. It is not a ranking of which medicine suits this patient.</p>}
      {hiddenByMajor.length > 0 && <p role="status" className="mt-2 rounded border border-rose-200 bg-rose-50 px-2 py-1 text-xs font-semibold text-rose-900">{hiddenByMajor.length} medicine{hiddenByMajor.length === 1 ? '' : 's'} hidden because of Major alerts: {hiddenByMajor.map((item) => item.name).join(', ')}</p>}
      <div className="mt-3 max-h-96 overflow-y-auto rounded-lg border border-slate-200" aria-label={`Reference medicines for ${diseaseName}`}>
        {displayed.length ? grouped ? groups.map((group) => {
          const body = <div className="divide-y divide-slate-100">{group.items.map(renderRow)}</div>
          const open = !group.collapsed || query.trim().length > 0 || group.items.some((item) => isSelected(item.name))
          return <section key={group.label} aria-label={group.label} className="border-b border-slate-200 last:border-b-0">
            {group.collapsed
              ? <details open={open}><summary className="cursor-pointer bg-slate-50 px-3 py-2 text-xs font-bold uppercase tracking-wide text-slate-600">{group.label} ({group.items.length})</summary>{body}</details>
              : <><h5 className="bg-slate-50 px-3 py-2 text-xs font-bold uppercase tracking-wide text-slate-600">{group.label} ({group.items.length})</h5>{body}</>}
          </section>
        }) : <div className="divide-y divide-slate-100">{displayed.map(renderRow)}</div> : <p className="p-3 text-xs text-slate-500">No medicines match this filter.</p>}
      </div>
      <p className="mt-2 text-[11px] text-slate-500">{filtered.length} visible · {medicines.length} reference medicines{candidateNames.length > 100 && '; screening limited to the first 100 visible unselected medicines across diagnosis pickers'}</p>
    </>}
  </div>
}
