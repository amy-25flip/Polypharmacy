import { afterEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import * as api from '../api/client'
import { PatientFactors } from '../components/PatientFactors'

const caution: api.PatientCaution = {
  drug: 'Metformin', level: 'Avoid', factor: 'egfr', trigger: 'eGFR below 30',
  text: 'Contraindicated when eGFR is below 30 (risk of lactic acidosis).',
  source: 'FDA Metformin label', url: 'https://dailymed.nlm.nih.gov/dailymed/search.cfm?query=metformin',
}

describe('PatientFactors', () => {
  afterEach(() => vi.restoreAllMocks())

  it('asks for cautions only once a factor is entered, using the band\'s lower edge', async () => {
    const spy = vi.spyOn(api, 'fetchPatientCautions').mockResolvedValue([caution])
    render(<PatientFactors medicines={['Metformin']} />)
    expect(spy).not.toHaveBeenCalled()

    fireEvent.change(screen.getByLabelText(/Kidney function/i), { target: { value: '15' } })
    await waitFor(() => expect(spy).toHaveBeenCalled())
    expect(spy.mock.calls[0].slice(0, 3)).toEqual([['Metformin'], null, 15])
    expect(await screen.findByText(/Contraindicated when eGFR is below 30/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /FDA Metformin label/i })).toHaveAttribute('href', caution.url)
  })

  it('does not claim there are no cautions when the lookup fails', async () => {
    vi.spyOn(api, 'fetchPatientCautions').mockRejectedValue(new Error('network'))
    render(<PatientFactors medicines={['Metformin']} />)
    fireEvent.change(screen.getByLabelText(/Age/i), { target: { value: '72' } })
    expect(await screen.findByRole('alert')).toHaveTextContent(/does not mean there are none/i)
    expect(screen.queryByText(/No age or kidney cautions found/i)).not.toBeInTheDocument()
  })

  it('says so when a factor is set but there are no medicines yet', () => {
    const spy = vi.spyOn(api, 'fetchPatientCautions').mockResolvedValue([])
    render(<PatientFactors medicines={[]} />)
    fireEvent.change(screen.getByLabelText(/Age/i), { target: { value: '80' } })
    expect(screen.getByText(/Add medicines to see cautions/i)).toBeInTheDocument()
    expect(spy).not.toHaveBeenCalled()
  })
})
