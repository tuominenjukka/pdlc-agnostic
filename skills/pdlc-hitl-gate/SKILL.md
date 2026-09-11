---
name: pdlc-hitl-gate
description: Open, route, and close human-in-the-loop approval gates for the architecture-agnostic PDLC meta-builder. Use whenever a PDLC phase transition, wave promotion, rollback, pivot, schema extension, architecture decision, tenant migration consent, or decommission needs explicit operator approval before the orchestrator may continue. Routes the approval request to AskUserQuestion in Claude Cowork or to a GitHub PR label flow in Claude Code, automatically records gate-opened and gate-closed events through pdlc-log, and returns the operator decision to the caller. Trigger proactively whenever the orchestrator or any sub-agent is about to take an action whose effect cannot be cheaply reversed.
---

# pdlc-hitl-gate

The single approval primitive for the PDLC meta-builder. Every gate in the system flows through this skill so the routing, logging, and timeout semantics stay identical across runtimes and across architecture adapters. No adapter may add or remove a gate type; the set below is fixed by the governance spine.

## When to invoke

Open a gate whenever the orchestrator or a sub-agent is about to:

1. Move work from one PDLC phase to the next.
2. Promote a wave to the next cohort size.
3. Trigger a rollback that is not auto-fired by a red guardrail.
4. Take a pivot after retries have been exhausted.
5. Extend a log schema (operator must approve schema gaps before `pdlc-log` will accept new columns).
6. Bind (or re-bind) an architecture and shipping adapter in Discovery or rediscovery.
7. Route real traffic to a new architecture for a tenant whose contracted behavior changes (coexistence).
8. Tear down a tenant's incumbent fallback (decommission).
9. Make any other deploy decision that cannot be cheaply reversed.

If a request is reversible and routine (a typo fix in a back-log description, an evolve-agent ingestion of routine metrics), do not open a gate. Gates exist to slow down irreversible or high-risk actions only.

## CTO review before presenting (0.5.0)

Every gate carries a `pdlc-cto` review. The review runs SEQUENTIALLY before the gate is presented to the operator, so the operator's decision is informed and the auto-advance path can be evaluated. The orchestrator (or the owning skill) invokes `pdlc-cto` and passes the review's recommendation in the `open` payload as `cto_recommendation` (`approve` / `approve-with-override` / `reject`, with override text when applicable). The CTO agent independently re-runs the project's own validators/tests and lints the new decision against the existing ADRs, risk register, and prior contracts for consistency / security / GDPR contradictions. Its review is logged by `pdlc-cto` as a `learn-log` entry with `topic: cto-review` (A3); this skill does not duplicate that row.

### CTO auto-advance (low-risk class only)

For the LOW-RISK gate class ONLY, `pdlc-cto` may close the gate `approve` itself (auto-advance), WITHOUT operator action, but ONLY when all three hold: (a) the gate is in the low-risk class, (b) the CTO's independent verification is fully green, and (c) it raised ZERO consistency/security/GDPR flags. Any failure or any flag => no auto-advance; route to the operator normally with the recommendation attached.

- **LOW-RISK auto-advanceable class:** `discovery_to_delivery` for a `formalize` item; `delivery_to_deploy` for a non-deployed doc/schema/contract asset (activation = merge).
- **NEVER auto-advanceable (always operator), even if green:** `architecture_decision`, `wave_promotion`, `rollback_approval`, `tenant_migration_consent`, `decommission_approval`, `pivot_approval`, `schema_extension`, and any gate whose action is in the orchestrator's irreducible human set. This skill must refuse an auto-advance `close` from `pdlc-cto` for any gate type outside the low-risk class.

When `pdlc-cto` auto-advances, it calls this skill's `close` operation with `decided_by: pdlc-cto`, `decision: approve`, and `auto_advance: true`. The `close` is logged identically to an operator close (`hitl_gate_closed`), and the orchestrator then runs the git-on-approve sequence exactly as for an operator `approve`. Auto-advance never closes a gate guarding an action in the irreducible human set.

## Gate types

