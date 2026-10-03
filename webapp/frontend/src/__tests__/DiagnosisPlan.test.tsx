import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { PatientPrescriptionWorkflow } from '../components/PatientPrescriptionWorkflow'
import * as api from '../api/client'
import type { CandidateScreenResponse, CheckResponse } from '../api/client'

const basis = 'Adverse effects are the overlap of each medicine\'s individually known side effects (potentially additive), not an observed outcome of this specific combination.'
const diseases = [
  { id: 'diabetes', name: 'Diabetes', aliases: [], medicine_count: 2 },
  { id: 'kidney', name: 'Kidney disease', aliases: [], medicine_count: 2 },
]
const emptyScreen: CandidateScreenResponse = {
  results: [],
  selected_summary: { overall_severity: null, pairs: [], counts: { Major: 0, Moderate: 0, Minor: 0 } },
  unmatched: [], adverse_effect_basis: basis,
}
const report: CheckResponse = {
  entered: ['Warfarin', 'Metformin'], matched: ['Warfarin', 'Metformin'], unmatched: [],
  regimen: { overall_severity: 'Major', pairs: [{ drug_a: 'Warfarin', drug_b: 'Metformin', severity: 'Major' }] },
  combination_signal: null, subset_certificate: null,
}

async function addDiagnosis(name: string) {
  if (!screen.queryByRole('combobox', { name: 'Search diagnoses' })) fireEvent.click(screen.getByRole('button', { name: 'Add a diagnosis' }))
  const input = screen.getByRole('combobox', { name: 'Search diagnoses' })
  fireEvent.change(input, { target: { value: name } })
  const option = await screen.findByRole('option', { name: new RegExp(name, 'i') })
  fireEvent.click(option)
}

