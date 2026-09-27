import { useState, useEffect } from 'react'
import { Header } from './components/Header'
import { TransparencyPage } from './components/TransparencyPage'
import { PatientPrescriptionWorkflow } from './components/PatientPrescriptionWorkflow'
import { checkHealth } from './api/client'
import { BarChart3 } from 'lucide-react'

const TRANSPARENCY_PATH = '/model-card'

export function App() {
  const [knownDrugsCount, setKnownDrugsCount] = useState<number | null>(null)
  const [page, setPage] = useState<'checker' | 'transparency'>(
    window.location.pathname === TRANSPARENCY_PATH ? 'transparency' : 'checker'
  )

  useEffect(() => {
    const onPopState = () => {
      setPage(window.location.pathname === TRANSPARENCY_PATH ? 'transparency' : 'checker')
    }
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  const openTransparency = () => {
    window.history.pushState({}, '', TRANSPARENCY_PATH)
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
      })
      .catch((err) => {
        console.warn('Backend connection warning:', err)
        setKnownDrugsCount(null)
      })
  }, [])

  if (page === 'transparency') {
    return <TransparencyPage onBack={closeTransparency} />
  }

  return (
    <div className="min-h-screen bg-slate-100/70 text-slate-900 py-6 sm:py-10 px-4 sm:px-6 lg:px-8">
      <div className="max-w-3xl mx-auto space-y-6">
        {/* Header with safety line & system status */}
        <div className="print:hidden">
          <Header knownDrugsCount={knownDrugsCount} />
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
  )
}

export default App