| Gate type | When | Logs touched | Closing artifact |
|---|---|---|---|
| `discovery_to_delivery` | Discover phase outputs (PR-FAQ, C4, market analysis) ready to commit to build | `build-log` | |
| `delivery_to_deploy` | Delivery phase outputs (artifact, test pack) ready to deploy as wave 1 | `build-log` (with `related_log_refs` pointing to the test-log run) | |
| `wave_promotion` | Wave N observation window passed green, promote to N+1 | `deployment-log` | |
| `rollback_approval` | Yellow guardrail or operator-requested rollback (red is auto) | `deployment-log`, `adapt-log` | |
| `pivot_approval` | Two retries exhausted, pivot proposed | `adapt-log` | |
| `schema_extension` | A sub-agent wants to add a column to a log schema | `adapt-log` | |
| `architecture_decision` | Before binding an architecture and shipping adapter in Discovery or rediscovery. | `learn-log`, `adapt-log` (when rediscovery-triggered) | The ADR, with the migration class for rediscovery. |
| `tenant_migration_consent` | Before routing real traffic in `pdlc-coexist` when contracted behavior changes. Per tenant, or per cohort with an explicit tenant list. | `migration-log`, `adapt-log` | migration-log row per tenant, consent recorded. |
| `decommission_approval` | Before tearing down a tenant's incumbent fallback. Dedicated approver set, distinct from wave promotion. Per tenant for the first 5 tenants of a migration, then cohort-batchable with an explicit tenant list. | `migration-log`, `adapt-log` | migration-log `decommissioned` row per tenant. |

The first six gates are unchanged from the base spine. The last three are added by this plugin for the architecture-decision and migration stages. `architecture_decision`, `tenant_migration_consent`, and `decommission_approval` each guard an action with no cheap reverse (a committed binding, real traffic on a paradigm-shifted target, an irreversible teardown), so they fail closed like every other gate.

## Per-component / per-tenant approver resolution

`tenant_migration_consent` and `decommission_approval` are tenant-scoped: a single gate may carry an explicit tenant list (cohort form), in which case one gate id appears on every covered tenant's `migration-log` row. `architecture_decision` is project-scoped, and for a multi-component project (DESIGN 4.3) one `architecture_decision` gate covers the whole component set; its summary carries the per-component table. Approver lists are resolved per gate type from `pdlc/hitl.yaml`.

## Runtime routing

The skill picks its routing path based on which runtime it is executing in. Detection is automatic.

### Claude Cowork (desktop)

Use the `AskUserQuestion` tool. Build a single question per gate. Each gate type maps to a fixed question template.

The question payload always includes:
- A one-line summary of what's being approved.
- A `header` tag like `Approve W1?` (kept under 12 chars).
- Two to four options: at minimum `Approve` and `Reject`. For wave promotions, add `Pause` (do nothing, do not promote, hold gate open). For rollbacks, add `Approve + open P0`. For `decommission_approval`, the summary states plainly that the fallback cannot be restored without a rebuild.
- Notes block (rendered by Cowork) containing the artifact links.

The skill blocks on the question response, then closes the gate.

### Claude Code (CLI / headless)

Open or comment on a GitHub PR in the project's repo. The PR is identified by reading `.pdlc/project.txt` and the agent's `pdlc/repo.yaml`. Two flows depending on whether a relevant PR already exists:

**Flow A: PR exists (most common, the delivery-agent already opened it).**
1. Add a comment on the PR with the gate summary, artifact links, and decision options.
2. Add the label `pdlc-gate:{gate-type}` to the PR.
3. Poll for labels every 60 seconds (configurable via `pdlc/hitl.yaml`):
   - `pdlc-approved` -> close gate with `approve`.
   - `pdlc-rejected` -> close gate with `reject`.
   - `pdlc-pause` -> keep the gate open, exit the session, notify orchestrator.
4. Remove the `pdlc-gate:{gate-type}` label on close.

**Flow B: No PR exists (e.g., schema extension or architecture decision before any code exists).**
1. Open a draft PR titled `[pdlc-gate] {gate_type} for {project}`.
2. Put the gate summary and artifact links (including the ADR for `architecture_decision`) in the PR description.
3. Proceed as Flow A.

The list of approvers is read from `pdlc/hitl.yaml` per repo, with a default of the project's CODEOWNERS for the artifact path.

## Per-repo config: `pdlc/hitl.yaml`

The HITL behavior is per project. Example (approver groups are placeholders set per org):

```yaml
defaults:
  timeout_hours: 24
  escalation_after_timeout: slack
poll_interval_seconds: 60
approvers:
  discovery_to_delivery: ["engineering-leads@example.com"]
  delivery_to_deploy: ["engineering-leads@example.com"]
  wave_promotion: ["product-leads@example.com", "engineering-leads@example.com"]
  rollback_approval: ["product-leads@example.com"]
  pivot_approval: ["engineering-leads@example.com"]
  schema_extension: ["pdlc-admins@example.com"]
  architecture_decision: ["principal-engineers@example.com", "engineering-leads@example.com"]
  tenant_migration_consent: ["product-leads@example.com", "account-owner@example.com"]
  decommission_approval: ["principal-engineers@example.com"]   # dedicated set, distinct from wave_promotion
slack_channel: "#pdlc-{project}"
```

