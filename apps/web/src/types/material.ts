export type MaterialProperty = {
  name: string;
  value: number | string | Record<string, unknown>;
  unit?: string | null;
  source?: string;
  method?: string;
  confidence?: number | null;
  uncertainty?: number | null;
  source_id?: string | null;
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
  bulk_modulus?: number | null;
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
  fixture: { path: string; kind: string; disclaimer: string };
  record_count: number;
  graph: { included_count: number; excluded_count: number };
  ranking: {
    ranked_count: number;
    excluded_by_constraints: number;
    binary_normalization: boolean;
    objectives: Record<string, { direction: string; weight: number }>;
    constraints: Record<string, Record<string, number>>;
  };
  default_material_id: string;
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
};

export type GraphEdge = {
  source: number;
  target: number;
  distance: number;
  image: number[];
};

export type GraphSummary = {
  material_id: string;
  formula: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  edge_count: number;
  edges_truncated: boolean;
  node_feature_shape: number[];
  edge_feature_shape: number[];
  global_features: Record<string, number>;
  builder: { cutoff: number; max_neighbors: number };
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
  bulk_modulus?: number | string | null;
  energy_above_hull?: number | string | null;
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
