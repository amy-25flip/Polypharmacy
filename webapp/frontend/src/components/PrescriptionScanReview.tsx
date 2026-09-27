import { useState } from 'react'
import { AlertTriangle, Check, FileImage, Loader2, ScanLine, X } from 'lucide-react'
import { scanPrescription } from '../api/client'
import type { PrescriptionScanResult, ScannedMedicine } from '../api/client'
import { TIMING_OPTIONS } from './MedicationTimingTable'
import type { MedicationTiming } from './MedicationTimingTable'

export interface ConfirmedScannedDrug {
  name: string
  timing: MedicationTiming
}

interface ReviewRow extends ScannedMedicine {
  id: string
  editedName: string
  timing: MedicationTiming
  status: 'pending' | 'confirmed' | 'rejected'
}

interface PrescriptionScanReviewProps {
  onConfirmDrug: (drug: ConfirmedScannedDrug) => void
}

function timingFromGuess(guess: string | null): MedicationTiming {
  const value = (guess || '').toLowerCase()
  if (/morning|breakfast|\bam\b/.test(value)) return 'Morning'
  if (/afternoon|lunch|noon/.test(value)) return 'Afternoon'
  if (/evening|dinner|\bpm\b/.test(value)) return 'Evening'
  if (/bedtime|night|hs/.test(value)) return 'Bedtime'
  if (/as needed|prn/.test(value)) return 'As-needed'
  return 'Unspecified'
}

export function PrescriptionScanReview({ onConfirmDrug }: PrescriptionScanReviewProps) {
  const [isScanning, setIsScanning] = useState(false)
  const [scan, setScan] = useState<PrescriptionScanResult | null>(null)
  const [rows, setRows] = useState<ReviewRow[]>([])
  const [error, setError] = useState<string | null>(null)

  const handleFile = async (file?: File) => {
    if (!file) return
    setIsScanning(true)
    setError(null)
    setScan(null)
    setRows([])
    try {
      const result = await scanPrescription(file)
      setScan(result)
      setRows(result.medicines.map((medicine, index) => ({
        ...medicine,
        id: `${index}-${medicine.raw_text}`,
        editedName: medicine.suggested_vocab_matches[0] || medicine.drug_name_guess,
        timing: timingFromGuess(medicine.frequency_or_timing_guess),
        status: 'pending',
      })))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Prescription scanning failed.')
    } finally {
      setIsScanning(false)
    }
  }

  const updateRow = (id: string, patch: Partial<ReviewRow>) => {
    setRows((current) => current.map((row) => row.id === id ? { ...row, ...patch } : row))
  }

  const confirmRow = (row: ReviewRow) => {
    const name = row.editedName.trim()
    if (!name || row.status !== 'pending') return
    onConfirmDrug({ name, timing: row.timing })
    updateRow(row.id, { status: 'confirmed' })
  }

  return (
    <div className="rounded-lg border border-blue-200 bg-blue-50/40 p-4 space-y-4">
      <div className="flex items-start gap-3">
        <ScanLine className="h-5 w-5 text-blue-700 shrink-0 mt-0.5" />
        <div>
          <h4 className="text-sm font-bold text-slate-900">Scan a prescription image</h4>
          <p className="text-xs text-slate-600 mt-1">
            Every extracted medicine must be reviewed and confirmed below before it is added or checked.
          </p>
        </div>
      </div>

      <label className="flex cursor-pointer items-center justify-center gap-2 rounded-lg border-2 border-dashed border-blue-300 bg-white px-4 py-4 text-sm font-semibold text-blue-800 hover:bg-blue-50">
        {isScanning ? <Loader2 className="h-5 w-5 animate-spin" /> : <FileImage className="h-5 w-5" />}
        {isScanning ? 'Reading prescription…' : 'Choose or photograph prescription'}
        <input
          aria-label="Upload prescription image"
          type="file"
          accept="image/*"
          capture="environment"
          className="sr-only"
          disabled={isScanning}
          onChange={(event) => void handleFile(event.target.files?.[0])}
        />
      </label>

      {error && (
        <div role="alert" className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
          <p className="font-semibold">
            {error.toLowerCase().includes('not configured')
              ? 'Prescription scanning is not set up on this server yet.'
              : 'Prescription scanning failed.'}
          </p>
          <p className="text-xs mt-1">{error} You can still add medicines manually below.</p>
        </div>
      )}

      {scan?.warnings.map((warning) => (
        <p key={warning} className="flex gap-2 text-xs text-amber-800">
          <AlertTriangle className="h-4 w-4 shrink-0" /> {warning}
        </p>
      ))}

      {rows.length > 0 && (
        <div className="space-y-3" aria-label="Extracted medicines awaiting review">
          {rows.map((row, index) => (
            <div key={row.id} className={`rounded-lg border p-3 ${row.status === 'pending' ? 'bg-white border-amber-300' : 'bg-slate-50 border-slate-200 opacity-75'}`}>
              <div className="flex items-center justify-between gap-2">
                <p className="text-xs font-bold text-slate-500">Extracted row {index + 1}</p>
                <span className="text-xs font-semibold capitalize text-slate-500">{row.status}</span>
              </div>
              <p className="mt-1 text-xs text-slate-600">Raw image text: <span className="font-medium">{row.raw_text || 'Not available'}</span></p>
              <div className="mt-3 grid sm:grid-cols-2 gap-3">
                <label className="text-xs font-semibold text-slate-700">
                  Reviewed medicine name
                  <input
                    aria-label={`Reviewed medicine name ${index + 1}`}
                    list={`scan-suggestions-${index}`}
                    value={row.editedName}
                    disabled={row.status !== 'pending'}
                    onChange={(event) => updateRow(row.id, { editedName: event.target.value })}
                    className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm font-normal text-slate-900"
                  />
                  <datalist id={`scan-suggestions-${index}`}>
                    {row.suggested_vocab_matches.map((match) => <option key={match} value={match} />)}
                  </datalist>
                </label>
                <label className="text-xs font-semibold text-slate-700">
                  Timing
                  <select
                    aria-label={`Timing for extracted medicine ${index + 1}`}
                    value={row.timing}
                    disabled={row.status !== 'pending'}
                    onChange={(event) => updateRow(row.id, { timing: event.target.value as MedicationTiming })}
                    className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm font-normal text-slate-900"
                  >
                    {TIMING_OPTIONS.map((timing) => <option key={timing}>{timing}</option>)}
                  </select>
                </label>
              </div>
              {(row.dosage || row.confidence_notes || row.frequency_or_timing_guess) && (
                <p className="mt-2 text-xs text-amber-800">
                  {[row.dosage && `Dosage: ${row.dosage}`, row.frequency_or_timing_guess && `Timing read: ${row.frequency_or_timing_guess}`, row.confidence_notes].filter(Boolean).join(' · ')}
                </p>
              )}
              {row.status === 'pending' && (
                <div className="mt-3 flex gap-2">
                  <button type="button" disabled={!row.editedName.trim()} onClick={() => confirmRow(row)} className="inline-flex items-center gap-1.5 rounded-md bg-emerald-700 px-3 py-2 text-xs font-bold text-white disabled:opacity-40">
                    <Check className="h-4 w-4" /> Confirm this medicine
                  </button>
                  <button type="button" onClick={() => updateRow(row.id, { status: 'rejected' })} className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 px-3 py-2 text-xs font-bold text-slate-700">
                    <X className="h-4 w-4" /> Reject
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
