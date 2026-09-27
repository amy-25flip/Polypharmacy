import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import * as apiClient from '../api/client'
import { PrescriptionScanReview } from '../components/PrescriptionScanReview'

describe('PrescriptionScanReview safety gate', () => {
  it('does not add an extracted medicine until its row is explicitly confirmed', async () => {
    vi.spyOn(apiClient, 'scanPrescription').mockResolvedValue({
      source_guess: 'Cardiology',
      date_guess: null,
      warnings: [],
      medicines: [{
        raw_text: 'Warfarin 5 mg nocte',
        drug_name_guess: 'Warfarn',
        dosage: '5 mg',
        frequency_or_timing_guess: 'night',
        confidence_notes: 'Handwriting is slightly unclear',
        suggested_vocab_matches: ['Warfarin'],
      }],
    })
    const onConfirmDrug = vi.fn()
    render(<PrescriptionScanReview onConfirmDrug={onConfirmDrug} />)

    const file = new File(['image'], 'prescription.jpg', { type: 'image/jpeg' })
    fireEvent.change(screen.getByLabelText('Upload prescription image'), { target: { files: [file] } })

    await waitFor(() => expect(screen.getByDisplayValue('Warfarin')).toBeInTheDocument())
    expect(onConfirmDrug).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: 'Confirm this medicine' }))
    expect(onConfirmDrug).toHaveBeenCalledWith({ name: 'Warfarin', timing: 'Bedtime' })
  })
})
