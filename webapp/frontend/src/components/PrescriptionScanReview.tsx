import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, Check, FileImage, Loader2, RotateCcw, ScanLine, X } from 'lucide-react'
import { scanPrescription } from '../api/client'
import type { PrescriptionScanResult, ScannedMedicine } from '../api/client'
import { TIMING_OPTIONS } from './MedicationTimingTable'
import type { MedicationTiming } from './MedicationTimingTable'

export interface ConfirmedScannedDrug {
  name: string
  timing: MedicationTiming
  isUnmatched: boolean
}

interface ReviewRow extends ScannedMedicine {
  id: string
  editedName: string
  timing: MedicationTiming
  status: 'pending' | 'confirmed' | 'rejected'
  confirmedName?: string
  duplicateWarning?: string
}

interface PrescriptionScanReviewProps {
  onConfirmDrug: (drug: ConfirmedScannedDrug) => void
  /** Names already in this prescription (manually added or previously confirmed from
   * this same scan) - used to catch duplicates the way manual entry already does. */
  existingDrugs: string[]
  /** Called when a doctor undoes a confirmed row, so the caller can remove the
   * matching entry it already added via onConfirmDrug. */
  onUndoConfirm: (name: string) => void
  /** Called when a doctor accepts Gemini's guessed source/date as this prescription's
   * label - never applied automatically, since it could silently overwrite a label
   * the doctor already typed. */
  onUseSuggestedSource: (label: string) => void
}

function PrescriptionCrop({ imageUrl, box, label }: {
  imageUrl: string
  box: NonNullable<ScannedMedicine['bounding_box']>
  label: string
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const image = new Image()
    image.onload = () => {
      const sourceX = image.naturalWidth * box.x_min / 1000
      const sourceY = image.naturalHeight * box.y_min / 1000
      const sourceWidth = image.naturalWidth * (box.x_max - box.x_min) / 1000
      const sourceHeight = image.naturalHeight * (box.y_max - box.y_min) / 1000
      if (sourceWidth <= 0 || sourceHeight <= 0) return
      const targetWidth = 240
      const targetHeight = Math.max(48, Math.min(120, Math.round(targetWidth * sourceHeight / sourceWidth)))
      canvas.width = targetWidth
      canvas.height = targetHeight
      const context = canvas.getContext('2d')
      context?.drawImage(image, sourceX, sourceY, sourceWidth, sourceHeight, 0, 0, targetWidth, targetHeight)
    }
    image.src = imageUrl
    return () => { image.onload = null }
  }, [box, imageUrl])

  return <canvas ref={canvasRef} aria-label={label} className="mt-2 max-w-full rounded-md border border-slate-300 bg-white" />
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

