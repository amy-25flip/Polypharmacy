import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Header } from '../components/Header'

describe('Header Component', () => {
  it('renders title and permanent clinical safety notice', () => {
    render(<Header knownDrugsCount={1902} />)

    expect(screen.getByText('PolyGuard')).toBeInTheDocument()
    expect(
      screen.getByText(
        /PolyGuard is a clinical decision-support tool\. It helps flag possible interaction risks and does not replace clinical judgment, prescribing guidelines, or pharmacist review\./i
      )
    ).toBeInTheDocument()
    expect(screen.getByText(/1,902 indexed medicines/i)).toBeInTheDocument()
  })

  it('renders connecting state when knownDrugsCount is null', () => {
    render(<Header knownDrugsCount={null} />)
    expect(screen.getByText(/Connecting to database\.\.\./i)).toBeInTheDocument()
  })
})
