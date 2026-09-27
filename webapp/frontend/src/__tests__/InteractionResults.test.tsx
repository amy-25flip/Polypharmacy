import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { InteractionResults } from '../components/InteractionResults'
import type { CheckResponse } from '../api/client'

describe('InteractionResults Component', () => {
  it('renders Major severity banner with required clinical action line and highest-risk pair', () => {
    const mockMajorResult: CheckResponse = {
      entered: ['Metformin', 'Warfarin', 'Aspirin'],
      matched: ['Metformin', 'Warfarin', 'Aspirin'],
      unmatched: [],
      regimen: {
        overall_severity: 'Major',
        pairs: [
          { drug_a: 'Warfarin', drug_b: 'Aspirin', severity: 'Major', confidence: 0.91 },
          { drug_a: 'Metformin', drug_b: 'Warfarin', severity: 'Moderate', confidence: 0.77 },
          { drug_a: 'Metformin', drug_b: 'Aspirin', severity: 'Minor', confidence: 0.65 },
        ],
      },
      subset_certificate: null,
      combination_signal: {
        drugs_used: 3,
        drugs_total: 3,
        probability: 0.82,
        elevated: true,
      },
    }

    render(<InteractionResults result={mockMajorResult} />)

    // Check Major banner
    expect(screen.getByText('Major Interaction Risk')).toBeInTheDocument()

    // Check action line for Major severity
    expect(
      screen.getByText(/Review therapy, dose, alternatives, or monitoring needs before continuing\./i)
    ).toBeInTheDocument()

    // Check highest risk pair callout
    expect(screen.getByText(/Highest-risk pair:/i)).toBeInTheDocument()
    expect(screen.getAllByText(/Warfarin/i).length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText(/Aspirin/i).length).toBeGreaterThanOrEqual(1)
    expect(screen.getByRole('heading', { name: /Warfarin \+ Aspirin/i })).toBeInTheDocument()

    // Check secondary combination signal prompt
    expect(screen.getByText('Multi-Drug Pattern Review')).toBeInTheDocument()
    expect(
      screen.getByText(/The set-level model reviewed 3 of 3 recognized medicines together/i)
    ).toBeInTheDocument()
    expect(
      screen.getByText(/This combination resembles known higher-risk medication patterns/i)
    ).toBeInTheDocument()

    // Verify NO internal ML terms appear anywhere in rendered text
    const textContent = document.body.textContent || ''
    expect(textContent).not.toMatch(/0\.91/i)
    expect(textContent).not.toMatch(/0\.82/i)
    expect(textContent).not.toMatch(/probability/i)
    expect(textContent).not.toMatch(/confidence/i)
    expect(textContent).not.toMatch(/AUROC/i)
    expect(textContent).not.toMatch(/TF-IDF/i)
    expect(textContent).not.toMatch(/neural network/i)
  })

  it('renders Moderate severity banner without major action line', () => {
    const mockModerateResult: CheckResponse = {
      entered: ['Metformin', 'Warfarin'],
      matched: ['Metformin', 'Warfarin'],
      unmatched: [],
      regimen: {
        overall_severity: 'Moderate',
        pairs: [
          { drug_a: 'Metformin', drug_b: 'Warfarin', severity: 'Moderate', confidence: 0.75 },
        ],
      },
      subset_certificate: null,
      combination_signal: null,
    }

    render(<InteractionResults result={mockModerateResult} />)

    expect(screen.getByText('Moderate Interaction Risk')).toBeInTheDocument()
    expect(
      screen.queryByText(/Review therapy, dose, alternatives, or monitoring needs before continuing\./i)
    ).not.toBeInTheDocument()
    expect(
      screen.queryByText(/Combination pattern check/i)
    ).not.toBeInTheDocument()
  })

  it('renders Minor severity banner for green/minor result', () => {
    const mockMinorResult: CheckResponse = {
      entered: ['Metformin', 'Aspirin'],
      matched: ['Metformin', 'Aspirin'],
      unmatched: [],
      regimen: {
        overall_severity: 'Minor',
        pairs: [
          { drug_a: 'Metformin', drug_b: 'Aspirin', severity: 'Minor', confidence: 0.6 },
        ],
      },
      subset_certificate: null,
      combination_signal: {
        drugs_used: 2,
        drugs_total: 2,
        probability: 0.2,
        elevated: false,
      },
    }

    render(<InteractionResults result={mockMinorResult} />)

    expect(screen.getByText('Minor Interaction Risk')).toBeInTheDocument()
    // When combination_signal.elevated is false, nothing extra should be displayed
    expect(
      screen.queryByText(/Combination pattern check/i)
    ).not.toBeInTheDocument()
    expect(screen.queryByText(/not elevated/i)).not.toBeInTheDocument()
  })

  it('renders unmatched medicines limitation note', () => {
    const mockUnmatchedResult: CheckResponse = {
      entered: ['Metformin', 'Azithromicin'],
      matched: ['Metformin'],
      unmatched: ['Azithromicin'],
      regimen: {
        overall_severity: null,
        pairs: [],
      },
      subset_certificate: null,
      combination_signal: null,
    }

    render(<InteractionResults result={mockUnmatchedResult} />)

    expect(screen.getByText('Incomplete Check')).toBeInTheDocument()
    expect(
      screen.getByText(/1 medicine could not be checked:/i)
    ).toBeInTheDocument()
    expect(screen.getByText('Azithromicin')).toBeInTheDocument()
  })

  it('renders pair-by-pair review immediately for every evaluated pair', () => {
    const mockResult: CheckResponse = {
      entered: ['Metformin', 'Warfarin', 'Aspirin'],
      matched: ['Metformin', 'Warfarin', 'Aspirin'],
      unmatched: [],
      regimen: {
        overall_severity: 'Major',
        pairs: [
          { drug_a: 'Warfarin', drug_b: 'Aspirin', severity: 'Major', confidence: 0.91 },
          { drug_a: 'Metformin', drug_b: 'Warfarin', severity: 'Moderate', confidence: 0.77 },
        ],
      },
      subset_certificate: null,
      combination_signal: null,
    }

    render(<InteractionResults result={mockResult} />)

    expect(screen.getByRole('heading', { name: /Pair-by-Pair Interaction Review/i })).toBeInTheDocument()
    expect(screen.getByText(/2 pairs evaluated/i)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /Warfarin \+ Aspirin/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /Metformin \+ Warfarin/i })).toBeInTheDocument()
    expect(
      screen.getAllByText(/No separate knowledge-graph mechanism was found/i).length
    ).toBeGreaterThanOrEqual(1)
  })

  it('renders explanation inline for each explained pair', () => {
    const mockResultWithExplanation: CheckResponse = {
      entered: ['Metformin', 'Furosemide'],
      matched: ['Metformin', 'Furosemide'],
      unmatched: [],
      regimen: {
        overall_severity: 'Moderate',
        pairs: [
          {
            drug_a: 'Metformin',
            drug_b: 'Furosemide',
            severity: 'Moderate',
            confidence: 0.963,
            explanation: {
              has_explanation: true,
              primary_reason: {
                type: 'side_effect',
                title: 'Shared adverse-effect evidence',
                plain_text:
                  'Both medicines are linked to overlapping effects (Abdominal bloating, Epigastric discomfort, Lightheadedness), so combining them may increase that risk.',
                evidence: ['Abdominal bloating', 'Epigastric discomfort', 'Lightheadedness'],
              },
              supporting_evidence: [],
              coverage: { drug_a_has_kg_data: true, drug_b_has_kg_data: true },
              caveat: 'This is knowledge-graph evidence, not a confirmed patient-specific mechanism.',
            },
          },
        ],
      },
      subset_certificate: null,
      combination_signal: null,
    }

    render(<InteractionResults result={mockResultWithExplanation} />)

    expect(screen.getByRole('heading', { name: /Pair-by-Pair Interaction Review/i })).toBeInTheDocument()
    expect(screen.getByText('Why this may be risky')).toBeInTheDocument()
    expect(
      screen.getByText(/Both medicines are linked to overlapping effects/i)
    ).toBeInTheDocument()
    expect(
      screen.getAllByText(/Abdominal bloating, Epigastric discomfort, Lightheadedness/i).length
    ).toBeGreaterThanOrEqual(1)
  })

  it('triggers onReset when button clicked', () => {
    const onReset = vi.fn()
    const mockResult: CheckResponse = {
      entered: ['Metformin', 'Warfarin'],
      matched: ['Metformin', 'Warfarin'],
      unmatched: [],
      regimen: {
        overall_severity: 'Moderate',
        pairs: [
          { drug_a: 'Metformin', drug_b: 'Warfarin', severity: 'Moderate', confidence: 0.75 },
        ],
      },
      subset_certificate: null,
      combination_signal: null,
    }

    render(<InteractionResults result={mockResult} onReset={onReset} />)

    const resetBtn = screen.getByRole('button', { name: /check another regimen/i })
    fireEvent.click(resetBtn)
    expect(onReset).toHaveBeenCalledTimes(1)
  })
})
