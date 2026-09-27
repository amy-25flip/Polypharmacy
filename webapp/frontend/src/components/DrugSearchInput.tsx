import React, { useState, useEffect, useRef } from 'react'
import { Search, PlusCircle, AlertCircle, Loader2 } from 'lucide-react'
import { searchDrugs } from '../api/client'
import type { DrugSearchResult } from '../api/client'

interface DrugSearchInputProps {
  onAddDrug: (drugName: string, isUnmatched?: boolean) => void
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

  const inputRef = useRef<HTMLInputElement>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)

  // Debounced search logic (200ms)
  useEffect(() => {
    const trimmed = query.trim()
    if (trimmed.length < 2) {
      setSuggestions([])
      setIsLoading(false)
      setIsOpen(false)
      setSelectedIndex(-1)
      return
    }

    setIsLoading(true)
    const controller = new AbortController()

    const timer = setTimeout(async () => {
      try {
        const results = await searchDrugs(trimmed, controller.signal)
        setSuggestions(results)
        setIsOpen(true)
        setSelectedIndex(-1)
      } catch (err: unknown) {
        if (err instanceof Error && err.name !== 'AbortError') {
          console.error('Error fetching drug suggestions:', err)
          setSuggestions([])
        }
      } finally {
        setIsLoading(false)
      }
    }, 200)

    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [query])

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
      onAddDrug(trimmed, isUnmatched)
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
  const showUnmatchedOption = isOpen && !isLoading && trimmedQuery.length >= 2 && suggestions.length === 0

  return (
    <div className="relative w-full">
      <label
        htmlFor="drug-search-input"
        className="block text-sm font-semibold text-slate-800 mb-1.5"
      >
        Add medicine
      </label>

      <div className="relative">
        <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
          {isLoading ? (
            <Loader2 className="h-5 w-5 animate-spin text-blue-600" />
          ) : (
            <Search className="h-5 w-5" />
          )}
        </div>

        <input
          id="drug-search-input"
          ref={inputRef}
          type="text"
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

      {feedback && (
        <p className="mt-1.5 text-xs font-medium text-amber-700 flex items-center gap-1.5">
          <AlertCircle className="h-3.5 w-3.5 shrink-0" />
          {feedback}
        </p>
      )}

      {/* Autocomplete Dropdown */}
      {isOpen && (suggestions.length > 0 || showUnmatchedOption) && (
        <div
          ref={dropdownRef}
          role="listbox"
          className="absolute z-30 mt-1.5 w-full bg-white border border-slate-200 rounded-lg shadow-lg overflow-hidden max-h-72 overflow-y-auto"
        >
          {suggestions.length > 0 && (
            <div className="py-1">
              <div className="px-3 py-1.5 text-[11px] font-bold uppercase tracking-wider text-slate-400 bg-slate-50 border-b border-slate-100">
                Matched database medicines
              </div>
              {suggestions.map((drug, index) => {
                const isSelected = index === selectedIndex
                return (
                  <button
                    key={`${drug.name}-${drug.matched_via_brand || 'direct'}`}
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
