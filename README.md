# pdlc-agnostic

An architecture-agnostic Product Development Lifecycle (PDLC) meta-builder for [Claude Code](https://docs.claude.com/en/docs/claude-code) and Claude Cowork.

One process spine, Discover, Deliver, Evolve, that stays fixed for every project. Everything architecture-specific lives behind two pluggable contracts (a Target Adapter and a Shipping Adapter) that are chosen during Discovery, not hard-coded into the process. The plugin ships the lifecycle agents, the human-in-the-loop (HITL) gates, nine append-only logs, and a build-time CTO reviewer agent that independently re-verifies every gate before a human sees it.

It was built to run real product increments unattended for hours at a time and still leave a human in control of every irreversible action.

## What you get

**Lifecycle agents**

| Agent | Role |
|---|---|
| `pdlc-orchestrator` | Master engineering meta-agent. Owns phase transitions, opens every HITL gate, runs retry / pivot / escalate, keeps project state under `.pdlc/`. Never builds artifacts itself. |
| `pdlc-discovery-agent` | Discover phase: problem framing, PR-FAQ, C4, risks, market evidence, back-log items. Calls the architecture decision engine. |
| `pdlc-delivery-agent` | Deliver phase: builds the increment through the bound adapter, writes tests before declaring done, records build-log and test-log. |
| `pdlc-evolve-agent` | Evolve phase: observes metrics through the adapter, ingests errors and feedback, triggers observe / promote / rollback. Observes, never mutates. |
| `pdlc-cto` | Build-time CTO. Re-runs the project's own validators and tests, lints new decisions against ADRs, risk register and schemas for consistency, security and GDPR contradictions, and emits approve / approve-with-override / reject at every gate. |

**Skills (slash commands)**

| Skill | Purpose |
|---|---|
| `pdlc-start` | Bootstrap a greenfield project: folder set, empty logs, `.pdlc/` state, permissions profile. |
| `pdlc-adopt` | Bring an existing system under the PDLC without rebuilding it. |
| `pdlc-architecture-decision` | The decision engine: bind a Target Adapter and a Shipping Adapter behind the `architecture_decision` gate, classify migrations as Class A (retarget, revertible) or Class B (paradigm shift, not revertible). |
| `pdlc-rediscover` | Re-architect a live project. The default way to evolve architecture. |
| `pdlc-fork` | New project with inherited lineage (logs, ADRs, learnings) from a parent. |
| `pdlc-coexist` | Shadow or strangler stage for Class B migrations, with the incumbent as the equivalence oracle. |
| `pdlc-decommission` | Retire the incumbent behind a terminal gate with a dedicated approver. |
| `pdlc-deploy` | Plan, execute, observe, promote and roll back waves through the bound adapters. |
| `pdlc-preflight` | Deploy preflight: plan lint against the adapter's guardrail catalog. |
| `pdlc-gate`, `pdlc-hitl-gate` | Open, route, check and close HITL gates from chat, a PR label, or an `AskUserQuestion` prompt. |
| `pdlc-log` | Read, append and reconcile the nine canonical logs plus the migration ledger. |
| `pdlc-status`, `pdlc-resume`, `pdlc-rollback` | One-screen status, resume after an externally closed gate, operator-triggered rollback. |

**Adapters (reference implementations)**

- `adapters/architecture/agentic-harness-selfhosted.md`: a self-hosted LLM with a full agentic harness and no deterministic workflows. The Class B stress-test target.
- `adapters/shipping/tenant-wave.md`: standard wave rollout across multi-tenant cohorts.
- `adapters/shipping/env-promotion.md`: dev, staging, prod promotion for infrastructure changes.
- `adapters/shipping/shadow-strangler.md`: Class B coexistence.
- `adapters/shipping/direct-mvp.md`: ship-all, no live customers.

The adapter contracts are in `adapters/ADAPTER-CONTRACT.md` and `adapters/SHIPPING-CONTRACT.md`. Adapters are plain Markdown manifests plus operation descriptions; write one for your own stack and register it in Discovery. The `reference_architecture` and `phase0_fallback` paths in the manifests are placeholders you fill in for your adapter.

## Install

Add the marketplace and install the plugin from a Claude Code session:

```
/plugin marketplace add tuominenjukka/pdlc-agnostic
/plugin install pdlc-agnostic@pdlc-agnostic
```

In Claude Cowork, add the same marketplace from the plugin settings and enable `pdlc-agnostic`.

To try a local checkout without installing, run Claude Code with `claude --plugin-dir /path/to/pdlc-agnostic`.

## Quick start

1. In the repository you want to build in, run `/pdlc-start` and give the orchestrator a one-paragraph brief. It scaffolds `.pdlc/`, the log store, a `.gitignore` that keeps the audit trail, and a Claude Code permissions profile that auto-allows reversible in-repo work and always asks for the irreducible human set.
2. Discovery produces the PR-FAQ, C4 and risks, then calls `pdlc-architecture-decision`. You approve the `architecture_decision` gate; that binds a Target Adapter and a Shipping Adapter.
3. Delivery builds the increment through the adapter, writes tests, and stops at the `delivery_to_deploy` gate. `pdlc-cto` re-runs the tests and reviews before you see the gate.
4. `pdlc-deploy` plans waves, `pdlc-evolve-agent` observes them, guardrail breaches roll back automatically, promotions wait for you.
5. Come back any time with `/pdlc-status` or `/pdlc-resume`. Every gate writes `.pdlc/CHECKPOINT.md` for single-read resume.

## Design principles

- **The spine is invariant.** Three phases in order, append-only logs, the HITL gate as the only path to an irreversible action, idempotency on every mutation, retry-pivot-escalate, and a Phase 0 manual fallback. Adapters contribute mechanism and guardrails, never process.
- **Assert the outcome, not the status.** The CTO agent re-runs validators itself. A green self-report is not evidence.
- **The irreducible human set is policy.** Merges to a protected branch, deploys to customers, spend, data deletion, consent changes and decommission always wait for a person.
- **Migrations are classified.** Class A retargets are revertible and use waves. Class B paradigm shifts refuse the cutover stage and go through fork, coexist and decommission instead.

`DESIGN.md` is the spec of record and explains each of these in depth.

## Repository layout

```
.claude-plugin/     plugin.json and marketplace.json
DESIGN.md           the spec of record
adapters/           the two contracts and the reference adapters
agents/             the five lifecycle agents
schemas/            migration-log and the deployment-log extension
skills/             the skills, each with SKILL.md (pdlc-log carries the nine log schemas)
```

## Contributing

Improvements are welcome: new reference adapters for other stacks, better gate routing, schema fixes, docs. See `CONTRIBUTING.md`. Please open an issue before a large change so the design stays coherent.

## License

MIT License. Copyright 2026 Jukka Tuominen. See `LICENSE`.
