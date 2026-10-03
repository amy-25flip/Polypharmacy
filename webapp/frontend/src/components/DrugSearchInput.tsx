import React, { useState, useEffect, useId, useRef } from 'react'
import { Search, PlusCircle, AlertCircle, Loader2, RefreshCw } from 'lucide-react'
import { searchDrugs } from '../api/client'
import type { DrugSearchResult } from '../api/client'
import { TIMING_OPTIONS } from './MedicationTimingTable'
import type { MedicationTiming } from './MedicationTimingTable'

interface DrugSearchInputProps {
  onAddDrug: (drugName: string, timing: MedicationTiming, isUnmatched?: boolean) => void
  existingDrugs: string[]
}

export const DrugSearchInput: React.FC<DrugSearchInputProps> = ({
  onAddDrug,
  existingDrugs,
}) => {
  const [query, setQuery] = useState('')
  const [suggestions, setSuggestions] = useState<DrugSearchResult[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isOpen, setIsOpen] = useState(false)
  const [selectedIndex, setSelectedIndex] = useState<number>(-1)
  const [feedback, setFeedback] = useState<string | null>(null)
  const [searchError, setSearchError] = useState<string | null>(null)
  const [retryTick, setRetryTick] = useState(0)
  // Persists across adds so entering several same-schedule medicines in a row
  // (a common real prescription pattern) doesn't require resetting it each time.
  const [timing, setTiming] = useState<MedicationTiming>('Unspecified')

  const inputRef = useRef<HTMLInputElement>(null)
  const instanceId = useId()
  const dropdownRef = useRef<HTMLDivElement>(null)
  // Guards against a slower, superseded search response landing after a newer one -
  // e.g. typing quickly could otherwise briefly show suggestions or an error for a
  // query the user has already changed.
  const searchRequestIdRef = useRef(0)

  // Debounced search logic (200ms)
  useEffect(() => {
    const trimmed = query.trim()
    if (trimmed.length < 2) {
      searchRequestIdRef.current += 1
      setSuggestions([])
      setIsLoading(false)
      setIsOpen(false)
      setSelectedIndex(-1)
      setSearchError(null)
      return
    }

    setIsLoading(true)
    setSearchError(null)
    const requestId = ++searchRequestIdRef.current
    const controller = new AbortController()

    const timer = setTimeout(async () => {
      try {
        const results = await searchDrugs(trimmed, controller.signal)
        if (searchRequestIdRef.current !== requestId) return
        setSuggestions(results)
        setSearchError(null)
        setIsOpen(true)
        setSelectedIndex(-1)
      } catch (err: unknown) {
        if (searchRequestIdRef.current !== requestId) return
        if (err instanceof Error && err.name !== 'AbortError') {
          console.error('Error fetching drug suggestions:', err)
          setSuggestions([])
          setSearchError('Search failed - check your connection.')
          setIsOpen(true)
        }
      } finally {
        if (searchRequestIdRef.current === requestId) setIsLoading(false)
      }
    }, 200)

    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [query, retryTick])

  // Handle outside click to close dropdown
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node) &&
        inputRef.current &&
        !inputRef.current.contains(e.target as Node)
      ) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleSelect = (drugName: string, isUnmatched = false) => {
    const trimmed = drugName.trim()
    if (!trimmed) return

    // Prevent duplicate entries
    const isDuplicate = existingDrugs.some(
      (d) => d.toLowerCase() === trimmed.toLowerCase()
    )

    if (isDuplicate) {
      setFeedback(`"${trimmed}" is already added to the patient's list.`)
      setTimeout(() => setFeedback(null), 3000)
    } else {
      onAddDrug(trimmed, timing, isUnmatched)
      setFeedback(null)
    }

    setQuery('')
    setSuggestions([])
    setIsOpen(false)
    setSelectedIndex(-1)
    inputRef.current?.focus()
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!isOpen) return

    const totalOptions = suggestions.length + (suggestions.length === 0 && query.trim().length >= 2 ? 1 : 0)

    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIndex((prev) => (prev < totalOptions - 1 ? prev + 1 : 0))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIndex((prev) => (prev > 0 ? prev - 1 : totalOptions - 1))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (selectedIndex >= 0 && selectedIndex < suggestions.length) {
        handleSelect(suggestions[selectedIndex].name)
      } else if (suggestions.length === 0 && query.trim().length >= 2) {
        // Pick fallback unmatched option
        handleSelect(query.trim(), true)
      } else if (suggestions.length > 0 && selectedIndex === -1) {
        // Pick top suggestion on enter
        handleSelect(suggestions[0].name)
      }
    } else if (e.key === 'Escape') {
      setIsOpen(false)
      setSelectedIndex(-1)
    }
  }

  const trimmedQuery = query.trim()
  const showUnmatchedOption = isOpen && !isLoading && !searchError && trimmedQuery.length >= 2 && suggestions.length === 0
  const activeOptionId =
    selectedIndex < 0 ? undefined : selectedIndex < suggestions.length ? `${instanceId}-drug-option-${selectedIndex}` : `${instanceId}-drug-option-unmatched`
  const statusMessage = isLoading
    ? 'Searching…'
    : searchError
    ? searchError
    : isOpen && suggestions.length > 0
    ? `${suggestions.length} matching medicine${suggestions.length === 1 ? '' : 's'} found`
    : isOpen && showUnmatchedOption
    ? 'No database match found for this medicine'
    : ''

  return (
    <div className="relative w-full">
      <div className="flex items-end gap-3 mb-1.5">
        <label
          htmlFor={`${instanceId}-drug-search-input`}
          className="block text-sm font-semibold text-slate-800"
        >
          Add medicine
        </label>
      </div>

      <div className="flex flex-col sm:flex-row gap-2">
        <div className="relative flex-1">
          <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
            {isLoading ? (
              <Loader2 className="h-5 w-5 animate-spin text-blue-600" />
            ) : (
              <Search className="h-5 w-5" />
            )}
          </div>

          <input
            id={`${instanceId}-drug-search-input`}
            ref={inputRef}
            type="text"
            role="combobox"
            aria-expanded={isOpen && (suggestions.length > 0 || showUnmatchedOption || !!searchError)}
            aria-controls={`${instanceId}-drug-search-listbox`}
            aria-autocomplete="list"
            aria-activedescendant={activeOptionId}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => {
              if (trimmedQuery.length >= 2) setIsOpen(true)
            }}
            onKeyDown={handleKeyDown}
            placeholder="Type medicine name (e.g. Metformin, Warfarin, Lisinopril)..."
            autoComplete="off"
            className="w-full pl-11 pr-4 py-3 bg-white border-2 border-slate-300 rounded-lg text-slate-900 text-base placeholder-slate-400 focus:border-blue-600 focus:ring-2 focus:ring-blue-100 transition-colors shadow-xs"
          />
        </div>

        <label className="sm:w-40 shrink-0 text-xs font-semibold text-slate-600">
          <span className="sm:hidden">Timing for next medicine</span>
          <select
            aria-label="Timing for the next medicine you add"
            value={timing}
            onChange={(e) => setTiming(e.target.value as MedicationTiming)}
            className="mt-1 sm:mt-0 w-full h-full rounded-lg border-2 border-slate-300 px-2.5 py-3 text-sm font-medium text-slate-800 focus:border-blue-600 focus:ring-2 focus:ring-blue-100"
          >
            {TIMING_OPTIONS.map((option) => <option key={option}>{option}</option>)}
          </select>
        </label>
      </div>
      <p className="mt-1 text-[11px] text-slate-500">
        Sets the timing applied to the next medicine you add - change per-medicine anytime below.
      </p>

      {feedback && (
        <p className="mt-1.5 text-xs font-medium text-amber-700 flex items-center gap-1.5">
          <AlertCircle className="h-3.5 w-3.5 shrink-0" />
          {feedback}
        </p>
      )}

      {/* Visually-hidden status announcements for screen-reader users - the visual
          dropdown alone doesn't announce result counts, errors, or duplicate feedback. */}
      <div aria-live="polite" className="sr-only">
        {statusMessage}
        {feedback}
      </div>

      {/* Autocomplete Dropdown */}
      {isOpen && (suggestions.length > 0 || showUnmatchedOption || searchError) && (
        <div
          ref={dropdownRef}
          id={`${instanceId}-drug-search-listbox`}
          role="listbox"
          className="absolute z-30 mt-1.5 w-full bg-white border border-slate-200 rounded-lg shadow-lg overflow-hidden max-h-72 overflow-y-auto"
        >
          {searchError && (
            <div className="p-3 flex items-start gap-2.5 bg-rose-50">
              <AlertCircle className="h-4 w-4 text-rose-600 shrink-0 mt-0.5" />
              <div className="text-sm flex-1">
                <p className="font-semibold text-rose-900">{searchError}</p>
                <p className="text-xs mt-0.5 text-rose-700">This is a connection problem, not a database result - it does not mean the medicine is unknown.</p>
                <button
                  type="button"
                  onClick={() => setRetryTick((t) => t + 1)}
                  className="mt-2 inline-flex items-center gap-1.5 text-xs font-bold text-rose-800 hover:text-rose-950"
                >
                  <RefreshCw className="h-3.5 w-3.5" /> Retry search
                </button>
              </div>
            </div>
          )}

          {suggestions.length > 0 && (
            <div className="py-1">
              <div className="px-3 py-1.5 text-[11px] font-bold uppercase tracking-wider text-slate-400 bg-slate-50 border-b border-slate-100">
                Matched database medicines
              </div>
              {suggestions.map((drug, index) => {
                const isSelected = index === selectedIndex
                return (
                  <button
                    key={`${drug.name}-${drug.matched_via_brand || drug.matched_via_synonym || 'direct'}`}
                    id={`${instanceId}-drug-option-${index}`}
                    type="button"
                    role="option"
                    aria-selected={isSelected}
                    onClick={() => handleSelect(drug.name)}
                    onMouseEnter={() => setSelectedIndex(index)}
                    className={`w-full text-left px-3.5 py-2.5 text-sm font-medium flex items-center justify-between transition-colors ${
                      isSelected
                        ? 'bg-blue-600 text-white'
                        : 'text-slate-800 hover:bg-slate-100'
                    }`}
                  >
                    <span className="min-w-0">
                      <span className="block">{drug.name}</span>
                      {drug.matched_via_synonym && (
                        <span className={`block text-xs font-normal ${isSelected ? 'text-blue-100' : 'text-slate-500'}`}>
                          also known as: {drug.matched_via_synonym}
                        </span>
                      )}
                      {drug.matched_via_brand && (
                        <span className={`block text-xs font-normal ${isSelected ? 'text-blue-100' : 'text-slate-500'}`}>
                          brand: {drug.matched_via_brand}
                        </span>
                      )}
                    </span>
                    <PlusCircle
                      className={`h-4 w-4 ${
                        isSelected ? 'text-white' : 'text-slate-400'
                      }`}
                    />
                  </button>
                )
              })}
            </div>
          )}

          {/* Non-blocking Unmatched Option */}
          {showUnmatchedOption && (
            <div className="p-2">
              <button
                id={`${instanceId}-drug-option-unmatched`}
                type="button"
                role="option"
                aria-selected={selectedIndex === 0}
                onClick={() => handleSelect(trimmedQuery, true)}
                className={`w-full text-left p-3 rounded-md border border-dashed text-sm flex items-start gap-2.5 transition-colors ${
                  selectedIndex === 0
                    ? 'bg-amber-50 border-amber-400 text-amber-900'
                    : 'bg-slate-50 border-slate-300 text-slate-700 hover:bg-amber-50/50 hover:border-amber-300'
                }`}
              >
                <AlertCircle className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
                <div>
                  <div className="font-semibold text-slate-900">
                    No match found in database
                  </div>
                  <div className="text-xs mt-0.5 text-slate-600">
                    Add <strong className="font-bold text-slate-800">"{trimmedQuery}"</strong> anyway? (Will be marked as unverified/unmatched)
                  </div>
                </div>
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
