import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { DrugSearchInput } from '../components/DrugSearchInput'
import * as apiClient from '../api/client'

describe('DrugSearchInput Component', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
  })

  afterEach(() => {
    vi.clearAllTimers()
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('debounces search and displays suggestions when query >= 2 chars', async () => {
    const searchSpy = vi.spyOn(apiClient, 'searchDrugs').mockResolvedValue([
      { name: 'Metformin' },
      { name: 'Metformin hydrochloride' },
    ])
    const onAddDrug = vi.fn()

    render(<DrugSearchInput onAddDrug={onAddDrug} existingDrugs={[]} />)

    const input = screen.getByLabelText(/Add medicine/i)
    fireEvent.change(input, { target: { value: 'metf' } })

    // Before debounce timer fires
    expect(searchSpy).not.toHaveBeenCalled()

    // Fast-forward 200ms debounce
    vi.advanceTimersByTime(200)

    await waitFor(() => {
      expect(searchSpy).toHaveBeenCalledWith('metf', expect.any(AbortSignal))
    })

    await waitFor(() => {
      expect(screen.getByText('Metformin')).toBeInTheDocument()
      expect(screen.getByText('Metformin hydrochloride')).toBeInTheDocument()
    })

    // Click on suggestion
    fireEvent.click(screen.getByText('Metformin'))
    expect(onAddDrug).toHaveBeenCalledWith('Metformin', false)
  })

  it('displays non-blocking unmatched option when no matches are found', async () => {
    vi.spyOn(apiClient, 'searchDrugs').mockResolvedValue([])
    const onAddDrug = vi.fn()

    render(<DrugSearchInput onAddDrug={onAddDrug} existingDrugs={[]} />)

    const input = screen.getByLabelText(/Add medicine/i)
    fireEvent.change(input, { target: { value: 'UnknownMed123' } })
    vi.advanceTimersByTime(200)

    await waitFor(() => {
      expect(screen.getByText(/No match found in database/i)).toBeInTheDocument()
      expect(screen.getByText(/anyway\?/i)).toBeInTheDocument()
    })

    // Click the fallback unmatched option
    fireEvent.click(screen.getByText(/No match found in database/i))
    expect(onAddDrug).toHaveBeenCalledWith('UnknownMed123', true)
  })

  it('warns when attempting to add duplicate medicine', async () => {
    vi.spyOn(apiClient, 'searchDrugs').mockResolvedValue([{ name: 'Metformin' }])
    const onAddDrug = vi.fn()

    render(<DrugSearchInput onAddDrug={onAddDrug} existingDrugs={['Metformin']} />)

    const input = screen.getByLabelText(/Add medicine/i)
    fireEvent.change(input, { target: { value: 'metf' } })
    vi.advanceTimersByTime(200)

    await waitFor(() => {
      expect(screen.getByText('Metformin')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('Metformin'))

    expect(onAddDrug).not.toHaveBeenCalled()
    expect(screen.getByText(/"Metformin" is already added to the patient's list\./i)).toBeInTheDocument()
  })

  it('shows the originating brand but adds the generic name', async () => {
    vi.spyOn(apiClient, 'searchDrugs').mockResolvedValue([
      { name: 'Acetaminophen', matched_via_brand: 'dolo 650' },
    ])
    const onAddDrug = vi.fn()
    render(<DrugSearchInput onAddDrug={onAddDrug} existingDrugs={[]} />)

    fireEvent.change(screen.getByLabelText(/Add medicine/i), { target: { value: 'Dolo 650' } })
    vi.advanceTimersByTime(200)
    await waitFor(() => expect(screen.getByText('brand: dolo 650')).toBeInTheDocument())

    fireEvent.click(screen.getByText('Acetaminophen'))
    expect(onAddDrug).toHaveBeenCalledWith('Acetaminophen', false)
  })
})
