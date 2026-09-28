import React from 'react'
import { ShieldAlert, Activity, WifiOff } from 'lucide-react'

interface HeaderProps {
  knownDrugsCount?: number | null
  healthStatus?: 'loading' | 'ready' | 'error'
}

export const Header: React.FC<HeaderProps> = ({ knownDrugsCount, healthStatus = 'loading' }) => {
  return (
    <header className="space-y-4">
      {/* Top Brand Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-slate-200 pb-3">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-700 text-white font-bold text-xl shadow-xs">
            PG
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
              PolyGuard
              <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-blue-50 text-blue-800 border border-blue-200">
                Clinical Decision Support
              </span>
            </h1>
            <p className="text-xs text-slate-500 font-medium">
              Multi-drug interaction & regimen risk screening
            </p>
          </div>
        </div>

        {healthStatus === 'error' ? (
          <div className="flex items-center gap-2 text-xs text-rose-800 bg-rose-50 border border-rose-200 rounded-md px-2.5 py-1.5 self-start sm:self-auto">
            <WifiOff className="h-3.5 w-3.5 text-rose-600" />
            <span>Backend unavailable - check the server connection</span>
          </div>
        ) : (
          <div className="flex items-center gap-2 text-xs text-slate-600 bg-slate-50 border border-slate-200 rounded-md px-2.5 py-1.5 self-start sm:self-auto">
            <Activity className={`h-3.5 w-3.5 ${healthStatus === 'ready' ? 'text-emerald-600' : 'text-slate-400'}`} />
            <span>
              {healthStatus === 'ready' && knownDrugsCount != null
                ? `${knownDrugsCount.toLocaleString()} indexed medicines`
                : 'Connecting to database...'}
            </span>
          </div>
        )}
      </div>

      {/* Mandatory Clinical Safety Disclaimer - Always visible at the top */}
      <div
        role="region"
        aria-label="Clinical safety disclaimer"
        className="rounded-lg bg-amber-50 border-l-4 border-amber-500 p-3.5 sm:p-4 text-amber-950 shadow-xs"
      >
        <div className="flex items-start gap-3">
          <ShieldAlert className="h-5 w-5 text-amber-700 shrink-0 mt-0.5" />
          <p className="text-xs sm:text-sm font-medium leading-relaxed">
            <strong className="font-semibold">Safety Notice: </strong>
            PolyGuard is a clinical decision-support tool. It helps flag possible interaction risks and does not replace clinical judgment, prescribing guidelines, or pharmacist review.
          </p>
        </div>
      </div>
    </header>
  )
}
