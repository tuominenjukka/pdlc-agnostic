---
name: pdlc-coexist
description: Run the shadow-and-strangler coexistence stage for a Class B paradigm-shift migration. The new architecture runs alongside the live incumbent, validated by an equivalence harness instead of revert-based rollback, then takes real traffic progressively per task class and per tenant, with the incumbent always hot as the fallback. Tracks each tenant in the migration-log and gates contracted-behavior changes with tenant_migration_consent. Trigger after pdlc-fork creates a class-b-migration project.
---

# pdlc-coexist

The coexistence stage for paradigm-shift migrations, where the target cannot be reverted to the source because the artifacts are incommensurable. The incumbent stays live and hot throughout. Nothing here uses the wave-revert model.

## Preconditions

- A `pdlc-fork` project with `fork_reason: class-b-migration` and a known incumbent.
- The forked architecture is provisioned (its own `provision` stage has run).
- A task-acceptance suite exists (defined during Discovery for the new architecture).

## Stage steps

### 1. Shadow
Run the new architecture against live inputs with zero customer impact. Outputs are captured and compared to the incumbent's outputs, never returned to users. Append `migration-log` rows with state `shadowing` per tenant in scope. Shadow runs on a defined tenant cohort, not the whole population by default, and may sample task volume; widen the scope progressively. Shadow compute and token spend count against the mandatory cost ceiling, since shadowing an agentic target doubles work with zero revenue.

### 2. Equivalence evaluation (replaces revert-rollback)
The incumbent is the oracle. The new architecture must match or beat it on the task-acceptance suite before it takes traffic. Evaluate agent-era metrics, not `workflow_success_rate`:
- task completion rate
- human-intervention rate
- cost per task (against the mandatory cost ceiling)
- outcome correctness against the incumbent result

Green means ready to route. Yellow or red means stay in shadow and open a follow-up. There is no revert step, because there is nothing to revert to.

Pin the incumbent version as the oracle baseline for each evaluation window. If the incumbent ships a change touching a task class under evaluation, re-baseline that task class before any further promotion decision, so equivalence is never judged against a moved oracle.

### 3. Progressive routing
Route real traffic to the new architecture per task class and per tenant, smallest blast radius first. After each routing step, observe for the configured window and re-evaluate equivalence. Promotion between steps opens a `wave_promotion` gate. Rollback is `stop-routing`: stop sending traffic to the new architecture; the incumbent never left.

### 4. Per-tenant ledger and consent
Track every tenant in `migration-log` as a state machine: `incumbent`, `shadowing`, `partial`, `migrated`, `rolled_back`. Where the change alters contracted behavior (for example removing deterministic execution), open a `tenant_migration_consent` gate before routing that tenant's real traffic. Determine consent-required tenants from the tenant contract register (or the closest contractual source of truth); when a tenant's contract status is unknown, treat the tenant as consent-required. Consent may be gated per cohort: one `tenant_migration_consent` gate carrying the explicit tenant list, with a per-tenant migration-log row referencing the shared gate id. This is the "human controls irreversible actions" principle extended to the customer.

## Exit

A tenant reaches `migrated` only after sustained-green equivalence across its task classes for the configured window. The incumbent for that tenant is still hot and is retired only by `pdlc-decommission`, never automatically here.

## Abandoning the migration

The operator may abandon at any pre-decommission point. Stop routing everywhere, move all in-flight tenants to `rolled_back`, write a migration-level `migration_abandoned` event to `migration-log`, and record the rationale in `learn-log`. The forked target's provisioned infrastructure is then torn down via its own adapter's `teardown` behind a dedicated heavy gate; this is distinct from `pdlc-decommission`, which only ever retires the incumbent. The incumbent never stopped serving, so abandonment has zero customer impact.

## Guardrails

- The cost ceiling is mandatory and evaluated every step (autonomous agents loop and consume tokens).
- Never auto-decommission the incumbent from this skill.
- Never route a tenant's real traffic before equivalence is green and, where required, consent is granted.

## Companion skills

`pdlc-fork`, `pdlc-decommission`, `pdlc-hitl-gate`, `pdlc-log`, `pdlc-deploy` (for the new architecture's own increments).
