# adapt-log schema

**Prefix:** `AL`
**Owner phase:** `meta`
**Scope:** Global (single store across all projects).
**Purpose:** System-wide record of failures, retries, pivots, escalations, and meta-builder self-improvement notes. Reading the adapt-log tells you where the meta-builder hit friction and how it adapted.

## When to append

Append:
- Every retry attempt (with `retry_count`).
- Every pivot (when retry budget exhausted and the agent switched approach).
- Every escalation (retries + pivots exhausted, operator notified).
- Every canonical-store write failure (from `pdlc-log` reconciliation queue).
- Every schema gap encountered (an agent wanted to write a column not in the schema).
- Every concurrent-write conflict.
- Every operator-noted improvement suggestion ("the orchestrator should also do X").

## Log-specific columns

In addition to the universal columns. Note: `project` is set to `_meta` for purely meta-builder entries that are not scoped to a specific project. `customer` is set only when a tenant-specific failure occurred (rare in adapt-log).

| Column | Type | Required | Notes |
|---|---|---|---|
| `scope` | enum | yes | `project`, `meta_builder`, `tooling`, `schema`, `entitlement` |
| `failure_type` | string | yes | `retry`, `pivot`, `escalation`, `drive_write_failed`, `cache_write_failed`, `schema_gap`, `concurrent_write`, `connector_unavailable`, `improvement_suggestion` |
| `attempted_action` | string | yes | What we were trying to do. |
| `retry_count` | int | no | Defaults to 0. |
| `pivot_taken` | string | no | The alternative approach attempted. |
| `resolution` | enum | yes | `resolved`, `unresolved`, `escalated`, `deferred` |
| `resolution_summary` | string | no | How it was resolved, if at all. |
| `operator_notified` | bool | yes | Did we ping the operator? |
| `notification_ref` | string | no | URL or message id of the notification. |
| `hitl_gate_id` | string | no | Set when this adapt-log row is tied to a HITL gate (pivot_approval, schema_extension, rollback_approval, architecture_decision, tenant_migration_consent, decommission_approval). |
| `hitl_decision` | enum | no | Set when this row closes a gate. One of `approve`, `reject`, `pause`, `timeout`, `failed_closed`. |
| `related_log_refs` | string | no | Pointers to the project-scoped entries this relates to. |

## Lifecycle of an escalation

A single failure usually produces multiple adapt-log rows over time:

1. First retry: `failure_type: retry`, `retry_count: 1`, `resolution: unresolved`.
2. Second retry: `failure_type: retry`, `retry_count: 2`, `resolution: unresolved`.
3. Pivot: `failure_type: pivot`, `pivot_taken: <new approach>`, `resolution: unresolved`.
4. Pivot retries: similar.
5. Escalation: `failure_type: escalation`, `operator_notified: true`, `notification_ref: <message-ref>`, `resolution: escalated`.
6. Operator resolves: append final row with `resolution: resolved` and `resolution_summary: <what fixed it>`.

Each row is a distinct event with its own `id` and timestamp. They are tied together by sharing `related_log_refs` and by being a continuous sequence for the same `attempted_action` and `customer`.

## Example append

```
pdlc-log append adapt-log {
  project: "lead-routing-suite",
  agent_id: "territory-router",
  phase: "meta",
  actor: "orchestrator",
  session_ref: "claude-session-xyz",
  scope: "project",
  failure_type: "pivot",
  attempted_action: "Deploy wave 2 (30%) after wave 1 green",
  retry_count: 0,
  pivot_taken: "Wait for operator to clear yellow guardrail before promoting",
  resolution: "unresolved",
  operator_notified: true,
  notification_ref: "slack://C0123/p1716130800",
  related_log_refs: "deployment-log:DL-20260519-7fk2a9c1"
}
```
