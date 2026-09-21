import React from 'react'
import { X, AlertCircle, Pill, Trash2 } from 'lucide-react'

export interface DrugItem {
  id: string
  name: string
  isUnmatched?: boolean
}

interface DrugChipListProps {
  drugs: DrugItem[]
  onRemoveDrug: (id: string) => void
  onClearAll: () => void
}

export const DrugChipList: React.FC<DrugChipListProps> = ({
  drugs,
  onRemoveDrug,
  onClearAll,
}) => {
  if (drugs.length === 0) {
    return (
      <div className="rounded-lg border-2 border-dashed border-slate-200 p-6 text-center text-slate-500">
        <Pill className="h-8 w-8 mx-auto text-slate-300 mb-2" />
        <p className="text-sm font-medium text-slate-600">No medicines added yet</p>
        <p className="text-xs text-slate-400 mt-1">
          Type above and select at least 2 medicines to screen for interactions
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between text-xs font-semibold text-slate-600">
        <div className="flex items-center gap-1.5">
          <span>Current Regimen</span>
          <span className="inline-flex items-center justify-center px-2 py-0.5 rounded-full bg-slate-200 text-slate-800 text-[11px] font-bold">
            {drugs.length} {drugs.length === 1 ? 'medicine' : 'medicines'}
          </span>
        </div>
        <button
          type="button"
          onClick={onClearAll}
          className="text-slate-500 hover:text-rose-600 font-medium flex items-center gap-1 transition-colors px-2 py-1 rounded hover:bg-rose-50"
        >
          <Trash2 className="h-3.5 w-3.5" />
          Clear list
        </button>
      </div>

      <div className="flex flex-wrap gap-2">
        {drugs.map((drug) => (
          <div
            key={drug.id}
            className={`inline-flex items-center gap-2 pl-3 pr-2 py-1.5 rounded-lg text-sm font-medium transition-all shadow-2xs ${
              drug.isUnmatched
                ? 'bg-slate-100 text-slate-700 border-2 border-dashed border-slate-400'
                : 'bg-blue-50 text-blue-950 border border-blue-200'
            }`}
          >
            {drug.isUnmatched ? (
              <span className="flex items-center gap-1 text-slate-600">
                <AlertCircle className="h-3.5 w-3.5 text-amber-600" />
                <span>{drug.name}</span>
                <span className="text-[11px] text-slate-500 italic">(unmatched)</span>
              </span>
            ) : (
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-blue-600" />
                <span>{drug.name}</span>
              </span>
            )}

            <button
              type="button"
              onClick={() => onRemoveDrug(drug.id)}
              aria-label={`Remove ${drug.name}`}
              className={`p-0.5 rounded-full hover:bg-slate-300/60 transition-colors ${
                drug.isUnmatched ? 'text-slate-600 hover:text-slate-900' : 'text-blue-700 hover:text-blue-900'
              }`}
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
