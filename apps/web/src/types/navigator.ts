export type ConstraintKind = "physical" | "categorical" | "calculation_quality" | "evidence";
export type ConstraintOperator = "eq" | "lt" | "lte" | "gt" | "gte" | "include_all" | "exclude_any";
export type OutcomeState = "feasible_set" | "plan_conflict" | "index_capability_mismatch" | "evidence_unknown" | "no_feasible_set";
export type CandidateStatus = "pass" | "fail" | "unknown";
export type ConstraintValue = number | string | boolean | string[];

export type NavigatorConstraint = {
  id: string;
  field: string;
  operator: ConstraintOperator;
  value: ConstraintValue;
  unit: string | null;
  kind: ConstraintKind;
  locked: boolean;
  confirmed: boolean;
  label: string | null;
  source_text: string | null;
};

export type UnresolvedConstraint = {
  id: string;
  text: string;
  reason: string;
  code: string;
  actions: string[];
};

export type ConstraintPlan = {
  constraints: NavigatorConstraint[];
  unresolved_constraints: UnresolvedConstraint[];
  registry_version: string;
  index_id: string;
  engine_version: string;
  interpreter_version: string | null;
};

export type RegistryEntry = {
  field: string;
  label: string;
  kind: ConstraintKind;
  executable: boolean;
  unit: string | null;
  operators: ConstraintOperator[];
  source: string;
  derivation_id: string | null;
  comparability_scope: string;
  missingness: string;
  relaxable: boolean;
  confirmation_required: boolean;
  display_only: boolean;
  bounds: [number, number] | null;
  supported_values: string[] | null;
  scientific_note: string | null;
};

export type NavigatorRegistry = {
  version: string;
  index_id: string;
  entries: RegistryEntry[];
  digest: string;
  record_count: number;
  source_kind: string;
  scope: string;
};

export type InterpretationResult = {
  plan: ConstraintPlan;
  interpreter: {
    id: string;
    kind: string;
    model_used: boolean;
    scientific_boundary: string;
  };
  confirmation_required: boolean;
  privacy: string;
};

export type ValidationIssue = {
  code: string;
  message: string;
  constraint_ids: string[];
  field: string | null;
};

export type ConstraintCheck = {
  constraint_id: string;
  status: CandidateStatus;
  actual: ConstraintValue | null;
  expected: ConstraintValue;
  unit: string | null;
  message: string;
};

export type CandidateEvaluation = {
  material_id: string;
  formula: string;
  status: CandidateStatus;
  checks: ConstraintCheck[];
  properties: Record<string, number | string | boolean | null>;
};

export type EvaluationResult = {
  state: OutcomeState;
  index_id: string;
  registry_version: string;
  engine_version: string;
  total_count: number;
  feasible_count: number;
  indeterminate_count: number;
  candidates: CandidateEvaluation[];
  issues: ValidationIssue[];
  scientific_boundary: string;
};

export type ConstraintChange = {
  constraint_id: string;
  field: string;
  old_operator: ConstraintOperator;
  old_value: ConstraintValue;
  new_operator: ConstraintOperator;
  new_value: ConstraintValue;
  unit: string | null;
  normalized_change: number;
  message: string;
};

export type RelaxationPath = {
  path_id: string;
  changes: ConstraintChange[];
  recovered_count: number;
  recovered_material_ids: string[];
  maximum_normalized_change: number;
  total_normalized_change: number;
  relative_to: string;
  causal: false;
};

export type RecoveryAction = { code: string; label: string; detail: string };

export type RelaxationResult = {
  state: OutcomeState;
  physical_relaxations: RelaxationPath[];
  quality_relaxations: RelaxationPath[];
  evidence_recoveries: RecoveryAction[];
  capability_recoveries: RecoveryAction[];
  scientific_boundary: string;
};

export type NavigatorStructure = {
  structure_id: string;
  source_id: string;
  source: string;
  method: string;
  structure: {
    lattice: [number, number, number][];
    species: Array<string | Record<string, number>>;
    coords: [number, number, number][];
    site_properties: Array<Record<string, unknown> | null> | null;
  };
  lattice_unit: "angstrom";
  coordinate_convention: "fractional";
  occupancy_convention: "species_mapping";
  periodic_axes: [boolean, boolean, boolean];
  provenance: Array<Record<string, unknown>>;
};

export type NavigatorMaterial = {
  material_id: string;
  formula: string;
  elements: string[];
  nsites: number;
  functional: string;
  properties: Record<string, number | string | boolean | null>;
  property_provenance: Record<string, Record<string, unknown>>;
  structure: NavigatorStructure;
  inspection_boundary: string;
};