describe('diagnosis medication plan', () => {
  beforeEach(() => {
    vi.spyOn(api, 'searchDiseases').mockImplementation(async (query) => diseases.filter((disease) => disease.name.toLowerCase().includes(query.toLowerCase())))
    vi.spyOn(api, 'fetchDiseaseMedicines').mockImplementation(async (id) => id === 'diabetes'
      ? [{ name: 'Metformin', sources: ['reference'] }, { name: 'Warfarin', sources: ['reference'] }]
      : [{ name: 'Metformin', sources: ['reference'] }, { name: 'Lisinopril', sources: ['reference'] }])
    vi.spyOn(api, 'screenCandidates').mockResolvedValue(emptyScreen)
    vi.spyOn(api, 'searchDrugs').mockResolvedValue([])
  })
  afterEach(() => vi.restoreAllMocks())

  it('searches and selects a diagnosis, blocks duplicate selection, and retries a failed search', async () => {
    const search = vi.mocked(api.searchDiseases)
    search.mockRejectedValueOnce(new Error('503'))
    render(<PatientPrescriptionWorkflow mode="diagnosis" />)
    // The diagnosis tab opens with the search box ready - no extra click needed to start.
    expect(screen.getByText(/No diagnoses added yet/)).toBeInTheDocument()
    const input = screen.getByRole('combobox', { name: 'Search diagnoses' })
    fireEvent.focus(input)
    await waitFor(() => expect(screen.getByText(/Diagnosis search unavailable/)).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: 'Retry diagnosis search' }))
    const option = await screen.findByRole('option', { name: /Diabetes/i })
    fireEvent.click(option)
    expect(screen.getByRole('heading', { name: 'Diabetes' })).toBeInTheDocument()
    fireEvent.focus(input)
    fireEvent.change(input, { target: { value: 'diabetes' } })
    fireEvent.click(await screen.findByRole('option', { name: /Diabetes/i }))
    expect(screen.getAllByRole('heading', { name: 'Diabetes' })).toHaveLength(1)
    expect(screen.getAllByText(/already in this plan/i).length).toBeGreaterThan(0)
  })

  it('multi-selects medicines per diagnosis, merges duplicates, and removes only the selected source', async () => {
    render(<PatientPrescriptionWorkflow mode="diagnosis" />)
    await addDiagnosis('diabetes')
    const diabetes = await screen.findByLabelText('Reference medicines for Diabetes')
    fireEvent.click(within(diabetes).getByRole('checkbox', { name: 'Metformin' }))
    fireEvent.click(within(diabetes).getByRole('checkbox', { name: 'Warfarin' }))
    await addDiagnosis('kidney')
    const kidney = await screen.findByLabelText('Reference medicines for Kidney disease')
    expect(within(kidney).getByText(/Already in plan \(from Diabetes\)/)).toBeInTheDocument()
    fireEvent.click(within(kidney).getByRole('checkbox', { name: 'Metformin' }))
    const combined = screen.getByRole('heading', { name: 'Combined medication list' }).parentElement?.parentElement as HTMLElement
    expect(within(combined).getAllByText('Metformin')).toHaveLength(1)
    expect(within(combined).getByText(/From: Diabetes, Kidney disease/)).toBeInTheDocument()
    fireEvent.click(within(diabetes).getByRole('checkbox', { name: 'Metformin' }))
    expect(within(combined).getByText(/From: Kidney disease/)).toBeInTheDocument()
    await waitFor(() => expect(api.screenCandidates).toHaveBeenCalledWith(expect.arrayContaining(['Metformin', 'Warfarin']), expect.any(Array), expect.any(AbortSignal)))
  })

  it('shows candidate flags, adverse effects, low-confidence marker, no-flag state, and whole-plan summary', async () => {
    vi.mocked(api.screenCandidates).mockImplementation(async (selected, candidates) => ({
      results: candidates.map((candidate) => candidate === 'Warfarin' ? {
        candidate, worst_severity: 'Major', adverse_effects: ['Bleeding'],
        flags: [{ with: 'Metformin', severity: 'Major', is_documented: false, uncertain: true, adverse_effects: ['Bleeding'] }],
      } : { candidate, worst_severity: null, adverse_effects: [], flags: [] }),
      selected_summary: selected.length >= 2 ? {
        overall_severity: 'Major', counts: { Major: 1, Moderate: 0, Minor: 0 },
        pairs: [{ drug_a: 'Metformin', drug_b: 'Warfarin', severity: 'Major', is_documented: false, uncertain: true, adverse_effects: ['Bleeding'] }],
      } : emptyScreen.selected_summary,
      unmatched: [], adverse_effect_basis: basis,
    }))
    vi.spyOn(api, 'checkInteractions').mockResolvedValue(report)
    render(<PatientPrescriptionWorkflow mode="diagnosis" />)
    await addDiagnosis('diabetes')
    const list = await screen.findByLabelText('Reference medicines for Diabetes')
    fireEvent.click(within(list).getByRole('checkbox', { name: 'Metformin' }))
    await waitFor(() => expect(within(list).getAllByText(/with Metformin/i).length).toBeGreaterThan(0))
    expect(within(list).getAllByText(/low-confidence estimate/i).length).toBeGreaterThan(0)
    fireEvent.click(within(list).getByText('Interaction details'))
    expect(within(list).getByText('Bleeding')).toBeInTheDocument()
    expect(within(list).getByText(basis)).toBeInTheDocument()
    fireEvent.click(within(list).getByRole('checkbox', { name: 'Warfarin' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Whole plan screening' })).toBeInTheDocument())
    const summary = screen.getByRole('region', { name: 'Whole plan screening' })
    await waitFor(() => expect(within(summary).getByText(/1 Major/)).toBeInTheDocument())
    fireEvent.click(within(summary).getByRole('button', { name: 'Check interactions for whole plan' }))
    await waitFor(() => expect(api.checkInteractions).toHaveBeenCalledWith(['Metformin', 'Warfarin']))
    expect(await screen.findByText('Major Interaction Risk')).toBeInTheDocument()
  })

  it('discards a superseded screening response and clears results when diagnosis is removed', async () => {
    let resolveOld!: (value: CandidateScreenResponse) => void
    const old = new Promise<CandidateScreenResponse>((resolve) => { resolveOld = resolve })
    const spy = vi.mocked(api.screenCandidates)
    spy.mockResolvedValueOnce(emptyScreen).mockImplementationOnce(() => old).mockResolvedValue(emptyScreen)
    render(<PatientPrescriptionWorkflow mode="diagnosis" />)
    await addDiagnosis('diabetes')
    const list = await screen.findByLabelText('Reference medicines for Diabetes')
    await waitFor(() => expect(spy).toHaveBeenCalled())
    fireEvent.click(within(list).getByRole('checkbox', { name: 'Metformin' }))
    await waitFor(() => expect(spy).toHaveBeenCalledTimes(2))
    fireEvent.click(within(list).getByRole('checkbox', { name: 'Warfarin' }))
    await waitFor(() => expect(spy).toHaveBeenCalledTimes(3))
    resolveOld({ ...emptyScreen, selected_summary: { ...emptyScreen.selected_summary, overall_severity: 'Major' } })
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Whole plan screening' })).toBeInTheDocument())
    expect(screen.getByRole('region', { name: 'Whole plan screening' })).not.toHaveTextContent('Major pairs')
    fireEvent.click(screen.getByRole('button', { name: 'Remove diagnosis Diabetes' }))
    expect(screen.queryByRole('heading', { name: 'Whole plan screening' })).not.toBeInTheDocument()
    expect(screen.queryByText(/No interaction found with current plan/i)).not.toBeInTheDocument()
  })

  it('retries a failed medicine list and shows a no-flag estimate only after screening succeeds', async () => {
    vi.mocked(api.fetchDiseaseMedicines).mockRejectedValueOnce(new Error('503'))
    vi.mocked(api.screenCandidates).mockImplementation(async (_selected, candidates) => ({
      ...emptyScreen,
      results: candidates.map((candidate) => ({ candidate, worst_severity: null, flags: [], adverse_effects: [] })),
    }))
    render(<PatientPrescriptionWorkflow mode="diagnosis" />)
    await addDiagnosis('diabetes')
    expect(await screen.findByText(/Medicine reference list unavailable/)).toBeInTheDocument()
    expect(screen.queryByText(/No interaction found with current plan/i)).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Retry medicines' }))
    const list = await screen.findByLabelText('Reference medicines for Diabetes')
    await waitFor(() => expect(within(list).getByRole('checkbox', { name: 'Metformin' })).toBeInTheDocument())
    // Nothing is selected yet, so there is nothing to compare against: no "no interaction" claim.
    expect(within(list).queryByText(/No interaction found with current plan/i)).not.toBeInTheDocument()
    fireEvent.click(within(list).getByRole('checkbox', { name: 'Metformin' }))
    await waitFor(() => expect(within(list).getAllByText(/No interaction found with current plan/i).length).toBeGreaterThan(0))
  })

  it('shows where each medicine comes from, and closes the diagnosis list after a selection', async () => {
    vi.mocked(api.fetchDiseaseMedicines).mockResolvedValue([
      { name: 'Metformin', sources: ['hetionet:CtD', 'NLEM 2022: section 18.3, medicines used in diabetes mellitus'] },
      { name: 'Bromocriptine', sources: ['hetionet:CpD'] },
    ])
    render(<PatientPrescriptionWorkflow mode="diagnosis" />)
    await addDiagnosis('diabetes')
    const list = await screen.findByLabelText('Reference medicines for Diabetes')
    expect(await within(list).findByText('Listed by: Hetionet (treats) · NLEM 2022')).toBeInTheDocument()
    expect(within(list).getByText('Listed by: Hetionet (symptom relief)')).toBeInTheDocument()
    await waitFor(() => expect(screen.queryByRole('listbox')).not.toBeInTheDocument())
  })

  it('shows a distinct screening failure with Retry, and the printed diagnosis plan', async () => {
    vi.mocked(api.screenCandidates).mockRejectedValue(new Error('network'))
    vi.spyOn(api, 'checkInteractions').mockResolvedValue(report)
    render(<PatientPrescriptionWorkflow mode="diagnosis" />)
    await addDiagnosis('diabetes')
    const list = await screen.findByLabelText('Reference medicines for Diabetes')
    fireEvent.click(within(list).getByRole('checkbox', { name: 'Metformin' }))
    fireEvent.click(within(list).getByRole('checkbox', { name: 'Warfarin' }))
    await waitFor(() => expect(screen.getAllByText(/Live screening unavailable/).length).toBeGreaterThan(0))
    expect(screen.queryByText(/No interaction found with current plan/i)).not.toBeInTheDocument()
    vi.mocked(api.screenCandidates).mockResolvedValue(emptyScreen)
    const callsBeforeRetry = vi.mocked(api.screenCandidates).mock.calls.length
    fireEvent.click(screen.getByRole('button', { name: 'Retry live screening' }))
    await waitFor(() => expect(api.screenCandidates).toHaveBeenCalledTimes(callsBeforeRetry + 1))
    fireEvent.click(screen.getByRole('button', { name: /Check interactions \(2 medicines\)/ }))
    await waitFor(() => expect(screen.getByText('Major Interaction Risk')).toBeInTheDocument())
    expect(screen.getByText('Medication plan by diagnosis')).toBeInTheDocument()
    expect(screen.getByText(/Diabetes:/).parentElement).toHaveTextContent('Metformin, Warfarin')
    fireEvent.click(screen.getByRole('button', { name: 'Remove diagnosis Diabetes' }))
    expect(screen.queryByText('Major Interaction Risk')).not.toBeInTheDocument()
    expect(screen.queryByText('Medication plan by diagnosis')).not.toBeInTheDocument()
  })
})
