---
name: pdlc-decommission
description: Tear down a tenant's incumbent fallback after a Class B migration has reached sustained-green coexistence. Irreversible terminal stage, per tenant, behind a dedicated decommission gate. Trigger only after pdlc-coexist reports a tenant at migrated state for the full sustained-green window. Never invoke automatically.
---

# pdlc-decommission

Retires the incumbent for a tenant once the new architecture has proven itself in coexistence. This is the only stage that removes the fallback, so it is irreversible and terminal.

## Preconditions (all required)

- The tenant is at `migrated` state in `migration-log`.
- Equivalence has been green for the full sustained-green window. Default: 14 days, overridable per migration in `guardrails.yaml`.
- No open P0 referencing this tenant's migration.

If any precondition fails, refuse and report which one.

## Procedure

1. Open the `decommission_approval` HITL gate with a dedicated approver set, distinct from `wave_promotion` approvers. The summary states plainly that the incumbent fallback for this tenant is being removed and cannot be restored without a rebuild.
2. On approval, call the incumbent architecture adapter's `teardown(scope=tenant)` for this tenant only.
3. Verify teardown, then write `migration-log` state `decommissioned` for the tenant and a `learn-log` entry recording the window and the evidence.
4. Notify the project Slack channel.

## Rules

- Per tenant for the first 5 tenants of a migration. After 5 successful decommissions in the same migration, a cohort gate is allowed: one `decommission_approval` carrying the explicit tenant list in its summary. Preconditions are evaluated per tenant regardless; any tenant failing one drops out of the cohort. A `decommissioned` migration-log row is still written per tenant.
- Never auto-trigger. A human opens this stage.
- If teardown fails partway, do not retry blindly. Surface to the operator and write an `adapt-log` escalation. A half-torn-down incumbent is worse than either state.

## Companion skills

`pdlc-coexist`, `pdlc-hitl-gate`, `pdlc-log`.
