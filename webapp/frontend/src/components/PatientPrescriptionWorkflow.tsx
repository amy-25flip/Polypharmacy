import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react'
import { ClipboardPlus, Loader2, Plus, RefreshCw, ShieldCheck, Sparkles, Trash2 } from 'lucide-react'
import { checkInteractions, fetchSpecialties, screenCandidates } from '../api/client'
import type { CandidateScreenResponse, CheckResponse, Disease, Specialty } from '../api/client'
import { DrugSearchInput } from './DrugSearchInput'
import { DiseaseCombobox } from './DiseaseCombobox'
import { DiagnosisMedicinePicker } from './DiagnosisMedicinePicker'
import { pairAsFlag, ScreeningFlag, SeverityLabel } from './ScreeningFlag'
import { basisLabel } from '../severity'
import { PatientFactors } from './PatientFactors'
import { InteractionResults } from './InteractionResults'
import { MedicationTimingTable, TIMING_OPTIONS } from './MedicationTimingTable'
import type { CombinedMedication, MedicationTiming } from './MedicationTimingTable'
import { PrescriptionScanReview } from './PrescriptionScanReview'

interface SessionDrug {
  id: string
  name: string
  timing: MedicationTiming
  isUnmatched?: boolean
}

interface SessionPrescription {
  id: string
  label: string
  drugs: SessionDrug[]
  kind: 'prescription' | 'diagnosis'
  diseaseId?: string
  // Cautions shown with a diagnosis's medicine list (for example "symptom entry" or "mostly topical").
  note?: string
  routeNote?: string
}

const makeId = () => `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`

const newPrescription = (number: number): SessionPrescription => ({
  id: makeId(),
  label: `Prescription ${number}`,
  drugs: [],
  kind: 'prescription',
})

// A verified real combination (confirmed live against the interaction engine) that
// exercises documented evidence, model-predicted evidence, low cross-model
// disagreement, and the Minimal Unsafe Subset Certificate in one click - useful for
// a fast, reliable walkthrough instead of typing a combination live.
const EXAMPLE_DRUGS = ['Warfarin', 'Amiodarone', 'Acetylsalicylic acid', 'Digoxin']

export type WorkflowMode = 'prescription' | 'diagnosis'

