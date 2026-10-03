import { useEffect, useId, useRef, useState } from 'react'
import { AlertTriangle, ExternalLink, Loader2, UserRound } from 'lucide-react'
import { fetchPatientCautions } from '../api/client'
import type { PatientCaution } from '../api/client'

// The number sent is the lower edge of the chosen band, so "eGFR below 45" includes 30-44.
const EGFR_BANDS: { value: string; label: string }[] = [
  { value: '', label: 'Not specified' },
  { value: '90', label: '90 or above' },
  { value: '60', label: '60 to 89' },
  { value: '45', label: '45 to 59' },
  { value: '30', label: '30 to 44' },
  { value: '15', label: '15 to 29' },
  { value: '0', label: 'Below 15 or on dialysis' },
]

const levelClass: Record<string, string> = {
  Avoid: 'border-rose-300 bg-rose-50 text-rose-900',
  'Adjust dose': 'border-amber-300 bg-amber-50 text-amber-900',
  'Use with caution': 'border-amber-200 bg-amber-50/60 text-amber-900',
}

export function PatientFactors({ medicines }: { medicines: string[] }) {
  const id = useId()
  const requestIdRef = useRef(0)
  const [age, setAge] = useState('')
  const [egfr, setEgfr] = useState('')
  const [cautions, setCautions] = useState<PatientCaution[]>([])
  const [loading, setLoading] = useState(false)
  const [failed, setFailed] = useState(false)
  const medicinesKey = medicines.join('|')

  useEffect(() => {
    const ageValue = age === '' ? null : Number(age)
    const egfrValue = egfr === '' ? null : Number(egfr)
    const validAge = ageValue !== null && Number.isInteger(ageValue) && ageValue >= 0 && ageValue <= 120
    if (medicines.length === 0 || (!validAge && egfrValue === null)) {
      requestIdRef.current += 1
      setCautions([])
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
        const found = await fetchPatientCautions(medicines, validAge ? ageValue : null, egfrValue, controller.signal)
        if (requestIdRef.current === requestId) setCautions(found)
      } catch (caught) {
        if (requestIdRef.current !== requestId || (caught instanceof Error && caught.name === 'AbortError')) return
        setFailed(true)
      } finally {
        if (requestIdRef.current === requestId) setLoading(false)
      }
    }, 300)
    return () => { window.clearTimeout(timer); controller.abort() }
    // medicinesKey stands in for the medicines array so a new array with the same names does not refetch
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [age, egfr, medicinesKey])

  const anyFactor = age !== '' || egfr !== ''
  return (
    <section aria-label="Patient factors" className="print:hidden rounded-xl border border-slate-200 bg-white p-5 sm:p-7 space-y-3">
      <div className="flex items-start gap-2">
        <UserRound className="mt-0.5 h-5 w-5 shrink-0 text-slate-600" />
        <div>
          <h2 className="text-lg font-bold text-slate-900">Patient factors (optional)</h2>
          <p className="text-xs text-slate-500 mt-1">Age and kidney function change which medicines need extra care. Nothing here is saved.</p>
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label htmlFor={`${id}-age`} className="block text-sm font-semibold text-slate-800">Age (years)</label>
          <input id={`${id}-age`} type="number" inputMode="numeric" min={0} max={120} value={age}
            onChange={(event) => setAge(event.target.value)}
            className="mt-1 w-full rounded-lg border-2 border-slate-300 bg-white px-3 py-2 text-sm text-slate-900" />
        </div>
        <div>
          <label htmlFor={`${id}-egfr`} className="block text-sm font-semibold text-slate-800">Kidney function (eGFR, mL/min/1.73 m²)</label>
          <select id={`${id}-egfr`} value={egfr} onChange={(event) => setEgfr(event.target.value)}
            className="mt-1 w-full rounded-lg border-2 border-slate-300 bg-white px-3 py-2 text-sm text-slate-900">
            {EGFR_BANDS.map((band) => <option key={band.value} value={band.value}>{band.label}</option>)}
          </select>
        </div>
      </div>
      {anyFactor && medicines.length === 0 && <p className="text-xs text-slate-500">Add medicines to see cautions for this patient.</p>}
      {loading && <p className="flex items-center gap-1 text-xs text-slate-500"><Loader2 className="h-3 w-3 animate-spin" /> Checking cautions…</p>}
      {failed && <p role="alert" className="text-xs text-rose-800">Patient cautions are unavailable right now. This does not mean there are none.</p>}
      {!loading && !failed && anyFactor && medicines.length > 0 && (cautions.length === 0
        ? <p className="text-xs text-slate-600">No age or kidney cautions found for these medicines. This list covers only a small set of well-documented cautions.</p>
        : <ul className="space-y-2" aria-label="Cautions for this patient">
          {cautions.map((caution) => <li key={`${caution.drug}-${caution.factor}`} className={`min-w-0 break-words rounded-lg border p-3 text-sm ${levelClass[caution.level] ?? levelClass['Use with caution']}`}>
            <p className="flex flex-wrap items-center gap-2 font-semibold"><AlertTriangle className="h-4 w-4 shrink-0" />{caution.drug}<span className="rounded-full border border-current px-2 py-0.5 text-[11px]">{caution.level}</span><span className="text-xs font-normal">({caution.trigger})</span></p>
            <p className="mt-1">{caution.text}</p>
            <a href={caution.url} target="_blank" rel="noreferrer" className="mt-1 inline-flex items-center gap-1 text-xs font-semibold underline">{caution.source}<ExternalLink className="h-3 w-3" /></a>
          </li>)}
        </ul>)}
    </section>
  )
}
