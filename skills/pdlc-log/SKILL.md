---
name: pdlc-log
description: Read, append, and reconcile entries in the nine PDLC logs that power the architecture-agnostic PDLC meta-builder (back-log, build-log, learn-log, test-log, deployment-log, user-behavior-log, error-log, feedback-log, adapt-log), plus the companion migration-log for cross-architecture migrations. Use whenever the PDLC orchestrator or any sub-agent needs to record a decision, event, observation, or failure that must persist beyond the current session. Trigger proactively whenever Discovery, Delivery, or Evolve produces a durable result, whenever a HITL gate opens or closes, whenever a retry or pivot is taken, and whenever a wave-rollout or migration decision is made.
---

# pdlc-log

Single source of truth for the nine canonical logs that drive the Product Development Life Cycle, plus the companion migration-log used during cross-architecture migrations. The orchestrator and every sub-agent (discovery-agent, delivery-agent, evolve-agent) read and append through this skill so the log surface stays consistent across sessions and runtimes. The log surface is architecture-neutral: no log encodes a specific product, and the only product-specific deployment fields live under the deployment-log `adapter_ext` namespace.

## When to invoke

Invoke `pdlc-log` whenever any of these is true:

1. A PDLC phase produces a result the next session needs to read (a backlog item, a build artifact reference, a learning, a test outcome, a deployment record).
2. The agent crosses a HITL gate (record the gate decision in the relevant phase log and, on retries or pivots, in `adapt-log`).
3. The evolve-agent observes a metric, error, or feedback signal that must persist.
4. The retry-pivot-escalate protocol fires (always append to `adapt-log`).
5. A wave rollout advances, pauses, or rolls back (always append to `deployment-log`).
6. A tenant changes migration state during a Class A `migrate` or a Class B `coexist`/`decommission` (append to `migration-log`).

If a request needs information that has been captured in a prior session, the first move is `pdlc-log read` against the relevant log, not asking the operator to recall it.

## Storage model

The log-store home is set per project in `.pdlc/log-store.txt`, one of two modes, and every reader and writer keys off it. If the marker is absent, assume `repo` (the safe default, so the record lives with the code and is never silently lost).