## Operations

### open

Procedure:

1. Generate `gate_id` as `GT-{gate_type}-{YYYYMMDD}-{nanoid8}`.
2. Validate the payload: every gate must include `gate_type`, `summary`, `artifacts`, `caller`. Optional: `approvers_override`, `timeout_hours_override`, `auto_promote_allowed`, `tenant_list` (for the cohort form of `tenant_migration_consent` / `decommission_approval`), and `cto_recommendation` (the `pdlc-cto` review result attached for the operator; carry it into the routed question/PR comment so the decision is informed).
3. Call `pdlc-log append` to write a `hitl_gate_opened` event to the relevant phase log (per the table above) and, for retry-or-pivot-triggered and migration-triggered gates, also to `adapt-log`. For `tenant_migration_consent` and `decommission_approval`, also write the per-tenant `hitl_gate_opened` rows to `migration-log` (carrying the base gate record id in `related_log_refs`).
4. Route via Cowork or Claude Code path (see above).
5. Block until decision, timeout, or pause.
6. Call `pdlc-log append` to write a `hitl_gate_closed` event with the decision and comment, plus the gate's closing artifact (per the table): for `architecture_decision`, the ADR ref and migration class; for `tenant_migration_consent`, the consent-recorded migration-log rows; for `decommission_approval`, the `decommissioned` migration-log rows.
7. Return the decision object to the caller: `{ gate_id, decision, decided_by, decided_at, comment }`.

### check

Look up a still-open gate. Useful when a session resumes and needs to know whether a gate has been resolved.

Procedure:
1. Read all `hitl_gate_opened` events from the relevant log without a matching `hitl_gate_closed`.
2. For each, fetch the current state of its routing target (AskUserQuestion is not pollable, so only PR-routed gates are checkable).
3. Return list of open gates with current state.

### close

