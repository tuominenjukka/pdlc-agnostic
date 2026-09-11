# migration-log schema [v2]

**Prefix:** `ML`
**Owner phase:** `evolve` (rediscovery, coexistence, decommission)
**Purpose:** Per-tenant ledger for a cross-architecture migration. Mandatory for Class B paradigm shifts, recommended for any Class A retarget touching more than one tenant. One project may have hundreds of tenants in flight at once, each a state machine. The migration-log is the source of truth for `pdlc-coexist` and `pdlc-decommission`.

## State machine (per tenant)

`incumbent` -> `shadowing` -> `partial` -> `migrated` -> `decommissioned`
Any pre-decommission state may move to `rolled_back` (stop-routing; incumbent never left).
`decommissioned` is terminal and irreversible.
On abandonment, all in-flight tenants move to `rolled_back` and a single `migration_abandoned` event closes the migration.

## Log-specific columns

| Column | Type | Required | Notes |
|---|---|---|---|
| `event` | enum | yes | `tenant_state_changed`, `migration_abandoned` (migration-level closure), plus gate events `hitl_gate_opened/closed/timeout`. Gate events written here must carry the base gate record id in `related_log_refs`; the base gate log remains the source of truth for gate lifecycle. |
| `tenant_id` | string | yes | The tenant this row is about. |
| `migration_id` | string | yes | `{source-project}->{target-project}`. Stable across the migration. |
| `from_state` | enum | yes | Prior state. |
| `to_state` | enum | yes | New state. |
| `task_class` | string | no | The task class being routed, when partial. |
| `equivalence_decision` | enum | no | `green`, `yellow`, `red`, from the equivalence harness. |
| `equivalence_metrics` | json | no | task_completion, human_intervention, cost_per_task, correctness_vs_incumbent. |
| `consent_gate_id` | string | no | Set when a `tenant_migration_consent` gate applies. A cohort gate's id appears on every covered tenant's row. |
| `sustained_green_since` | timestamp | no | When the tenant first went green and stayed green. Drives the decommission precondition. |
| `incumbent_adapter_id` | string | yes | The architecture being retired. |
| `target_adapter_id` | string | yes | The architecture being adopted. |
| `related_log_refs` | string | no | learn-log, deployment-log of the target project. |

## Query

`SELECT * FROM migration-log WHERE migration_id = X ORDER BY tenant_id, created_at` gives the full ledger. The decommission precondition check is: tenant at `migrated` AND `sustained_green_since` older than the configured window AND no open P0 for the tenant.
