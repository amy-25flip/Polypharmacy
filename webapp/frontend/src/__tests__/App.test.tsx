import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { App } from '../App'
import * as apiClient from '../api/client'
import type { CheckResponse } from '../api/client'

describe('App Full Integration Flow', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.spyOn(apiClient, 'checkHealth').mockResolvedValue({
      status: 'ok',
      known_drugs: 1902,
    })
  })

  it('disables check button with fewer than 2 medicines and enables when 2+ are added', async () => {
    vi.spyOn(apiClient, 'searchDrugs').mockImplementation(async (q) => {
      if (q.toLowerCase().startsWith('met')) return [{ name: 'Metformin' }]
      if (q.toLowerCase().startsWith('war')) return [{ name: 'Warfarin' }]
      return []
    })

    render(<App />)

    // Check button initially disabled
    const checkBtn = screen.getByRole('button', { name: /Check interactions/i })
    expect(checkBtn).toBeDisabled()

    // Add first drug
    const input = screen.getByLabelText(/Add medicine/i)
    fireEvent.change(input, { target: { value: 'metf' } })
    await waitFor(() => expect(screen.getByText('Metformin')).toBeInTheDocument())
    fireEvent.click(screen.getByText('Metformin'))

    // Still disabled with 1 medicine
    expect(checkBtn).toBeDisabled()
    expect(screen.getByText(/Add at least 1 more medicine/i)).toBeInTheDocument()

    // Add second drug
    fireEvent.change(input, { target: { value: 'warf' } })
    await waitFor(() => expect(screen.getByText('Warfarin')).toBeInTheDocument())
    fireEvent.click(screen.getByText('Warfarin'))

    // Now enabled with 2 medicines
    expect(checkBtn).not.toBeDisabled()
  })

  it('executes interaction check and displays results panel', async () => {
    vi.spyOn(apiClient, 'searchDrugs').mockImplementation(async (q) => {
      if (q.toLowerCase().startsWith('met')) return [{ name: 'Metformin' }]
      if (q.toLowerCase().startsWith('war')) return [{ name: 'Warfarin' }]
      return []
    })

    const mockResponse: CheckResponse = {
      entered: ['Metformin', 'Warfarin'],
      matched: ['Metformin', 'Warfarin'],
      unmatched: [],
      regimen: {
        overall_severity: 'Moderate',
        pairs: [
          { drug_a: 'Metformin', drug_b: 'Warfarin', severity: 'Moderate', confidence: 0.77 },
        ],
      },
      subset_certificate: null,
      combination_signal: null,
    }

    vi.spyOn(apiClient, 'checkInteractions').mockResolvedValue(mockResponse)

    render(<App />)

    const input = screen.getByLabelText(/Add medicine/i)
    fireEvent.change(input, { target: { value: 'metf' } })
    await waitFor(() => expect(screen.getByText('Metformin')).toBeInTheDocument())
    fireEvent.click(screen.getByText('Metformin'))

    fireEvent.change(input, { target: { value: 'warf' } })
    await waitFor(() => expect(screen.getByText('Warfarin')).toBeInTheDocument())
    fireEvent.click(screen.getByText('Warfarin'))

    const checkBtn = screen.getByRole('button', { name: /Check interactions/i })
    fireEvent.click(checkBtn)

    await waitFor(() => {
      expect(screen.getByText('Moderate Interaction Risk')).toBeInTheDocument()
      expect(screen.getByText(/Metformin \+ Warfarin/i)).toBeInTheDocument()
    })
  })
  describe('workflow tabs', () => {
    beforeEach(() => {
      vi.spyOn(apiClient, 'searchDrugs').mockImplementation(async (q) => (q.toLowerCase().startsWith('met') ? [{ name: 'Metformin' }] : []))
      vi.spyOn(apiClient, 'searchDiseases').mockResolvedValue([])
    })

    it('opens on the original prescription workflow, with no diagnosis controls', () => {
      render(<App />)
      expect(screen.getByRole('tab', { name: /Prescriptions & scan/ })).toHaveAttribute('aria-selected', 'true')
      expect(screen.getByRole('tab', { name: /Plan by diagnosis/ })).toHaveAttribute('aria-selected', 'false')
      expect(screen.getByRole('heading', { name: 'Patient prescription session' })).toBeInTheDocument()
      expect(screen.getByText('Scan a prescription image')).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Add a diagnosis' })).not.toBeInTheDocument()
      expect(screen.queryByRole('heading', { name: 'Plan by diagnosis' })).not.toBeInTheDocument()
    })

    it('switches to the diagnosis workflow, which has its own controls and none of the prescription ones', () => {
      render(<App />)
      fireEvent.click(screen.getByRole('tab', { name: /Plan by diagnosis/ }))
      expect(screen.getByRole('tab', { name: /Plan by diagnosis/ })).toHaveAttribute('aria-selected', 'true')
      expect(screen.getByRole('heading', { name: 'Plan by diagnosis' })).toBeInTheDocument()
      expect(screen.getByRole('combobox', { name: 'Search diagnoses' })).toBeInTheDocument()
      // The prescription panel is hidden, so its controls are not available here.
      expect(screen.queryByRole('heading', { name: 'Scan a prescription image' })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Try an example' })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Add another prescription' })).not.toBeInTheDocument()
    })

    it('keeps each tab session when switching back and forth', async () => {
      render(<App />)
      fireEvent.change(screen.getByLabelText(/Add medicine/i), { target: { value: 'metf' } })
      await waitFor(() => expect(screen.getByText('Metformin')).toBeInTheDocument())
      fireEvent.click(screen.getByText('Metformin'))
      expect(screen.getByText(/From: Prescription 1/)).toBeInTheDocument()

      fireEvent.click(screen.getByRole('tab', { name: /Plan by diagnosis/ }))
      // Only the visible panel is exposed; the diagnosis session is separate and empty.
      expect(within(screen.getByRole('tabpanel')).queryByText(/From: Prescription 1/)).not.toBeInTheDocument()
      expect(within(screen.getByRole('tabpanel')).getByText(/No diagnoses added yet/)).toBeInTheDocument()
      fireEvent.click(screen.getByRole('tab', { name: /Prescriptions & scan/ }))
      expect(within(screen.getByRole('tabpanel')).getByText(/From: Prescription 1/)).toBeInTheDocument()
    })

    it('supports arrow-key navigation between tabs', () => {
      render(<App />)
      const first = screen.getByRole('tab', { name: /Prescriptions & scan/ })
      first.focus()
      fireEvent.keyDown(first, { key: 'ArrowRight' })
      const second = screen.getByRole('tab', { name: /Plan by diagnosis/ })
      expect(second).toHaveAttribute('aria-selected', 'true')
      expect(second).toHaveFocus()
    })
  })
})
