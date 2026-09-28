import { useState, useEffect } from 'react'
import { Header } from './components/Header'
import { TransparencyPage } from './components/TransparencyPage'
import { PatientPrescriptionWorkflow } from './components/PatientPrescriptionWorkflow'
import { checkHealth } from './api/client'
import { BarChart3 } from 'lucide-react'

const TRANSPARENCY_PATH = '/model-card'

export function App() {
  const [knownDrugsCount, setKnownDrugsCount] = useState<number | null>(null)
  const [healthStatus, setHealthStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [page, setPage] = useState<'checker' | 'transparency'>(
    window.location.pathname === TRANSPARENCY_PATH ? 'transparency' : 'checker'
  )
  // The checker is a stateless, session-only workflow with no persistence - unmounting
  // it (e.g. by navigating to the transparency page) would silently wipe a doctor's
  // in-progress patient session. Keep it mounted at all times and only toggle
  // visibility; lazy-mount the transparency page once, on first visit, then do the same.
  const [transparencyMounted, setTransparencyMounted] = useState(page === 'transparency')

  useEffect(() => {
    const onPopState = () => {
      const next = window.location.pathname === TRANSPARENCY_PATH ? 'transparency' : 'checker'
      if (next === 'transparency') setTransparencyMounted(true)
      setPage(next)
    }
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  const openTransparency = () => {
    window.history.pushState({}, '', TRANSPARENCY_PATH)
    setTransparencyMounted(true)
    setPage('transparency')
  }

  const closeTransparency = () => {
    window.history.pushState({}, '', '/')
    setPage('checker')
  }

  // Fetch initial health status
  useEffect(() => {
    checkHealth()
      .then((data) => {
        setKnownDrugsCount(data.known_drugs)
        setHealthStatus('ready')
      })
      .catch((err) => {
        console.warn('Backend connection warning:', err)
        setHealthStatus('error')
      })
  }, [])

  return (
    <>
      <div className={page === 'transparency' ? 'hidden' : ''}>
        <div className="min-h-screen bg-slate-100/70 text-slate-900 py-6 sm:py-10 px-4 sm:px-6 lg:px-8">
          <div className="max-w-3xl mx-auto space-y-6">
            {/* Header with safety line & system status */}
            <div className="print:hidden">
              <Header knownDrugsCount={knownDrugsCount} healthStatus={healthStatus} />
            </div>

            <PatientPrescriptionWorkflow />

            {/* Quiet Footer */}
            <footer className="print:hidden text-center text-xs text-slate-400 pt-4 space-y-2">
              <button
                type="button"
                onClick={openTransparency}
                className="inline-flex items-center gap-1.5 text-slate-500 hover:text-slate-700 font-medium transition-colors"
              >
                <BarChart3 className="h-3.5 w-3.5" />
                Model transparency &amp; real evaluation numbers
              </button>
              <p>PolyGuard v1.0 • Clinical Drug Interaction Screening System</p>
            </footer>
          </div>
        </div>
      </div>
      {transparencyMounted && (
        <div className={page === 'checker' ? 'hidden' : ''}>
          <TransparencyPage onBack={closeTransparency} />
        </div>
      )}
    </>
  )
}

export default App
