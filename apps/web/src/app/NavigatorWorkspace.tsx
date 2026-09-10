import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";

import { NavigatorDesignSpace } from "../components/NavigatorDesignSpace";
import {
  evaluateNavigatorPlan,
  fetchNavigatorMaterial,
  fetchNavigatorRegistry,
  fetchNavigatorRelaxations,
  interpretNavigatorRequest,
} from "../lib/api";
import { savePrivateNavigatorReplay } from "../lib/navigatorReplay";
import type {
  CandidateEvaluation,
  ConstraintPlan,
  ConstraintValue,
  EvaluationResult,
  NavigatorConstraint,
  NavigatorMaterial,
  NavigatorRegistry,
  RegistryEntry,
  RelaxationPath,
  RelaxationResult,
} from "../types/navigator";

const NavigatorCrystalViewer = lazy(() =>
  import("../components/NavigatorCrystalViewer").then((module) => ({
    default: module.NavigatorCrystalViewer,
  })),
);

const DEFAULT_REQUEST = "Find a ternary nitride with fewer than 20 sites, density below 6 g/cm3, and maximum force below 0.2 eV/Å.";

export function NavigatorWorkspace({ onReturnDemo }: { onReturnDemo: () => void }) {
  const [registry, setRegistry] = useState<NavigatorRegistry | null>(null);
  const [request, setRequest] = useState(DEFAULT_REQUEST);
  const [plan, setPlan] = useState<ConstraintPlan | null>(null);
  const [evaluation, setEvaluation] = useState<EvaluationResult | null>(null);
  const [recoveries, setRecoveries] = useState<RelaxationResult | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [material, setMaterial] = useState<NavigatorMaterial | null>(null);
  const [replayId, setReplayId] = useState<string | null>(null);
  const [fieldToAdd, setFieldToAdd] = useState<string>("");
  const [liveUpdates, setLiveUpdates] = useState(false);
  const [loading, setLoading] = useState<"registry" | "interpret" | "evaluate" | "material" | null>("registry");
  const [error, setError] = useState<string | null>(null);
  const lastExecutedPlan = useRef<string | null>(null);
  const evaluationSequence = useRef(0);

  useEffect(() => {
    fetchNavigatorRegistry()
      .then((next) => {
        setRegistry(next);
        setFieldToAdd(next.entries.find((entry) => entry.executable)?.field ?? "");
      })
      .catch((reason: unknown) => setError(errorMessage(reason)))
      .finally(() => setLoading(null));
  }, []);

  useEffect(() => {
    if (!selectedId) {
      setMaterial(null);
      return;
    }
    let active = true;
    setLoading("material");
    fetchNavigatorMaterial(selectedId)
      .then((next) => { if (active) setMaterial(next); })
      .catch((reason: unknown) => { if (active) setError(errorMessage(reason)); })
      .finally(() => { if (active) setLoading(null); });
    return () => { active = false; };
  }, [selectedId]);

  useEffect(() => {
    if (!liveUpdates || !plan) return;
    const signature = JSON.stringify(plan);
    if (signature === lastExecutedPlan.current) return;
    const timer = window.setTimeout(() => void execute(plan, false), 350);
    return () => window.clearTimeout(timer);
  }, [liveUpdates, plan]);

  const selectedCandidate = evaluation?.candidates.find((candidate) => candidate.material_id === selectedId) ?? null;
  const visibleCandidates = useMemo(() => {
    if (!evaluation) return [];
    const order = { pass: 0, unknown: 1, fail: 2 };
    return [...evaluation.candidates].sort((left, right) => (
      order[left.status] - order[right.status]
      || left.formula.localeCompare(right.formula)
      || left.material_id.localeCompare(right.material_id)
    ));
  }, [evaluation]);

  async function interpret() {
    setLoading("interpret");
    setError(null);
    setEvaluation(null);
    setRecoveries(null);
    setSelectedId(null);
    setReplayId(null);
    setLiveUpdates(false);
    lastExecutedPlan.current = null;
    try {
      const result = await interpretNavigatorRequest(request);
      setPlan(result.plan);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setLoading(null);
    }
  }

  async function execute(nextPlan = plan, enableLive = true) {
    if (!nextPlan) return;
    const sequence = ++evaluationSequence.current;
    lastExecutedPlan.current = JSON.stringify(nextPlan);
    if (enableLive) setLiveUpdates(true);
    setLoading("evaluate");
    setError(null);
    try {
      const nextEvaluation = await evaluateNavigatorPlan(nextPlan);
      const nextRecoveries = nextEvaluation.state === "feasible_set"
        ? null
        : await fetchNavigatorRelaxations(nextPlan);
      if (sequence !== evaluationSequence.current) return;
      setEvaluation(nextEvaluation);
      setRecoveries(nextRecoveries);
      try {
        setReplayId(await savePrivateNavigatorReplay(nextPlan, nextEvaluation, nextRecoveries));
      } catch {
        setReplayId(null);
      }
      const preferred = nextEvaluation.candidates.find((candidate) => candidate.status === "pass")
        ?? nextEvaluation.candidates.find((candidate) => candidate.status === "unknown")
        ?? nextEvaluation.candidates[0];
      setSelectedId(preferred?.material_id ?? null);
    } catch (reason) {
      if (sequence === evaluationSequence.current) setError(errorMessage(reason));
    } finally {
      if (sequence === evaluationSequence.current) setLoading(null);
    }
  }

  function addConstraint() {
    if (!plan || !registry) return;
    const entry = registry.entries.find((item) => item.field === fieldToAdd);
    if (!entry?.executable || !entry.operators.length) return;
    let serial = 1;
    const used = new Set(plan.constraints.map((constraint) => constraint.id));
    while (used.has(`manual-${serial}`)) serial += 1;
    const constraint: NavigatorConstraint = {
      id: `manual-${serial}`,
      field: entry.field,
      operator: entry.operators[0],
      value: defaultConstraintValue(entry),
      unit: entry.unit,
      kind: entry.kind,
      locked: false,
      confirmed: false,
      label: entry.label,
      source_text: null,
    };
    setPlan({ ...plan, constraints: [...plan.constraints, constraint] });
  }

  function updateConstraint(id: string, patch: Partial<NavigatorConstraint>) {
    if (!plan) return;
    setPlan({
      ...plan,
      constraints: plan.constraints.map((constraint) => (
        constraint.id === id ? { ...constraint, ...patch } : constraint
      )),
    });
    setEvaluation(null);
    setRecoveries(null);
  }

  function applyRecovery(path: RelaxationPath) {
    if (!plan) return;
    const changes = new Map(path.changes.map((change) => [change.constraint_id, change]));
    const nextPlan = {
      ...plan,
      constraints: plan.constraints.map((constraint) => {
        const change = changes.get(constraint.id);
        return change ? {
          ...constraint,
          operator: change.new_operator,
          value: change.new_value,
        } : constraint;
      }),
    };
    setPlan(nextPlan);
    void execute(nextPlan);
  }

  return (
    <div className="navigator-shell">
      <header className="topbar navigator-topbar">
        <div className="brand-lockup">
          <span className="dot" />
          <span className="brand">MatterGraph</span>
          <span className="mode">Constraint-to-Crystal Navigator</span>
        </div>
        <div className="topbar-actions">
          <span>{registry ? `${registry.record_count.toLocaleString()} frozen records` : "loading index"}</span>
          <button className="text-button" type="button" onClick={onReturnDemo}>Evidence demo</button>
        </div>
      </header>

      <main className="navigator-main">
        <section className="navigator-hero">
          <div>
            <p className="eyebrow">ASK → CONFIRM → NAVIGATE → INSPECT → RECOVER</p>
            <h1>Navigate a frozen public crystal index.</h1>
            <p className="subhead">
              Language proposes a reviewable plan. A deterministic engine owns filtering,
              exclusions, missing evidence, and index-relative recovery.
            </p>
          </div>
          <div className="navigator-index-card">
            <span className="eval-label">Frozen evidence surface</span>
            <strong>{registry?.index_id ?? "loading"}</strong>
            <span>{registry?.scope ?? "Resolving registry…"}</span>
            <code>{registry?.digest.slice(0, 16) ?? "—"}</code>
          </div>
        </section>

        {error ? <div className="api-offline" role="alert"><strong>Navigator stopped safely.</strong><p>{error}</p></div> : null}

        <section className="panel navigator-request-panel">
          <div className="panel-heading"><span>Natural-language requirement</span><span>N1</span></div>
          <label htmlFor="navigator-request">Describe the indexed material requirements</label>
          <textarea
            id="navigator-request"
            value={request}
            onChange={(event) => setRequest(event.target.value)}
            rows={4}
            maxLength={2000}
          />
          <div className="navigator-request-actions">
            <p>Raw prompts and provider outputs are not persisted.</p>
            <button className="primary-button" type="button" disabled={!registry || loading !== null} onClick={() => void interpret()}>
              {loading === "interpret" ? "Interpreting…" : "Compile request"}
            </button>
          </div>
        </section>

        {plan ? (
          <section className="panel navigator-plan-panel">
            <div className="panel-heading"><span>Confirmed constraint plan</span><span>N2</span></div>
            <div className="navigator-plan-toolbar">
              <span>{plan.constraints.length} proposed · {plan.unresolved_constraints.length} unresolved</span>
              <div>
                <button type="button" onClick={() => setPlan({
                  ...plan,
                  constraints: plan.constraints.map((constraint) => ({ ...constraint, confirmed: true })),
                })}>Confirm all interpretations</button>
                <button className="primary-button" type="button" disabled={loading !== null} onClick={() => void execute()}>
                  {loading === "evaluate" ? "Executing…" : "Execute confirmed plan"}
                </button>
              </div>
            </div>
            <div className="navigator-add-constraint">
              <label htmlFor="navigator-add-field">Add registry constraint</label>
              <select id="navigator-add-field" value={fieldToAdd} onChange={(event) => setFieldToAdd(event.target.value)}>
                {registry?.entries.filter((entry) => entry.executable).map((entry) => (
                  <option key={entry.field} value={entry.field}>{entry.label}</option>
                ))}
              </select>
              <button type="button" onClick={addConstraint}>Add constraint</button>
              {liveUpdates ? <span className="tag boundary">live recompute on</span> : null}
            </div>
            <div className="navigator-chips">
              {plan.constraints.map((constraint) => (
                <ConstraintChip
                  key={constraint.id}
                  constraint={constraint}
                  registryEntry={registry?.entries.find((entry) => entry.field === constraint.field)}
                  onChange={(patch) => updateConstraint(constraint.id, patch)}
                  onRemove={() => setPlan({
                    ...plan,
                    constraints: plan.constraints.filter((item) => item.id !== constraint.id),
                  })}
                />
              ))}
            </div>
            {plan.unresolved_constraints.length ? (
              <div className="navigator-unresolved">
                {plan.unresolved_constraints.map((item) => (
                  <article key={item.id}>
                    <span className="tag warn">Not executable</span>
                    <strong>{item.text}</strong>
                    <p>{item.reason}</p>
                    <button type="button" onClick={() => setPlan({
                      ...plan,
                      unresolved_constraints: plan.unresolved_constraints.filter((entry) => entry.id !== item.id),
                    })}>Remove after confirmation</button>
                    <button type="button" onClick={() => downloadFollowUp(item.text, item.reason, plan.index_id)}>Export follow-up request</button>
                  </article>
                ))}
              </div>
            ) : null}
          </section>
        ) : null}

        {evaluation ? (
          <>
            <section className={`navigator-outcome ${evaluation.state}`} aria-live="polite">
              <div><span className="eval-label">Deterministic outcome</span><strong>{stateLabel(evaluation.state)}</strong></div>
              <div><span>definite passes</span><strong>{evaluation.feasible_count}</strong></div>
              <div><span>evidence unknown</span><strong>{evaluation.indeterminate_count}</strong></div>
              <div><span>indexed records</span><strong>{evaluation.total_count}</strong></div>
              <p>{stateDetail(evaluation.state, evaluation.index_id)}</p>
              {replayId ? <code className="navigator-replay-id">private replay · {replayId.slice(0, 22)}…</code> : null}
            </section>

            {evaluation.issues.length ? (
              <section className="panel navigator-issues">
                <div className="panel-heading"><span>Plan issues</span><span>N3</span></div>
                {evaluation.issues.map((issue) => <p key={`${issue.code}-${issue.message}`}><strong>{issue.code}</strong> · {issue.message}</p>)}
              </section>
            ) : null}

            {evaluation.candidates.length ? (
              <section className="navigator-results-grid">
                <div className="panel">
                  <div className="panel-heading"><span>Live feasible design space</span><span>N4</span></div>
                  <NavigatorDesignSpace candidates={evaluation.candidates} selectedId={selectedId} onSelect={setSelectedId} />
                </div>
                <div className="panel navigator-inspector">
                  <div className="panel-heading"><span>Why this candidate?</span><span>N5</span></div>
                  <CandidateInspector candidate={selectedCandidate} />
                </div>
              </section>
            ) : null}

            {recoveries ? <RecoveryPanel recoveries={recoveries} onApply={applyRecovery} /> : null}

            {evaluation.candidates.length ? (
              <section className="panel navigator-table-panel">
                <div className="panel-heading"><span>Accessible candidate evidence</span><span>N6</span></div>
                <CandidateTable candidates={visibleCandidates} selectedId={selectedId} onSelect={setSelectedId} />
              </section>
            ) : null}
          </>
        ) : null}

        {selectedId ? (
          <section className="panel navigator-structure-panel">
            <div className="panel-heading"><span>Source-backed crystal inspection · {selectedId}</span><span>N7</span></div>
            {loading === "material" ? <p className="empty-note">Validating structure contract…</p> : null}
            {material ? (
              <Suspense fallback={<p className="empty-note">Loading atoms-only renderer…</p>}>
                <NavigatorCrystalViewer material={material} />
              </Suspense>
            ) : null}
          </section>
        ) : null}
      </main>
    </div>
  );
}

