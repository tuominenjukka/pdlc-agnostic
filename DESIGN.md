# PDLC-Agnostic: Design (v2.1)

Revision of the architecture-agnostic PDLC plugin. v2 folds in the seven improvements surfaced by the workflow-to-agentic-harness migration stress test; v2.1 folds in the second stress test (workspace FINDINGS.md, 2026-06-10). New since v1 is marked **[v2]**, new since v2 is marked **[v2.1]**.

## 1. Principle

One process spine, pluggable target architecture and shipping approach, both chosen in Discovery. Discover, Deliver, Evolve stay fixed and architecture-neutral. Everything architecture-specific lives behind two contracts (Target Adapter, Shipping Adapter) bound during Discovery. Rediscovery is the standard way to evolve a live project's architecture.

## 2. The governance spine (invariant)

Fixed for every project, no adapter may override: the three phases and their order, the append-only logs, the HITL gate as the only path for irreversible actions, idempotency on every mutation, retry-pivot-escalate, and the Phase 0 manual fallback pattern. An adapter contributes mechanism, infrastructure, and guardrails, never process.

### 2.1 Log-store modes **[v0.5.2]**

The append-only logs live in one of two homes, set per project in `.pdlc/log-store.txt`:

- **`repo` (default):** `.pdlc/logs/{log-name}.jsonl` is the canonical, git-tracked audit trail, committed with the code. This is the mode for greenfield and local-only projects, where the repo is the durable record.
- **`shared`:** a shared document store (e.g. a Google Drive of Sheets) is canonical and `.pdlc/logs/` is a write-through cache.

The scaffolded `.gitignore` follows the mode: in `repo` mode it tracks `.pdlc/logs/` and `.pdlc/bin/` while ignoring the ephemeral session state; in `shared` mode the logs stay ignored as a cache. This resolves a latent failure where a blanket `.pdlc/` ignore dropped the audit trail on a fresh clone and forced a per-commit `git add -f`. `pdlc-start` writes `.pdlc/log-store.txt` and the `.gitignore` stanza; `pdlc-log` and `pdlc-status` read the mode. Absent marker means `repo`.

## 3. Stage models under the spine

The spine runs six stage models, each with its own risk profile. Only `deliver` and parts of `migrate` use the wave loop.

| Stage | Reversibility | Wave model | Gate weight |
|---|---|---|---|
| `provision` | Destructive teardown, not revert | No | Heavy, dedicated approver |
| `deliver` (increments) | Clean revert | Yes (10/30/50/100) | Standard |
| `ship` | Per shipping adapter | Per shipping adapter | Standard |
| `migrate` **[v2 class-aware]** | Class A revertible, Class B not | Class A yes, Class B no | Heavy |
| `coexist` (shadow or strangler) **[v2]** | Stop routing to new | Per task class and tenant | Heavy, plus consent |
| `decommission` **[v2]** | Irreversible | No | Terminal, dedicated approver |

## 4. Two adapter contracts

### 4.1 Target Adapter
Declares what an architecture is and how it is operated. Manifest fields plus four operations the neutral core calls: `assign_cohort`, `deploy`, `rollback`, `fetch_metrics`. **[v2]** also carries a reference architecture (a reusable infrastructure blueprint) and a `provision` and `teardown` operation. Full spec in `adapters/ADAPTER-CONTRACT.md`.

### 4.2 Shipping Adapter **[v2 separated from the architecture adapter]**
Declares how increments are shipped (wave, shadow or strangler, direct), independent of the architecture. Carries a typed `requires` predicate block (`architecture.*` and `project.*` namespaces) so Discovery and later re-validation can check the pairing mechanically. Full spec in `adapters/SHIPPING-CONTRACT.md`.

Discovery binds one architecture adapter and one shipping adapter, and validates the pairing. The choice is "propose a new one or reuse an existing reference," mirrored across both contracts.

### 4.3 Per-component binding **[v2.1, resolves open decision 2]**

