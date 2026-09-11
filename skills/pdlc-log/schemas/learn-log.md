# learn-log schema

**Prefix:** `LL`
**Owner phase:** any (`discover`, `deliver`, `evolve`, `meta`)
**Purpose:** Capture insights, design decisions, and surprises. The engineering journal for the meta-builder. Becomes the source for retros and future reuse, and the internal-evidence input to `pdlc-architecture-decision`.

## When to append

Append when:
- A non-obvious decision is taken (e.g., "chose webhook-poll hybrid over websocket because of trial limits").
- A surprise is encountered (data shape didn't match the contract, etc.).
- A retro or post-rollback review yields a lesson.
- An operator overrides an automated recommendation.
- An architecture decision, rediscovery, fork, or adoption is recorded (`topic: architecture-decision`, `rediscovery`, `fork`, `adoption`).

Do not use learn-log for routine progress notes. Those belong in build-log.

## Log-specific columns

| Column | Type | Required | Notes |
|---|---|---|---|
| `topic` | string | yes | Short tag like `rate-limits`, `crm-throttle`, `rollback-design`, `architecture-decision`. |
| `insight` | string | yes | What was learned. |
| `decision` | string | no | What we decided to do because of it. |
| `alternatives_considered` | string | no | What we ruled out and why. |
| `evidence_ref` | string | no | Link to artifact backing the insight. |
| `applies_to` | string | no | Comma-separated tags: project slugs, agent ids, or `all`. |
| `inherited` | bool | no | True on rows copied into a forked project's learn-log from its source (see `pdlc-fork`). |
| `related_log_refs` | string | no | |

## Example append

```
pdlc-log append learn-log {
  project: "lead-routing-suite",
  agent_id: "territory-router",
  phase: "deliver",
  actor: "delivery-agent",
  session_ref: "claude-session-xyz",
  topic: "crm-throttle",
  insight: "CRM bulk API throttles at 100k/day per org; peak load per tenant is 30k.",
  decision: "Use bulk API with daily quota guard. Fall back to REST for hot leads.",
  alternatives_considered: "Composite API (rejected, too complex for v1)",
  evidence_ref: "https://developer.example.com/docs/...",
  applies_to: "all"
}
```
