# user-behavior-log schema

**Prefix:** `UB`
**Owner phase:** `evolve`
**Purpose:** Persist per-tenant usage and behavior observations relevant to a deployed agent. The evolve-agent reads the bound adapter's `metrics_sources` on a schedule and appends salient events. Used by `pdlc-deploy` for guardrail evaluation.

## When to append

Append:
- On every scheduled evolve-agent metric pull (typically hourly during an observation window, daily otherwise).
- On manual operator queries that surface an anomaly worth persisting.

Do not mirror every metric. Persist aggregates and named events tied to a deployment.

## Log-specific columns

| Column | Type | Required | Notes |
|---|---|---|---|
| `source` | enum | yes | Adapter-agnostic categories: `metrics_store` (usage/cost rows: tokens, latency, cost, success), `platform_metrics` (request rate, error rate, latency percentiles), `execution_records` (managed-artifact run records), `operator` (operator-recorded observation). The concrete products behind each come from the bound adapter's `metrics_sources` and may be noted in `tags`. |
| `metric_kind` | enum | yes | `token_spend`, `latency_p50`, `latency_p95`, `latency_p99`, `request_rate`, `error_rate`, `success_rate`, `budget_utilization_pct`, `cost`, `task_completion`, `human_intervention`, `cost_per_task`, `anomaly` |
| `metric_name` | string | yes | Concrete metric identifier. Examples: `llm_calls_total`, `latency_p95_ms`, `cost_total`, `task_success_rate`. |
| `value` | number | yes | Raw value for this observation. |
| `unit` | string | no | `count`, `rate`, `seconds`, etc. |
| `window_start` | ISO 8601 | yes | Observation window start. |
| `window_end` | ISO 8601 | yes | Observation window end. |
| `cohort_ref` | string | no | Wave cohort this applies to, when relevant. |
| `wave_id` | string | no | When tied to a deployment-log wave. |
| `baseline_value` | number | no | Pre-deploy baseline for comparison. |
| `delta_pct` | number | no | (value - baseline) / baseline, signed. |
| `tags` | string | no | Free-form, comma-separated. |
| `related_log_refs` | string | no | |

## Example append

```
pdlc-log append user-behavior-log {
  project: "lead-routing-suite",
  agent_id: "territory-router",
  customer: "acme",
  phase: "evolve",
  actor: "evolve-agent",
  session_ref: "claude-session-xyz",
  source: "metrics_store",
  metric_kind: "cost",
  metric_name: "eur_spend_24h",
  value: 4.21,
  unit: "EUR",
  window_start: "2026-05-18T00:00:00Z",
  window_end: "2026-05-19T00:00:00Z",
  cohort_ref: "cohort://lead-routing-suite-1.2.0-wave1",
  wave_id: "lead-routing-suite-1.2.0-w1",
  baseline_value: 3.85,
  delta_pct: 0.094,
  tags: "wave1, observation-day-1, metrics_store=timescaledb"
}
```
