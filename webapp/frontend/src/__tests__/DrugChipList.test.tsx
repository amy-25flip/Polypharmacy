import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { DrugChipList } from '../components/DrugChipList'
import type { DrugItem } from '../components/DrugChipList'

describe('DrugChipList Component', () => {
  it('renders empty state when no drugs are in list', () => {
    render(<DrugChipList drugs={[]} onRemoveDrug={vi.fn()} onClearAll={vi.fn()} />)
    expect(screen.getByText('No medicines added yet')).toBeInTheDocument()
  })

  it('renders drug chips with distinct styling for matched vs unmatched', () => {
    const drugs: DrugItem[] = [
      { id: '1', name: 'Metformin', isUnmatched: false },
      { id: '2', name: 'Azithromicin', isUnmatched: true },
    ]
    const onRemove = vi.fn()
    const onClear = vi.fn()

    render(<DrugChipList drugs={drugs} onRemoveDrug={onRemove} onClearAll={onClear} />)

    expect(screen.getByText('Metformin')).toBeInTheDocument()
    expect(screen.getByText('Azithromicin')).toBeInTheDocument()
    expect(screen.getByText('(unmatched)')).toBeInTheDocument()
    expect(screen.getByText(/2 medicines/i)).toBeInTheDocument()

    // Test removing a drug
    const removeButtons = screen.getAllByRole('button', { name: /remove/i })
    expect(removeButtons).toHaveLength(2)
    fireEvent.click(removeButtons[0])
    expect(onRemove).toHaveBeenCalledWith('1')

    // Test clear all
    const clearBtn = screen.getByRole('button', { name: /clear list/i })
    fireEvent.click(clearBtn)
    expect(onClear).toHaveBeenCalledTimes(1)
  })
})
