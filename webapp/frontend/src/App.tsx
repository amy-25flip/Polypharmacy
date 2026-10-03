import { useState, useEffect } from 'react'
import { Header } from './components/Header'
import { TransparencyPage } from './components/TransparencyPage'
import { PatientPrescriptionWorkflow } from './components/PatientPrescriptionWorkflow'
import type { WorkflowMode } from './components/PatientPrescriptionWorkflow'
import { checkHealth } from './api/client'
import { BarChart3, ClipboardList, Stethoscope } from 'lucide-react'
import type { KeyboardEvent } from 'react'

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
  // Two independent workflows: doctors pick whichever suits the visit. Each keeps its own
  // session while hidden (switching tabs must never discard work); the diagnosis tab is
  // mounted the first time it is opened.
  const [tab, setTab] = useState<WorkflowMode>('prescription')
  const [diagnosisMounted, setDiagnosisMounted] = useState(false)
  const selectTab = (next: WorkflowMode) => {
    if (next === 'diagnosis') setDiagnosisMounted(true)
    setTab(next)
  }
  const onTabKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    const order: WorkflowMode[] = ['prescription', 'diagnosis']
    let next: WorkflowMode | null = null
    if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') next = order[(order.indexOf(tab) + 1) % order.length]
    else if (event.key === 'Home') next = order[0]
    else if (event.key === 'End') next = order[order.length - 1]
    if (!next) return
    event.preventDefault()
    selectTab(next)
    document.getElementById(`tab-${next}`)?.focus()
  }

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

            <div role="tablist" aria-label="Choose a workflow" className="print:hidden grid gap-2 sm:grid-cols-2">
              {([
                ['prescription', 'Prescriptions & scan', 'Enter medicines from prescriptions, a photo, or by name', ClipboardList],
                ['diagnosis', 'Plan by diagnosis', 'Pick each diagnosis, then its medicines', Stethoscope],
              ] as const).map(([key, label, hint, Icon]) => {
                const selected = tab === key
                return (
                  <button
                    key={key}
                    id={`tab-${key}`}
                    type="button"
                    role="tab"
                    aria-selected={selected}
                    aria-controls={`panel-${key}`}
                    tabIndex={selected ? 0 : -1}
                    onClick={() => selectTab(key)}
                    onKeyDown={onTabKeyDown}
                    className={`min-w-0 rounded-xl border-2 px-4 py-3 text-left transition-colors ${selected ? 'border-blue-700 bg-white shadow-sm' : 'border-slate-200 bg-slate-50 hover:bg-white'}`}
                  >
                    <span className={`flex items-center gap-2 text-sm font-bold ${selected ? 'text-blue-800' : 'text-slate-700'}`}>
                      <Icon className="h-4 w-4 shrink-0" />
                      <span className="break-words">{label}</span>
                      {key === 'diagnosis' && <span className="rounded-full bg-purple-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-purple-800">New</span>}
                    </span>
                    <span className="mt-0.5 block break-words text-xs text-slate-500">{hint}</span>
                  </button>
                )
              })}
            </div>

            <div role="tabpanel" id="panel-prescription" aria-labelledby="tab-prescription" hidden={tab !== 'prescription'}>
              <PatientPrescriptionWorkflow mode="prescription" />
            </div>
            {diagnosisMounted && (
              <div role="tabpanel" id="panel-diagnosis" aria-labelledby="tab-diagnosis" hidden={tab !== 'diagnosis'}>
                <PatientPrescriptionWorkflow mode="diagnosis" />
              </div>
            )}

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
