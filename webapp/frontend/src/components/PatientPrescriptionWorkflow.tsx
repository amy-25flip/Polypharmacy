import { useMemo, useRef, useState } from 'react'
import { ClipboardPlus, Loader2, Plus, RefreshCw, ShieldCheck, Sparkles, Trash2 } from 'lucide-react'
import { checkInteractions } from '../api/client'
import type { CheckResponse } from '../api/client'
import { DrugSearchInput } from './DrugSearchInput'
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
}

const makeId = () => `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`

const newPrescription = (number: number): SessionPrescription => ({
  id: makeId(),
  label: `Prescription ${number}`,
  drugs: [],
})

// A verified real combination (confirmed live against the interaction engine) that
// exercises documented evidence, model-predicted evidence, low cross-model
// disagreement, and the Minimal Unsafe Subset Certificate in one click - useful for
// a fast, reliable walkthrough instead of typing a combination live.
const EXAMPLE_DRUGS = ['Warfarin', 'Amiodarone', 'Acetylsalicylic acid', 'Digoxin']

export function PatientPrescriptionWorkflow() {
  const [prescriptions, setPrescriptions] = useState<SessionPrescription[]>([newPrescription(1)])
  const [isChecking, setIsChecking] = useState(false)
  const [checkError, setCheckError] = useState<string | null>(null)
  const [result, setResult] = useState<CheckResponse | null>(null)
  // Bumped on every edit/check so a slow, superseded /api/check response can never
  // overwrite state with results for a medication list the user has since changed.
  const requestIdRef = useRef(0)

  const updatePrescription = (id: string, updater: (prescription: SessionPrescription) => SessionPrescription) => {
    requestIdRef.current += 1 // any in-flight check is now stale and will discard its response
    setPrescriptions((current) => current.map((prescription) => prescription.id === id ? updater(prescription) : prescription))
    setResult(null)
    setCheckError(null)
    setIsChecking(false)
  }

  const addDrug = (prescriptionId: string, name: string, timing: MedicationTiming = 'Unspecified', isUnmatched = false) => {
    updatePrescription(prescriptionId, (prescription) => ({
      ...prescription,
      drugs: [...prescription.drugs, { id: makeId(), name, timing, isUnmatched }],
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
    setPrescriptions([newPrescription(1)])
    setResult(null)
    setCheckError(null)
    setIsChecking(false)
  }

  const loadExample = () => {
    requestIdRef.current += 1
    const example = newPrescription(1)
    example.label = 'Example: multi-drug regimen'
    example.drugs = EXAMPLE_DRUGS.map((name) => ({ id: makeId(), name, timing: 'Unspecified' as MedicationTiming }))
    setPrescriptions([example])
    setResult(null)
    setCheckError(null)
    setIsChecking(false)
  }

  return (
    <div className="space-y-6">
      <main className="print:hidden bg-white rounded-xl border border-slate-200 shadow-sm p-5 sm:p-7 space-y-6">
        <div className="border-b border-slate-100 pb-3 flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-bold text-slate-900">Patient prescription session</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Add separate prescriptions from each clinician. This visit stays in browser memory only and is not saved.
            </p>
          </div>
          <button
            type="button"
            onClick={loadExample}
            className="shrink-0 inline-flex items-center gap-1.5 rounded-lg border border-purple-200 bg-purple-50 px-3 py-2 text-xs font-bold text-purple-800 hover:bg-purple-100"
          >
            <Sparkles className="h-3.5 w-3.5" /> Try an example
          </button>
        </div>

        <div className="space-y-5">
          {prescriptions.map((prescription, prescriptionIndex) => (
            <section key={prescription.id} className="rounded-xl border border-slate-200 bg-slate-50/60 p-4 space-y-4">
              <div className="flex items-center gap-3">
                <ClipboardPlus className="h-5 w-5 text-blue-700 shrink-0" />
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
                {prescriptions.length > 1 && (
                  <button
                    type="button"
                    aria-label={`Remove prescription ${prescriptionIndex + 1}`}
                    onClick={() => setPrescriptions((current) => current.filter((item) => item.id !== prescription.id))}
                    className="mt-5 rounded-md p-2 text-slate-500 hover:bg-rose-50 hover:text-rose-700"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                )}
              </div>

              <PrescriptionScanReview onConfirmDrug={({ name, timing }) => addDrug(prescription.id, name, timing)} />

              <div className="rounded-lg border border-slate-200 bg-white p-4">
                <DrugSearchInput
                  onAddDrug={(name, timing, isUnmatched) => addDrug(prescription.id, name, timing, isUnmatched)}
                  existingDrugs={prescription.drugs.map((drug) => drug.name)}
                />
              </div>

              {prescription.drugs.length === 0 ? (
                <p className="rounded-lg border-2 border-dashed border-slate-200 p-4 text-center text-xs text-slate-500">No confirmed medicines in this prescription.</p>
              ) : (
                <div className="space-y-2">
                  {prescription.drugs.map((drug) => (
                    <div key={drug.id} className="grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-slate-900">{drug.name}</p>
                        {drug.isUnmatched && <p className="text-[11px] text-amber-700">Not matched to the reference vocabulary</p>}
                      </div>
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
                  ))}
                </div>
              )}
            </section>
          ))}
        </div>

        <button
          type="button"
          onClick={() => setPrescriptions((current) => [...current, newPrescription(current.length + 1)])}
          className="inline-flex items-center gap-2 rounded-lg border border-blue-300 bg-blue-50 px-4 py-2.5 text-sm font-bold text-blue-800 hover:bg-blue-100"
        >
          <Plus className="h-4 w-4" /> Add another prescription
        </button>
      </main>

      <section className="rounded-xl border border-slate-200 bg-white p-5 sm:p-7 space-y-4">
        <div>
          <h2 className="text-lg font-bold text-slate-900">Combined medication list</h2>
          <p className="text-xs text-slate-500 mt-1">Confirmed medicines are merged by name across all prescription sources.</p>
        </div>
        {combinedMedications.length ? (
          <div className="divide-y divide-slate-100 rounded-lg border border-slate-200">
            {combinedMedications.map((drug) => (
              <div key={drug.name.toLowerCase()} className="px-4 py-3 sm:flex sm:items-center sm:justify-between gap-4">
                <p className="font-semibold text-slate-900">{drug.name}</p>
                <p className="text-xs text-slate-500 mt-1 sm:mt-0">From: {drug.sources.join(', ')} · {drug.timings.join(', ')}</p>
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
          <div className="print:hidden rounded-lg bg-rose-50 border border-rose-200 p-4 text-rose-900 text-sm flex items-start gap-2.5">
            <RefreshCw className="h-4 w-4 shrink-0 mt-0.5 text-rose-600" />
            <div><p className="font-semibold">Screening error</p><p className="text-xs mt-0.5">{checkError}</p></div>
          </div>
        )}
      </section>

      <MedicationTimingTable medications={combinedMedications} />

      {result && (
        <section aria-label="Interaction Screening Results">
          <InteractionResults result={result} onReset={clearSession} />
        </section>
      )}
    </div>
  )
}
