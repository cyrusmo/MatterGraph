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

export type CandidateSliceSummary = {
  slice_id: string;
  slice_name: string;
  target: string;
  input_count: number;
  output_count: number;
  removed_count: number;
  filter_steps: Array<Record<string, unknown>>;
};

export type GraphExportSummary = {
  included_count: number;
  excluded_count: number;
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
};

export type LeMaterialWorkflowSummary = {
  workflow_id: string;
  source_dataset: string;
  source_subset: string;
  schema_report: Record<string, unknown>;
  candidate_slice: CandidateSliceSummary;
  graph_export: GraphExportSummary;
  benchmark_preview: BenchmarkPreviewRow[];
  provenance: WorkflowProvenance;
};
