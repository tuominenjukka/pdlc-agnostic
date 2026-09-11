---
name: pdlc-status
description: Read-only snapshot of in-flight PDLC work for one or all architecture-agnostic PDLC projects. Trigger with `/pdlc-status`, "what's the status of my PDLC projects", "show open gates", "where are we on lead-routing-suite", "what's in flight", or whenever the operator wants a one-screen view of phases, bound adapters, open HITL gates, recent deployments, in-flight migrations, and unresolved adapt-log items. Pulls from deployment-log, migration-log, back-log, adapt-log, and the open-gates cache. Writes nothing.
---

# pdlc-status

Read-only inspection. Use whenever the operator wants to know where things stand without changing anything. The skill never writes a log entry, never opens a gate, never delegates to an agent. It pulls, summarizes, and prints.

## When to invoke

- Operator types `/pdlc-status`.
- Operator asks "what's the status?", "what's open?", "where are we on {project}?".
- Resuming a session and the operator wants the lay of the land before deciding what to do.

## Modes

The skill runs in one of two modes based on input:

- **Project mode** (default): reads `.pdlc/project.txt` and shows status for that project only.
- **All-projects mode**: triggered by `/pdlc-status --all` or by an explicit "show all my PDLC projects". Lists every project that has a folder under `Product/Portfolio/` with at least one row in any of its logs in the last 30 days.

## Reading the adapter binding (per-component)

For each project in scope, resolve its bound adapters:

1. If `.pdlc/components/` exists, read each component's `adapter.txt`, `shipping.txt`, and `shipping-next.txt` (when present) under `.pdlc/components/{component}/`, and show the per-component binding table.
2. If `.pdlc/components/` does NOT exist, read the top-level `.pdlc/adapter.txt` and `.pdlc/shipping.txt` (the single-component case).
3. If neither is set, the project is pre-architecture-decision; show `Architecture: unbound (in Discovery)`.

Also read `.pdlc/incumbent.txt` if present (a live Class A migration keeps the source `adapter_id@version` here while it stays hot).

## Procedure

1. Resolve scope. Project mode reads `.pdlc/project.txt`. All-projects mode lists subfolders under `Product/Portfolio/` excluding `_meta/`.

2. For each project in scope, gather:
   - **Current phase**: read `.pdlc/phase.txt` for the active project (project mode) or infer from the most recent log entry's `phase` column (all-projects mode). If `.pdlc/phase.txt` is missing, infer and surface `(inferred)`. Note that `.pdlc/phase.txt` may show `deploy`; the log-schema phase enum does not include `deploy` because deploy work writes log rows with `phase: deliver`.
   - **Bound adapters**: per the "Reading the adapter binding" section. Show `adapter_id@version` and `shipping_id@version` (per component if multi-component).
   - **Open back-log items** with status `in_progress` or `hitl_pending`. Sort by priority then `updated_at`. Cap at 5 per project.
   - **Open HITL gates**: read `.pdlc/open-gates.jsonl` for the active project, or scan recent `hitl_gate_opened` events without matching close events for the all-projects view.
   - **Active waves**: query `deployment-log` for any `wave_id` whose most recent event is not `wave_completed` or `wave_rolled_back`. Show wave number, observation window remaining, last event timestamp, and `adapter_id`.
   - **In-flight migrations**: query `migration-log` for any `migration_id` with tenants not in a terminal state (`migrated`+`decommissioned`, or `rolled_back`). Show the migration id, the incumbent and target adapters, and a count of tenants per state (incumbent / shadowing / partial / migrated / decommissioned / rolled_back). Skip this block if the project has no `migration-log`.
   - **Recent adapt-log entries** with `resolution: unresolved` or `resolution: escalated` in the last 7 days.
   - **Most recent learn-log entry** per project: a one-line context for the reader.

3. Render. Use the format below. Keep it scannable. Match the operator's terseness preference.

## Output format

### Project mode

```
PROJECT: {project-slug}
Phase: {phase}
Architecture: {adapter_id@version} + {shipping_id@version}   (or per-component table, or "unbound (in Discovery)")
Incumbent (if migrating): {incumbent adapter_id@version}
Last activity: {ISO datetime}

Open back-log ({n}):
- [{priority}] {bl-id} {title}  ({status}, updated {relative time})
- ...

Open HITL gates ({n}):
- {gate-id} {gate_type} — opened {time}, awaiting {approvers}, routed via {cowork|github_pr}
- ...

Active waves ({n}):
- {wave_id}  {adapter_id} v{version}  last_event={event} @ {time}  window_remaining={hours}h
- ...

In-flight migrations ({n}):
- {migration_id}  {incumbent_adapter_id} -> {target_adapter_id}
  tenants: incumbent={a} shadowing={b} partial={c} migrated={d} decommissioned={e} rolled_back={f}
- ...

Unresolved adapt-log ({n}):
- {al-id} {failure_type} on {attempted_action}  ({retry_count} retries)
- ...

Recent learning:
- {ll-id} {topic}: {insight} (one line)

Next action: {what the orchestrator or operator should do next}
```

### All-projects mode

A condensed table:

```
ALL PROJECTS

| Project                | Phase    | Architecture        | Open BL | Open Gates | Active Waves | Migrations | Unresolved | Last Activity      |
| ---------------------- | -------- | ------------------- | ------- | ---------- | ------------ | ---------- | ---------- | ------------------ |
| lead-routing-suite     | deliver  | workflow-multitenant     | 3       | 1          | 0            | 0          | 0          | 2026-05-19 14:08   |
| invoice-classifier     | evolve   | workflow-multitenant     | 1       | 0          | 1            | 0          | 0          | 2026-05-19 13:40   |
| agentic-router         | evolve   | agentic-harness     | 0       | 1          | 0            | 1          | 1          | 2026-05-18 17:22   |

Open gates across all projects:
- {gate-id} {project} {gate_type} — awaiting {approvers}

In-flight migrations across all projects:
- {migration_id} {project} {incumbent}->{target}  (m={migrated}/{total} tenants)

Unresolved adapt-log across all projects:
- {al-id} {project} {failure_type}
```

Cap the table at 10 projects, sorted by `Last Activity` descending. Show "N more" if there are additional projects.

## Source-of-truth precedence

The skill reads from `pdlc-log` (which reads from the canonical store, with cache fallback). If the cache is fresher than the store (e.g., a gate was just closed locally), the skill uses the cache value and notes `(cache, pending sync)` in the output.

## What you do not do

- You do not write any log entries.
- You do not open gates.
- You do not delegate to phase agents.
- You do not interpret unclear situations. If two log entries conflict, surface both and let the operator decide.

## Failure modes

- **Store unreachable**: in `shared` log-store mode, fall back to the local `.pdlc/logs/*.jsonl` cache and mark the output `(local cache only, store unreachable)`; in `repo` mode `.pdlc/logs/` is the canonical record, so read it directly with no fallback banner. Proceed.
- **`.pdlc/project.txt` missing in project mode**: prompt the operator to run `/pdlc-start` or provide a slug explicitly.
- **No projects exist in all-projects mode**: print "No PDLC projects found under Product/Portfolio/. Run /pdlc-start to create one."

## Companion skills

- `pdlc-log` for all reads.
- That's the only dependency. The status skill is intentionally self-contained.
