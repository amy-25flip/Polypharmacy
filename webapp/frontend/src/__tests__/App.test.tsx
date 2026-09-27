import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
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
})
