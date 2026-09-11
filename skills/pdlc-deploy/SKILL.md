---
name: pdlc-deploy
description: Plan, execute, observe, promote, and roll back wave rollouts for any architecture-agnostic PDLC project. The wave loop is fixed by the governance spine; the mechanism is delegated to the bound architecture adapter's contract operations (assign_cohort, deploy, rollback, fetch_metrics) and the bound shipping adapter's step plan. Use whenever the orchestrator is ready to ship a new project version, when an observation window has elapsed and guardrails need evaluation, or when a regression requires rollback. Every state change flows through pdlc-log; every operator-required decision flows through pdlc-hitl-gate. Trigger proactively whenever the delivery-agent finishes test coverage, whenever the evolve-agent is asked to evaluate a wave, and whenever the orchestrator decides to advance, hold, or revert a rollout.
---

# pdlc-deploy

The neutral wave-rollout skill. Owns the deploy step of PDLC Deliver and the wave-by-wave decision loop of PDLC Evolve. The loop is invariant; the mechanism is whatever the bound architecture adapter implements behind the contract. This skill never names a specific product. It calls only `adapter.assign_cohort`, `adapter.deploy`, `adapter.rollback`, and `adapter.fetch_metrics`, and reads the bound shipping adapter's `step_plan`, `rollback_model`, and `observation_windows`.

## Reading the binding (per-component)

Resolve the bound adapters for the component being acted on, then fall back:

1. If `.pdlc/components/` exists, read the per-component binding for the component under deploy: `.pdlc/components/{component}/adapter.txt` (architecture `adapter_id@version`), `.pdlc/components/{component}/shipping.txt` (shipping `shipping_id@version`), and `.pdlc/components/{component}/shipping-next.txt` when a re-pairing is staged. The component is supplied by the caller (orchestrator) with the back-log item; default to the single declared component when only one exists.
2. If `.pdlc/components/` does NOT exist, read the top-level `.pdlc/adapter.txt` and `.pdlc/shipping.txt` (the single-component case).

A wave acts on exactly one component's binding. A multi-component rollout is several `pdlc-deploy` runs, one per component, each reading that component's binding. Every `deployment-log` row carries `adapter_id` and `shipping_id` for the binding it used, so mixed-adapter projects log without ambiguity.

## When to invoke

Invoke whenever:

1. The delivery-agent has completed tests for a new version and the orchestrator decides to ship.
2. An observation window has elapsed on a live wave and guardrails need evaluation.
3. Metrics, errors, or feedback exceed a guardrail threshold mid-wave.
4. An operator requests a rollback.
5. The orchestrator advances a green wave to the next cohort size.

Do not invoke for deploys the bound architecture handles itself outside the cohort model (the adapter declares these); those have no cohort to slice.

## Architecture context

The architecture invariants live in the bound adapter's manifest and its `reference_architecture`. Read them before changing this skill. The spine-level invariants this skill must respect, whatever the adapter:

- **Rollback model comes from the shipping adapter.** `revert` (undo the step on the target) or `stop-routing` (incumbent stays hot; used by shadow-strangler). If `rollback_constraints.non_revertible: true` on the architecture adapter, `adapter.rollback` is unavailable and the project must run `coexist`, not the wave-revert model. Refuse a revert-style rollback against a non-revertible target.
- **Prefer rollback over forward-fix** during a live wave breach.
- **Backward-compatible migrations.** If the build-log for the version under deploy references a non-backward-compatible data migration, refuse to proceed and surface to the operator. This is architecture-neutral: a new artifact and its rollback target must both work against the data at rest.
- **Respect `rollback_constraints`.** For example a bounded revert history depth; refuse a rollback target outside it.

## Wave model (fixed by the spine)

A wave rollout has four predefined cohort sizes. These percentages, the observation windows, and the green/yellow/red rule are governance invariants; no adapter may change them.

| Wave | Cohort size | Default observation window | Default decision |
|---|---|---|---|
| 1 | 10% of entitled recipients | 24h | Hold for `wave_promotion` HITL gate before wave 2 |
| 2 | 30% (cumulative) | 24h | Same |
| 3 | 50% (cumulative) | 24h | Same |
| 4 | 100% | 48h | `wave_completed` after green observation |

The shipping adapter's `step_plan` must match `[10, 30, 50, 100]` for the `tenant-wave` / `user-flag-wave` strategies; a `shadow-strangler` shipping adapter does not use this skill's wave loop (it runs `pdlc-coexist` with per-task-class, per-tenant routing). Cohort selection is delegated: `adapter.assign_cohort(wave)` returns a deterministic recipient set, reproducible across `plan` and `execute-wave` even if population state evolves between calls.