function ConstraintChip({
  constraint,
  registryEntry,
  onChange,
  onRemove,
}: {
  constraint: NavigatorConstraint;
  registryEntry: RegistryEntry | undefined;
  onChange: (patch: Partial<NavigatorConstraint>) => void;
  onRemove: () => void;
}) {
  return (
    <article className={`navigator-chip ${constraint.kind} ${constraint.confirmed ? "confirmed" : "pending"}`}>
      <div><span>{constraint.kind.replace("_", " ")}</span><strong>{constraint.label ?? constraint.field}</strong></div>
      <label>Operator
        <select value={constraint.operator} onChange={(event) => onChange({ operator: event.target.value as NavigatorConstraint["operator"] })}>
          {(registryEntry?.operators ?? [constraint.operator]).map((operator) => <option key={operator}>{operator}</option>)}
        </select>
      </label>
      <label>Value
        <input
          value={displayValue(constraint.value)}
          onChange={(event) => onChange({ value: parseValue(event.target.value, constraint.value) })}
        />
      </label>
      <div className="navigator-chip-actions">
        <label><input type="checkbox" checked={constraint.confirmed} onChange={(event) => onChange({ confirmed: event.target.checked })} />confirmed</label>
        <label><input type="checkbox" checked={constraint.locked} onChange={(event) => onChange({ locked: event.target.checked })} />locked</label>
        <button type="button" onClick={onRemove}>remove</button>
      </div>
    </article>
  );
}

