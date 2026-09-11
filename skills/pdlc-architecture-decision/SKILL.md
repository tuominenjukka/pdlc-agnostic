---
name: pdlc-architecture-decision
description: Run the Solution Architecture Decision inside Discovery. Derive the opportunity's required capabilities, gather company-internal and external best-practice evidence, score registered architecture adapters, select and validate a compatible shipping adapter, emit an ADR, and bind both adapters behind the architecture_decision HITL gate. Trigger after the discovery-agent has framed the opportunity, or from pdlc-rediscover and pdlc-fork when an existing project needs a fresh architecture decision.
---

# pdlc-architecture-decision

The decision engine that picks the target architecture and shipping approach. Called once per project during Discovery, and again by `pdlc-rediscover` and `pdlc-fork`.

## When to invoke

- The discovery-agent has produced the opportunity framing (PR-FAQ or PRD equivalent) and the project needs an architecture.
- `pdlc-rediscover` asks for a fresh decision on a live project.
- `pdlc-fork` needs a decision for the forked project.

## Inputs

- The opportunity framing from Discovery.
- The current `.pdlc/project.txt`, and for rediscovery or fork, the source project's `forked_from` or rediscovery context.
- An optional reference input: an existing project's outputs used as a validated spec (the MVP-as-reference case).

## Procedure

1. **Derive required capabilities.** From the framing and any reference input, extract the capability set: tenancy model, data residency and PII, real-time versus batch, expected scale and usage shape, UI surface, integration points, reversibility needs, and memory layers (company, project, user).

2. **Gather evidence.**
   - Internal: read the organization's knowledge base for the Engineering Guide, prior project C4 and ADRs, and relevant `learn-log` and `adapt-log` entries (what worked, what was rolled back, what escalated).
   - External: web-search current best practice for the candidate runtimes and for agentic-automation design patterns, at decision time, so the choice is not frozen.

3. **Score architecture adapters.** For each registered adapter in `adapters/architecture/`, score capability fit, internal precedent, external alignment, and reversibility and operational cost. If the best score is below threshold, the decision is "propose a new adapter and reference architecture," not a forced match.

4. **Select and validate shipping.** Choose a shipping adapter from `adapters/shipping/` whose `requires` block evaluates true against the chosen architecture's manifest and the project facts. If none holds, propose a shipping approach. Record the pairing. When more than one shipping adapter is valid, select the lightest strategy that satisfies the opportunity's risk profile; binding a heavier one (for example shadow-strangler onto a cleanly revertible Class A target) is allowed only with explicit justification in the ADR, and is flagged as over-heavy in the gate summary.

5. **Cost-ceiling check.** Key on the manifest field: if the chosen architecture declares `cost_ceiling_required: true` (which MUST be the case whenever `capabilities` includes `agentic`; treat any disagreement between the two as a manifest defect and refuse), require a cost-ceiling guardrail in the project's `guardrails.yaml`: an absolute currency cap per 24h window, set per tenant and per project. Refuse to bind without it.

6. **Emit the ADR.** Write an Architecture Decision Record to the project's `c4/` (or `product/`) folder, citing the internal and external evidence used and the rejected alternatives. Append a `learn-log` entry with `topic: architecture-decision`.

7. **Open the gate.** Open the `architecture_decision` HITL gate via `pdlc-hitl-gate`. The operator approves, rejects, or requests a different adapter.

For a multi-component opportunity (DESIGN 4.3), run capability derivation, scoring, and pairing per component, emit one ADR with a component table, and bind under `.pdlc/components/{component}/`. A single `architecture_decision` gate covers the set.

8. **Bind on approval.** Write `.pdlc/adapter.txt` (architecture `adapter_id@version`) and `.pdlc/shipping.txt` (shipping `shipping_id@version`); pin the version so an adapter update can be offered explicitly instead of absorbed silently. Append a `deployment-log` row is not done here; binding is a discovery artifact, not a deploy event.

## Migration classification (called from rediscovery)

When invoked by `pdlc-rediscover` against a live project, also classify the change:
- **Class A (retarget):** artifacts portable, target adapter exposes a working `rollback`, and portability is verified rather than assumed: run an export/import test of a representative artifact into a scratch target, and list version skew, credential, webhook-URL, and community-node deltas in the migration plan. If portability cannot be verified, classify as B. Route to the `migrate` stage (wave-based cutover).
- **Class B (paradigm shift):** target adapter has `rollback_constraints.non_revertible: true`, or the build_artifact_kind is incommensurable with the source. Refuse the cutover stage. Route to `pdlc-fork` plus `pdlc-coexist`.

Write the class into the ADR and the `architecture_decision` gate summary. Misclassifying a Class B as Class A is the most dangerous failure this skill can make, so when in doubt, classify as B.

## What you do not do

You do not provision infrastructure, write code, or open a migration. You produce a decision, an ADR, a class, and a binding. The stages act on the binding.

## Companion skills

`pdlc-log`, `pdlc-hitl-gate`, `pdlc-rediscover`, `pdlc-fork`.