- **`repo` (default for greenfield and any project without a shared document connector):** `.pdlc/logs/{log-name}.jsonl` **is** the canonical, durable audit trail, tracked in git and committed with the code. There is no separate shared store; writes go only to `.pdlc/logs/`. Because this is the record, the scaffolded `.gitignore` tracks `.pdlc/logs/` (see `pdlc-start`), so it survives a fresh clone.
- **`shared` (when the operator's environment provides a shared document store, e.g. a Google Drive of Sheets):** the shared store is canonical and `.pdlc/logs/{log-name}.jsonl` is a write-through cache. Every write goes to both. If the shared store is unreachable, write to the cache and append a reconciliation entry to `adapt-log` with `failure_type: drive_write_failed`. In this mode the cache is not committed.

**Canonical store layout (reference deployment):**

```
Product/
  Portfolio/
    _meta/
      adapt-log                       # global, cross-project
    {project-slug}/
      pdlc-logs/
        back-log
        build-log
        learn-log
        test-log
        deployment-log
        user-behavior-log
        error-log
        feedback-log
        migration-log                 # present only for projects with a cross-architecture migration in flight
        # adapt-log is global, lives at Product/Portfolio/_meta/ above
```

`adapt-log` is global because the orchestrator itself can fail outside the scope of any single project. Every other log is partitioned by **project** slug.

**Cache layout (inside the workflow repo or plugin scratch):**

```
.pdlc/
  logs/
    back-log.jsonl
    build-log.jsonl
    ...
    migration-log.jsonl                # when applicable
    adapt-log.jsonl
  reconciliation-queue.jsonl          # pending canonical-store writes
  project.txt                         # current project slug
```

## Project vs customer

The PDLC logs are partitioned by **project** (the deployable container), not by customer. A project ships one bound architecture (or a per-component set of bound architectures); customer-specific behavior is gated by whatever entitlement or cohort mechanism the bound architecture adapter provides.

The `customer` column is retained as an optional filter column on rows that are inherently tenant-scoped (errors from a specific tenant instance, feedback from a specific user, behavior metrics for a tenant cohort). It is never the partition key.

When the evolve-agent or `pdlc-deploy` needs to resolve a cohort of customers entitled to a feature or version, it calls the bound architecture adapter's `assign_cohort` operation rather than reading a customer list from a log. Cohort identifiers in `deployment-log` therefore point to the adapter-resolved cohort reference returned by `assign_cohort`, not to a document listing customers.

## Operations

The skill exposes four operations. Each is described as a procedure the agent runs, not a CLI command, so it works identically in Cowork and Claude Code.

### append

Every log entry must include the universal fields (see "Universal columns" below) plus the log-specific columns defined in `schemas/{log-name}.md`. Procedure:

1. Resolve project slug from `.pdlc/project.txt` (or prompt operator if missing on first run).
2. Generate `id` as `{LOG-PREFIX}-{YYYYMMDD}-{nanoid8}`. Prefixes: BL, BU, LL, TL, DL, UB, EL, FL, AL, ML.
3. Set `created_at` and `updated_at` to ISO 8601 with timezone.
4. Validate the entry against the schema in `schemas/{log-name}.md`. Reject if required columns missing.
5. In `shared` mode, append a row to the shared store via the configured document MCP. In `repo` mode there is no shared store, so skip this step; the `.pdlc/logs/` write in step 6 is the canonical write.
6. Append a JSON line to `.pdlc/logs/{log-name}.jsonl` **via the append helper (see "Safe write mechanics" below), never an inline shell append.**
7. If step 5 fails, append the row to `.pdlc/reconciliation-queue.jsonl` and write an `adapt-log` entry. Continue.

### read-by-id

Look up a single entry. Try cache first (`grep` the jsonl). Fall back to a canonical-store query if not in cache.

### read-recent

Return the last N entries for a given log. Default N is 25 unless caller specifies. In `shared` mode, read from the shared store to avoid a stale cache; in `repo` mode, read from `.pdlc/logs/` (it is canonical).

### query-by-field

Filter entries by one or more column values. Used heavily by the evolve-agent (e.g., `query error-log where severity=high and customer=acme and timestamp > 7d ago`).

## Safe write mechanics (tool-hygiene, mandatory)

Every cache append and every pre-commit guard runs through two small helper scripts kept in the workflow repo at `.pdlc/bin/`. The point is to keep every emitted shell command free of heredocs, `python3 -c` one-liners with braces or f-strings, `$'...'` ANSI-C quoting, and secret-shaped regex. Those constructs trip Claude Code's hardcoded safety prompts and stall an otherwise-approved autonomous run. Do not inline them. Always write a file with the Write tool, then run the helper by its stable path.

**Bootstrap (idempotent, once per repo).** Before the first append or commit in a session, ensure `.pdlc/bin/pdlc_append.py` and `.pdlc/bin/pdlc_guard.py` exist. If either is missing, create it with the Write tool from the exact body below (use the Write tool, do not shell-echo the body). These bodies are the canonical source.

`.pdlc/bin/pdlc_append.py`:

```python
#!/usr/bin/env python3
"""Append one JSON row to a JSONL log, deduping on id+v.
Usage: pdlc_append.py <jsonl_path> <row_json_path>"""
import json, os, sys

def main():
    if len(sys.argv) != 3:
        print("usage: pdlc_append.py <jsonl_path> <row_json_path>", file=sys.stderr)
        return 2
    jsonl_path, row_path = sys.argv[1], sys.argv[2]
    with open(row_path, encoding="utf-8") as fh:
        row = json.load(fh)
    rid, rv = row.get("id"), row.get("v", 1)
    os.makedirs(os.path.dirname(jsonl_path) or ".", exist_ok=True)
    if os.path.exists(jsonl_path):
        with open(jsonl_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    existing = json.loads(line)
                except ValueError:
                    continue
                if existing.get("id") == rid and existing.get("v", 1) == rv:
                    print(f"skip: {rid} v{rv} already present")
                    return 0
    with open(jsonl_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"appended: {rid} -> {jsonl_path}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

`.pdlc/bin/pdlc_guard.py`:

```python
#!/usr/bin/env python3
"""Pre-commit guard: block secret-shaped strings in the staged diff.
Exit 0 = clean, 1 = violation. Usage: pdlc_guard.py
(No style checks here: em-dash / prose style is a human-facing-output concern,
not a code-commit concern, so it is deliberately not scanned.)"""
import re, subprocess, sys

def main():
    diff = subprocess.run(
        ["git", "diff", "--cached", "--unified=0"],
        capture_output=True, text=True,
    ).stdout
    added = "\n".join(
        ln[1:] for ln in diff.splitlines()
        if ln.startswith("+") and not ln.startswith("+++")
    )
    secret = re.compile(
        r"sk-ant-[A-Za-z0-9_\-]{8,}"
        r"|(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*[\"']?[A-Za-z0-9_\-]{12,}"
    )
    if secret.search(added):
        print("GUARD FAIL: possible secret; keep it out of the commit", file=sys.stderr)
        return 1
    print("GUARD: clean")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

**Append procedure (replaces any inline jsonl write in step 6 of `append`).**

1. Write the fully-formed row to `.pdlc/tmp/{log-name}-{id}.json` with the Write tool (not bash).
2. Run: `python3 .pdlc/bin/pdlc_append.py .pdlc/logs/{log-name}.jsonl .pdlc/tmp/{log-name}-{id}.json`. The helper dedups on `id`+`v` and appends a single JSON line, printing `appended:` or `skip:`.
3. The canonical-store write (step 5) is unchanged; only the cache mechanic changes.

**Pre-commit guard (replaces any improvised secret grep).** After staging and before every commit, run `python3 .pdlc/bin/pdlc_guard.py`. It exits non-zero on a secret-shaped string in the staged diff. Never write an inline `grep -iE 'sk-ant...'` on the command line; that inline form is exactly what triggers the obfuscation prompts. On failure, fix the staged content and re-run. The guard does not check prose style: em-dash / "no AI-generated tone" is a human-facing-output rule (operator messages and customer-facing generated copy), not a code-commit rule, so internal code and logs are never scanned for it.

**Allowlist note (for the operator).** Because these are stable, argument-only commands, they can be added to the repo's `.claude/settings.json` under `permissions.allow` so they run without a prompt: `Bash(python3 .pdlc/bin/pdlc_append.py:*)` and `Bash(python3 .pdlc/bin/pdlc_guard.py:*)`. Push and merge stay gated.

## Universal columns

Every log entry, regardless of type, includes:

| Column | Type | Required | Notes |
|---|---|---|---|
| `id` | string | yes | Format above. Globally unique. |
| `created_at` | ISO 8601 datetime | yes | UTC, with offset. |
| `updated_at` | ISO 8601 datetime | yes | UTC, with offset. Equal to `created_at` on insert. |
| `project` | string | yes | Project slug (the deployable container). Use `_meta` for adapt-log entries not scoped to a project. |
| `agent_id` | string | no | The managed agent/artifact under management within the project. Empty for project-level entries. |
| `customer` | string | no | Tenant the row pertains to. Set on observation/feedback/error/cohort rows. Never used as a partition. |
| `phase` | enum | yes | `discover`, `deliver`, `evolve`, `meta` |
| `actor` | string | yes | `discovery-agent`, `delivery-agent`, `evolve-agent`, `orchestrator`, or operator email. |
| `session_ref` | string | no | Claude session id or PR number, for traceback. |
| `notes` | string | no | Free text. |

Log-specific columns are listed in each `schemas/{log-name}.md` file. Treat them as additive: the universal columns always come first.

## Append-only discipline

These logs are append-only. To "edit" an entry, append a new entry with the same `id` and an incremented version field (`v` column, default 1). The query layer always returns the highest `v` per `id`. This preserves history and lets the adapt-log show the full sequence of state changes.

The only exception is `back-log`, which tracks live state (status, assignee). For `back-log`, use an `updated_at` bump plus a new entry with the changed fields, but keep `id` constant. See `schemas/back-log.md`.

## HITL gate logging

A HITL gate is logged in two places:
- The phase log it relates to (e.g., delivery gate -> `build-log` with `event: hitl_gate_opened` then `event: hitl_gate_closed`).
- `adapt-log` whenever the gate is triggered by a meta-builder event rather than a normal phase transition: retries, pivots, rollback approvals, and schema-extension proposals all write to `adapt-log` in addition to (or, for `schema_extension`, instead of) the phase log.

The `pdlc-hitl-gate` skill calls `pdlc-log append` automatically. Do not duplicate.

## Cross-references

When one log entry references another (e.g., a deployment-log row references a build-log row), use the column `related_log_refs` containing a comma-separated list of `{log-name}:{id}` pairs. Example: `build-log:BU-20260519-7fk2a9c1, test-log:TL-20260519-9k3p2m4n`.

## Schemas

The full per-log schema lives in:

- `schemas/back-log.md`
- `schemas/build-log.md`
- `schemas/learn-log.md`
- `schemas/test-log.md`
- `schemas/deployment-log.md` (neutral; the `adapter_id`/`shipping_id`/`adapter_ext` extension is specified in the plugin-root `schemas/deployment-log-ext.md`)
- `schemas/user-behavior-log.md`
- `schemas/error-log.md`
- `schemas/feedback-log.md`
- `schemas/adapt-log.md`

Companion schema for cross-architecture migrations (per-tenant ledger), at the plugin root rather than under this skill:

- `../../schemas/migration-log.md` (prefix `ML`; owned by `evolve`; mandatory for Class B paradigm shifts and recommended for any multi-tenant Class A retarget). Written by `pdlc-coexist`, `pdlc-rediscover`'s migrate stage, and `pdlc-decommission`.

Read the relevant schema file before any append. Do not invent columns. If a new column is needed, append a proposal entry to `adapt-log` with `failure_type: schema_gap` and open a `schema_extension` HITL gate via `pdlc-hitl-gate`. Any sub-agent that hits this case opens the gate directly (this is the one HITL gate type that is not orchestrator-owned). The operator decides whether to extend the schema; if approved, update the schema file in the plugin and the new column becomes valid for future appends.

## Failure modes

- **Canonical store unreachable**: write to cache, queue reconciliation, append to adapt-log. Continue.
- **Schema validation fails**: do not write. Surface the validation error to the caller (the sub-agent) so it can fix the payload. Do not silently coerce.
- **Cache write fails**: rare. If it does, write directly to the canonical store and append a `cache_write_failed` adapt-log entry.
- **Conflicting writes (same id, same v)**: last-writer-wins on the canonical store, but append an adapt-log entry of type `concurrent_write`. The orchestrator should review.

## Examples

### Appending a backlog item from the Discovery phase

```
pdlc-log append back-log {
  project: "lead-routing-suite",
  agent_id: "territory-router",
  phase: "discover",
  actor: "discovery-agent",
  session_ref: "claude-session-xyz",
  title: "Route inbound leads from the form tool to the CRM by territory",
  description: "Sales ops requested territory-based routing. Entitled to the cohort the bound shipping adapter resolves.",
  status: "backlog",
  priority: "P1",
  source: "discovery",
  source_ref: "drive://Product/Portfolio/lead-routing-suite/pr-faq.gdoc",
  estimate: "M",
  hitl_required: true
}
```

### Reading the last 10 build-log entries for a project

```
pdlc-log read-recent build-log --project lead-routing-suite --limit 10
```

### Querying errors for a specific tenant within a project

```
pdlc-log query error-log --project lead-routing-suite --customer acme --where "severity=high AND timestamp>=2026-05-12T00:00:00Z"
```

## Companion skills

- `pdlc-hitl-gate`: opens and closes HITL gates, calls `pdlc-log` to record each transition.
- `pdlc-deploy`: writes deployment-log entries per wave decision, calls `pdlc-log` for baseline capture.
- `pdlc-coexist`, `pdlc-rediscover`, `pdlc-decommission`: write `migration-log` rows per tenant during a migration.

Do not bypass `pdlc-log` to write directly to the canonical store or to the cache. Every entry must flow through this skill so schemas stay enforced and the cache stays consistent.
