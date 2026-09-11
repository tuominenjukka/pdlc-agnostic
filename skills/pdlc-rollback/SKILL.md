---
name: pdlc-rollback
description: Operator-triggered manual rollback of a live PDLC wave. Trigger with `/pdlc-rollback`, "roll back the lead-routing-suite wave", "revert that deploy", "undo the last release", or when the operator wants to revert without waiting for an automated guardrail breach. Routes the request through `pdlc-deploy rollback` with the `rollback_approval` HITL gate (the gate is opened by pdlc-deploy as usual; this skill provides the operator entry point and pre-fills the reason).
---

# pdlc-rollback

The operator's explicit "revert this now" entry point. Use whenever the operator wants to roll back a wave for a reason the automated guardrails haven't caught (or wouldn't catch): customer complaint, sales escalation, observed-but-not-thresholded regression, compliance issue.

The mechanism is whatever the bound architecture adapter's `rollback` operation does; this skill never names a product. For a non-revertible (Class B) target the brake is "stop routing," not a revert; see "Non-revertible targets" below.

## When to invoke

- Operator types `/pdlc-rollback` (optionally with a wave id or "latest").
- Operator says "roll back", "revert", "undo the deploy", "kill the current wave."
- A non-evolve-agent observer (customer success, support) reports something an automated guardrail would miss.

Do NOT invoke for:
- Auto-rollback on red guardrail (pdlc-deploy does that itself per `auto_on_red`).
- Reverting a discovery_to_delivery decision (that is a re-Discover or a rediscovery, not a rollback).
- Reverting a non-deployed change (use git revert on the PR; no wave to roll back).

## Required input

1. **Wave id** (`{project}-{version}-w{1..4}`, matches `deployment-log.wave_id`). If the operator says "latest" or omits it, default to the most recent wave with a non-terminal event (not `wave_completed` or `wave_rolled_back`) for the active project. If every wave is terminal, refuse with `no_active_wave_to_roll_back` and surface the most recent completed wave's id so the operator can confirm.
2. **Reason**: a free-text explanation. The skill does not invent the reason. If the operator gives a vague reason ("looks weird"), prompt for a sharper statement, since the reason becomes the back-log P0 description and the learn-log entry.
3. **Confirmation**: explicit operator confirmation that they understand the rollback affects the cohort identified in the wave's `cohort_ref`, not just one recipient. Required even when invoked via slash command.

## Procedure

1. Resolve the wave and its component binding:
   - Read the wave's planning + execution rows from deployment-log; the `adapter_id` and `shipping_id` on those rows identify the binding (per-component when `.pdlc/components/` exists, else top-level `.pdlc/adapter.txt`/`.pdlc/shipping.txt`).
   - If "latest", query deployment-log for the project and pick the wave whose most recent event is one of `wave_deployed`, `wave_observed`, `wave_promoted`, `wave_paused`.

2. Verify rollback is mechanically possible:
   - If the bound shipping `rollback_model` is `revert`, confirm `previous_version` is still within the adapter's `rollback_constraints`. If not, refuse with `rollback_outside_history` and surface the manual recovery path (rebuild the prior artifact, redeploy as a new version).
   - If the bound shipping `rollback_model` is `stop-routing` (non-revertible target), this is a coexistence concern; do not attempt a revert. Route the operator to `pdlc-coexist` to stop routing the affected tenant(s)/cohort to the new architecture (the incumbent never left).

3. Show the operator the impact: cohort_ref, cohort_size_n, the version being rolled back from/to, the bound `adapter_id`, and the wave events to date. Get explicit confirmation.

4. Call `pdlc-deploy rollback --wave-id {wave_id} --reason "{reason}"`.
   - pdlc-deploy opens the `rollback_approval` HITL gate via `pdlc-hitl-gate`.
   - In Cowork, the gate presents an AskUserQuestion. In Claude Code, it labels the relevant PR.
   - This skill blocks on the gate decision (or yields to `/pdlc-resume` if the operator pauses).

5. On gate `approve`:
   - pdlc-deploy executes the rollback via `adapter.rollback`.
   - pdlc-deploy writes the `wave_rolled_back` event, the P0 back-log entry with `block_redeploy: true`, and the learn-log summary.
   - This skill prints the resulting state to the operator.

6. On gate `reject`: write a learn-log entry recording the rejection rationale. Wave continues as-is.

7. On gate `pause`: leave the gate open. The skill exits; the next `/pdlc-resume` session re-evaluates.

## Non-revertible targets

If the bound architecture adapter declares `rollback_constraints.non_revertible: true`, there is no revert. The project should be running `coexist`, not the wave-revert model, so a `/pdlc-rollback` request on such a project means "stop routing the new architecture for this scope." Route to `pdlc-coexist`, which moves the affected tenant(s) to `rolled_back` (stop-routing) in `migration-log`; the still-hot incumbent keeps serving. Do not call `adapter.rollback`.

## Output to the operator

On successful rollback:

```
Rollback complete for {wave_id}.
- Adapter: {adapter_id}
- Shipping rollback_model: {revert|stop-routing}
- Reverted from: {version or routing state}
- Reverted to: {previous_version or incumbent}
- Cohort: {cohort_size_n} recipients via {cohort_ref}
- Reason: "{reason}"

Logs:
- deployment-log: {dl-id}  (wave_rolled_back)
- back-log: {bl-id}  (P0, block_redeploy=true)
- learn-log: {ll-id}
- adapt-log: {al-id, if any retries/pivots}

Next: investigate the cause. The back-log P0 blocks re-deploy until resolved.
```

On rejection or pause, print the gate decision and current wave state.

## What you do not do

- You do not bypass `pdlc-deploy rollback`. The skill exists to keep cohort selection, idempotency, and log writes consistent.
- You do not write directly to deployment-log, back-log, or adapt-log. pdlc-deploy and pdlc-log own those writes.
- You do not page on-call. pdlc-deploy's rollback path handles paging if `notifications.on_red: page_oncall` is set.
- You do not roll back multiple waves in one call. Each invocation rolls back exactly one `wave_id`. To revert a multi-wave rollout, the operator runs the skill once per wave in reverse order (4 → 3 → 2 → 1) and the orchestrator's adapt-log captures the chain.
- You do not attempt a revert against a non-revertible target. Route to `pdlc-coexist`.

## Failure modes

- **`rollback_outside_history`**: refuse, explain manual recovery. Do not attempt a partial rollback.
- **Adapter control surface unavailable**: pdlc-deploy owns the retry-and-degrade path (the adapter's Phase 0 fallback); this skill does not duplicate it. Surface whatever pdlc-deploy returns.
- **Non-revertible target**: route to `pdlc-coexist` rather than failing; this is expected for Class B projects.
- **Operator declines confirmation in step 3**: write a learn-log entry recording the declined rollback and exit.

## Companion skills

- `pdlc-deploy` for the actual rollback execution.
- `pdlc-hitl-gate` (invoked by pdlc-deploy) for the approval gate.
- `pdlc-log` (invoked by pdlc-deploy) for the wave_rolled_back, back-log P0, learn-log writes.
- `pdlc-coexist` for stop-routing on non-revertible targets.