A project may bind one architecture-plus-shipping pair per component. Layout: `.pdlc/components/{component}/adapter.txt` and `.pdlc/components/{component}/shipping.txt`. The flat `.pdlc/adapter.txt` and `.pdlc/shipping.txt` remain valid as the single-component case and need no change. One `architecture_decision` gate covers the whole component set; the ADR carries a component table (component, adapter, shipping, rationale). Pairing is validated per component. `deployment-log` rows already carry `adapter_id` and `shipping_id`, so mixed-adapter logging needs no schema change. Rediscovery classifies migration class per component: one project may have a Class A retarget on one component and no change on another.

## 5. Discovery: the Solution Architecture Decision

After framing the opportunity, the discovery-agent runs `pdlc-architecture-decision`:

1. Derive the opportunity's required capabilities (tenancy, residency, real-time, scale, UI, reversibility, memory layers).
2. Gather evidence: company-internal patterns from the organization's knowledge base (Engineering Guide, prior C4 and ADRs, learn-log and adapt-log), plus external best practice via web search at decision time.
3. Score registered architecture adapters on capability fit, internal precedent, external alignment, reversibility and cost. Below threshold means propose a new adapter and its reference architecture rather than force a poor fit.
4. Select a compatible shipping adapter and validate the pairing.
5. Emit an ADR plus a learn-log entry citing the evidence, and bind both adapters by writing `.pdlc/adapter.txt` (architecture) and `.pdlc/shipping.txt`.
6. Open the `architecture_decision` HITL gate before the binding commits.

## 6. Rediscovery (standard practice for live projects) **[v2 class-aware]**

`pdlc-rediscover` re-runs the architecture decision on a live project against current evidence and classifies the result:

- **Class A, retarget.** Portable artifacts, revertible cutover (for example a managed workflow service to a self-hosted instance of the same engine). Produces a migration plan, re-binds the adapter, runs the wave-based `migrate` stage.
- **Class B, paradigm shift.** Incommensurable, non-revertible artifacts (for example deterministic workflows to a self-hosted agentic harness with no workflows). The decision **refuses the cutover stage** and routes to `pdlc-fork` plus the `coexist` stage.

Classification is explicit and gated. The single most important rule: the plugin detects a paradigm shift and does not pretend it is a retarget.

### 6.1 The migrate stage (Class A execution) **[v2.1]**

Dual binding for the duration of the migration: on `architecture_decision` approval, `.pdlc/adapter.txt` is re-bound to the target (`adapter_id@version`) and `.pdlc/incumbent.txt` records the source (`adapter_id@version`). The source stays hot and serving until the final wave completes its observation window green.

The wave loop: `assign_cohort` runs against the source population. For each wave, deploy the cohort's artifacts on the target (target `deploy`), verify, then cut the cohort's traffic over by re-pointing entry points (webhooks, DNS, routing). **Wave rollback is re-pointing the cohort back to the still-hot source.** It is never `target.rollback`, which only reverts a deployment on the target and cannot cross architectures. The migration plan must list the re-point mechanism per entry point, plus the credential, webhook-URL, and data moves per cohort.

`migration-log` is mandatory for any multi-tenant Class A migration; each tenant moves `incumbent -> migrated` (the Class B intermediate states are skipped) or `rolled_back`.

Exit: after the final wave is green for its window, clear `.pdlc/incumbent.txt`. Source infrastructure teardown is a separate, heavy-gated step, never automatic. Until it runs, full rollback to source remains possible, which is the point of paying the double-running cost.

## 7. Fork with lineage **[v2]**

`pdlc-fork` creates a new project that inherits the source project's logs read-only and its learn-log and adapt-log, and records a `forked_from` edge. Both projects stay live. Distinct from rediscovery (same project, re-bind) and `pdlc-start` (greenfield, no lineage). Serves parallel sibling projects and Class B migrations.

## 7.1 Adoption of an existing system **[v2.1]**

`pdlc-adopt` is the entry point for a system that already exists and was built outside the PDLC (start is greenfield, rediscover requires existing PDLC state, fork requires a PDLC source project). It reads the running system, classifies its architecture against the registered adapters (or proposes a new adapter), binds the current architecture as the baseline behind the `architecture_decision` gate, seeds the neutral logs and `.pdlc` state, writes a baseline ADR, and enters the project at Evolve. Adoption never provisions, migrates, or changes the system; any later re-architecture goes through `pdlc-rediscover`.

