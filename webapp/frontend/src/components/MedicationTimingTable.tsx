import { Clock3 } from 'lucide-react'

export const TIMING_OPTIONS = [
  'Morning',
  'Afternoon',
  'Evening',
  'Bedtime',
  'As-needed',
  'Unspecified',
] as const

export type MedicationTiming = (typeof TIMING_OPTIONS)[number]

export interface CombinedMedication {
  name: string
  sources: string[]
  timings: MedicationTiming[]
}

interface MedicationTimingTableProps {
  medications: CombinedMedication[]
}

export function MedicationTimingTable({ medications }: MedicationTimingTableProps) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white overflow-hidden">
      <div className="px-5 py-4 bg-slate-50 border-b border-slate-200">
        <h3 className="font-bold text-slate-900 flex items-center gap-2">
          <Clock3 className="h-4 w-4 text-blue-700" /> Medication timing overview
        </h3>
        <p className="text-xs text-slate-600 mt-1">
          Informational grouping from the entered prescription timing—not a computed interaction timing risk score.
        </p>
      </div>
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 divide-y sm:divide-y-0 border-slate-200">
        {TIMING_OPTIONS.map((timing) => {
          const names = medications
            .filter((medication) => medication.timings.includes(timing))
            .map((medication) => medication.name)
          return (
            <div key={timing} className="p-4 border-slate-100 sm:border-b">
              <h4 className="text-xs font-bold uppercase tracking-wide text-slate-500">{timing}</h4>
              {names.length ? (
                <ul className="mt-2 space-y-1 text-sm font-medium text-slate-800">
                  {names.map((name) => <li key={name}>• {name}</li>)}
                </ul>
              ) : (
                <p className="mt-2 text-xs text-slate-400">None listed</p>
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}
