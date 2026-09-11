# deployment-log schema

**Prefix:** `DL`
**Owner phase:** `deliver` (deploy step) + `evolve` (wave decisions and rollbacks)
**Purpose:** Wave-by-wave record of cohort assignment, baseline metrics, guardrail evaluation, and rollback events. The deployment-log is the source of truth for `pdlc-deploy`.

This is the **neutral** deployment-log: one schema for every architecture, plus an adapter namespace. It replaces the per-architecture forked schemas. The bound architecture adapter (`adapter_id`) and shipping adapter (`shipping_id`) determine what a wave event means mechanically; product-specific fields live under `adapter_ext`, never as top-level columns. The `[v2]` extension that defines `adapter_id`, `shipping_id`, and `adapter_ext` is in `../../../schemas/deployment-log-ext.md`. For cross-architecture migrations, the per-tenant ledger lives in the companion `../../../schemas/migration-log.md`.

## Deploy mechanism

A wave's deploy and rollback mechanism is not hardcoded here. It comes from the bound shipping adapter's `rollback_model` (`revert` or `stop-routing`) and is executed through the architecture adapter's contract operations `deploy`, `rollback`, `assign_cohort`, and `fetch_metrics`. Whatever the adapter does under the hood (an image bump, an entitlement flip, a feature-flag percentage, a strangler route) is recorded in `adapter_ext`, with the adapter-agnostic outcome in the top-level columns. See ADAPTER-CONTRACT.md and SHIPPING-CONTRACT.md.

## When to append

Append a new row for each of these events:
- `wave_planned` (before any deploy in the wave): captures baseline + cohort.
- `wave_deployed`: cohort actually receives the new version.
- `wave_observed`: end-of-window check, records guardrail evaluation.
- `wave_promoted`: cohort cleared to expand to next wave size.
- `wave_paused`: wave is paused. Either yellow guardrail awaiting HITL, or the brief transition marker before an auto-rollback on red.
- `wave_rolled_back`: red guardrail or operator-triggered rollback.
- `wave_completed`: 100% wave passed observation.

Same `id` chains a wave's events using `wave_id` (separate from row `id`).

## Log-specific columns

| Column | Type | Required | Notes |
|---|---|---|---|
| `event` | enum | yes | One of the wave events listed above, or one of the gate events: `hitl_gate_opened`, `hitl_gate_closed`, `hitl_gate_timeout`, `hitl_gate_failed_closed`, `hitl_gate_paused`. |
| `hitl_gate_id` | string | no | Set on any `hitl_gate_*` event. |
| `hitl_decision` | enum | no | Set on `hitl_gate_closed`. One of `approve`, `reject`, `pause`, `timeout`, `failed_closed`. |
| `adapter_id` | string | yes | The architecture adapter that produced this event. Replaces hardcoded knowledge of the deploy mechanism. |
| `shipping_id` | string | yes | The shipping adapter driving the wave. |
| `deploy_ref` | string | no | Adapter-returned reference for the `deploy` call that initiated this wave event. Phase 0: leave empty and rely on the runbook reference instead. |
| `runbook_ref` | string | no | Path to the runbook used (Phase 0 only, before the adapter's control surface exists). |
| `observed_pause_seconds_p95` | int | no | Set on `wave_observed`, when the adapter reports a per-recipient deploy pause. Adapter-specific; flag if above the adapter's declared threshold. |
| `wave_id` | string | yes | `{project}-{version}-w{1..4}`. Project-scoped because the deployable artifact is per-project. Stable across events in the same wave. |
| `version` | string | yes | Artifact version being deployed. |
| `previous_version` | string | yes | What we'd revert to. |
| `cohort_size_pct` | int | yes | 10, 30, 50, or 100. |
| `cohort_size_n` | int | no | Absolute number of recipients. |
| `cohort_ref` | string | yes | Adapter-resolved reference for the cohort of entitled recipients returned by `assign_cohort`. Do not inline customer ids here. |
| `success_metric_baseline` | json | yes | `{error_rate: 0.014, conv_rate: 0.31, sentiment: 72}` |
| `success_metric_current` | json | no | Same shape. Populated on `wave_observed`. |
| `guardrail_decision` | enum | no | `green`, `yellow`, `red` |
| `guardrail_breach` | string | no | Which guardrail(s) breached, e.g., `error_rate, sentiment`. |
| `rollback_triggered` | bool | no | |
| `rollback_reason` | string | no | |
| `auto_promote` | bool | yes | Read from `pdlc/guardrails.yaml`. |
| `observation_window_hours` | int | yes | Default 24 (waves 1-3), 48 (wave 4). |
| `adapter_ext` | json | no | Adapter-specific fields that used to be top-level columns, now namespaced. Examples below. |
| `related_log_refs` | string | no | `build-log` artifact, `test-log` pre-deploy run. |

## adapter_ext examples

These are illustrative of what an adapter may carry; they are **adapter-provided**, not part of the neutral core.

workflow-multitenant (image rollout):
```json
{ "mode": "image_rollout",
  "image_tag": "tenant-image:1.2.0",
  "previous_image_tag": "tenant-image:1.1.4",
  "k8s_deployment_refs": ["tenant-acme/worker"],
  "deploy_call_ref": "https://control-plane.example/api/v1/...",
  "observed_pause_seconds_p95": 22 }
```

workflow-multitenant (entitlement flip):
```json
{ "mode": "entitlement_flip", "entitlement_id": "feature.territory-routing.v2" }
```

webapp-flags (feature flag):
```json
{ "flag_key": "recipe-search", "rollout_pct": 30, "deploy_ref": "hosting://..." }
```

## Backfill

Existing rows from an earlier per-architecture schema get `adapter_id` inferred from their current columns (image columns imply workflow-multitenant, flag columns imply webapp-flags), and their old top-level columns move under `adapter_ext`. This keeps existing projects working with no behavior change.

## Wave_id stability

A wave's planned -> deployed -> observed -> promoted or rolled-back sequence shares `wave_id` but each event is a separate row with its own `id` and `timestamp`. The dashboard query is `SELECT * FROM deployment-log WHERE wave_id = X ORDER BY created_at`.

## Example append

```
pdlc-log append deployment-log {
  project: "lead-routing-suite",
  agent_id: "territory-router",
  phase: "deliver",
  actor: "delivery-agent",
  session_ref: "claude-session-xyz",
  event: "wave_planned",
  wave_id: "lead-routing-suite-1.2.0-w1",
  version: "1.2.0",
  previous_version: "1.1.4",
  adapter_id: "workflow-multitenant",
  shipping_id: "tenant-wave",
  cohort_size_pct: 10,
  cohort_size_n: 23,
  cohort_ref: "cohort://lead-routing-suite-1.2.0-wave1",
  success_metric_baseline: {error_rate: 0.014, conv_rate: 0.31, sentiment: 72},
  auto_promote: false,
  observation_window_hours: 24,
  adapter_ext: {
    mode: "image_rollout",
    image_tag: "tenant-image:1.2.0",
    previous_image_tag: "tenant-image:1.1.4",
    k8s_deployment_refs: ["tenant-acme/worker", "tenant-globex/worker", "tenant-initech/worker"]
  },
  related_log_refs: "build-log:BU-20260519-7fk2a9c1, test-log:TL-20260519-9k3p2m4n"
}
```
