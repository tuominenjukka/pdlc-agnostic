# build-log schema

**Prefix:** `BU`
**Owner phase:** `deliver` (also records inbound `discovery_to_delivery` HITL gate events written by the orchestrator)
**Purpose:** Append-only record of every build action: artifact scaffold created, component added or modified, artifact exported, repo commit, PR opened, PR merged, HITL gate opened or closed. The concrete artifact kind is whatever the bound architecture adapter's `build_artifact_kind` declares.

## When to append

Append on every distinct build action. One event, one row. Granularity should be enough that an outside reviewer can reconstruct what the delivery-agent did without reading the codebase.

## Log-specific columns

In addition to the universal columns:

| Column | Type | Required | Notes |
|---|---|---|---|
| `event` | enum | yes | `scaffold_created`, `component_added`, `component_modified`, `artifact_exported`, `commit`, `pr_opened`, `pr_updated`, `pr_merged`, `dependency_added`, `hitl_gate_opened`, `hitl_gate_closed`, `hitl_gate_timeout`, `hitl_gate_failed_closed`, `hitl_gate_paused`. The architecture adapter may map these onto its own artifact vocabulary, but the event set is fixed. |
| `hitl_gate_id` | string | no | Set on any `hitl_gate_*` event. Format `GT-{gate_type}-{date}-{nanoid8}`. |
| `hitl_decision` | enum | no | Set on `hitl_gate_closed`. One of `approve`, `reject`, `pause`, `timeout`, `failed_closed`. |
| `artifact_ref` | string | no | Path or URL to the produced artifact (e.g., the exported build artifact, repo file path). |
| `commit_sha` | string | no | Git SHA when event is commit/pr-related. |
| `pr_url` | string | no | GitHub PR URL when applicable. |
| `adapter_id` | string | no | The architecture adapter that produced this artifact (matches the deployment-log `adapter_id`). |
| `adapter_artifact_id` | string | no | Adapter-specific internal artifact id, when applicable (for example a workflow id on a deterministic-workflow adapter, an agent-definition id on an agentic adapter). |
| `summary` | string | yes | One-sentence human-readable description. |
| `related_log_refs` | string | no | Links to back-log items being delivered. |

## Example append

```
pdlc-log append build-log {
  project: "lead-routing-suite",
  agent_id: "territory-router",
  phase: "deliver",
  actor: "delivery-agent",
  session_ref: "claude-session-xyz",
  event: "artifact_exported",
  adapter_id: "workflow-multitenant",
  adapter_artifact_id: "territory-router",
  artifact_ref: "github://acme/lead-routing-suite/flows/territory-router.json",
  commit_sha: "8f3e9c1",
  pr_url: "https://github.com/acme/lead-routing-suite/pull/42",
  summary: "Exported territory-router v1 with country-to-territory mapping and CRM upsert.",
  related_log_refs: "back-log:BL-20260519-7fk2a9c1"
}
```
