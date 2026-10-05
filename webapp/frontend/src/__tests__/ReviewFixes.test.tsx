import { afterEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import * as api from '../api/client'
import type { CheckResponse } from '../api/client'
import { PatientPrescriptionWorkflow } from '../components/PatientPrescriptionWorkflow'
import { InteractionResults } from '../components/InteractionResults'
import { PatientFactors } from '../components/PatientFactors'

const caution: api.PatientCaution = {
  drug: 'Isotretinoin', level: 'Avoid', factor: 'pregnancy', trigger: 'pregnancy possible',
  text: 'Causes serious birth defects.', source: 'FDA Isotretinoin label', url: 'https://dailymed.nlm.nih.gov/x',
}

describe('patient factors', () => {
  afterEach(() => vi.restoreAllMocks())

  it('asks for cautions when a pregnancy state is chosen, with no age or kidney value, and tells possible from pregnant', async () => {
    const spy = vi.spyOn(api, 'fetchPatientCautions').mockResolvedValue([caution])
    render(<PatientFactors medicines={['Isotretinoin']} />)
    expect(spy).not.toHaveBeenCalled()
    fireEvent.click(screen.getByLabelText('Could become pregnant'))
    await waitFor(() => expect(spy).toHaveBeenCalled())
    expect(spy.mock.calls[0][0]).toEqual(['Isotretinoin'])
    expect(spy.mock.calls[0][4]).toBe('possible')
    expect(await screen.findByText(/Causes serious birth defects/)).toBeInTheDocument()
    fireEvent.click(screen.getByLabelText('Currently pregnant'))
    await waitFor(() => expect(spy.mock.calls.some((call) => call[4] === 'pregnant')).toBe(true))
  })

  it('says nothing here is a clearance when no rule matched', async () => {
    vi.spyOn(api, 'fetchPatientCautions').mockResolvedValue([])
    render(<PatientFactors medicines={['Acetaminophen']} />)
    fireEvent.click(screen.getByLabelText('Currently pregnant'))
    expect(await screen.findByText(/not a clearance/i)).toBeInTheDocument()
  })

  it('warns that the tool is not for prescribing to a child', () => {
    vi.spyOn(api, 'fetchPatientCautions').mockResolvedValue([])
    render(<PatientFactors medicines={['Acetaminophen']} />)
    fireEvent.change(screen.getByLabelText(/Age/i), { target: { value: '4' } })
    expect(screen.getByText(/Paediatric patient: dose, weight and formulation are not assessed/)).toBeInTheDocument()
  })

  it('lists only the plan medicines in the panel but reports cautions for the candidates too', async () => {
    vi.spyOn(api, 'fetchPatientCautions').mockResolvedValue([
      { ...caution, drug: 'Isotretinoin' }, { ...caution, drug: 'Methotrexate', text: 'Can cause fetal death.' },
    ])
    const onCautions = vi.fn()
    render(<PatientFactors medicines={['Isotretinoin', 'Methotrexate']} selected={['Isotretinoin']} onCautions={onCautions} />)
    fireEvent.click(screen.getByLabelText('Could become pregnant'))
    expect(await screen.findByText(/Causes serious birth defects/)).toBeInTheDocument()
    expect(screen.queryByText(/Can cause fetal death/)).not.toBeInTheDocument()
    await waitFor(() => expect(onCautions).toHaveBeenLastCalledWith(expect.arrayContaining([expect.objectContaining({ drug: 'Methotrexate' })])))
  })
})

describe('result summary and print facts', () => {
  const pair = (a: string, b: string, severity: 'Major' | 'Moderate' | 'Minor' | 'None', basis: NonNullable<api.InteractionPair['severity_basis']>) =>
    ({ drug_a: a, drug_b: b, severity, severity_basis: basis, is_documented: basis === 'documented' }) as api.InteractionPair

  it('summarises recorded Major pairs first, separates model estimates, and flags an incomplete screen', () => {
    const result: CheckResponse = {
      entered: ['Warfarin', 'Aspirin', 'Amiodarone', 'Mupirocin', 'Foo'], matched: ['Warfarin', 'Aspirin', 'Amiodarone', 'Mupirocin'], unmatched: ['Foo'],
      regimen: {
        overall_severity: 'Major',
        pairs: [
          pair('Warfarin', 'Aspirin', 'Major', 'documented'), pair('Warfarin', 'Amiodarone', 'Major', 'inferred'),
          pair('Aspirin', 'Amiodarone', 'Minor', 'inferred'), pair('Mupirocin', 'Warfarin', 'None', 'no_data'),
        ],
      },
      subset_certificate: null, combination_signal: null,
    }
    render(<InteractionResults result={result} patient={{ age: '72 years', egfr: '15 to 29', pregnancy: 'not pregnant / not applicable' }} />)
    const glance = screen.getByLabelText('At a glance')
    expect(glance).toHaveTextContent(/Major, backed by a record or label warning \(1\): Warfarin \+ Aspirin/)
    expect(glance).toHaveTextContent(/Major, model estimate to verify \(1\): Warfarin \+ Amiodarone/)
    expect(glance).toHaveTextContent(/Not checked \(no interaction data\): Mupirocin, Warfarin/)
    expect(glance).toHaveTextContent(/Not matched to the database: Foo/)
    expect(screen.getByText('Screen incomplete')).toBeInTheDocument()
    expect(screen.getAllByText(/3 of 4 pairs screened; 1 not checked/).length).toBeGreaterThanOrEqual(1)
    // Minor and not-checked pairs sit behind a summary so the Major and Moderate ones lead.
    expect(screen.getByText(/Show 2 lower-priority pairs/)).toBeInTheDocument()
    // The printed copy states the facts the check used.
    expect(screen.getByText('Facts used for this check')).toBeInTheDocument()
    expect(screen.getByText(/Age: 72 years/)).toBeInTheDocument()
    expect(screen.getByText(/Reviewed by:/)).toBeInTheDocument()
  })
})

describe('clinical groups in a medicine list', () => {
  afterEach(() => vi.restoreAllMocks())

  it('shows first-line choices up front and keeps specialist options collapsed', async () => {
    vi.spyOn(api, 'fetchSpecialties').mockResolvedValue([])
    vi.spyOn(api, 'searchDiseases').mockResolvedValue([{ id: 'ht', name: 'Hypertension', aliases: [], medicine_count: 3 }])
    vi.spyOn(api, 'screenCandidates').mockResolvedValue({
      results: [], selected_summary: { overall_severity: null, pairs: [], counts: { Major: 0, Moderate: 0, Minor: 0 } }, unmatched: [], adverse_effect_basis: 'basis',
    })
    vi.spyOn(api, 'fetchDiseaseMedicines').mockResolvedValue([
      { name: 'Amlodipine', sources: ['ICMR STW'], group: 'Usual first choices', group_order: 0, group_collapsed: false },
      { name: 'Atorvastatin', sources: ['hetionet:CtD'], group: 'Lowers heart risk, not blood pressure', group_order: 2, group_collapsed: false, label: 'A statin: lowers cholesterol, not blood pressure' },
      { name: 'Guanethidine', sources: ['hetionet:CtD'], group: 'More options (specialist, acute-care or rarely used)', group_order: 99, group_collapsed: true },
    ])
    render(<PatientPrescriptionWorkflow mode="diagnosis" />)
    fireEvent.focus(screen.getByRole('combobox', { name: 'Search diagnoses' }))
    fireEvent.click(await screen.findByRole('option', { name: /Hypertension/ }))
    expect(await screen.findByRole('heading', { name: /Usual first choices \(1\)/ })).toBeInTheDocument()
    expect(screen.getByText('A statin: lowers cholesterol, not blood pressure')).toBeInTheDocument()
    const specialist = screen.getByText(/More options \(specialist, acute-care or rarely used\) \(1\)/)
    expect(specialist.closest('details')).not.toHaveAttribute('open')
    expect(screen.getByText('Fewest flagged interactions')).toBeInTheDocument()
    expect(screen.getByText(/have not yet been reviewed by an Indian clinician or pharmacist/)).toBeInTheDocument()
  })
})