export function PrescriptionScanReview({ onConfirmDrug, existingDrugs, onUndoConfirm, onUseSuggestedSource }: PrescriptionScanReviewProps) {
  const [isScanning, setIsScanning] = useState(false)
  const [scan, setScan] = useState<PrescriptionScanResult | null>(null)
  const [rows, setRows] = useState<ReviewRow[]>([])
  const [error, setError] = useState<string | null>(null)
  const [imageUrl, setImageUrl] = useState<string | null>(null)
  const imageUrlRef = useRef<string | null>(null)
  // Visible status text already changes (button label, row badges), but that alone
  // isn't announced to screen-reader users - this drives a matching live region.
  const [announcement, setAnnouncement] = useState('')
  const [sourceSuggestionDismissed, setSourceSuggestionDismissed] = useState(false)

  useEffect(() => () => {
    if (imageUrlRef.current) URL.revokeObjectURL(imageUrlRef.current)
  }, [])

  const handleFile = async (file?: File) => {
    if (!file) return
    if (imageUrlRef.current) URL.revokeObjectURL(imageUrlRef.current)
    const nextImageUrl = URL.createObjectURL(file)
    imageUrlRef.current = nextImageUrl
    setImageUrl(nextImageUrl)
    setIsScanning(true)
    setError(null)
    setScan(null)
    setRows([])
    setSourceSuggestionDismissed(false)
    setAnnouncement('Reading prescription image…')
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
      setAnnouncement(
        result.medicines.length > 0
          ? `${result.medicines.length} medicine${result.medicines.length === 1 ? '' : 's'} found - review each before adding.`
          : 'No medicines could be read from this image.'
      )
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : 'Prescription scanning failed.'
      setError(message)
      setAnnouncement(message)
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

    const isDuplicate = existingDrugs.some((d) => d.toLowerCase() === name.toLowerCase())
    if (isDuplicate) {
      const warning = `"${name}" is already in this prescription - not added again.`
      updateRow(row.id, { duplicateWarning: warning })
      setAnnouncement(warning)
      return
    }

    // The doctor may have edited the OCR suggestion into free text - only trust it as
    // "matched" if it's actually one of the vocabulary matches offered for this row,
    // the same standard manual entry uses.
    const isUnmatched = !row.suggested_vocab_matches.some((match) => match.toLowerCase() === name.toLowerCase())
    onConfirmDrug({ name, timing: row.timing, isUnmatched })
    updateRow(row.id, { status: 'confirmed', confirmedName: name, duplicateWarning: undefined })
    setAnnouncement(`"${name}" confirmed and added.`)
  }

  // Reopens a confirmed/rejected row for correction. For a confirmed row this must
  // also remove the drug it already added, or the reopened row could be re-confirmed
  // into a real duplicate once the doctor fixes the name.
  const undoRow = (row: ReviewRow) => {
    if (row.status === 'confirmed' && row.confirmedName) {
      onUndoConfirm(row.confirmedName)
    }
    updateRow(row.id, { status: 'pending', confirmedName: undefined, duplicateWarning: undefined })
    setAnnouncement('Row reopened for correction.')
  }

  return (
    <div className="rounded-lg border border-blue-200 bg-blue-50/40 p-4 space-y-4">
      <div aria-live="polite" className="sr-only">{announcement}</div>
      <div className="flex items-start gap-3">
        <ScanLine className="h-5 w-5 text-blue-700 shrink-0 mt-0.5" />
        <div>
          <h4 className="text-sm font-bold text-slate-900">Scan a prescription image</h4>
          <p className="text-xs text-slate-600 mt-1">
            Every extracted medicine must be reviewed and confirmed below before it is added or checked.
          </p>
        </div>
      </div>

      <p className="rounded-md bg-blue-100/70 px-3 py-2 text-xs text-slate-700">
        Photograph or crop to only the medicines list—not the whole pad or header. Use a clear, sharp, well-lit image in focus, without blur, glare, shadows, or an extreme angle.
      </p>

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
          onChange={(event) => {
            const file = event.target.files?.[0]
            event.target.value = '' // allow re-selecting the identical file after a failed/empty scan
            void handleFile(file)
          }}
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

      {scan && !sourceSuggestionDismissed && (scan.source_guess || scan.date_guess) && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-blue-200 bg-white px-3 py-2 text-xs">
          <span className="text-slate-700">
            Detected on this image: <span className="font-semibold text-slate-900">{[scan.source_guess, scan.date_guess].filter(Boolean).join(' · ')}</span>
          </span>
          <span className="flex gap-2 shrink-0">
            <button
              type="button"
              onClick={() => {
                onUseSuggestedSource([scan.source_guess, scan.date_guess].filter(Boolean).join(' · '))
                setSourceSuggestionDismissed(true)
              }}
              className="font-bold text-blue-700 hover:text-blue-900"
            >
              Use as prescription label
            </button>
            <button type="button" onClick={() => setSourceSuggestionDismissed(true)} className="font-semibold text-slate-500 hover:text-slate-700">
              Dismiss
            </button>
          </span>
        </div>
      )}

      {scan && rows.length === 0 && (
        <div role="status" className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
          <p className="font-semibold">No medicines could be read from this image.</p>
          <p className="text-xs mt-1">
            Try a clearer, closer, better-lit photo of just the medicines list, or add medicines manually below.
          </p>
        </div>
      )}

      {rows.length > 0 && (
        <div className="space-y-3" aria-label="Extracted medicines awaiting review">
          {rows.map((row, index) => (
            <div key={row.id} className={`rounded-lg border p-3 ${row.status === 'pending' ? 'bg-white border-amber-300' : 'bg-slate-50 border-slate-200 opacity-75'}`}>
              <div className="flex items-center justify-between gap-2">
                <p className="text-xs font-bold text-slate-500">Extracted row {index + 1}</p>
                <span className="text-xs font-semibold capitalize text-slate-500">{row.status}</span>
              </div>
              <p className="mt-1 text-xs text-slate-600">Raw image text: <span className="font-medium">{row.raw_text || 'Not available'}</span></p>
              {imageUrl && row.bounding_box && (
                <PrescriptionCrop imageUrl={imageUrl} box={row.bounding_box} label={`Source image crop for extracted medicine ${index + 1}`} />
              )}
              <div className="mt-3 grid sm:grid-cols-2 gap-3">
                <label className="text-xs font-semibold text-slate-700">
                  Reviewed medicine name
                  <input
                    aria-label={`Reviewed medicine name ${index + 1}`}
                    list={`scan-suggestions-${index}`}
                    value={row.editedName}
                    disabled={row.status !== 'pending'}
                    onChange={(event) => updateRow(row.id, { editedName: event.target.value, duplicateWarning: undefined })}
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
              {row.duplicateWarning && (
                <p className="mt-2 flex items-center gap-1.5 text-xs font-semibold text-amber-800">
                  <AlertTriangle className="h-3.5 w-3.5 shrink-0" /> {row.duplicateWarning}
                </p>
              )}
              {row.status === 'pending' && (
                <div className="mt-3 flex flex-wrap gap-2">
                  <button type="button" disabled={!row.editedName.trim()} onClick={() => confirmRow(row)} className="inline-flex items-center gap-1.5 rounded-md bg-emerald-700 px-3 py-2 text-xs font-bold text-white disabled:opacity-40">
                    <Check className="h-4 w-4" /> Confirm this medicine
                  </button>
                  <button type="button" onClick={() => { updateRow(row.id, { status: 'rejected' }); setAnnouncement('Extracted medicine rejected.') }} className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 px-3 py-2 text-xs font-bold text-slate-700">
                    <X className="h-4 w-4" /> Reject
                  </button>
                </div>
              )}
              {row.status !== 'pending' && (
                <div className="mt-3">
                  <button type="button" onClick={() => undoRow(row)} className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-3 py-2 text-xs font-bold text-slate-700 hover:bg-slate-50">
                    <RotateCcw className="h-3.5 w-3.5" /> {row.status === 'confirmed' ? 'Undo - remove and re-edit' : 'Undo rejection'}
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
