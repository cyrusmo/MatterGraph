export type MaterialProperty = {
  name: string;
  value: number | string | Record<string, unknown>;
  unit?: string | null;
  source?: string;
  method?: string;
  confidence?: number | null;
  uncertainty?: number | null;
  source_id?: string | null;
  context?: Record<string, unknown> | null;
  source_artifact?: Record<string, unknown> | null;
  extra?: Record<string, unknown>;
};

export type ProvenanceRecord = {
  source?: string;
  method?: string;
  confidence?: number | null;
  notes?: string | null;
  model_version?: string | null;
  source_id?: string | null;
  [key: string]: unknown;
};

export type Material = {
  material_id?: string;
  formula?: string;
  reduced_formula?: string;
  elements?: string[];
  structure?: unknown | null;
  properties?: MaterialProperty[];
  provenance?: ProvenanceRecord[];
  source_id?: string | null;
  metadata?: Record<string, unknown>;
  [key: string]: unknown;
};

export type RankedRow = {
  material_id?: string;
  score?: number;
  density?: number | null;
  energy_above_hull?: number | null;
  max_force?: number | null;
  [key: string]: unknown;
};

export type ScoreReport = {
  pool_size: number;
  ranked_count: number;
  excluded_by_constraints: number;
  objectives: string[];
  weights: Record<string, number>;
  missing_policy: "worst" | "neutral" | "exclude";
  coverage: Record<string, number>;
  ignored_objectives: string[];
  effective_objectives: string[];
  mixed_methods: Record<string, string[]>;
  mixed_averaging_schemes: Record<string, string[]>;
  mixed_hull_conventions: Record<string, string[]>;
  binary_normalization: boolean;
  scores_are_pool_relative: boolean;
  [key: string]: unknown;
};

export type ScoreAudit = {
  ranked: RankedRow[];
  report: ScoreReport;
  request: Record<string, unknown>;
};

export type SimulationResult = {
  engine?: string;
  calculator?: string;
  converged?: boolean | null;
  steps?: number | null;
  energy?: number | null;
  max_force?: number | null;
  relaxed_structure?: unknown | null;
};

export type SimulationJob = {
  job_id?: string;
  status?: string;
  result?: SimulationResult | null;
  error?: string | null;
  log?: string | null;
  [key: string]: unknown;
};

export type SimulationReadiness = {
  ready: boolean;
  ase_available: boolean;
  calculator: string;
  unsupported_species: string[];
  reason: string;
};

export type PreflightCheck = {
  id: string;
  status: "pass" | "warn" | "fail";
  detail: string;
};

export type DemoPreflight = {
  status: "ready" | "degraded";
  fixture: {
    path: string;
    kind: string;
    disclaimer: string;
    dataset: string;
    subset: string;
    upstream_revision: string;
    hull_dataset: string;
    hull_revision: string;
    license: string;
    citation_doi: string;
    snapshot_sha256: string;
    source_population: number;
    field_sources: Record<string, string>;
  };
  record_count: number;
  graph: {
    included_count: number;
    excluded_count: number;
    invalid_count: number;
    validation_state: "valid" | "invalid";
  };
  ranking: {
    ranked_count: number;
    excluded_by_constraints: number;
    binary_normalization: boolean;
    objectives: Record<string, { direction: string; weight: number }>;
    constraints: Record<string, Record<string, number>>;
  };
  default_material_id: string;
  chgnet: ChgnetState;
  simulation_targets: Record<string, SimulationReadiness>;
  checks: PreflightCheck[];
};

export type CapabilityStatus = "demo_ready" | "sdk_ready" | "stub" | "out_of_scope";

export type Capability = {
  id: string;
  label: string;
  category: string;
  status: CapabilityStatus;
  evidence: string;
  optional_dependency?: string | null;
  boundary?: string | null;
};

export type GraphNode = {
  index: number;
  species: string;
  fractional_coordinates: number[];
  cartesian_coordinates: [number, number, number];
};

export type GraphEdge = {
  source: number;
  target: number;
  distance: number;
  image: number[];
  source_cartesian: [number, number, number];
  target_cartesian: [number, number, number];
  displacement_cartesian: [number, number, number];
};

export type GraphSummary = {
  material_id: string;
  formula: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  edge_count: number;
  edges_truncated: boolean;
  lattice_vectors: [number, number, number][];
  distance_shells: Array<{ index: number; distance: number; directed_edge_count: number }>;
  coordination_numbers: number[];
  node_feature_shape: number[];
  edge_feature_shape: number[];
  global_features: Record<string, number>;
  builder: {
    cutoff: number;
    max_neighbors: number;
    neighbor_target_is_soft: boolean;
    complete_tied_shells: boolean;
    reciprocal: boolean;
    truncated_sources: number[];
  };
  validation: {
    state: "valid" | "invalid";
    ordered_structure: boolean;
    reciprocal: boolean;
    zero_distance_edges: number;
    displacement_consistent: boolean;
    complete_tied_shells: boolean;
    symmetry: { status: "determined" | "unknown"; spacegroup_number: number };
    truncated: boolean;
    warnings: string[];
  };
};

