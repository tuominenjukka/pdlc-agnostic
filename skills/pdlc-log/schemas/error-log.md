# error-log schema

**Prefix:** `EL`
**Owner phase:** `evolve`
**Purpose:** Persist errors surfaced by the bound architecture's observability stack (whatever the adapter declares in `metrics_sources` plus its alerting and audit surfaces). Used by `pdlc-deploy` for guardrail evaluation and by the orchestrator to open back-log regressions.

## When to append

Append on:
- Any alert that fires through the architecture's alerting surface (corresponds to the on-call alert set defined by the bound adapter).
- Any managed artifact execution recorded as `failed` or `error` for a managed agent.
- Any audit row with `success=false` that breaches a frequency threshold (default >10 in 1h per tenant).
- Operator-flagged errors during triage.

Do not mirror every single low-severity error. Aggregate where possible.

## Log-specific columns

| Column | Type | Required | Notes |
|---|---|---|---|
| `source` | enum | yes | Adapter-agnostic categories: `alerting` (an alert from the adapter's alerting surface), `execution` (a failed managed-artifact execution record), `usage_audit` (an audit row with success=false), `secrets` (a secrets/credential store audit anomaly), `control_surface` (an error from the adapter's control/deploy surface), `operator`. The concrete products behind each category come from the bound adapter's `metrics_sources` and are recorded in `evidence_ref`. |
| `source_detail` | string | no | The concrete adapter-provided source, e.g., `prometheus`, `workflow_executions`, `langfuse`, `sentry`. Optional; the neutral core keys on `source`. |
| `severity` | enum | yes | `low`, `medium`, `high`, `critical` |
| `error_type` | string | yes | Exception class, node/step error code, HTTP status, or alert name. |
| `message` | string | yes | Truncated to 500 chars; full message in `evidence_ref`. |
| `evidence_ref` | string | no | Dashboard panel URL, alert URL, execution id, or audit row reference. |
| `correlation_id` | string | no | Trace id linking error to specific user event. |
| `occurrence_count` | int | yes | Default 1. Use for batched aggregations. |
| `first_seen` | ISO 8601 | yes | When this error type first appeared (for batched). |
| `last_seen` | ISO 8601 | yes | When this error type last appeared (for batched). |
| `status` | enum | yes | `new`, `triaged`, `linked_to_backlog`, `resolved` |
| `linked_back_log_id` | string | no | Set when status moves to `linked_to_backlog`. |
| `wave_id` | string | no | If error is tied to an active wave. |
| `related_log_refs` | string | no | |

## Example append

```
pdlc-log append error-log {
  project: "lead-routing-suite",
  agent_id: "territory-router",
  customer: "acme",
  phase: "evolve",
  actor: "evolve-agent",
  session_ref: "claude-session-xyz",
  source: "execution",
  source_detail: "workflow_executions",
  severity: "high",
  error_type: "CrmAuthError",
  message: "INVALID_SESSION_ID at upsert step, 47 occurrences in 12 minutes against acme tenant.",
  evidence_ref: "exec://tenant-acme/executions?status=error&since=2026-05-19T14:00Z",
  occurrence_count: 47,
  first_seen: "2026-05-19T14:08:00Z",
  last_seen: "2026-05-19T14:20:00Z",
  status: "new",
  wave_id: "lead-routing-suite-1.2.0-w1"
}
```
