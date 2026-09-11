---
name: pdlc-rediscover
description: Re-run Discovery's architecture decision on a live project to evolve its architecture. The standard practice for re-architecting. Re-runs pdlc-architecture-decision against current internal and external evidence, classifies the change as Class A retarget or Class B paradigm shift, and routes Class A to the wave-based migrate stage or Class B to pdlc-fork plus pdlc-coexist. Trigger with "rediscover", "re-architect this project", "move X to a new architecture", or when a live project needs a different target.
---

# pdlc-rediscover

Rediscovery is the main working practice for changing a live project's architecture. It keeps the project's identity and full log lineage while re-deciding the target.

## When to invoke

- An operator wants to move a live project to a different architecture.
- An adapter the project is bound to has a newer reference architecture worth adopting.
- Evidence has shifted (internal learnings, external best practice) enough to revisit the binding.

Do not invoke for a brand-new opportunity (use `pdlc-start`) or for a parallel sibling that should not mutate the source (use `pdlc-fork`).

## Procedure

1. Confirm the project is live and read its current `.pdlc/adapter.txt`, `.pdlc/shipping.txt`, and recent `deployment-log`. Refuse to proceed if a migration is already in flight (an open `migration_id` in `migration-log`, or an active `migrate` stage in `deployment-log`); the open migration must complete or be abandoned first.
2. Call `pdlc-architecture-decision` with the live project as context and any reference input. The decision returns a chosen architecture, a shipping pairing, an ADR, and a **migration class**.
3. Branch on the class:
   - **Class A (retarget).** Artifacts portable, target `rollback` works. Produce a migration plan as a Deliver artifact, re-bind `.pdlc/adapter.txt`, re-select and re-bind `.pdlc/shipping.txt` (the old pairing rarely survives a retarget; validate it against the new architecture), write `.pdlc/incumbent.txt` (source `adapter_id@version`, kept hot until the final wave completes), and run the `migrate` stage via `pdlc-deploy` using the wave model per DESIGN 6.1. Cutover is wave-based; wave rollback is re-pointing the cohort to the still-hot source, never `target.rollback`.
   - **Class B (paradigm shift).** Target is non-revertible or artifacts are incommensurable. Do not re-bind in place and do not cut over. Hand off to `pdlc-fork` to create the new-architecture project with lineage, then run `pdlc-coexist`. The source project stays live throughout.
4. In both cases, append a `learn-log` entry with `topic: rediscovery` recording the class and the rationale.

## Updating an adapter versus migrating a project

These are different and this skill handles only the second.
- **Adapter update:** the adapter definition itself improves (new reference architecture, new shipping option). That is offered to bound projects as an upgrade, not a migration. It does not change the project's identity.
- **Project migration:** this project moves to a different architecture. That is what `pdlc-rediscover` does, via Class A migrate or Class B fork-and-coexist.

## Guardrails on the decision

- Never let a Class B run through the wave-based `migrate` stage. If the decision returns Class B and the operator asks to cut over directly, refuse and explain that the incumbent cannot be reverted to once cut over.
- A re-architecture of a project with live tenants is an irreversible action surface. Every transition is gated.

## Companion skills

`pdlc-architecture-decision`, `pdlc-fork`, `pdlc-coexist`, `pdlc-deploy`, `pdlc-hitl-gate`, `pdlc-log`.
