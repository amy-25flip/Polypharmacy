// 'None' means no reaction is on record for the pair (not proof that it is safe).
export type Severity = 'None' | 'Minor' | 'Moderate' | 'Major' | null

// How a severity was reached: a documented record, a borrowed record for a drug with none of its
// own ('estimated'), the model's guess ('inferred'), no record at all, or a same-class duplicate.
export type SeverityBasis = 'documented' | 'estimated' | 'inferred' | 'no_record' | 'duplicate_class' | 'no_data' | 'class_rule'

// A sentence from an FDA drug label that names the other drug of a pair.
export interface LabelEvidenceEntry {
  from: string
  text: string
  effects: string[]
}

export interface EstimateNote {
  drug: string
  proxy: string
  reason: string
}

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
  severity: 'None' | 'Minor' | 'Moderate' | 'Major'
  severity_basis?: SeverityBasis
  severity_notice?: string
  estimated_from?: EstimateNote[]
  label_evidence?: LabelEvidenceEntry[]
  label_effects?: string[]
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

export interface ScannedMedicine {
  raw_text: string
  drug_name_guess: string
  generic_name_guess: string | null
  dosage: string | null
  frequency_or_timing_guess: string | null
  confidence_notes: string | null
  suggested_vocab_matches: string[]
  bounding_box: PrescriptionBoundingBox | null
}

export interface PrescriptionBoundingBox {
  y_min: number
  x_min: number
  y_max: number
  x_max: number
}

export interface PrescriptionScanResult {
  source_guess: string | null
  date_guess: string | null
  medicines: ScannedMedicine[]
  warnings: string[]
}

// Defaults to http://127.0.0.1:8765 (or proxied /api in vite dev if configured)
// Defaults to '' (same-origin relative requests: /api/...), which works both
// for local dev (Vite's dev-server proxy forwards /api to 127.0.0.1:8765 -
// see vite.config.ts) and for single-origin self-hosting where this same
// FastAPI server also serves the built frontend (see main.py). Render's
// separate-services deployment explicitly overrides this with VITE_API_URL
// at build time (see render.yaml) since frontend and backend are different
// origins there.
const API_BASE = import.meta.env.VITE_API_URL || ''

export async function checkHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/api/health`)
  if (!res.ok) {
    throw new Error(`Health check failed: ${res.statusText}`)
  }
  return res.json()
}

export interface DrugSearchResult {
  name: string
  matched_via_brand?: string | null
  matched_via_synonym?: string | null
  // Every ingredient of a combination brand; choosing the suggestion adds all of them.
  bundle?: string[]
}

export interface Disease {
  id: string
  name: string
  aliases: string[]
  specialties?: string[]
  note?: string | null
  route_note?: string | null
  medicine_count: number
}

export interface DiseaseMedicine {
  name: string
  sources: string[]
  // Clinical grouping and a short display label (for example "Inhaled. Use only with an inhaled steroid").
  group?: string
  group_order?: number
  group_collapsed?: boolean
  label?: string
}

export interface CandidateFlag {
  with: string
  severity: string
  severity_basis?: SeverityBasis
  severity_notice?: string | null
  estimated_from?: EstimateNote[]
  label_evidence?: LabelEvidenceEntry[]
  adverse_effect_source?: 'label' | 'overlap' | 'none'
  is_documented: boolean
  uncertain: boolean
  adverse_effects: string[]
}

export interface CandidateResult {
  candidate: string
  worst_severity: Severity
  flags: CandidateFlag[]
  adverse_effects: string[]
}

export interface ScreenedPair {
  drug_a: string
  drug_b: string
  severity: string
  severity_basis?: SeverityBasis
  severity_notice?: string
  estimated_from?: EstimateNote[]
  label_evidence?: LabelEvidenceEntry[]
  adverse_effect_source?: 'label' | 'overlap' | 'none'
  is_documented: boolean
  uncertain: boolean
  adverse_effects: string[]
}

export interface CandidateScreenResponse {
  results: CandidateResult[]
  selected_summary: {
    overall_severity: string | null
    pairs: ScreenedPair[]
    counts: { Major: number; Moderate: number; Minor: number; None?: number }
  }
  unmatched: string[]
  adverse_effect_basis: string
}

export interface PatientCaution {
  drug: string
  level: string
  factor: 'age' | 'egfr' | 'pregnancy'
  trigger: string
  text: string
  source: string
  url: string
}

export async function fetchPatientCautions(
  drugs: string[], age: number | null, egfr: number | null, signal?: AbortSignal, pregnancy?: 'possible' | 'pregnant',
): Promise<PatientCaution[]> {
  const res = await fetch(`${API_BASE}/api/patient-cautions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ drugs, age, egfr, pregnancy: pregnancy || null }),
    signal,
  })
  if (!res.ok) throw new Error(`Patient cautions failed: ${res.statusText}`)
  const body: { cautions: PatientCaution[] } = await res.json()
  return body.cautions
}