function CandidateInspector({ candidate }: { candidate: CandidateEvaluation | null }) {
  if (!candidate) return <p className="empty-note">Select a candidate from the map or table.</p>;
  return (
    <div>
      <div className={`eval-output ${candidate.status === "pass" ? "pass" : candidate.status === "fail" ? "fail" : "warn"}`}>
        <span className="eval-label">{candidate.material_id}</span>
        <strong>{candidate.formula}</strong>
        <span>{candidate.status}</span>
      </div>
      <div className="navigator-checks">
        {candidate.checks.map((check) => (
          <div key={check.constraint_id} className={check.status}>
            <span>{check.status}</span><p>{check.message}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function RecoveryPanel({ recoveries, onApply }: { recoveries: RelaxationResult; onApply: (path: RelaxationPath) => void }) {
  const hasAny = recoveries.physical_relaxations.length || recoveries.quality_relaxations.length || recoveries.evidence_recoveries.length || recoveries.capability_recoveries.length;
  if (!hasAny) return null;
  return (
    <section className="panel navigator-recovery-panel">
      <div className="panel-heading"><span>Bounded recovery workspace</span><span>N5R</span></div>
      {recoveries.physical_relaxations.length ? <RecoveryGroup title="Physical / categorical changes" paths={recoveries.physical_relaxations} onApply={onApply} /> : null}
      {recoveries.quality_relaxations.length ? <RecoveryGroup title="Calculation-quality changes · admit less-converged structures" paths={recoveries.quality_relaxations} onApply={onApply} /> : null}
      {[...recoveries.evidence_recoveries, ...recoveries.capability_recoveries].map((action) => (
        <article className="navigator-recovery-action" key={action.code}><strong>{action.label}</strong><p>{action.detail}</p></article>
      ))}
      <p className="boundary-note">{recoveries.scientific_boundary}</p>
    </section>
  );
}

function RecoveryGroup({ title, paths, onApply }: { title: string; paths: RelaxationPath[]; onApply: (path: RelaxationPath) => void }) {
  return (
    <div className="navigator-recovery-group">
      <h3>{title}</h3>
      <div className="navigator-recovery-grid">
        {paths.map((path) => (
          <article key={path.path_id}>
            <span className="tag boundary">relative to {path.relative_to}</span>
            {path.changes.map((change) => <p key={change.constraint_id}>{change.message}</p>)}
            <strong>Recovers {path.recovered_count} indexed candidate{path.recovered_count === 1 ? "" : "s"}</strong>
            <button type="button" onClick={() => onApply(path)}>Apply and recompute</button>
          </article>
        ))}
      </div>
    </div>
  );
}

function CandidateTable({ candidates, selectedId, onSelect }: { candidates: CandidateEvaluation[]; selectedId: string | null; onSelect: (id: string) => void }) {
  const visible = candidates.slice(0, 200);
  return (
    <div className="navigator-table-wrap">
      {candidates.length > visible.length ? <p className="boundary-note">Showing the first 200 deterministically ordered rows; all {candidates.length.toLocaleString()} points remain in the Canvas view.</p> : null}
      <table className="data-table navigator-candidate-table">
        <caption>Candidate status, values, and selection controls</caption>
        <thead><tr><th>Candidate</th><th>Formula</th><th>Status</th><th>Density</th><th>Sites</th><th>Max force</th></tr></thead>
        <tbody>
          {visible.map((candidate) => (
            <tr key={candidate.material_id} className={candidate.material_id === selectedId ? "selected" : undefined}>
              <td><button type="button" onClick={() => onSelect(candidate.material_id)}>{candidate.material_id}</button></td>
              <td>{candidate.formula}</td>
              <td><span className={`tag ${candidate.status}`}>{candidate.status}</span></td>
              <td>{formatProperty(candidate.properties.density)}</td>
              <td>{formatProperty(candidate.properties.nsites)}</td>
              <td>{formatProperty(candidate.properties.maximum_force_norm)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function stateLabel(state: EvaluationResult["state"]): string {
  return ({
    feasible_set: "Feasible indexed set",
    plan_conflict: "Plan conflict",
    index_capability_mismatch: "Index capability mismatch",
    evidence_unknown: "Required evidence unknown",
    no_feasible_set: "No feasible indexed candidate",
  })[state];
}

function stateDetail(state: EvaluationResult["state"], indexId: string): string {
  return ({
    feasible_set: `At least one record definitely satisfies every confirmed constraint in ${indexId}.`,
    plan_conflict: "Resolve the contradictory plan before searching.",
    index_capability_mismatch: "The request is logically valid but cannot be executed by this frozen index.",
    evidence_unknown: "Missing required values could change eligibility; unknown is not treated as failure.",
    no_feasible_set: `Every record in ${indexId} can be classified and none passes.`,
  })[state];
}

function displayValue(value: ConstraintValue): string {
  return Array.isArray(value) ? value.join(", ") : String(value);
}

function parseValue(value: string, previous: ConstraintValue): ConstraintValue {
  if (Array.isArray(previous)) return value.split(",").map((item) => item.trim()).filter(Boolean);
  if (typeof previous === "number") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : previous;
  }
  if (typeof previous === "boolean") return value.toLowerCase() === "true";
  return value;
}

function defaultConstraintValue(entry: RegistryEntry): ConstraintValue {
  if (entry.field === "elements") return [];
  if (entry.supported_values?.length) {
    if (entry.supported_values[0] === "true") return true;
    return entry.supported_values[0];
  }
  if (entry.bounds) return entry.bounds[0];
  return "";
}

function formatProperty(value: unknown): string {
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(4);
  return value === null || value === undefined ? "unknown" : String(value);
}

function downloadFollowUp(requirement: string, reason: string, indexId: string) {
  const payload = JSON.stringify({ requirement, reason, index_id: indexId, status: "required_follow_up" }, null, 2);
  const url = URL.createObjectURL(new Blob([payload], { type: "application/json" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "mattergraph-evidence-gap.json";
  anchor.click();
  URL.revokeObjectURL(url);
}

function errorMessage(reason: unknown): string {
  return reason instanceof Error ? reason.message : String(reason);
}
