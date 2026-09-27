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

export type EvidenceTier = 'documented' | 'mechanism_evidence' | 'indirect_evidence' | 'no_evidence'
export type SupportTier = 'sparse' | 'limited' | 'well_represented'
export type ReliabilityBand = 'High' | 'Moderate' | 'Low'

export interface DrugSupport {
  documented_pair_count: number
  tier: SupportTier
}

export interface Reliability {
  band: ReliabilityBand
  empirical_accuracy: number
}

export type DisagreementLevel = 'Low' | 'Moderate' | 'High'

export interface CrossModelAgreement {
  available: boolean
  chemistry_model_severity: 'Minor' | 'Moderate' | 'Major'
  js_divergence: number
  disagreement_level: DisagreementLevel
  model1_empirical_accuracy_at_this_disagreement: number
}

export interface EvidencePassport {
  evidence_tier: EvidenceTier
  drug_a_support: DrugSupport
  drug_b_support: DrugSupport
  reliability: Reliability
  abstain: boolean
  abstain_reason: string | null
  cross_model_agreement: CrossModelAgreement | null
}

export interface ConformalSet {
  set: ('Minor' | 'Moderate' | 'Major')[]
  size: number
}

export type ConformalSets = Record<string, ConformalSet> // key = target coverage, e.g. "0.9"

export interface InteractionPair {
  drug_a: string
  drug_b: string
  severity: 'Minor' | 'Moderate' | 'Major'
  confidence?: number // Internal from API, never shown in UI
  explanation?: PairExplanation
  is_documented?: boolean
  undocumented_pair_notice?: string
  evidence_passport?: EvidencePassport
  conformal_sets?: ConformalSets
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

export type CertificateType = 'reducible' | 'entangled' | 'higher_order'

export interface MinimalElevatedSubset {
  drugs: string[]
  probability: number
  size: number
}

export interface RemovalImpact {
  drug: string
  probability_without_this_drug: number
  still_elevated_without_it: boolean
  change: number
}

export interface SubsetCertificate {
  applicable: boolean
  reason?: string
  certificate_type?: CertificateType
  full_regimen_probability?: number
  summary?: string
  minimal_elevated_subsets?: MinimalElevatedSubset[]
  total_minimal_subsets_found?: number
  removal_impact?: RemovalImpact[]
  caveat?: string
}

export interface CheckResponse {
  entered: string[]
  matched: string[]
  unmatched: string[]
  regimen: RegimenResult
  combination_signal: CombinationSignal | null
  subset_certificate: SubsetCertificate | null
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

// --- Transparency page ---

export interface CalibrationBin {
  confidence_low: number
  confidence_high: number
  n: number
  empirical_accuracy: number
}

export interface RiskCoveragePoint {
  coverage: number
  n: number
  accuracy: number
}

export interface DisagreementBin {
  js_divergence_low: number
  js_divergence_high: number
  n: number
  model1_empirical_accuracy: number
  top_class_mismatch_rate: number
}

export interface ModelComparisonRow {
  model: string
  standard_accuracy: number
  standard_macro_f1: number
  cold_start_accuracy: number
  cold_start_macro_f1: number
  status: 'baseline' | 'shipped' | 'negative_result'
}

export interface ConformalCoverageResult {
  overall_coverage: number
  overall_avg_set_size: number
  singleton_rate: number
  per_class: Record<string, { n: number; coverage: number; avg_set_size: number }>
}

export interface TransparencyData {
  model1_calibration: {
    bins: CalibrationBin[]
    risk_coverage: RiskCoveragePoint[]
    thresholds: Record<string, number | string>
    method: string
  }
  conformal_sets: {
    eval: {
      standard_split: Record<string, ConformalCoverageResult>
      cold_start_split: Record<string, ConformalCoverageResult>
    }
    method: string
  }
  disagreement_sentinel: {
    calibration: {
      overall_model1_accuracy_on_this_heldout: number
      correlation_disagreement_vs_error: number
      bins: DisagreementBin[]
    }
    method: string
  }
  model_comparison: {
    note: string
    rows: ModelComparisonRow[]
    finding: string
  }
  dataset: {
    total_documented_pairs: number
    total_drugs: number
    drugs_with_drugbank_id: number
    support_tiers: { sparse_max: number; limited_max: number }
  }
}

export async function fetchTransparency(): Promise<TransparencyData> {
  const res = await fetch(`${API_BASE}/api/transparency`)
  if (!res.ok) {
    throw new Error(`Transparency data fetch failed: ${res.statusText}`)
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
