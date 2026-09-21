import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { PairExplanationView, formatEvidenceType } from '../components/PairExplanationView'
import type { PairExplanation } from '../api/client'

describe('PairExplanationView Component', () => {
  it('formats evidence types correctly', () => {
    expect(formatEvidenceType('class')).toBe('Shared drug class')
    expect(formatEvidenceType('side_effect')).toBe('Shared adverse-effect')
    expect(formatEvidenceType('gene')).toBe('Shared biological target')
    expect(formatEvidenceType('structural_resemblance')).toBe('Structural similarity')
    expect(formatEvidenceType('custom_type')).toBe('Custom_type')
  })

  it('renders primary reason, evidence list, supporting evidence, and caveat when has_explanation is true', () => {
    const mockExplanation: PairExplanation = {
      has_explanation: true,
      primary_reason: {
        type: 'side_effect',
        title: 'Shared adverse-effect evidence',
        plain_text:
          'Both medicines are linked to overlapping effects (Abdominal bloating, Epigastric discomfort, Lightheadedness), so combining them may increase that risk.',
        evidence: ['Abdominal bloating', 'Epigastric discomfort', 'Lightheadedness'],
      },
      supporting_evidence: [
        { type: 'class', items: ['Antithrombotic agent'] },
        { type: 'gene', items: ['CYP3A5', 'CYP2C9'] },
      ],
      coverage: { drug_a_has_kg_data: true, drug_b_has_kg_data: true },
      caveat: 'This is knowledge-graph evidence, not a confirmed patient-specific mechanism.',
    }

    render(<PairExplanationView explanation={mockExplanation} />)

    // Heading
    expect(screen.getByText('Why this may be risky')).toBeInTheDocument()

    // Plain text main sentence
    expect(
      screen.getByText(
        'Both medicines are linked to overlapping effects (Abdominal bloating, Epigastric discomfort, Lightheadedness), so combining them may increase that risk.'
      )
    ).toBeInTheDocument()

    // Evidence
    expect(screen.getByText(/Shared adverse-effect evidence:/i)).toBeInTheDocument()
    expect(
      screen.getAllByText(/Abdominal bloating, Epigastric discomfort, Lightheadedness/i).length
    ).toBeGreaterThanOrEqual(1)

    // Additional evidence
    expect(screen.getByText('Additional evidence')).toBeInTheDocument()
    expect(screen.getByText(/Shared drug class:/i)).toBeInTheDocument()
    expect(screen.getByText('Antithrombotic agent')).toBeInTheDocument()
    expect(screen.getByText(/Shared biological target:/i)).toBeInTheDocument()
    expect(screen.getByText('CYP3A5, CYP2C9')).toBeInTheDocument()

    // Caveat
    expect(
      screen.getByText(
        'This is knowledge-graph evidence, not a confirmed patient-specific mechanism.'
      )
    ).toBeInTheDocument()

    // Ensure forbidden certainty words do not appear
    const content = document.body.textContent || ''
    expect(content).not.toMatch(/\bcauses\b/i)
    expect(content).not.toMatch(/\bproves\b/i)
    expect(content).not.toMatch(/\bconfirmed patient mechanism\b/i)
    expect(content).not.toMatch(/AI explanation/i)
    expect(content).not.toMatch(/model reasoning/i)
  })

  it('renders calm message when has_explanation is false', () => {
    const mockEmptyExplanation: PairExplanation = {
      has_explanation: false,
      primary_reason: null,
      supporting_evidence: [],
      coverage: { drug_a_has_kg_data: true, drug_b_has_kg_data: false },
      caveat: 'This is knowledge-graph evidence, not a confirmed patient-specific mechanism.',
    }

    render(<PairExplanationView explanation={mockEmptyExplanation} />)

    expect(screen.getByText('Why this may be risky')).toBeInTheDocument()
    expect(
      screen.getByText(
        /No specific shared-mechanism evidence was found in the current knowledge base for this pair\. This may reflect incomplete data coverage rather than an absence of risk\./i
      )
    ).toBeInTheDocument()
    expect(
      screen.getByText(/Limited reference data available for one of these medicines\./i)
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        'This is knowledge-graph evidence, not a confirmed patient-specific mechanism.'
      )
    ).toBeInTheDocument()
  })
})
