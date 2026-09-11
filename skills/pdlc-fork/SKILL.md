---
name: pdlc-fork
description: Create a new PDLC project that inherits an existing project's logs and learnings while both stay live. Used for parallel sibling projects and for Class B paradigm-shift migrations where the new architecture must coexist with the incumbent. Records a forked_from lineage edge. Trigger with "fork this project", "spin up a sibling that reuses these learnings", or when pdlc-rediscover routes a Class B change here.
---

# pdlc-fork

A fork is a new project seeded with another project's history. Unlike `pdlc-start` it inherits lineage. Unlike `pdlc-rediscover` it does not mutate the source, both projects stay live.

## When to invoke

- A parallel sibling opportunity would benefit from an existing project's logs and learnings.
- `pdlc-rediscover` classified a change as Class B (paradigm shift) and the new architecture must run alongside the incumbent.

## Required input

1. Source project slug.
2. New project slug (kebab-case, must not exist).
3. Fork reason: `sibling` or `class-b-migration`.

## Procedure

1. Verify the source exists and the new slug is free. If the new slug exists, stop and ask.
2. Create the new project's artifact folder under `{portfolio-root}/{new-slug}/` with the standard empty artifact folders and fresh, empty log sheets (its own writable logs).
3. Inherit lineage:
   - Copy the source `learn-log` and the relevant `adapt-log` entries into the new project's learn-log as `inherited: true` rows, so learnings are present without losing their origin.
   - Grant the new project read-only reference to the source's full log set (do not copy operational logs like deployment-log; reference them).
   - Write `forked_from: {source-slug}` and `fork_reason` into `.pdlc/lineage.txt`.
4. Append an initial `learn-log` entry: `topic: fork`, `actor: {operator-email}`, insight describing what is being reused and why.
5. Set `.pdlc/phase.txt` to `discover`.
6. Hand off to `pdlc-architecture-decision` for the new target. For a `class-b-migration` fork, pass the source project as the incumbent so the decision and the later `coexist` stage know what to run against.

## What a fork is not

- Not a copy of the running system. The source keeps serving its tenants. The fork builds the new architecture.
- Not a way to abandon the source. For a Class B migration, the source is the live incumbent and the fallback until `pdlc-coexist` plus `pdlc-decommission` retire it per tenant.

## Companion skills

`pdlc-architecture-decision`, `pdlc-coexist`, `pdlc-decommission`, `pdlc-log`, `pdlc-start` (for the greenfield alternative).