## 8. Coexistence and the equivalence harness **[v2]**

`pdlc-coexist` runs the strangler pattern for Class B. The new architecture runs alongside the incumbent, which stays hot as the fallback:

- **Shadow first.** New runs against live inputs with zero customer impact, outputs captured, never returned to users.
- **Equivalence harness replaces revert-rollback.** Because you cannot revert across paradigms, the incumbent is the oracle. The new architecture must match or beat it on a task-acceptance suite before it takes real traffic. Success is measured with agent-era metrics (task completion, human-intervention rate, cost per task, outcome correctness against the incumbent result), not `workflow_success_rate`.
- **Progressive routing** per task class and per tenant, not a single wave percentage. Rollback is "stop routing to new."
- **Per-tenant migration ledger** (`schemas/migration-log.md`) tracks each tenant as a state machine: incumbent, shadowing, partial, migrated, rolled-back.
- **`tenant_migration_consent` gate** for cases where the change alters contracted behavior (for example removing determinism).

## 9. Decommission **[v2]**

`pdlc-decommission` tears down a tenant's incumbent fallback. Irreversible, so it is its own terminal gated stage, allowed only after a defined sustained-green window in coexistence, per tenant.

## 10. Guardrails

`observe` evaluates a universal core set (a latency-equivalent, an error-rate-equivalent, a cost-multiple, a success-rate, sentiment) merged with the adapter's catalog. **[v2]** a cost ceiling is mandatory, not optional, for any agentic-harness adapter, because autonomous agents loop and consume tokens without a fixed workflow bound. **[v2.1]** The ceiling's shape: an absolute currency cap per 24h window, set per tenant and per project, evaluated by `observe` in every stage including shadow. On red breach the core pauses new task intake for the affected scope and opens a gate; agentic targets cannot rely on `rollback` as the brake.

## 11. Logs

Seven neutral schemas carry over from the base plugins. Changed:
- `deployment-log` gains `adapter_id` and a typed `adapter_ext` JSON block, replacing the two forked schemas. See `schemas/deployment-log-ext.md`.
- **[v2]** new `migration-log` for the per-tenant migration ledger. See `schemas/migration-log.md`.

## 12. Skill inventory

New in this plugin: `pdlc-architecture-decision`, `pdlc-rediscover`, `pdlc-fork`, `pdlc-coexist`, `pdlc-decommission`, and **[v2.1]** `pdlc-adopt` (section 7.1). Extended: `pdlc-hitl-gate` (new gate types), `pdlc-log` (schema changes). Carried over with neutralization: `pdlc-start`, the orchestrator, `pdlc-deploy` core loop, `pdlc-status`, `pdlc-resume`. See `PORTING.md`.

## 13. Open decisions to confirm before hardening

1. Adapter format: declarative manifest interpreted by the core, versus a small executable interface per adapter. v1 ships manifest-first.
2. Whether a project may bind different adapters per component. **[v2.1]** Resolved: yes, per-component binding, see section 4.3.
3. Exact universal guardrail core set and the cutoff that triggers "propose a new adapter." **[v2.1]** Partially resolved: the cost-ceiling shape is defined in section 10. The core set and the cutoff remain open.
4. Whether an adapter update auto-propagates to bound projects or is only offered.
5. Sustained-green window length for the decommission gate. **[v2.1]** Resolved: default 14 days, overridable per migration.
6. **[v2.1]** Resolved (operator approved 2026-06-10): migrate-stage execution semantics, see section 6.1.
7. **[v2.1]** Resolved (operator approved 2026-06-10): typed `requires` predicate grammar, see SHIPPING-CONTRACT.
8. **[v2.1]** Resolved (operator approved 2026-06-10): cohort-level consent and decommission gates, decommission per-tenant for the first 5 tenants then cohort-batchable, per-tenant ledger retained.
