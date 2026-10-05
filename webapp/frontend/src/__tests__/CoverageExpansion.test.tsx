import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import * as api from '../api/client'
import type { CandidateFlag, CheckResponse, Disease } from '../api/client'
import { PatientPrescriptionWorkflow } from '../components/PatientPrescriptionWorkflow'
import { InteractionResults } from '../components/InteractionResults'
import { PatientFactors } from '../components/PatientFactors'
import { ScreeningFlag } from '../components/ScreeningFlag'

const fever: Disease = {
  id: 'undifferentiated-fever', name: 'Undifferentiated fever', aliases: ['fever'], specialties: ['General medicine'],
  note: 'Symptom entry: find the cause. Antibiotics are not routine for fever.',
  route_note: 'Most medicines here are applied to the skin.', medicine_count: 2,
}
const emptyScreen = {
  results: [], selected_summary: { overall_severity: null, pairs: [], counts: { Major: 0, Moderate: 0, Minor: 0 } },
  unmatched: [], adverse_effect_basis: 'basis',
}

describe('specialty filter and diagnosis notes', () => {
  beforeEach(() => {
    vi.spyOn(api, 'fetchSpecialties').mockResolvedValue([
      { name: 'Cardiology', disease_count: 7 }, { name: 'Dermatology', disease_count: 33 },
    ])
    vi.spyOn(api, 'searchDiseases').mockResolvedValue([fever])
    vi.spyOn(api, 'fetchDiseaseMedicines').mockResolvedValue([{ name: 'Acetaminophen', sources: ['ICMR STW paediatrics: fever in children'] }])
    vi.spyOn(api, 'screenCandidates').mockResolvedValue(emptyScreen)
  })
  afterEach(() => vi.restoreAllMocks())

  it('narrows the diagnosis search to the chosen specialty', async () => {
    render(<PatientPrescriptionWorkflow mode="diagnosis" />)
    const select = await screen.findByLabelText('Specialty')
    expect(screen.getByRole('option', { name: 'Dermatology (33)' })).toBeInTheDocument()
    fireEvent.change(select, { target: { value: 'Dermatology' } })
    fireEvent.focus(screen.getByRole('combobox', { name: 'Search diagnoses' }))
    await waitFor(() => expect(vi.mocked(api.searchDiseases).mock.calls.some((call) => call[2] === 'Dermatology')).toBe(true))
  })

  it('shows the diagnosis note and the route note above its medicines', async () => {
    render(<PatientPrescriptionWorkflow mode="diagnosis" />)
    fireEvent.focus(screen.getByRole('combobox', { name: 'Search diagnoses' }))
    fireEvent.click(await screen.findByRole('option', { name: /Undifferentiated fever/ }))
    expect(await screen.findByText(/Antibiotics are not routine for fever/)).toBeInTheDocument()
    expect(screen.getByText(/Most medicines here are applied to the skin/)).toBeInTheDocument()
  })
})

describe('medicines the checker cannot check', () => {
  it('says "Not checked" beside a medicine with no interaction data, never "No reaction"', () => {
    const flag: CandidateFlag = {
      with: 'Warfarin', severity: 'None', severity_basis: 'no_data', is_documented: false, uncertain: false, adverse_effects: [],
      severity_notice: 'Mupirocin is applied to the skin and has no interaction records in the reference database.',
    }
    render(<ScreeningFlag flags={[flag]} severity="None" basis="basis" />)
    expect(screen.getAllByText(/Not checked \(no interaction data\)/).length).toBeGreaterThan(0)
    expect(screen.queryByText('No reaction')).not.toBeInTheDocument()
    expect(screen.queryByText(/not proof that it is safe/i)).not.toBeInTheDocument()
  })

  it('headlines a regimen of unchecked pairs as not checked', () => {
    const result: CheckResponse = {
      entered: ['Mupirocin', 'Warfarin'], matched: ['Mupirocin', 'Warfarin'], unmatched: [],
      regimen: {
        overall_severity: 'None',
        pairs: [{
          drug_a: 'Mupirocin', drug_b: 'Warfarin', severity: 'None', severity_basis: 'no_data', is_documented: false,
          severity_notice: 'Mupirocin is applied to the skin and has no interaction records in the reference database.',
        }],
      },
      subset_certificate: null, combination_signal: null,
    }
    render(<InteractionResults result={result} />)
    expect(screen.getByText('Not Checked — No Interaction Data')).toBeInTheDocument()
    expect(screen.queryByText('No Reaction on Record')).not.toBeInTheDocument()
    expect(screen.getAllByText('Not checked').length).toBeGreaterThan(0)
  })
})

describe('pregnancy cautions', () => {
  afterEach(() => vi.restoreAllMocks())

  it('asks for cautions when pregnancy is ticked, even with no age or kidney value', async () => {
    const spy = vi.spyOn(api, 'fetchPatientCautions').mockResolvedValue([{
      drug: 'Isotretinoin', level: 'Avoid', factor: 'pregnancy', trigger: 'pregnant or may become pregnant',
      text: 'Causes serious birth defects.', source: 'FDA Isotretinoin label', url: 'https://dailymed.nlm.nih.gov/x',
    }])
    render(<PatientFactors medicines={['Isotretinoin']} />)
    expect(spy).not.toHaveBeenCalled()
    fireEvent.click(screen.getByLabelText(/Pregnant, or could become pregnant/))
    await waitFor(() => expect(spy).toHaveBeenCalled())
    expect(spy.mock.calls[0][0]).toEqual(['Isotretinoin'])
    expect(spy.mock.calls[0][4]).toBe(true)
    expect(await screen.findByText(/Causes serious birth defects/)).toBeInTheDocument()
  })
})