Used by operators, by an auto-rollback that programmatically resolves a gate, or by `pdlc-cto` on the low-risk auto-advance path. Procedure:
1. Read the open gate by `gate_id`.
2. Authorize the closer:
   - **Operator close:** if the closer is not in the approvers list, reject with `not_authorized`. For `decommission_approval`, the approver set is the dedicated decommission set, not the wave_promotion set.
   - **CTO auto-advance close** (`decided_by: pdlc-cto`, `auto_advance: true`): allowed ONLY when the gate type is in the low-risk auto-advanceable class (`discovery_to_delivery` for a `formalize` item, `delivery_to_deploy` for a non-deployed doc/schema/contract asset) AND the CTO review was fully green with zero consistency/security/GDPR flags. Refuse with `not_authorized` for any other gate type (the never-auto-advanceable set and anything in the orchestrator's irreducible human set), and refuse with `auto_advance_blocked` if the review carried any failure or flag. The decision recorded is `approve`.
3. Write `hitl_gate_closed` to `pdlc-log` with decision, decided_by, comment, and the closing artifact.
4. If PR-routed, remove the gate label and post a closing comment.
5. Return decision to any caller blocked on this gate.

## Timeouts and escalation

Default timeout is 24 hours. On timeout:
1. Write a `hitl_gate_timeout` event to `pdlc-log` (in the phase log and `adapt-log`).
2. Send a notification to the per-project channel listing the gate and approvers.
3. Escalate to the default admin group if still unresolved after a second 24-hour window.
4. After 72 total hours, fail closed: treat as `reject`, write `hitl_gate_failed_closed` to `adapt-log`, surface to the orchestrator which then logs an `escalation` adapt-log entry.

Fail-closed is the safe default because every gate is guarding an irreversible action.

## Decision payload

The decision object returned by `open`:

```json
{
  "gate_id": "GT-wave_promotion-20260519-7fk2a9c1",
  "gate_type": "wave_promotion",
  "decision": "approve",
  "decided_by": "operator@example.com",
  "decided_at": "2026-05-20T08:14:22Z",
  "comment": "Wave 1 metrics look clean. Promote to 30%.",
  "routing": "github_pr",
  "routing_ref": "github://acme/lead-routing-suite/pull/42#issuecomment-12345"
}
```

`routing` is one of `cowork` or `github_pr` (set by the skill from the detected runtime). `routing_ref` is an `askuserquestion://...` URI when routed through Cowork.

Possible `decision` values: `approve`, `reject`, `pause`, `timeout`, `failed_closed`.

### Pause semantics

`pause` is a non-terminal outcome. When pause is selected, the skill writes a `hitl_gate_paused` event (with `hitl_decision: pause`) to the relevant log and returns `decision: pause` to the caller, but the gate is **not** closed. A future session can resume by calling `check` to detect the still-open gate and `open` again to re-route the approval request. A gate that has been paused but not subsequently resolved still counts toward timeout.

Terminal outcomes are `approve`, `reject`, `timeout`, and `failed_closed`. Only these emit `hitl_gate_closed`, `hitl_gate_timeout`, or `hitl_gate_failed_closed` respectively.

## Logging contract

This skill never writes to a store or jsonl directly. All gate events flow through `pdlc-log append`. The event names this skill emits:

- `hitl_gate_opened`
- `hitl_gate_closed`
- `hitl_gate_timeout`
- `hitl_gate_failed_closed`
- `hitl_gate_paused`

`pdlc-log` does not auto-detect these; the caller (this skill) is responsible for naming them correctly.

## Examples

### Open a wave-promotion gate from Cowork

```
pdlc-hitl-gate open {
  gate_type: "wave_promotion",
  summary: "Promote territory-router 1.2.0 from wave 1 (10%) to wave 2 (30%). All guardrails green after 24h observation.",
  artifacts: [
    "https://drive.example.com/.../deployment-log",
    "https://github.com/acme/lead-routing-suite/pull/42"
  ],
  caller: "delivery-agent",
  project: "lead-routing-suite",
  agent_id: "territory-router",
  related_log_refs: "deployment-log:DL-20260519-7fk2a9c1"
}
```

This generates an AskUserQuestion with header `Promote W2?`, options `Approve`, `Pause`, `Reject`, and the summary in the question body.

### Open an architecture_decision gate

```
pdlc-hitl-gate open {
  gate_type: "architecture_decision",
  summary: "Bind workflow-multitenant@1.0.0 + tenant-wave@1.0.0 for lead-routing-suite. Class A. ADR attached.",
  artifacts: ["drive://Product/Portfolio/lead-routing-suite/c4/ADR-001.md"],
  caller: "pdlc-architecture-decision",
  project: "lead-routing-suite"
}
```

### Open a decommission_approval gate (per tenant)

```
pdlc-hitl-gate open {
  gate_type: "decommission_approval",
  summary: "Retire incumbent fallback for tenant acme on migration legacy-router->agentic-router. 14d sustained-green met. Irreversible.",
  artifacts: ["migration-log:ML-20260620-7fk2a9c1"],
  caller: "pdlc-decommission",
  project: "agentic-router",
  tenant_list: ["acme"]
}
```

## Git on approve (0.5.0)

The gate approval IS the git authorization. On a terminal `approve` (operator-decided or CTO auto-advanced), the orchestrator runs the git itself — there is no manual operator git. For `discovery_to_delivery` and a non-activation `delivery_to_deploy`, that is a commit + push on the item branch; for an activation = merge `delivery_to_deploy`, the approval authorizes the known-good `gh pr merge --squash --delete-branch` + `git checkout main && git pull --ff-only` + next-branch sequence (see the orchestrator's "Git on gate approval"). This skill only records the decision; it does not run git. Destructive git (`push --force`, history rewrite) is never authorized by a gate approval and stays on explicit operator ask.

## Companion skills

- `pdlc-log`: every event lands there.
- `pdlc-cto` (agent): runs the technical review before this skill presents any gate, and is the only non-operator allowed to `close` a gate — on the low-risk auto-advance path only.
- `pdlc-deploy`: opens `wave_promotion` and `rollback_approval` gates on wave transitions.
- `pdlc-orchestrator` (agent): opens `discovery_to_delivery`, `delivery_to_deploy`, `pivot_approval`, `architecture_decision` (via the discovery-agent / rediscover), `tenant_migration_consent`, and `decommission_approval` gates, and runs the git-on-approve sequence on gate approval.
- `pdlc-architecture-decision`, `pdlc-coexist`, `pdlc-decommission`: open the three added gate types.

Do not bypass this skill for ad-hoc operator confirmations. Every approval that affects state must be a logged gate. Routine confirmation prompts ("Did you mean X?") should use AskUserQuestion or a simple chat exchange directly, not a gate.
