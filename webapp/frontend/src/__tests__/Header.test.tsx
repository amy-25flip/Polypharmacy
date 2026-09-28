import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Header } from '../components/Header'

describe('Header Component', () => {
  it('renders title and permanent clinical safety notice', () => {
    render(<Header knownDrugsCount={1902} healthStatus="ready" />)

    expect(screen.getByText('PolyGuard')).toBeInTheDocument()
    expect(
      screen.getByText(
        /PolyGuard is a clinical decision-support tool\. It helps flag possible interaction risks and does not replace clinical judgment, prescribing guidelines, or pharmacist review\./i
      )
    ).toBeInTheDocument()
    expect(screen.getByText(/1,902 indexed medicines/i)).toBeInTheDocument()
  })

  it('renders connecting state while health check is loading', () => {
    render(<Header knownDrugsCount={null} healthStatus="loading" />)
    expect(screen.getByText(/Connecting to database\.\.\./i)).toBeInTheDocument()
  })

  it('renders a distinct error state when the health check fails', () => {
    render(<Header knownDrugsCount={null} healthStatus="error" />)
    expect(screen.getByText(/Backend unavailable/i)).toBeInTheDocument()
    expect(screen.queryByText(/Connecting to database\.\.\./i)).not.toBeInTheDocument()
  })
})
