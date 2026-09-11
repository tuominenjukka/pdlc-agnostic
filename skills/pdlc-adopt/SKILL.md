---
name: pdlc-adopt
description: Bring an existing, already-built system under PDLC governance without changing it. Read the running system, classify its current architecture against registered adapters or propose a new adapter, bind the current architecture as the baseline behind the architecture_decision gate, seed the neutral logs and .pdlc state, write a baseline ADR, and enter the project at Evolve. Trigger with "adopt this system", "bring X under the PDLC", or when a system built outside the PDLC needs governance. Never use for greenfield (pdlc-start), re-architecting a governed project (pdlc-rediscover), or lineage forks (pdlc-fork).
---

# pdlc-adopt

The entry point for a system that already exists and was built outside the PDLC. Adoption formalizes what is, it does not change what is. The system keeps running untouched; the PDLC wraps governance around it.

## Why this skill exists

The other three entries do not fit an existing system: `pdlc-start` is greenfield and assumes nothing exists, `pdlc-rediscover` requires a live PDLC project with `.pdlc` state and logs, `pdlc-fork` requires a PDLC source project to inherit from.

## Required input

1. System name and project slug (kebab-case, must not exist as a PDLC project).
2. Read access to the system's current state: code, configs, infrastructure descriptions, runbooks, any docs.
3. The operator's statement of what the system does and who depends on it.

## Procedure

1. **Read the system.** Inventory components, runtime, tenancy model, data residency, integrations, memory layers, and operational surface. Read only; adoption never modifies the system.
2. **Classify the architecture.** Run `pdlc-architecture-decision` in adoption mode: score the CURRENT architecture against the registered adapters. The question is "which adapter describes what is running", not "which adapter should run it". If no adapter fits above threshold, propose a new adapter manifest and reference architecture that describe the system as built. If the system is agentic, the proposed adapter MUST set `cost_ceiling_required: true`, and binding requires a cost-ceiling guardrail like any other agentic binding.
3. **Write the baseline ADR.** Record the current architecture as the bound baseline, the evidence read, the capabilities observed, and the known gaps or risks. The ADR states explicitly that this decision documents an existing state rather than selecting among alternatives.
4. **Open the `architecture_decision` gate.** The operator approves the classification and binding. Nothing is bound before approval.
5. **Bind and seed on approval.** Write `.pdlc/project.txt`, `.pdlc/phase.txt` (set to `evolve`), `.pdlc/adapter.txt` (`adapter_id@version`), and `.pdlc/shipping.txt`. Seed the neutral logs empty, then append the first `learn-log` entry with `topic: adoption` describing what was adopted and why. If the system has no sensible shipping adapter yet (for example it ships ad hoc), record `shipping: unbound` and flag selecting one as the first Evolve back-log item.
6. **Enter Evolve.** The system is now observed under the universal guardrail core plus the adapter catalog. Deliver work on it follows the normal spine from here on.

## What adoption is not

- Not a migration. Nothing moves. A later re-architecture is a normal `pdlc-rediscover` on the now-governed project.
- Not retroactive history. Logs start at adoption; do not fabricate past entries. Prior history lives in the ADR narrative.
- Not approval to change the system. Adoption grants governance, not a build mandate.

## Guardrails

- Read-only against the system, always.
- The `architecture_decision` gate is mandatory even though nothing is being built, because the binding determines every future guardrail and migration classification.
- An agentic system without an enforceable cost ceiling may be adopted only with the missing ceiling recorded as a P1 back-log item at the gate.

## Companion skills

`pdlc-architecture-decision`, `pdlc-rediscover`, `pdlc-log`, `pdlc-hitl-gate`.
