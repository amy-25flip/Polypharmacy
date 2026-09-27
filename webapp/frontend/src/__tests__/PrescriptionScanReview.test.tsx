import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import * as apiClient from '../api/client'
import { PrescriptionScanReview } from '../components/PrescriptionScanReview'

describe('PrescriptionScanReview safety gate', () => {
  it('does not add an extracted medicine until its row is explicitly confirmed', async () => {
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:test-prescription')
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined)
    vi.spyOn(apiClient, 'scanPrescription').mockResolvedValue({
      source_guess: 'Cardiology',
      date_guess: null,
      warnings: [],
      medicines: [{
        raw_text: 'Warfarin 5 mg nocte',
        drug_name_guess: 'Warfarn',
        generic_name_guess: null,
        dosage: '5 mg',
        frequency_or_timing_guess: 'night',
        confidence_notes: 'Handwriting is slightly unclear',
        suggested_vocab_matches: ['Warfarin'],
        bounding_box: { y_min: 100, x_min: 200, y_max: 250, x_max: 800 },
      }],
    })
    const onConfirmDrug = vi.fn()
    render(<PrescriptionScanReview onConfirmDrug={onConfirmDrug} />)

    const file = new File(['image'], 'prescription.jpg', { type: 'image/jpeg' })
    fireEvent.change(screen.getByLabelText('Upload prescription image'), { target: { files: [file] } })

    await waitFor(() => expect(screen.getByDisplayValue('Warfarin')).toBeInTheDocument())
    expect(screen.getByLabelText('Source image crop for extracted medicine 1')).toBeInTheDocument()
    expect(onConfirmDrug).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: 'Confirm this medicine' }))
    expect(onConfirmDrug).toHaveBeenCalledWith({ name: 'Warfarin', timing: 'Bedtime' })
  })

  it('renders a medicine safely when no source bounding box is available', async () => {
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:test-without-box')
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined)
    vi.spyOn(apiClient, 'scanPrescription').mockResolvedValue({
      source_guess: null,
      date_guess: null,
      warnings: [],
      medicines: [{
        raw_text: 'Unclear tablet',
        drug_name_guess: 'illegible',
        generic_name_guess: null,
        dosage: null,
        frequency_or_timing_guess: null,
        confidence_notes: 'Medicine name is not reasonably legible',
        suggested_vocab_matches: [],
        bounding_box: null,
      }],
    })

    render(<PrescriptionScanReview onConfirmDrug={vi.fn()} />)
    fireEvent.change(screen.getByLabelText('Upload prescription image'), {
      target: { files: [new File(['image'], 'unclear.jpg', { type: 'image/jpeg' })] },
    })

    await waitFor(() => expect(screen.getByDisplayValue('illegible')).toBeInTheDocument())
    expect(screen.queryByLabelText(/Source image crop/)).not.toBeInTheDocument()
  })
})
