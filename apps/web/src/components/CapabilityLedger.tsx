import type { Capability, CapabilityStatus } from "../types/material";

const groups: Array<{
  status: CapabilityStatus;
  title: string;
  note: string;
}> = [
  {
    status: "demo_ready",
    title: "Exercised here",
    note: "Implemented and used by this deterministic walkthrough.",
  },
  {
    status: "sdk_ready",
    title: "Available in the SDK",
    note: "Implemented and tested, but intentionally not called live on stage.",
  },
  {
    status: "stub",
    title: "Explicit stubs",
    note: "Extension points that fail honestly instead of pretending to run.",
  },
  {
    status: "out_of_scope",
    title: "Public boundary",
    note: "Capabilities the open-source baseline does not claim.",
  },
];

export function CapabilityLedger({ capabilities }: { capabilities: Capability[] }) {
  return (
    <div className="capability-ledger">
      {groups.map((group) => {
        const items = capabilities.filter((capability) => capability.status === group.status);
        return (
          <article className="capability-group" key={group.status}>
            <div className="capability-group-header">
              <div>
                <h3>{group.title}</h3>
                <p>{group.note}</p>
              </div>
              <span className={`tag ${statusClass(group.status)}`}>{items.length}</span>
            </div>
            <div className="capability-list">
              {items.map((capability) => (
                <div className="capability-item" key={capability.id}>
                  <strong>{capability.label}</strong>
                  <span>{capability.evidence}</span>
                  {capability.optional_dependency ? (
                    <small>optional: {capability.optional_dependency}</small>
                  ) : null}
                  {capability.boundary ? <small>{capability.boundary}</small> : null}
                </div>
              ))}
            </div>
          </article>
        );
      })}
    </div>
  );
}

function statusClass(status: CapabilityStatus): "pass" | "warn" | "fail" | "" {
  if (status === "demo_ready") return "pass";
  if (status === "sdk_ready") return "";
  if (status === "stub") return "warn";
  return "fail";
}
