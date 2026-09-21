export type Severity = 'Minor' | 'Moderate' | 'Major' | null

export type PrimaryReasonType = 'class' | 'side_effect' | 'gene' | 'structural_resemblance' | string

export interface PrimaryReason {
  type: PrimaryReasonType
  title: string
  plain_text: string
  evidence: string[]
}

export interface SupportingEvidenceItem {
  type: string
  items: string[]
}

export interface ExplanationCoverage {
  drug_a_has_kg_data: boolean
  drug_b_has_kg_data: boolean
}

export interface PairExplanation {
  has_explanation: boolean
  primary_reason: PrimaryReason | null
  supporting_evidence: SupportingEvidenceItem[]
  coverage: ExplanationCoverage
  caveat: string
}

export interface InteractionPair {
  drug_a: string
  drug_b: string
  severity: 'Minor' | 'Moderate' | 'Major'
  confidence?: number // Internal from API, never shown in UI
  explanation?: PairExplanation
  is_documented?: boolean
  undocumented_pair_notice?: string
}

export interface RegimenResult {
  overall_severity: Severity
  pairs: InteractionPair[]
}

export interface CombinationSignal {
  drugs_used: number
  drugs_total: number
  probability?: number // Internal from API, never shown in UI
  elevated: boolean
}

export interface CheckResponse {
  entered: string[]
  matched: string[]
  unmatched: string[]
  regimen: RegimenResult
  combination_signal: CombinationSignal | null
}

export interface HealthResponse {
  status: string
  known_drugs: number
}

// Defaults to http://127.0.0.1:8765 (or proxied /api in vite dev if configured)
const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8765'

export async function checkHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/api/health`)
  if (!res.ok) {
    throw new Error(`Health check failed: ${res.statusText}`)
  }
  return res.json()
}

export async function searchDrugs(query: string, signal?: AbortSignal): Promise<string[]> {
  const trimmed = query.trim()
  if (trimmed.length < 2) {
    return []
  }
  const res = await fetch(`${API_BASE}/api/drugs/search?q=${encodeURIComponent(trimmed)}`, {
    signal,
  })
  if (!res.ok) {
    throw new Error(`Drug search failed: ${res.statusText}`)
  }
  return res.json()
}

export async function checkInteractions(drugs: string[]): Promise<CheckResponse> {
  const res = await fetch(`${API_BASE}/api/check`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ drugs }),
  })
  if (!res.ok) {
    throw new Error(`Interaction check failed: ${res.statusText}`)
  }
  return res.json()
}