## Per-project config: `pdlc/guardrails.yaml`

Sits in the project's repo path (under the component's overlay materials, or the project root for a single component). Read at `plan` time.

```yaml
auto_promote: false
observation_windows:        # defaults; the bound shipping adapter may supply these
  wave_1_hours: 24
  wave_2_hours: 24
  wave_3_hours: 24
  wave_4_hours: 48
guardrails:
  # Universal core set (always evaluated, merged with the adapter catalog below):
  latency_equivalent:
    red_above: 2000
    yellow_above: 1500
    sample_window_minutes: 5
  error_rate_equivalent_pct:
    red_above: 5.0
    yellow_above: 2.5
    sample_window_minutes: 5
  cost_multiple:
    red_above: 4.0
    yellow_above: 2.5
  success_rate_drop_pct:
    red_above: 10
    yellow_above: 5
  feedback_sentiment_drop_points:
    red_above: 20
    yellow_above: 10
  # Mandatory for any agentic adapter (cost_ceiling_required: true): an absolute
  # cap per 24h window, set per tenant and per project. Evaluated in every stage
  # including shadow. On red breach, pause new task intake for the affected scope
  # and open a gate; agentic targets cannot rely on rollback as the brake.
  cost_ceiling_eur_24h:
    per_tenant_cap: null      # MUST be set when the bound adapter is agentic
    per_project_cap: null
rollback:
  mode: auto_on_red             # auto_on_red | hitl_only | manual
notifications:
  channel: "#pdlc-{project}"
  on_red: page_oncall
  on_yellow: notify_only
```

The effective guardrail set is the **universal core set merged with the bound architecture adapter's `guardrail_catalog`**. On key collision, the adapter catalog value applies (the architecture knows its own thresholds); the universal core key cannot be dropped, only re-thresholded. The cost ceiling is mandatory and cannot be removed when the adapter declares `cost_ceiling_required: true`; refuse to plan a wave for such an adapter if `cost_ceiling_eur_24h` caps are unset.

## Operations

Six operations. All idempotent (every mutation accepts an `idempotency_key`, defaulting to a deterministic hash of `{operation}-{wave_id}`).

### `plan`

Prepare a rollout. Does not deploy anything yet.

