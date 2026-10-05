import { useEffect, useId, useRef, useState } from 'react'
import { AlertTriangle, ExternalLink, Loader2, UserRound } from 'lucide-react'
import { fetchPatientCautions } from '../api/client'
import type { PatientCaution } from '../api/client'

export type PregnancyState = '' | 'possible' | 'pregnant'

export interface PatientFactorValue {
  age: string
  egfr: string
  pregnancy: PregnancyState
}

export const EMPTY_PATIENT: PatientFactorValue = { age: '', egfr: '', pregnancy: '' }

// The number sent is the lower edge of the chosen band, so "eGFR below 45" includes 30-44.
export const EGFR_BANDS: { value: string; label: string }[] = [
  { value: '', label: 'Not specified' },
  { value: '90', label: '90 or above' },
  { value: '60', label: '60 to 89' },
  { value: '45', label: '45 to 59' },
  { value: '30', label: '30 to 44' },
  { value: '15', label: '15 to 29' },
  { value: '0', label: 'Below 15 or on dialysis' },
]

export const pregnancyLabel = (state: PregnancyState) =>
  state === 'pregnant' ? 'currently pregnant' : state === 'possible' ? 'could become pregnant' : 'not pregnant / not applicable'

const levelClass: Record<string, string> = {
  Avoid: 'border-rose-300 bg-rose-50 text-rose-900',
  'Adjust dose': 'border-amber-300 bg-amber-50 text-amber-900',
  'Use with caution': 'border-amber-200 bg-amber-50/60 text-amber-900',
}

interface Props {
  // Every medicine to look up (the plan and the candidates beside it), so cautions can show next to each one.
  medicines: string[]
  // The medicines actually in the plan; only their cautions are listed in this panel.
  selected?: string[]
  value?: PatientFactorValue
  onChange?: (value: PatientFactorValue) => void
  onCautions?: (cautions: PatientCaution[]) => void
}