// 'prescription' is the original workflow (prescriptions, image scan, text search).
// 'diagnosis' is the plan-by-diagnosis workflow. Both share this component's logic
// for the combined list, check and report, but are mounted as separate tabs with
// separate sessions, so a doctor can use whichever fits the visit.
export function PatientPrescriptionWorkflow({ mode = 'prescription' }: { mode?: WorkflowMode }) {
  const isDiagnosisMode = mode === 'diagnosis'
  const [prescriptions, setPrescriptions] = useState<SessionPrescription[]>(isDiagnosisMode ? [] : [newPrescription(1)])
  const [isChecking, setIsChecking] = useState(false)
  const [checkError, setCheckError] = useState<string | null>(null)
  const [result, setResult] = useState<CheckResponse | null>(null)
  const [showDiagnosisSearch, setShowDiagnosisSearch] = useState(isDiagnosisMode)
  const specialtyId = useId()
  const [specialty, setSpecialty] = useState('')
  const [specialties, setSpecialties] = useState<Specialty[]>([])
  // The specialty list only narrows the diagnosis search, so a failure just hides the filter.
  useEffect(() => {
    if (!isDiagnosisMode) return
    let cancelled = false
    void (async () => {
      try {
        const found = await fetchSpecialties()
        if (!cancelled) setSpecialties(found)
      } catch { /* filter stays hidden */ }
    })()
    return () => { cancelled = true }
  }, [isDiagnosisMode])
  const [focusDiagnosisSearch, setFocusDiagnosisSearch] = useState(false)
  const diagnosisButtonRef = useRef<HTMLButtonElement>(null)
  const [visibleCandidates, setVisibleCandidates] = useState<Record<string, string[]>>({})
  const [screening, setScreening] = useState<CandidateScreenResponse | null>(null)
  const [screeningLoading, setScreeningLoading] = useState(false)
  const [screeningError, setScreeningError] = useState(false)
  const [screenRetry, setScreenRetry] = useState(0)
  const screenRequestIdRef = useRef(0)
  const screenControllerRef = useRef<AbortController | null>(null)
  // Bumped on every edit/check so a slow, superseded /api/check response can never
  // overwrite state with results for a medication list the user has since changed.
  const requestIdRef = useRef(0)
  // The report renders well below the "Check interactions" button - without this, a
  // sighted user could miss that it appeared at all, and a keyboard/screen-reader
  // user would be stuck at the button with no indication anything happened.
  const resultsRef = useRef<HTMLElement>(null)
  const errorRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (result) resultsRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
    resultsRef.current?.focus()
  }, [result])

  useEffect(() => {
    if (checkError) errorRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' })
    errorRef.current?.focus()
  }, [checkError])

  const updatePrescription = (id: string, updater: (prescription: SessionPrescription) => SessionPrescription) => {
    requestIdRef.current += 1 // any in-flight check is now stale and will discard its response
    setPrescriptions((current) => current.map((prescription) => prescription.id === id ? updater(prescription) : prescription))
    setResult(null)
    setCheckError(null)
    setIsChecking(false)
    screenRequestIdRef.current += 1
    screenControllerRef.current?.abort()
    setScreening(null)
  }

  const addDrug = (prescriptionId: string, name: string, timing: MedicationTiming = 'Unspecified', isUnmatched = false) => {
    updatePrescription(prescriptionId, (prescription) => ({
      ...prescription,
      drugs: [...prescription.drugs, { id: makeId(), name, timing, isUnmatched }],
    }))
  }

  // Used to undo a scan confirmation - safe to match by name since the scan review's
  // own duplicate check prevents two drugs in the same prescription sharing a name.
  const removeDrugByName = (prescriptionId: string, name: string) => {
    updatePrescription(prescriptionId, (prescription) => ({
      ...prescription,
      drugs: prescription.drugs.filter((drug) => drug.name.toLowerCase() !== name.toLowerCase()),
    }))
  }

  const combinedMedications = useMemo<CombinedMedication[]>(() => {
    const merged = new Map<string, CombinedMedication>()
    prescriptions.forEach((prescription) => prescription.drugs.forEach((drug) => {
      const key = drug.name.trim().toLowerCase().replace(/\s+/g, ' ')
      const source = prescription.label.trim() || 'Unlabelled prescription'
      const existing = merged.get(key)
      if (existing) {
        if (!existing.sources.includes(source)) existing.sources.push(source)
        if (!existing.timings.includes(drug.timing)) existing.timings.push(drug.timing)
      } else {
        merged.set(key, { name: drug.name.trim(), sources: [source], timings: [drug.timing] })
      }
    }))
    return [...merged.values()]
  }, [prescriptions])

  const diagnosisGroups = prescriptions.filter((item) => item.kind === 'diagnosis')
  const selectedNames = combinedMedications.map((drug) => drug.name)
  const selectedKey = selectedNames.join('\u0000')
  const candidates = [...new Set(Object.values(visibleCandidates).flat().filter((name) => !selectedNames.some((selected) => selected.toLowerCase() === name.toLowerCase())))].slice(0, 100)
  const candidatesKey = candidates.join('\u0000')
  const candidateCount = new Set(Object.values(visibleCandidates).flat().filter((name) => !selectedNames.some((selected) => selected.toLowerCase() === name.toLowerCase()))).size
  const onVisibleChange = useCallback((id: string, names: string[]) => {
    setVisibleCandidates((current) => {
      if ((current[id] || []).join('\u0000') === names.join('\u0000')) return current
      const next = { ...current }
      if (names.length) next[id] = names
      else delete next[id]
      return next
    })
  }, [])

  useEffect(() => {
    const requestId = ++screenRequestIdRef.current
    screenControllerRef.current?.abort()
    setScreening(null)
    setScreeningError(false)
    if (!diagnosisGroups.length) { setScreeningLoading(false); return }
    if (selectedNames.length > 100) { setScreeningLoading(false); setScreeningError(true); return }
    setScreeningLoading(true)
    const controller = new AbortController()
    screenControllerRef.current = controller
    const timer = window.setTimeout(async () => {
      try {
        const response = await screenCandidates(selectedNames, candidates, controller.signal)
        if (screenRequestIdRef.current !== requestId) return
        setScreening(response)
      } catch (caught) {
        if (screenRequestIdRef.current !== requestId || (caught instanceof Error && caught.name === 'AbortError')) return
        setScreeningError(true)
      } finally {
        if (screenRequestIdRef.current === requestId) setScreeningLoading(false)
      }
    }, 300)
    return () => { window.clearTimeout(timer); controller.abort() }
  // String keys capture the contents without re-screening on unrelated workflow renders.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedKey, candidatesKey, diagnosisGroups.length, screenRetry])

  const handleCheck = async () => {
    if (combinedMedications.length < 2) return
    const requestId = ++requestIdRef.current
    setIsChecking(true)
    setCheckError(null)
    try {
      const response = await checkInteractions(combinedMedications.map((drug) => drug.name))
      if (requestIdRef.current !== requestId) return // superseded by a later edit/check - discard
      setResult(response)
    } catch {
      if (requestIdRef.current !== requestId) return
      setCheckError('Unable to complete interaction screening. Please verify the backend connection and try again.')
    } finally {
      if (requestIdRef.current === requestId) setIsChecking(false)
    }
  }

  const clearSession = () => {
    requestIdRef.current += 1
    screenRequestIdRef.current += 1
    screenControllerRef.current?.abort()
    setPrescriptions(isDiagnosisMode ? [] : [newPrescription(1)])
    setVisibleCandidates({})
    setScreening(null)
    setShowDiagnosisSearch(isDiagnosisMode)
    setFocusDiagnosisSearch(false)
    setResult(null)
    setCheckError(null)
    setIsChecking(false)
  }

  const loadExample = () => {
    requestIdRef.current += 1
    screenRequestIdRef.current += 1
    screenControllerRef.current?.abort()
    const example = newPrescription(1)
    example.label = 'Example: multi-drug regimen'
    example.drugs = EXAMPLE_DRUGS.map((name) => ({ id: makeId(), name, timing: 'Unspecified' as MedicationTiming }))
    setPrescriptions([example])
    setVisibleCandidates({})
    setScreening(null)
    setShowDiagnosisSearch(false)
    setResult(null)
    setCheckError(null)
    setIsChecking(false)
  }

  const removePrescription = (id: string) => {
    requestIdRef.current += 1 // any in-flight check covered the now-removed prescription's drugs - discard it
    screenRequestIdRef.current += 1
    screenControllerRef.current?.abort()
    setPrescriptions((current) => current.filter((item) => item.id !== id))
    setVisibleCandidates((current) => { const next = { ...current }; delete next[id]; return next })
    setScreening(null)
    setResult(null)
    setCheckError(null)
    setIsChecking(false)
    diagnosisButtonRef.current?.focus()
  }

  const addDiagnosis = (disease: Disease) => {
    requestIdRef.current += 1
    screenRequestIdRef.current += 1
    screenControllerRef.current?.abort()
    setPrescriptions((current) => current.some((item) => item.diseaseId === disease.id) ? current : [...current, {
      id: makeId(), kind: 'diagnosis', diseaseId: disease.id, label: disease.name, drugs: [],
      note: disease.note ?? undefined, routeNote: disease.route_note ?? undefined,
    }])
    setResult(null)
    setCheckError(null)
    setIsChecking(false)
    setScreening(null)
  }

  return (
    <div className="space-y-6">
      <main className="print:hidden bg-white rounded-xl border border-slate-200 shadow-sm p-5 sm:p-7 space-y-6">
        <div className="border-b border-slate-100 pb-3 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-bold text-slate-900">{isDiagnosisMode ? 'Plan by diagnosis' : 'Patient prescription session'}</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              {isDiagnosisMode
                ? "Add each of the patient's diagnoses and choose its medicines; every medicine is screened against the rest of the plan. This visit stays in browser memory only and is not saved."
                : 'Add separate prescriptions from each clinician. This visit stays in browser memory only and is not saved.'}
            </p>
          </div>
          {!isDiagnosisMode && <button
            type="button"
            onClick={loadExample}
            className="shrink-0 inline-flex items-center gap-1.5 rounded-lg border border-purple-200 bg-purple-50 px-3 py-2 text-xs font-bold text-purple-800 hover:bg-purple-100"
          >
            <Sparkles className="h-3.5 w-3.5" /> Try an example
          </button>}
        </div>

        <div className="space-y-5">
          {prescriptions.map((prescription, prescriptionIndex) => (
            <section key={prescription.id} className="rounded-xl border border-slate-200 bg-slate-50/60 p-4 space-y-4">
              <div className="flex items-center gap-3 min-w-0">
                <ClipboardPlus className="h-5 w-5 text-blue-700 shrink-0" />
                {prescription.kind === 'diagnosis' ? (
                  <h3 className="min-w-0 flex-1 break-words text-base font-bold text-slate-900">{prescription.label}</h3>
                ) : (
                <label className="flex-1 text-xs font-bold text-slate-600">
                  Prescription source or label
                  <input
                    aria-label={`Prescription ${prescriptionIndex + 1} source or label`}
                    value={prescription.label}
                    onChange={(event) => updatePrescription(prescription.id, (current) => ({ ...current, label: event.target.value }))}
                    placeholder="e.g. Endocrinologist, 3 Oct"
                    className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-900"
                  />
                </label>
                )}
                {(prescriptions.length > 1 || prescription.kind === 'diagnosis') && (
                  <button
                    type="button"
                    aria-label={prescription.kind === 'diagnosis' ? `Remove diagnosis ${prescription.label}` : `Remove prescription ${prescriptionIndex + 1}`}
                    onClick={() => removePrescription(prescription.id)}
                    className="mt-5 rounded-md p-2 text-slate-500 hover:bg-rose-50 hover:text-rose-700"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                )}
              </div>

              {prescription.kind === 'diagnosis' && prescription.diseaseId && <DiagnosisMedicinePicker
                id={prescription.id}
                diseaseId={prescription.diseaseId}
                diseaseName={prescription.label}
                note={prescription.note}
                routeNote={prescription.routeNote}
                selected={prescription.drugs.map((drug) => drug.name)}
                combined={combinedMedications}
                screening={screening}
                screeningLoading={screeningLoading}
                screeningError={screeningError}
                onVisibleChange={onVisibleChange}
                onToggle={(name, checked) => checked ? addDrug(prescription.id, name) : removeDrugByName(prescription.id, name)}
              />}

              {prescription.kind === 'prescription' && <PrescriptionScanReview
                onConfirmDrug={({ name, timing, isUnmatched }) => addDrug(prescription.id, name, timing, isUnmatched)}
                existingDrugs={prescription.drugs.map((drug) => drug.name)}
                onUndoConfirm={(name) => removeDrugByName(prescription.id, name)}
                onUseSuggestedSource={(label) => updatePrescription(prescription.id, (current) => ({ ...current, label }))}
              />}

              <div className="rounded-lg border border-slate-200 bg-white p-4">
                <DrugSearchInput
                  onAddDrug={(name, timing, isUnmatched) => addDrug(prescription.id, name, timing, isUnmatched)}
                  existingDrugs={prescription.drugs.map((drug) => drug.name)}
                />
              </div>

              {prescription.drugs.length === 0 ? (
                <p className="rounded-lg border-2 border-dashed border-slate-200 p-4 text-center text-xs text-slate-500">{prescription.kind === 'diagnosis' ? 'No medicines selected for this diagnosis.' : 'No confirmed medicines in this prescription.'}</p>
              ) : (
                <div className="space-y-2">
                  {prescription.drugs.map((drug) => (
                    <div key={drug.id} className="flex flex-col sm:flex-row sm:items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2">
                      <div className="min-w-0 flex-1">
                        <p className="break-words text-sm font-semibold text-slate-900" title={drug.name}>{drug.name}</p>
                        {drug.isUnmatched && <p className="text-[11px] text-amber-700">Not matched to the reference vocabulary</p>}
                      </div>
                      <div className="flex items-center gap-2 shrink-0 self-end sm:self-auto">
                      <select
                        aria-label={`Timing for ${drug.name}`}
                        value={drug.timing}
                        onChange={(event) => updatePrescription(prescription.id, (current) => ({
                          ...current,
                          drugs: current.drugs.map((item) => item.id === drug.id ? { ...item, timing: event.target.value as MedicationTiming } : item),
                        }))}
                        className="rounded-md border border-slate-300 px-2 py-1.5 text-xs text-slate-800"
                      >
                        {TIMING_OPTIONS.map((timing) => <option key={timing}>{timing}</option>)}
                      </select>
                      <button
                        type="button"
                        aria-label={`Remove ${drug.name}`}
                        onClick={() => updatePrescription(prescription.id, (current) => ({ ...current, drugs: current.drugs.filter((item) => item.id !== drug.id) }))}
                        className="rounded p-1.5 text-slate-500 hover:bg-rose-50 hover:text-rose-700"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          ))}
        </div>

        {isDiagnosisMode && diagnosisGroups.length === 0 && <p className="rounded-lg border-2 border-dashed border-slate-200 p-4 text-center text-sm text-slate-500">No diagnoses added yet. Search for a diagnosis below to start building the plan.</p>}
        <div className="flex flex-wrap gap-2">
        {!isDiagnosisMode && <button
          type="button"
          onClick={() => setPrescriptions((current) => [...current, newPrescription(current.filter((item) => item.kind === 'prescription').length + 1)])}
          className="inline-flex items-center gap-2 rounded-lg border border-blue-300 bg-blue-50 px-4 py-2.5 text-sm font-bold text-blue-800 hover:bg-blue-100"
        >
          <Plus className="h-4 w-4" /> Add another prescription
        </button>}
        {isDiagnosisMode && <button ref={diagnosisButtonRef} type="button" onClick={() => { setShowDiagnosisSearch((value) => !value); setFocusDiagnosisSearch(true) }} className="inline-flex items-center gap-2 rounded-lg border border-blue-300 bg-white px-4 py-2.5 text-sm font-bold text-blue-800 hover:bg-blue-50">
          <Plus className="h-4 w-4" /> Add a diagnosis
        </button>}
        </div>
        {isDiagnosisMode && showDiagnosisSearch && <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <DiseaseCombobox existingIds={diagnosisGroups.map((item) => item.diseaseId || '')} onSelect={addDiagnosis} autoFocus={focusDiagnosisSearch} specialty={specialty} />
          {specialties.length > 1 && <div className="w-full max-w-xs">
            <label htmlFor={`${specialtyId}-specialty`} className="block text-sm font-semibold text-slate-800">Specialty</label>
            <select id={`${specialtyId}-specialty`} value={specialty} onChange={(event) => setSpecialty(event.target.value)} className="mt-1 w-full rounded-lg border-2 border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900">
              <option value="">All specialties</option>
              {specialties.map((item) => <option key={item.name} value={item.name}>{item.name} ({item.disease_count})</option>)}
            </select>
          </div>}
        </div>}
        {diagnosisGroups.length > 0 && combinedMedications.length >= 2 && <section aria-label="Whole plan screening" className="rounded-xl border border-blue-200 bg-blue-50/50 p-4 space-y-3">
          <h3 className="text-base font-bold text-slate-900">Whole plan screening</h3>
          {screeningLoading ? <p className="flex items-center gap-2 text-xs text-slate-600"><Loader2 className="h-4 w-4 animate-spin" /> Screening the current plan…</p> : screening && <>
            <div className="flex flex-wrap items-center gap-2 text-sm font-semibold text-slate-800"><span>Overall:</span><SeverityLabel severity={screening.selected_summary.overall_severity} uncertain={screening.selected_summary.pairs.some((pair) => pair.uncertain && pair.severity === screening.selected_summary.overall_severity)} /></div>
            <p className="text-xs text-slate-700">{screening.selected_summary.counts.Major} Major · {screening.selected_summary.counts.Moderate} Moderate · {screening.selected_summary.counts.Minor} Minor · {screening.selected_summary.counts.None ?? 0} No reaction pairs</p>
            {screening.selected_summary.pairs.filter((pair) => pair.severity === 'Major' || pair.severity === 'Moderate').map((pair, index) => <div key={`${pair.drug_a}-${pair.drug_b}-${index}`} className="break-words rounded-lg bg-white p-2 text-xs">
              <span className="font-semibold">{pair.drug_a} + {pair.drug_b}: </span><SeverityLabel severity={pair.severity} uncertain={pair.uncertain} /> <span>{basisLabel(pair.severity_basis, pair.is_documented)}</span>
              {pair.adverse_effects.length > 0 && <div className="mt-1 flex flex-wrap gap-1">{pair.adverse_effects.map((effect) => <span key={effect} className="rounded bg-slate-100 px-1.5 py-0.5">{effect}</span>)}</div>}
            </div>)}
            {screening.selected_summary.pairs.some((pair) => pair.adverse_effects.length > 0) && <p className="text-[11px] text-slate-600">{screening.adverse_effect_basis}</p>}
            {screening.unmatched.length > 0 && <p className="text-xs text-slate-700">Could not screen: {screening.unmatched.join(', ')}</p>}
          </>}
          <p className="text-xs text-slate-600">The full evidence-graded report is produced by Check interactions.</p>
          <button type="button" onClick={() => void handleCheck()} disabled={isChecking} className="rounded-lg bg-blue-700 px-3 py-2 text-xs font-bold text-white disabled:opacity-50">Check interactions for whole plan</button>
        </section>}
        {diagnosisGroups.length > 0 && <div aria-live="polite" className="sr-only">{screeningLoading ? 'Screening medicines…' : screeningError ? 'Live screening unavailable.' : screening ? 'Live screening updated for the current plan.' : ''}</div>}
        {diagnosisGroups.length > 0 && screeningError && <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-900">
          <p className="font-semibold">Live screening unavailable. No risk estimate is shown; this does not mean there are no interactions.</p>
          {selectedNames.length > 100 && <p className="mt-1 text-xs">Live screening accepts at most 100 selected medicines.</p>}
          <button type="button" onClick={() => setScreenRetry((value) => value + 1)} className="mt-2 inline-flex items-center gap-1 text-xs font-bold"><RefreshCw className="h-3.5 w-3.5" /> Retry live screening</button>
        </div>}
        {candidateCount > 100 && <p className="text-xs text-amber-800">Screening limited to the first 100 visible unselected medicines across diagnosis pickers.</p>}
      </main>

      <section className="rounded-xl border border-slate-200 bg-white p-5 sm:p-7 space-y-4">
        <div>
          <h2 className="text-lg font-bold text-slate-900">Combined medication list</h2>
          <p className="text-xs text-slate-500 mt-1">Confirmed medicines are merged by name across all plan sources.</p>
        </div>
        {combinedMedications.length ? (
          <div className="divide-y divide-slate-100 rounded-lg border border-slate-200">
            {combinedMedications.map((drug) => (
              <div key={drug.name.toLowerCase()} className="min-w-0 px-4 py-3 sm:flex sm:items-start sm:justify-between gap-4">
                <div className="min-w-0">
                  <p className="break-words font-semibold text-slate-900">{drug.name}</p>
                  {diagnosisGroups.length > 0 && (screeningLoading ? <p className="flex items-center gap-1 text-xs text-slate-500"><Loader2 className="h-3 w-3 animate-spin" /> Screening…</p> : screening && (() => {
                    if (screening.unmatched.some((name) => name.toLowerCase() === drug.name.toLowerCase())) return <p className="text-xs text-amber-800">Not matched to screening reference data; interaction status unknown</p>
                    const pairs = screening.selected_summary.pairs.filter((pair) => pair.drug_a.toLowerCase() === drug.name.toLowerCase() || pair.drug_b.toLowerCase() === drug.name.toLowerCase())
                    const flags = pairs.map((pair) => pairAsFlag(pair, drug.name))
                    const severity = flags.some((flag) => flag.severity === 'Major') ? 'Major' : flags.some((flag) => flag.severity === 'Moderate') ? 'Moderate' : flags.some((flag) => flag.severity === 'Minor') ? 'Minor' : flags.some((flag) => flag.severity === 'None') ? 'None' : null
                    return <ScreeningFlag flags={flags} severity={severity} basis={screening.adverse_effect_basis} />
                  })())}
                </div>
                <p className="min-w-0 break-words text-xs text-slate-500 mt-1 sm:mt-0">From: {drug.sources.join(', ')} · {drug.timings.join(', ')}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="rounded-lg border-2 border-dashed border-slate-200 p-5 text-center text-sm text-slate-500">No medicines confirmed yet.</p>
        )}

        <button
          type="button"
          disabled={combinedMedications.length < 2 || isChecking}
          onClick={() => void handleCheck()}
          className="print:hidden w-full py-3.5 px-6 rounded-lg font-bold text-base flex items-center justify-center gap-2 bg-blue-700 hover:bg-blue-800 text-white disabled:bg-slate-200 disabled:text-slate-400 disabled:border disabled:border-slate-300"
        >
          {isChecking ? <Loader2 className="h-5 w-5 animate-spin" /> : <ShieldCheck className="h-5 w-5" />}
          {isChecking ? 'Screening regimen interactions…' : `Check interactions ${combinedMedications.length >= 2 ? `(${combinedMedications.length} medicines)` : '(Add at least 2)'}`}
        </button>
        {combinedMedications.length === 1 && <p className="print:hidden text-xs text-center text-slate-500 font-medium">Add at least 1 more medicine to evaluate pairwise interactions</p>}
        {checkError && (
          <div ref={errorRef} role="alert" tabIndex={-1} className="print:hidden rounded-lg bg-rose-50 border border-rose-200 p-4 text-rose-900 text-sm flex items-start gap-2.5 focus:outline-none">
            <RefreshCw className="h-4 w-4 shrink-0 mt-0.5 text-rose-600" />
            <div><p className="font-semibold">Screening error</p><p className="text-xs mt-0.5">{checkError}</p></div>
          </div>
        )}
      </section>

      <PatientFactors medicines={selectedNames} />

      {combinedMedications.length > 0 && <MedicationTimingTable medications={combinedMedications} />}

      {result && (
        <section ref={resultsRef} tabIndex={-1} aria-label="Interaction Screening Results" className="focus:outline-none">
          <InteractionResults result={result} onReset={clearSession} diagnoses={diagnosisGroups.map((group) => ({ name: group.label, medicines: group.drugs.map((drug) => drug.name) }))} />
        </section>
      )}
    </div>
  )
}