1. Resolve project slug from `.pdlc/project.txt` and the component binding (see "Reading the binding").
2. Read `pdlc/guardrails.yaml` (fall back to defaults). Merge the universal core set with `adapter.guardrail_catalog`. If the adapter is agentic and the cost ceiling is unset, refuse with `cost_ceiling_required`.
3. Resolve target `version` (caller input) and `previous_version` (current version on the target via the adapter; in Phase 0, read it from the runbook/operator).
4. Verify the target artifact exists (via the adapter's build surface). In Phase 0, prompt the operator if the build surface is unavailable.
5. Verify rollback is possible within `rollback_constraints` (e.g., the previous version is within the adapter's revert history). Refuse if not. If the shipping `rollback_model` is `stop-routing` against a non-revertible target, this skill does not own the rollout; route to `pdlc-coexist`.
6. Read the build-log entry for the version and refuse with `migration_not_backward_compatible` if a referenced data migration is flagged non-backward-compatible.
7. Call `adapter.assign_cohort` to snapshot the entitled recipient population and slice it into four waves deterministically. Store the cohort reference it returns.
8. Capture baseline metrics for the full entitled cohort via `adapter.fetch_metrics(window=last_7_days)`: the universal core metrics plus the adapter catalog metrics. Include average `sentiment_score` from `feedback-log` for the same cohort.
9. For each wave, call `pdlc-log append deployment-log` with `event: wave_planned`, `adapter_id`, `shipping_id`, the wave's cohort ref, baseline metrics, version, previous_version, `auto_promote`, observation window, and any adapter-specific fields under `adapter_ext`.
10. **Pre-apply preflight (plan lint).** Before returning the plan (and therefore before any apply gate opens), lint the plan against the bound architecture adapter's `provisioning_preflight` rules (see ADAPTER-CONTRACT.md):
    - If no architecture is bound, this step does not apply (skip silently; greenfield projects reaching `plan` have a bound adapter by definition).
    - If the bound adapter declares no `provisioning_preflight`, skip with a note in the returned plan (`preflight: "skipped (adapter declares no provisioning_preflight)"`).
    - Otherwise, produce the plan output for the change (run the adapter's plan surface, e.g. `terraform plan`; in Phase 0, the operator supplies the plan text per the runbook). For each rule whose `when` holds (`"always"`, or the predicate evaluates true for this change's context), check that the plan output contains the rule's `match`. A rule with no satisfied `when` is skipped.
    - If ANY rule fails, do NOT return a clear plan and do NOT let the caller open the apply gate. Instead surface ALL failures at once, each with its `resource` and `assert` text as remediation, and route to the retry/pivot path (write an `adapt-log` entry with `failure_type: pivot` and return `error: provisioning_preflight_failed` with the full failure list). The point is to convert a multi-apply gauntlet into one corrected plan and one gate.
    - If every applicable rule passes, include `preflight: "passed (<n> rules)"` in the returned plan and proceed.
11. Return the plan to the caller: `{ wave_ids: [...], cohorts: [...], baseline: {...}, adapter_id, shipping_id, version, preflight }`.

The orchestrator typically inspects the plan and opens a `delivery_to_deploy` HITL gate before calling `execute-wave` on wave 1.

### Activation by merge (non-deployed assets)

For a bound adapter whose `build_artifact_kind` is a documentation / schema / contract asset (no cohort, wave, or environment rollout), there is nothing for the wave loop to roll out. In that case ACTIVATION = the PR merge to `main`: the `delivery_to_deploy` gate approval authorizes the merge, and `pdlc-deploy` is not invoked for a wave plan at all. The item's single branch carries spec -> build -> the back-log status flip and is merged once (collapsing the prior two-PR pattern). This skill's wave operations (`plan`, `execute-wave`, `observe`, `promote`, `rollback`) apply only to real rollout artifacts (infrastructure, workflows, apps), whose flow is unchanged. If no architecture is bound, this classification does not apply.

**Git on approve (0.5.0).** The gate approval IS the merge authorization, and the merge is executed automatically — no manual operator git. On the `delivery_to_deploy` approve for an activation = merge asset (operator-decided, or auto-advanced by `pdlc-cto` for this low-risk class when its independent verification was fully green with zero flags), the orchestrator runs the known-good merge + sync + next-branch block from its "Git on gate approval" / Branch-and-merge-discipline rule as one unit:

```
gh pr merge N --squash --delete-branch
git checkout main && git pull --ff-only
git checkout -b discover/bl-XX-<slug>     # next item's branch, cut from fresh main
git branch --show-current                  # re-verify: must NOT print "main"
```

Before the merge, the gate carried a `pdlc-cto` review (independent re-run of the project's own validators/tests plus a consistency/security/GDPR lint); the orchestrator verifies it is on the item branch, the PR is green, and the review is attached, then merges. Destructive git (`push --force`, history rewrite) is never run by this path; it stays on explicit operator ask. This activation = merge path is one of the two low-risk auto-advanceable gate classes; a `delivery_to_deploy` for a real rollout artifact is never auto-advanced.

### `execute-wave`

Ship one wave's change for its cohort.

1. Read the `wave_planned` row by `wave_id` from `deployment-log`.
2. Idempotency check: refuse if a `wave_deployed` event already exists for this `wave_id` (return existing event ref).
3. Call `adapter.deploy(wave)` with the cohort, the target version, and an `idempotency_key`. The adapter performs whatever its mechanism is (an image rollout, a flag flip, a flag percentage, a route change) and returns a `deploy_ref`.
4. On adapter error, retry once, then pivot to the adapter's `phase0_fallback` runbook for operator-confirmed manual rollout (see Phase 0 fallback).
5. Write `event: wave_deployed` to `deployment-log` with `deploy_ref`, `idempotency_key`, `adapter_id`, `shipping_id`, and any adapter-specific refs under `adapter_ext`.
6. Schedule `observe` to run at `wave_planned.created_at + observation_window_hours` via `mcp__scheduled-tasks__create_scheduled_task`. The scheduled task invokes `pdlc-deploy observe --wave-id {wave_id}`.
7. Notify the project channel: "Wave {N} of {project} {version} deployed to {cohort_size_n} recipients. Observation window: {hours}h."

### `observe`

Evaluate guardrails at the end of an observation window.

1. Read the wave's planning row.
2. Pull current metrics for the cohort over the observation window via `adapter.fetch_metrics(window=observation_window)`: the universal core metrics plus the adapter catalog metrics. Pull average `sentiment_score` from `feedback-log` directly (`pdlc-log query feedback-log --wave-id {wave_id}`).
3. Append a `user-behavior-log` entry per adapter metric with `wave_id` set, so the evolve-agent has a durable trace. Do NOT mirror sentiment into `user-behavior-log`; the canonical record is the `feedback-log` rows.
4. Compute `cost_multiple` and, for agentic adapters, the `cost_ceiling_eur_24h` utilization (max across the cohort, per tenant and per project).
5. Compare each guardrail (merged set) against baseline plus threshold: each returns `green` (within yellow_above), `yellow` (between yellow_above and red_above), or `red` (above red_above).
6. Overall decision: `red` if any red, `yellow` if any yellow, else `green`.
7. If the adapter reports a per-recipient deploy pause, sample it and flag `observed_pause_seconds_p95` above the adapter's declared threshold.
8. Write `event: wave_observed` to `deployment-log` with `success_metric_current`, `guardrail_decision`, `guardrail_breach`, and adapter specifics under `adapter_ext`.
9. Branch:
   - `green` and `auto_promote: true`: call `promote` directly.
   - `green` and `auto_promote: false`: open `wave_promotion` HITL gate via `pdlc-hitl-gate`. Caller resumes on gate close.
   - `yellow`: open `wave_promotion` HITL gate regardless of `auto_promote`. The gate options include `Approve + open P0 for follow-up`.
   - `red` and `rollback.mode: auto_on_red`: write `wave_paused`, then call `rollback`. (If the bound target is non-revertible, do NOT call `adapter.rollback`; instead pause new intake for the scope and open a `rollback_approval` gate, since the brake is "stop routing," not revert.)
   - `red` and `rollback.mode: hitl_only`: open `rollback_approval` HITL gate.
   - `red` and `rollback.mode: manual`: write `wave_paused`, notify on-call, await operator.
10. Notify the channel with the decision and the breached guardrails (if any).

### `promote`

Advance to the next wave.

1. Read the wave's `wave_observed` row. Refuse if missing or if `guardrail_decision: red`.
2. Open `wave_promotion` HITL gate via `pdlc-hitl-gate` unless the operator decision is already captured by the caller.
3. On gate `approve`, write `event: wave_promoted` to `deployment-log`.
4. Compute the next wave's cohort (next 20% for wave 2, next 20% for wave 3, remaining 50% for wave 4) via `adapter.assign_cohort` using the same snapshot from `plan`.
5. Call `execute-wave` for the next wave.
6. If the current wave is wave 4 and observation is green: write `event: wave_completed` and notify.

### `rollback`

Revert a cohort to the previous version, via the shipping adapter's `rollback_model`.

1. Read the wave's most recent event. The rollback can target any deployed wave; in practice it targets the wave that breached.
2. Open `rollback_approval` HITL gate via `pdlc-hitl-gate` unless `rollback.mode: auto_on_red` and the trigger is a red `wave_observed`.
3. For `rollback_model: revert`:
   - Verify `previous_version` is still within the adapter's `rollback_constraints`. Refuse with `rollback_outside_history` if not.
   - Call `adapter.rollback(wave)` with the cohort, the previous version, and an `idempotency_key`.
4. For `rollback_model: stop-routing`: this is a coexistence concern; route to `pdlc-coexist` (stop sending traffic to the new architecture; the incumbent never left). `adapter.rollback` is not used.
5. Verify rollback succeeded via `adapter.fetch_metrics` or the adapter's verification path (poll up to the adapter's declared window).
6. Write `event: wave_rolled_back` to `deployment-log` with `rollback_triggered: true`, `rollback_reason`, and the rollback `deploy_ref` under `adapter_ext`.
7. Open a P0 entry in `back-log` via `pdlc-log append back-log` with `block_redeploy: true`, `source: regression`, `source_ref: deployment-log:{wave_id}`.
8. Write a `learn-log` entry summarizing the breach: which guardrail, the values, the evidence.
9. Notify the project channel and page on-call per `notifications.on_red`.

### `status`

Read-only inspection.

1. Read all `deployment-log` entries for the given project where `event != wave_completed` in the last 30 days.
2. Group by `wave_id`. Show the latest event per wave plus the time-to-next-action.
3. Return a structured summary the operator or orchestrator can use to decide next steps.

## Phase 0 degradation mode

Detected automatically by absence of the bound adapter's control surface. In this mode:

- `plan` runs normally but writes `runbook_ref` (the adapter's `phase0_fallback`) instead of `deploy_ref`.
- `execute-wave` does not call `adapter.deploy`. Instead it emits the adapter's runbook steps to the operator's terminal or via AskUserQuestion with the exact manual commands for the cohort. The operator runs them and confirms; the skill appends a `wave_deployed` event with the confirmation.
- `observe` and `rollback` operate the same way: emit runbook steps, await operator confirmation, append events.
- The plugin auto-detects when the adapter's control surface becomes available and switches to the contract path on the next session.

The Phase 0 path is otherwise identical: same wave gating, same guardrail evaluation against the adapter's `metrics_sources` (which generally exist from Phase 0). This is the governance Phase 0 fallback pattern; no adapter may bypass it.

## Idempotency

Every mutating operation accepts `idempotency_key`. If the caller omits it, the skill computes `sha256({operation}|{wave_id}|{actor})`. Operations check for matching keys on prior `deployment-log` events before executing. The adapter operations also accept this key so the mechanism is idempotent end to end.

## Error handling

The retry-pivot-escalate protocol is applied per adapter call:
- Two retries on the same operation.
- On second failure, pivot to the adapter's Phase 0 fallback for that single recipient (manual runbook step).
- On pivot exhaustion, write an `escalation` row to `adapt-log` and page on-call.

## Decision payload returned by `observe`

```json
{
  "wave_id": "lead-routing-suite-1.2.0-w1",
  "adapter_id": "workflow-multitenant",
  "shipping_id": "tenant-wave",
  "decision": "yellow",
  "guardrail_breach": ["feedback_sentiment_drop_points"],
  "metrics": {
    "latency_equivalent": 1320,
    "error_rate_equivalent_pct": 1.4,
    "cost_multiple": 1.8,
    "feedback_sentiment_drop_points": 14,
    "success_rate_pct": 98.6
  },
  "next_action": "open_wave_promotion_hitl_gate"
}
```

`decision` values: `green`, `yellow`, `red`.

## Examples

### Plan a wave rollout

```
pdlc-deploy plan {
  project: "lead-routing-suite",
  component: "default",
  version: "1.2.0",
  caller: "delivery-agent",
  session_ref: "claude-session-xyz"
}
```

The skill reads the component's `adapter.txt` and `shipping.txt`, merges the guardrail sets, calls `adapter.assign_cohort` and `adapter.fetch_metrics`, and writes four `wave_planned` entries. The orchestrator then opens a `delivery_to_deploy` gate before `execute-wave` on wave 1.

### Auto-rollback on red guardrail

The scheduled `observe` task fires 24h after wave 1. `adapter.fetch_metrics` returns `cost_multiple: 4.7` for two recipients, above the 4.0 red threshold. With `rollback.mode: auto_on_red` and a revert-capable target:

1. Write `wave_observed` with `guardrail_decision: red`, `guardrail_breach: "cost_multiple"`.
2. Write `wave_paused`.
3. Call `adapter.rollback` for the wave 1 cohort.
4. Write `wave_rolled_back` with the reason.
5. Open a P0 in `back-log` with `block_redeploy: true`.
6. Write a `learn-log` entry pointing to the deployment-log trail.
7. Page on-call per `notifications.on_red`.

### Rollback refused: outside revert history

```
pdlc-deploy rollback --wave-id lead-routing-suite-1.0.4-w3 --reason "..."
```

returns:

```
error: rollback_outside_history
message: "previous_version 1.0.3 is outside the adapter's rollback_constraints. Available revert targets: <adapter-reported list>. Manual recovery required: rebuild the artifact, redeploy as a new version."
```

The orchestrator writes this to `adapt-log` and pages on-call.

## Companion skills

- `pdlc-log`: every event flows here.
- `pdlc-hitl-gate`: opens `delivery_to_deploy`, `wave_promotion`, and `rollback_approval` gates (each carrying a `pdlc-cto` review before it is presented).
- `pdlc-cto` (agent): reviews the `delivery_to_deploy` gate (and any wave/rollback gate) before it is presented, and for the activation = merge low-risk class may auto-advance it when verification is green with zero flags.
- `pdlc-coexist`: owns the `stop-routing` rollout for non-revertible (Class B) targets; this skill routes there instead of attempting a cross-architecture revert.

## Adapter contract dependency

This skill is correct only against an adapter that honors ADAPTER-CONTRACT.md: `assign_cohort` is deterministic and reproducible, `deploy`/`rollback` are idempotent on `idempotency_key`, `fetch_metrics` reads the declared `metrics_sources`, and `rollback_constraints` are truthful. If an adapter declares `non_revertible: true`, this skill will not attempt a revert; the project must use `coexist`.
