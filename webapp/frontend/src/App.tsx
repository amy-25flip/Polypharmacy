import { useState, useEffect } from 'react'
import { Header } from './components/Header'
import { DrugSearchInput } from './components/DrugSearchInput'
import { DrugChipList } from './components/DrugChipList'
import type { DrugItem } from './components/DrugChipList'
import { InteractionResults } from './components/InteractionResults'
import { TransparencyPage } from './components/TransparencyPage'
import { checkHealth, checkInteractions } from './api/client'
import type { CheckResponse } from './api/client'
import { ShieldCheck, Loader2, RefreshCw, BarChart3 } from 'lucide-react'

const TRANSPARENCY_PATH = '/model-card'

export function App() {
  const [drugs, setDrugs] = useState<DrugItem[]>([])
  const [knownDrugsCount, setKnownDrugsCount] = useState<number | null>(null)
  const [isChecking, setIsChecking] = useState(false)
  const [checkError, setCheckError] = useState<string | null>(null)
  const [result, setResult] = useState<CheckResponse | null>(null)
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

  const handleAddDrug = (drugName: string, isUnmatched = false) => {
    const newItem: DrugItem = {
      id: `${Date.now()}-${Math.random().toString(36).substring(2, 7)}`,
      name: drugName,
      isUnmatched,
    }
    setDrugs((prev) => [...prev, newItem])
    // Clear previous error if any
    setCheckError(null)
  }

  const handleRemoveDrug = (id: string) => {
    setDrugs((prev) => prev.filter((d) => d.id !== id))
  }

  const handleClearAll = () => {
    setDrugs([])
    setResult(null)
    setCheckError(null)
  }

  const handleCheck = async () => {
    if (drugs.length < 2) return

    setIsChecking(true)
    setCheckError(null)

    try {
      const drugNames = drugs.map((d) => d.name)
      const data = await checkInteractions(drugNames)
      setResult(data)
    } catch (err: unknown) {
      console.error('Interaction check failed:', err)
      setCheckError(
        'Unable to complete interaction screening. Please verify backend connection and try again.'
      )
    } finally {
      setIsChecking(false)
    }
  }

  const canCheck = drugs.length >= 2

  if (page === 'transparency') {
    return <TransparencyPage onBack={closeTransparency} />
  }

  return (
    <div className="min-h-screen bg-slate-100/70 text-slate-900 py-6 sm:py-10 px-4 sm:px-6 lg:px-8">
      <div className="max-w-3xl mx-auto space-y-6">
        {/* Header with safety line & system status */}
        <Header knownDrugsCount={knownDrugsCount} />

        {/* Main Card: Medication Entry & Controls */}
        <main className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 sm:p-7 space-y-6">
          {/* Section Heading */}
          <div className="border-b border-slate-100 pb-3">
            <h2 className="text-lg font-bold text-slate-900">
              Patient Medication Entry
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Enter prescribed, over-the-counter, or co-administered drugs to evaluate potential interactions.
            </p>
          </div>

          {/* Autocomplete Input */}
          <DrugSearchInput
            onAddDrug={handleAddDrug}
            existingDrugs={drugs.map((d) => d.name)}
          />

          {/* Added Medicine Chips */}
          <DrugChipList
            drugs={drugs}
            onRemoveDrug={handleRemoveDrug}
            onClearAll={handleClearAll}
          />

          {/* Primary Action Button */}
          <div className="pt-2">
            <button
              type="button"
              disabled={!canCheck || isChecking}
              onClick={handleCheck}
              className={`w-full py-3.5 px-6 rounded-lg font-bold text-base transition-all flex items-center justify-center gap-2 shadow-xs ${
                canCheck && !isChecking
                  ? 'bg-blue-700 hover:bg-blue-800 text-white cursor-pointer hover:shadow-sm active:scale-[0.99]'
                  : 'bg-slate-200 text-slate-400 border border-slate-300 cursor-not-allowed'
              }`}
            >
              {isChecking ? (
                <>
                  <Loader2 className="h-5 w-5 animate-spin" />
                  <span>Screening regimen interactions...</span>
                </>
              ) : (
                <>
                  <ShieldCheck className="h-5 w-5" />
                  <span>
                    Check interactions{' '}
                    {drugs.length >= 2 ? `(${drugs.length} medicines)` : '(Add at least 2)'}
                  </span>
                </>
              )}
            </button>
            {!canCheck && drugs.length > 0 && (
              <p className="text-xs text-center text-slate-500 mt-2 font-medium">
                Add at least 1 more medicine to evaluate pairwise interactions
              </p>
            )}
          </div>

          {/* Check Error Message */}
          {checkError && (
            <div className="rounded-lg bg-rose-50 border border-rose-200 p-4 text-rose-900 text-sm flex items-start gap-2.5">
              <RefreshCw className="h-4 w-4 shrink-0 mt-0.5 text-rose-600" />
              <div>
                <p className="font-semibold">Screening error</p>
                <p className="text-xs mt-0.5 text-rose-800">{checkError}</p>
              </div>
            </div>
          )}
        </main>

        {/* Results Panel */}
        {result && (
          <section aria-label="Interaction Screening Results">
            <InteractionResults
              result={result}
              onReset={handleClearAll}
            />
          </section>
        )}

        {/* Quiet Footer */}
        <footer className="text-center text-xs text-slate-400 pt-4 space-y-2">
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