export function PatientFactors({ medicines, selected, value, onChange, onCautions }: Props) {
  const id = useId()
  const requestIdRef = useRef(0)
  const [own, setOwn] = useState<PatientFactorValue>(EMPTY_PATIENT)
  const [cautions, setCautions] = useState<PatientCaution[]>([])
  const [loading, setLoading] = useState(false)
  const [failed, setFailed] = useState(false)
  const current = value ?? own
  const update = (patch: Partial<PatientFactorValue>) => {
    const next = { ...current, ...patch }
    if (onChange) onChange(next)
    else setOwn(next)
  }
  const { age, egfr, pregnancy } = current
  const medicinesKey = medicines.join('|')
  const onCautionsRef = useRef(onCautions)
  onCautionsRef.current = onCautions

  useEffect(() => {
    const ageValue = age === '' ? null : Number(age)
    const egfrValue = egfr === '' ? null : Number(egfr)
    const validAge = ageValue !== null && Number.isInteger(ageValue) && ageValue >= 0 && ageValue <= 120
    if (medicines.length === 0 || (!validAge && egfrValue === null && !pregnancy)) {
      requestIdRef.current += 1
      setCautions([])
      onCautionsRef.current?.([])
      setLoading(false)
      setFailed(false)
      return
    }
    const requestId = ++requestIdRef.current
    const controller = new AbortController()
    setLoading(true)
    setFailed(false)
    const timer = window.setTimeout(async () => {
      try {
        const found = await fetchPatientCautions(medicines, validAge ? ageValue : null, egfrValue, controller.signal, pregnancy || undefined)
        if (requestIdRef.current === requestId) { setCautions(found); onCautionsRef.current?.(found) }
      } catch (caught) {
        if (requestIdRef.current !== requestId || (caught instanceof Error && caught.name === 'AbortError')) return
        setFailed(true)
        onCautionsRef.current?.([])
      } finally {
        if (requestIdRef.current === requestId) setLoading(false)
      }
    }, 300)
    return () => { window.clearTimeout(timer); controller.abort() }
    // medicinesKey stands in for the medicines array so a new array with the same names does not refetch
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [age, egfr, pregnancy, medicinesKey])

  const planNames = new Set((selected ?? medicines).map((name) => name.toLowerCase()))
  const listed = cautions.filter((caution) => planNames.has(caution.drug.toLowerCase()))
  const anyFactor = age !== '' || egfr !== '' || pregnancy !== ''
  const ageNumber = age === '' ? null : Number(age)
  return (
    <section aria-label="Patient factors" className="print:hidden rounded-xl border border-slate-200 bg-white p-5 sm:p-7 space-y-3">
      <div className="flex items-start gap-2">
        <UserRound className="mt-0.5 h-5 w-5 shrink-0 text-slate-600" />
        <div>
          <h2 className="text-lg font-bold text-slate-900">Patient factors (optional)</h2>
          <p className="text-xs text-slate-500 mt-1">Age, kidney function and pregnancy change which medicines need extra care. Enter them before choosing medicines. Nothing here is saved, and it clears when you start a new patient.</p>
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label htmlFor={`${id}-age`} className="block text-sm font-semibold text-slate-800">Age (years)</label>
          <input id={`${id}-age`} type="number" inputMode="numeric" min={0} max={120} value={age}
            onChange={(event) => update({ age: event.target.value })}
            className="mt-1 w-full rounded-lg border-2 border-slate-300 bg-white px-3 py-2 text-sm text-slate-900" />
        </div>
        <div>
          <label htmlFor={`${id}-egfr`} className="block text-sm font-semibold text-slate-800">Kidney function (eGFR, mL/min/1.73 m²)</label>
          <select id={`${id}-egfr`} value={egfr} onChange={(event) => update({ egfr: event.target.value })}
            className="mt-1 w-full rounded-lg border-2 border-slate-300 bg-white px-3 py-2 text-sm text-slate-900">
            {EGFR_BANDS.map((band) => <option key={band.value} value={band.value}>{band.label}</option>)}
          </select>
        </div>
      </div>
      <fieldset>
        <legend className="text-sm font-semibold text-slate-800">Pregnancy</legend>
        <div className="mt-1 flex flex-wrap gap-x-5 gap-y-1 text-sm text-slate-800">
          <label className="flex items-center gap-1.5"><input type="radio" name={`${id}-pregnancy`} checked={pregnancy === ''} onChange={() => update({ pregnancy: '' })} /> Not pregnant, or not applicable</label>
          <label className="flex items-center gap-1.5"><input type="radio" name={`${id}-pregnancy`} checked={pregnancy === 'possible'} onChange={() => update({ pregnancy: 'possible' })} /> Could become pregnant</label>
          <label className="flex items-center gap-1.5"><input type="radio" name={`${id}-pregnancy`} checked={pregnancy === 'pregnant'} onChange={() => update({ pregnancy: 'pregnant' })} /> Currently pregnant</label>
        </div>
      </fieldset>
      {ageNumber !== null && ageNumber < 18 && (
        <p role="note" className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-950">
          Paediatric patient: dose, weight and formulation are not assessed, and the medicine lists are written for adults. Do not use this tool as a prescription for a child.
        </p>
      )}
      {anyFactor && medicines.length === 0 && <p className="text-xs text-slate-500">Add medicines to see cautions for this patient.</p>}
      {loading && <p className="flex items-center gap-1 text-xs text-slate-500"><Loader2 className="h-3 w-3 animate-spin" /> Checking cautions…</p>}
      {failed && <p role="alert" className="text-xs text-rose-800">Patient cautions are unavailable right now. This does not mean there are none.</p>}
      {!loading && !failed && anyFactor && medicines.length > 0 && (listed.length === 0
        ? <p className="text-xs text-slate-600">No rule in this limited set matched the medicines in the plan. Age, kidney and pregnancy safety have not been fully assessed, so this is not a clearance.</p>
        : <ul className="space-y-2" aria-label="Cautions for this patient">
          {listed.map((caution) => <li key={`${caution.drug}-${caution.factor}`} className={`min-w-0 break-words rounded-lg border p-3 text-sm ${levelClass[caution.level] ?? levelClass['Use with caution']}`}>
            <p className="flex flex-wrap items-center gap-2 font-semibold"><AlertTriangle className="h-4 w-4 shrink-0" />{caution.drug}<span className="rounded-full border border-current px-2 py-0.5 text-[11px]">{caution.level}</span><span className="text-xs font-normal">({caution.trigger})</span></p>
            <p className="mt-1">{caution.text}</p>
            <a href={caution.url} target="_blank" rel="noreferrer" className="mt-1 inline-flex items-center gap-1 text-xs font-semibold underline">{caution.source}<ExternalLink className="h-3 w-3" /></a>
          </li>)}
        </ul>)}
    </section>
  )
}