export type CandidateSliceSummary = {
  slice_id: string;
  slice_name: string;
  target: string;
  input_count: number;
  output_count: number;
  removed_count: number;
  filter_steps: Array<Record<string, unknown>>;
  report: Record<string, unknown>;
};

export type GraphExportSummary = {
  included_count: number;
  excluded_count: number;
  previews: Array<{
    material_id: string;
    formula: string;
    node_count: number;
    edge_count: number;
    node_feature_shape: number[];
    edge_feature_shape: number[];
    global_features: Record<string, number>;
  }>;
};

export type BenchmarkPreviewRow = {
  material_id: string;
  formula: string;
  target: number | string | null;
  density?: number | string | null;
  energy_above_hull?: number | string | null;
  max_force?: number | string | null;
  nsites?: number | null;
  nelements?: number | null;
};

export type WorkflowProvenance = {
  fixture_path: string;
  loader: string;
  workflow_version: string;
  run_id: string;
  fixture_kind: string;
  disclaimer: string;
  upstream_revision: string;
  hull_revision: string;
  license: string;
  citation_doi: string;
  snapshot_sha256: string;
  field_sources: Record<string, string>;
};

export type ChgnetState = {
  state: "live" | "warming" | "cached_only" | "unavailable";
  live_available: boolean;
  reference_available: boolean;
  reference_material_id?: string;
  model_version?: string;
  detail: string;
  scientific_boundary: string;
};

export type ChgnetReference = {
  artifact_version: string;
  material_id: string;
  label: "cached_reference";
  model: { name: string; version: string; weight_checksum: string };
  input_checksum: string;
  run: Record<string, unknown>;
  result: {
    converged: boolean;
    steps: number;
    energy_per_atom: number;
    max_force: number;
    volume_change_percent: number;
    lattice_change_percent: number;
    trajectory: Array<Record<string, number>>;
    relaxed_structure: unknown;
  };
  scientific_boundary: string;
};

export type LeMaterialWorkflowSummary = {
  workflow_id: string;
  source_dataset: string;
  source_subset: string;
  schema_report: Record<string, unknown>;
  candidate_slice: CandidateSliceSummary;
  graph_export: GraphExportSummary;
  benchmark: { target: string; row_count: number; columns: string[] };
  benchmark_preview: BenchmarkPreviewRow[];
  provenance: WorkflowProvenance;
};

export type PropertyColumnMapping = {
  column: string;
  name: string;
  unit?: string | null;
  source: string;
  method: "dft" | "experimental" | "model_predicted" | "derived" | "unknown";
};

export type DatasetImportMapping = {
  identity_column: string;
  formula_column: string;
  structure_column?: string | null;
  source_id_column?: string | null;
  property_columns: PropertyColumnMapping[];
};

export type ImportIssue = {
  code: string;
  severity: "error" | "warning";
  message: string;
  row?: number | null;
  column?: string | null;
};

export type ImportReport = {
  status: "ready" | "degraded" | "invalid";
  checksum: string;
  row_count: number;
  accepted_count: number;
  rejected_count: number;
  columns: string[];
  inferred_mapping?: DatasetImportMapping | null;
  issues: ImportIssue[];
  issue_counts: Record<string, number>;
  truncated_issue_count: number;
};

export type DatasetManifest = {
  schema_version: "0.1";
  dataset_id: string;
  name: string;
  source: string;
  format: "csv" | "jsonl" | "normalized_jsonl";
  record_count: number;
  accepted_count: number;
  rejected_count: number;
  content_sha256: string;
  normalized_sha256: string;
  normalized_bytes: number;
  degraded: boolean;
  created_at: string;
};

export type ImportResult = {
  dataset_id: string;
  manifest: DatasetManifest;
  accepted_count: number;
  rejected_count: number;
  issues: ImportIssue[];
  issue_counts: Record<string, number>;
  truncated_issue_count: number;
  preview: Material[];
};

export type DatasetEntry = {
  manifest: DatasetManifest;
  readiness: "ready";
  normalized_bytes: number;
  materialized: boolean;
  eviction: { policy: string; entry_limit: number; byte_limit: number };
};

export type DatasetList = {
  datasets: DatasetEntry[];
  registry: {
    entry_count: number;
    normalized_bytes: number;
    max_entries: number;
    max_normalized_bytes: number;
    active_dataset_id?: string | null;
    eviction_policy: string;
  };
};

export type SlicePreview = {
  slice: Record<string, unknown> & { output_count?: number };
  material_ids: string[];
  graph_readiness: { included_count: number; excluded_count: number };
  benchmark_preview: Array<Record<string, unknown>>;
};
