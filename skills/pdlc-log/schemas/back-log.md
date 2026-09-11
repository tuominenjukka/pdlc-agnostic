# back-log schema

**Prefix:** `BL`
**Owner phase:** `deliver` (writes), `discover` (proposes), `evolve` (proposes)
**Purpose:** Live state of every PDLC work item across the project's customers.

## When to append

Append a new entry when:
- Discovery proposes a new item.
- The evolve-agent surfaces a regression (P0 from rollback) or insight that becomes work.
- An operator files a request through the orchestrator.
- An existing entry changes state (status, priority, assignee, estimate). Use the same `id` and bump `v`.

## Log-specific columns

In addition to the universal columns (`id`, `created_at`, `updated_at`, `customer`, `agent_id`, `phase`, `actor`, `session_ref`, `notes`):

| Column | Type | Required | Notes |
|---|---|---|---|
| `v` | int | yes | Version. Increments on state change. |
| `title` | string | yes | One-line summary. |
| `description` | string | yes | Full context, including links to PR-FAQ or feedback. |
| `status` | enum | yes | `backlog`, `in_progress`, `blocked`, `hitl_pending`, `done`, `dropped` |
| `priority` | enum | yes | `P0`, `P1`, `P2`, `P3` |
| `source` | enum | yes | `discovery`, `feedback`, `error`, `operator`, `regression` |
| `source_ref` | string | no | URL or doc ref to originating evidence. |
| `assignee` | string | no | Sub-agent or operator email. |
| `estimate` | enum | no | `S`, `M`, `L`, `XL` |
| `hitl_required` | bool | yes | Whether moving this to `done` requires operator approval. |
| `block_redeploy` | bool | no | Default false. True for P0 regressions from rollback. |
| `related_log_refs` | string | no | Comma-separated `{log}:{id}` pairs. |

## State-change protocol

To change status:
1. Read current entry by id.
2. Append a new entry with same `id`, `v + 1`, new `updated_at`, only the changed columns plus required columns.
3. Query layer returns max-v per id.

## Example append

```
pdlc-log append back-log {
  project: "lead-routing-suite",
  agent_id: "territory-router",
  phase: "discover",
  actor: "discovery-agent",
  session_ref: "claude-session-xyz",
  v: 1,
  title: "Route inbound leads to the CRM by territory",
  description: "Sales ops requested territory-based routing. Will be gated to the entitled cohort via the bound shipping adapter.",
  status: "backlog",
  priority: "P1",
  source: "discovery",
  source_ref: "drive://Product/Portfolio/lead-routing-suite/pr-faq.gdoc",
  estimate: "M",
  hitl_required: true
}
```