export interface Specialty {
  name: string
  disease_count: number
}

export async function fetchSpecialties(signal?: AbortSignal): Promise<Specialty[]> {
  const res = await fetch(`${API_BASE}/api/specialties`, { signal })
  if (!res.ok) throw new Error(`Specialties failed: ${res.statusText}`)
  const body: { specialties: Specialty[] } = await res.json()
  return body.specialties
}

export async function searchDiseases(query: string, signal?: AbortSignal, specialty?: string): Promise<Disease[]> {
  const filter = specialty ? `&specialty=${encodeURIComponent(specialty)}` : ''
  const res = await fetch(`${API_BASE}/api/diseases?q=${encodeURIComponent(query.trim())}${filter}`, { signal })
  if (!res.ok) throw new Error(`Disease search failed: ${res.statusText}`)
  const body: { diseases: Disease[] } = await res.json()
  return body.diseases
}

export async function fetchDiseaseMedicines(id: string, signal?: AbortSignal): Promise<DiseaseMedicine[]> {
  const res = await fetch(`${API_BASE}/api/diseases/${encodeURIComponent(id)}/medicines`, { signal })
  if (!res.ok) throw new Error(`Disease medicines failed: ${res.statusText}`)
  const body: { disease: Pick<Disease, 'id' | 'name'>; medicines: DiseaseMedicine[] } = await res.json()
  return body.medicines
}

export async function screenCandidates(selected: string[], candidates: string[], signal?: AbortSignal): Promise<CandidateScreenResponse> {
  const res = await fetch(`${API_BASE}/api/screen-candidates`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ selected, candidates }),
    signal,
  })
  if (!res.ok) throw new Error(`Candidate screening failed: ${res.statusText}`)
  return res.json()
}

export async function searchDrugs(query: string, signal?: AbortSignal): Promise<DrugSearchResult[]> {
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

export async function scanPrescription(file: File): Promise<PrescriptionScanResult> {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch(`${API_BASE}/api/prescriptions/scan`, {
    method: 'POST',
    body: formData,
  })
  if (!res.ok) {
    let message = `Prescription scan failed: ${res.statusText}`
    try {
      const body = (await res.json()) as { detail?: string; error?: string }
      message = body.detail || body.error || message
    } catch {
      // Keep the HTTP fallback when the server did not return JSON.
    }
    throw new Error(message)
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

export interface NoReactionValidation {
  model_alone_on_documented_pairs: {
    documented_pairs: number
    model_wrong_pct: number
    documented_major_pairs: number
    major_shown_as_minor_pct: number
  }
  method: string
  held_out_pairs: number
  by_true_severity: Record<string, { pairs: number; shown_no_reaction_pct: number; shown_correctly_pct: number }>
}

export interface TransparencyData {
  no_reaction_validation?: NoReactionValidation | null
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
