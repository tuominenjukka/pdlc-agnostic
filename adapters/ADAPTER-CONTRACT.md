# Target Adapter Contract

An architecture adapter declares what an architecture is, how to stand it up, and how to operate a deployment on it. The neutral core calls only the operations defined here. It never names a specific product (an analytics service, a control plane, an entitlement service) directly.

An adapter is a manifest plus a set of operations. Most variation is data in the manifest. Only the operations are behavior.

## Manifest fields

| Field | Required | Notes |
|---|---|---|
| `adapter_id` | yes | Stable id, kebab-case. Written to every build-log and deployment-log row. |
| `version` | yes | Semver. Bumping it is an adapter update (see `pdlc-rediscover`). |
| `capabilities` | yes | Set used for selection, e.g. `multi-tenant`, `data-residency`, `deterministic-workflow`, `agentic`, `real-time`, `hierarchical-memory`. |
| `discovery_artifacts` | yes | Artifact set Discovery must produce, e.g. `pr-faq`, `c4`. |
| `build_artifact_kind` | yes | What Deliver produces, e.g. `workflow+image`, `agent-definition+tools`. |
| `reference_architecture` | yes | Path to a reusable infrastructure blueprint (components and wiring). See "Reference architecture" below. |
| `metrics_sources` | yes | Where `fetch_metrics` reads, e.g. `timescaledb`, `prometheus`, `langfuse`. |
| `guardrail_catalog` | yes | Adapter-specific guardrails plus defaults, merged with the universal core set. |
| `rollback_constraints` | yes | Limits the core must respect, e.g. `replicaset_depth: 5`, or `non_revertible: true` for paradigm targets. |
| `cost_ceiling_required` | yes | Boolean. MUST be `true` for any agentic adapter (autonomous agents have no fixed work bound). |
| `phase0_fallback` | yes | Manual runbook reference when the control surface is absent. |
| `provisioning_preflight` | no | Declarative list of required-resource rules the core lints the deploy plan against **before** opening the apply gate. Optional; evaluated only once an architecture is bound. See "Provisioning preflight" below. |

## Provisioning preflight (optional)

When an adapter's `provision` / `deploy` has a mandatory target topology (for example a specific cloud network stack), the adapter MAY declare `provisioning_preflight`: a list of rules the core checks against the *plan* output (e.g. `terraform plan`) before opening the apply gate. This turns a sequence of one-failed-apply-at-a-time discoveries into a single up-front lint that surfaces every missing piece at once.

Each rule is an object:

| Key | Required | Notes |
|---|---|---|
| `resource` | yes | The resource type the rule is about (e.g. `cloud_private_network`). Human/diagnostic label; also used in the failure message. |
| `when` | yes | Condition under which the rule applies: the string `"always"`, or a short human-readable predicate the core evaluates against plan context (e.g. `"region is REGION-3-AZ"`). If the predicate does not hold, the rule is skipped. |
| `assert` | yes | Human-readable statement of what must be true. Shown verbatim in the failure list so the remediation is self-explanatory. |
| `match` | yes | A string or pattern the plan output MUST contain for the rule to pass. The core greps the plan text for it. If absent, the rule fails. |

Semantics: this field is **optional**. The core evaluates it only when an architecture is bound and the bound adapter declares it; an adapter with no `provisioning_preflight` is simply skipped (with a note), and before any architecture is bound it does not apply at all. A failing rule does NOT open the apply gate; the core surfaces all failures together and routes to the retry/pivot path. The field is advisory-to-the-plan only: it never changes the wave model, gates, or any other contract behavior.

## Operations

The core calls these. Each accepts an `idempotency_key`.

| Operation | Purpose | Notes |
|---|---|---|
| `provision(scope)` | Stand up infrastructure from the reference architecture for a scope (platform, tenant). | Destructive teardown, not a revert. Always behind a heavy gate. |
| `teardown(scope)` | Remove provisioned infrastructure. | Irreversible. Used by `pdlc-decommission`. |
| `assign_cohort(wave)` | Deterministically slice the population into a wave. | Returns the recipient set. |
| `deploy(wave)` | Ship one wave's change. | Returns a `deploy_ref`. |
| `rollback(wave)` | Revert one wave. | If `rollback_constraints.non_revertible` is true, this operation is unavailable and the project must use `coexist`, not `migrate`. During a cross-architecture `migrate`, wave rollback is re-pointing traffic to the still-hot source, not this operation; see DESIGN 6.1. |
| `fetch_metrics(window)` | Read current metrics for a window from `metrics_sources`. | Feeds `observe` and the equivalence harness. |

## Reference architecture

The blueprint that `provision` materializes: the components an architecture needs and how they connect (compute, datastore, gateway, observability, memory layers, network and residency). It is a reusable template, so most projects reuse a proven blueprint and only bespoke-design when nothing fits. The architecture decision either reuses a reference architecture as-is, or proposes one (new adapter, or an extension of an existing blueprint).

## Selection by capability, not name

The architecture decision selects an adapter by matching the opportunity's required capabilities against `capabilities`, weighted by internal precedent and external best practice. It never selects by hardcoded product name. Below the fit threshold, it proposes a new adapter rather than forcing a poor match.

## What an adapter may not do

It may not change the phase order, add or remove a gate, alter the wave percentages or the green/yellow/red rule, invent a log, or bypass idempotency or the Phase 0 pattern. If a behavior would look different to an operator watching the gates and logs, it does not belong in an adapter.
