---
name: pdlc-resume
description: Resume a paused PDLC project after an externally closed HITL gate (e.g., the operator approved a `pdlc-gate:wave_promotion` label on a GitHub PR, or an AskUserQuestion was answered in a prior Cowork session). Trigger with `/pdlc-resume`, "resume the PDLC", "check open gates and continue", "is anything ready to move?", or whenever the operator returns to a project that had open gates at session end. Calls `pdlc-hitl-gate check` for every open gate, advances the playbook step for any newly closed gate, and hands control back to pdlc-orchestrator.
---

# pdlc-resume

The "wake up and continue" entry point. Use whenever the operator wants the orchestrator to pick up where it left off, after one or more HITL gates have been closed outside this session.

## When to invoke

- Operator types `/pdlc-resume`.
- Operator says "resume", "continue the PDLC", "check open gates", "anything ready to move?"
- A new session starts with non-empty `.pdlc/open-gates.jsonl`.
- A scheduled task fires after a Phase 0 manual rollout step.

If the project has no open gates (no `.pdlc/open-gates.jsonl` or it's empty), invoke `/pdlc-status` instead — there is nothing to resume.

## Procedure

1. Read `.pdlc/project.txt` to resolve the project. If missing, prompt the operator to provide one or run `/pdlc-start`.

2. Read `.pdlc/open-gates.jsonl`. Each line is one `gate_id` plus its `gate_type`, `routing`, and the playbook step (and, for component- or tenant-scoped gates, the `component` or `tenant_list`) that opened it. **Short-circuit**: if the file is missing or empty, print "No open gates. Use `/pdlc-status` for the current project state." and exit.

This skill mutates `.pdlc/open-gates.jsonl` directly (removing terminally closed gates). The file is shared state with the orchestrator, which appends new gates and reads the list.

3. For each open gate, call `pdlc-hitl-gate check`. Three possible outcomes per gate:
   - **Still open**: leave it. Note the latest activity and continue.
   - **Terminally closed with `approve`, `reject`, `timeout`, or `failed_closed`**: this is a transition. Remove from `.pdlc/open-gates.jsonl`. Capture the decision payload.
   - **Paused, with a fresh gate of the same type subsequently opened**: pause is non-terminal (see pdlc-hitl-gate "Pause semantics"). If a new gate id appears, append it; do not coalesce. Resume both separately.

4. For each newly closed gate, advance the playbook by routing the decision back to the agent or skill that opened it:
   - `discovery_to_delivery` closed -> route to pdlc-orchestrator with the decision, which then delegates to delivery-agent on approve.
   - `delivery_to_deploy` closed -> route to pdlc-orchestrator, which calls `pdlc-deploy plan` (for the relevant component's binding) on approve.
   - `wave_promotion` closed -> route to `pdlc-deploy promote` with the decision (resolve the component binding from the gate's `component` or from the `wave_id`).
   - `rollback_approval` closed -> route to `pdlc-deploy rollback` on approve.
   - `pivot_approval` closed -> route to pdlc-orchestrator, which routes to the relevant phase agent on approve.
   - `schema_extension` closed -> route to whichever sub-agent originally opened it; on approve, that agent extends the schema file and proceeds with its blocked write.
   - `architecture_decision` closed -> route to `pdlc-architecture-decision` (or `pdlc-rediscover` / `pdlc-fork` if that is what opened it). On approve, the binding commits: `.pdlc/adapter.txt` and `.pdlc/shipping.txt` are written (or the per-component `.pdlc/components/{component}/*` files for a multi-component project), the ADR is finalized, and for a rediscovery the migration class routes the next stage (Class A -> `migrate` via `pdlc-deploy`; Class B -> `pdlc-fork` + `pdlc-coexist`). On reject, do not bind; hand back to discovery/rediscover for another decision.
   - `tenant_migration_consent` closed -> route to `pdlc-coexist`. On approve, the listed tenants may receive real traffic; record consent in their `migration-log` rows (referencing the gate id) and proceed with progressive routing for the covered tenant(s)/cohort. On reject, those tenants stay on the incumbent; do not route their real traffic.
   - `decommission_approval` closed -> route to `pdlc-decommission`. On approve, the listed tenant(s) have their incumbent fallback torn down (`adapter.teardown(scope=tenant)`), then a `decommissioned` migration-log row is written per tenant. On reject, the incumbent stays hot. Re-verify each tenant's preconditions before acting; any tenant failing one drops out.

5. Write a `learn-log` entry summarizing the resume:
   - `phase: meta`
   - `topic: session-resume`
   - `insight`: list of gates that closed and the decisions taken.

6. Hand control to pdlc-orchestrator for any subsequent autonomous playbook progression.

## Order of operations when multiple gates close

Process them in dependency order:

1. Schema extensions first (they unblock other writes).
2. Architecture-decision gates next (they determine the binding every later stage acts on); if an `architecture_decision` and a phase-transition gate both closed, apply the binding before advancing the phase.
3. Phase-transition gates (`discovery_to_delivery`, `delivery_to_deploy`), in chronological close order.
4. Migration-consent gates (`tenant_migration_consent`) before any routing they unblock.
5. Wave gates (`wave_promotion`, `rollback_approval`), oldest first.
6. Decommission gates (`decommission_approval`) last, since they are terminal and irreversible; never process a decommission ahead of a consent or wave gate for the same tenant.
7. Pivot approvals can land anywhere; process in chronological close order with everything else.

Do not skip a gate to "catch up." If a wave 2 promotion needs to be processed before a wave 3 promotion, do them in that order even if wave 3 was approved first.

## Output to the operator

After processing, print:

```
Resume for {project}:
- Closed gates: {n}
  - {gate-id} {gate_type} → {decision} by {decided_by} @ {time}
  - ...
- Still open: {n}
  - {gate-id} {gate_type} — awaiting {approvers}, last polled {time}
- Actions taken:
  - {one line per playbook step advanced}

Next: {orchestrator handoff summary or "all caught up, no further action needed"}
```

If nothing closed since last session, print: "No gate state changed. {n} gates still open. Use /pdlc-status for detail."

## What you do not do

- You do not open new gates. Only respond to closures.
- You do not modify deployment-log, build-log, test-log, or migration-log directly. Routing to the right skill or agent does those writes.
- You do not bypass `pdlc-hitl-gate check`. The check is the source of truth for gate state; do not infer from cache alone.
- You do not commit an architecture binding yourself; you route the closed `architecture_decision` gate to the owning skill, which writes `.pdlc/adapter.txt` / per-component bindings.

## Failure modes

- **`pdlc-hitl-gate check` errors on a specific gate**: log to adapt-log with `failure_type: gate_check_failed`, keep that gate in `.pdlc/open-gates.jsonl`, continue with other gates. Surface to operator at the end.
- **A closed gate's downstream action fails twice on retry**: pivot per the standard protocol; if pivot exhausts, escalate to the operator with the adapt-log entry chain.
- **Project context missing**: prompt the operator; do not guess.

## Companion skills

- `pdlc-hitl-gate` for `check` calls.
- `pdlc-log` for the resume learn-log entry.
- `pdlc-deploy` for `promote` and `rollback` triggers.
- `pdlc-architecture-decision`, `pdlc-coexist`, `pdlc-decommission` for the three added gate types.
- pdlc-orchestrator (agent) takes over for non-trivial playbook progression.
