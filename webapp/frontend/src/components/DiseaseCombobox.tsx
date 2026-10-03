import { useEffect, useId, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'
import { Loader2, RefreshCw, Search } from 'lucide-react'
import { searchDiseases } from '../api/client'
import type { Disease } from '../api/client'

interface Props {
  existingIds: string[]
  onSelect: (disease: Disease) => void
  // Only move focus into the box when the user just asked for it (clicking "Add a diagnosis").
  // Stealing focus on mount broke keyboard tab navigation: arrowing to the diagnosis tab
  // would jump into the search field instead of staying on the tab.
  autoFocus?: boolean
}

export function DiseaseCombobox({ existingIds, onSelect, autoFocus = false }: Props) {
  const id = useId()
  const inputRef = useRef<HTMLInputElement>(null)
  const rootRef = useRef<HTMLDivElement>(null)
  const searchRequestIdRef = useRef(0)
  // After a selection the query is cleared, which re-runs the search; without this the
  // late response would reopen the list the doctor just closed by choosing a diagnosis.
  const suppressOpenRef = useRef(false)
  const [query, setQuery] = useState('')
  const [focused, setFocused] = useState(false)
  const [open, setOpen] = useState(false)
  const [results, setResults] = useState<Disease[]>([])
  const [active, setActive] = useState(-1)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(false)
  const [retry, setRetry] = useState(0)
  const [message, setMessage] = useState('')

  useEffect(() => { if (autoFocus) inputRef.current?.focus() }, [autoFocus])

  useEffect(() => {
    if (!focused) return
    const requestId = ++searchRequestIdRef.current
    const controller = new AbortController()
    setLoading(true)
    setError(false)
    setResults([])
    setActive(-1)
    const timer = window.setTimeout(async () => {
      try {
        const diseases = await searchDiseases(query, controller.signal)
        if (searchRequestIdRef.current !== requestId) return
        setResults(diseases)
        if (!suppressOpenRef.current) setOpen(true)
      } catch (caught) {
        if (searchRequestIdRef.current !== requestId || (caught instanceof Error && caught.name === 'AbortError')) return
        setError(true)
        setOpen(true)
      } finally {
        if (searchRequestIdRef.current === requestId) setLoading(false)
      }
    }, query ? 200 : 0)
    return () => { window.clearTimeout(timer); controller.abort() }
  }, [query, focused, retry])

  useEffect(() => {
    const outside = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', outside)
    return () => document.removeEventListener('mousedown', outside)
  }, [])

  const select = (disease: Disease) => {
    if (existingIds.includes(disease.id)) {
      setMessage(`${disease.name} is already in this plan.`)
    } else {
      onSelect(disease)
      setMessage(`${disease.name} added to this plan.`)
    }
    setQuery('')
    setActive(-1)
    inputRef.current?.focus()
    suppressOpenRef.current = true
    setOpen(false)
  }

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (!open) return
    if (event.key === 'ArrowDown' && results.length) {
      event.preventDefault()
      setActive((value) => (value + 1) % results.length)
    } else if (event.key === 'ArrowUp' && results.length) {
      event.preventDefault()
      setActive((value) => value <= 0 ? results.length - 1 : value - 1)
    } else if (event.key === 'Enter' && results.length) {
      event.preventDefault()
      select(results[active < 0 ? 0 : active])
    } else if (event.key === 'Escape') {
      setOpen(false)
      setActive(-1)
    }
  }

  return (
    <div ref={rootRef} className="relative w-full max-w-md">
      <label htmlFor={`${id}-input`} className="block text-sm font-semibold text-slate-800">Search diagnoses</label>
      <div className="relative mt-1">
        {loading ? <Loader2 className="pointer-events-none absolute left-3 top-3 h-4 w-4 animate-spin text-blue-700" /> : <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-slate-400" />}
        <input
          id={`${id}-input`}
          ref={inputRef}
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={open && (results.length > 0 || error)}
          aria-controls={`${id}-list`}
          aria-activedescendant={open && active >= 0 ? `${id}-option-${active}` : undefined}
          value={query}
          onChange={(event) => { suppressOpenRef.current = false; setQuery(event.target.value); setFocused(true); setOpen(true); setMessage('') }}
          onFocus={() => { setFocused(true); if (!suppressOpenRef.current) setOpen(true) }}
          onClick={() => { suppressOpenRef.current = false; setOpen(true) }}
          onKeyDown={onKeyDown}
          placeholder="e.g. diabetes or kidney disease"
          autoComplete="off"
          className="w-full rounded-lg border-2 border-slate-300 bg-white py-2.5 pl-9 pr-3 text-sm text-slate-900"
        />
      </div>
      <div aria-live="polite" className="sr-only">{loading ? 'Searching diagnoses…' : error ? 'Diagnosis search failed.' : open ? `${results.length} diagnoses found.` : ''} {message}</div>
      {message && <p className="mt-1 text-xs font-medium text-amber-800">{message}</p>}
      {open && (results.length > 0 || error || (!loading && focused)) && (
        <div id={`${id}-list`} role="listbox" className="absolute z-30 mt-1 max-h-64 w-full overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-lg">
          {error ? (
            <div className="p-3 text-sm text-rose-900">
              <p className="font-semibold">Diagnosis search unavailable. This does not mean there are no diagnoses.</p>
              <button type="button" onClick={() => setRetry((value) => value + 1)} className="mt-2 inline-flex items-center gap-1 font-bold text-rose-800"><RefreshCw className="h-4 w-4" /> Retry diagnosis search</button>
            </div>
          ) : results.length ? results.map((disease, index) => (
            <button
              key={disease.id}
              id={`${id}-option-${index}`}
              role="option"
              aria-selected={index === active}
              type="button"
              onMouseEnter={() => setActive(index)}
              onClick={() => select(disease)}
              className={`block w-full px-3 py-2 text-left text-sm ${index === active ? 'bg-blue-700 text-white' : 'text-slate-800 hover:bg-blue-50'}`}
            >
              <span className="block break-words font-semibold">{disease.name}</span>
              <span className="block text-xs opacity-80">{disease.medicine_count} reference medicines{existingIds.includes(disease.id) ? ' · Already added' : ''}</span>
            </button>
          )) : <p className="p-3 text-sm text-slate-600">No matching diagnoses in the reference list.</p>}
        </div>
      )}
    </div>
  )
}
