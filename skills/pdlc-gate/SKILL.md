---
name: pdlc-gate
description: Operator-facing entry point to list, close, or open a PDLC HITL gate directly from chat, without going through GitHub PR labels or an AskUserQuestion prompt. Trigger with `/pdlc-gate`, "approve gate {id}", "close that gate", "show me the open gates", "force-close GT-...", or when the operator wants to act on a gate from a context where the normal routing isn't reachable (mobile, away from the PR, between sessions). Routes to pdlc-hitl-gate's check / close / open operations. Authorization is enforced by pdlc-hitl-gate (the operator must be in the gate's approver list for close).
---

# pdlc-gate

The operator's chat-native gate console. Use whenever the operator wants to see, approve, reject, or open a gate from a place where the normal routing isn't convenient: away from the PR, on mobile, mid-conversation, or simply preferring to handle gates in chat rather than via labels.

## When to invoke

- Operator types `/pdlc-gate` with one of three sub-actions: `list`, `close`, or `open`.
- Operator says "approve gate GT-...", "reject that gate", "force-close...", "show me open gates", "open a schema_extension gate for...".
- A previous session ended with a gate the operator wants to act on right now, without waiting for the next `/pdlc-resume`.

## Sub-actions

The skill exposes three sub-actions, mirroring `pdlc-hitl-gate`'s three operations. Each is a thin pass-through with operator-friendly framing.

### `list`

`/pdlc-gate list` (default sub-action if none specified)

1. Resolve project scope from `.pdlc/project.txt` unless `--all` is supplied.
2. Call `pdlc-hitl-gate check` for every entry in `.pdlc/open-gates.jsonl` (project-scoped) or for every recent `hitl_gate_opened` event without a matching close (all-projects scope).
3. Render a compact table:

```
| Gate ID                                  | Type                  | Project            | Routing    | Opened           | Approvers                    |
| ---------------------------------------- | --------------------- | ------------------ | ---------- | ---------------- | ---------------------------- |
| GT-wave_promotion-20260519-7fk2a9c1      | wave_promotion        | lead-routing-suite | cowork     | 2026-05-19 14:08 | product-leads@example.com    |
| GT-architecture_decision-20260519-9k3p2m | architecture_decision | lead-routing-suite | github_pr  | 2026-05-19 16:20 | principal-engineers@example  |
```

4. If no gates are open, print "No open gates." and exit.

### `close`

`/pdlc-gate close <gate-id> --decision approve|reject --comment "..."`

1. Validate the operator's email matches one of the gate's approvers. If not, refuse with `not_authorized` and surface the list of authorized approvers. Do NOT proceed even if the operator insists. For `decommission_approval`, the approver set is the dedicated decommission set.
2. Validate the decision is one of `approve`, `reject`. Do not accept `pause` here (use `/pdlc-resume` flow for pause-and-revisit) or `timeout` / `failed_closed` (those are emitted automatically by pdlc-hitl-gate's timeout logic, not by manual operator action).
3. Confirm with the operator before sending: show the gate summary, the chosen decision, and the comment. Require explicit confirmation (especially in Cowork, via AskUserQuestion). For `decommission_approval`, the confirmation must restate that the teardown is irreversible.
4. Call `pdlc-hitl-gate close <gate-id> --decision {decision} --comment "{comment}" --closed-by {operator-email}`.
5. The skill (via pdlc-hitl-gate) writes the `hitl_gate_closed` event to the appropriate phase log, removes the gate from `.pdlc/open-gates.jsonl` if present, and unblocks any downstream waiting on this gate.
6. After successful close, the operator usually wants `/pdlc-resume` to advance the playbook. Suggest it explicitly in the output.

### `open`

`/pdlc-gate open <gate-type> --summary "..." --artifacts "{urls}" [--approvers "{emails}"]`

1. Resolve project from `.pdlc/project.txt`.
2. Validate `<gate-type>` is one of the nine known types: `discovery_to_delivery`, `delivery_to_deploy`, `wave_promotion`, `rollback_approval`, `pivot_approval`, `schema_extension`, `architecture_decision`, `tenant_migration_consent`, `decommission_approval`.
3. Refuse with `gate_normally_owned_by_orchestrator` for `discovery_to_delivery`, `delivery_to_deploy`, `pivot_approval`. These should flow through the orchestrator, not be manually opened. Surface the operator to address the orchestrator instead.
4. Refuse with `gate_owned_by_skill` for `architecture_decision`, `tenant_migration_consent`, `decommission_approval`. These are opened by their owning skills (`pdlc-architecture-decision`, `pdlc-coexist`, `pdlc-decommission`) so the closing artifact (ADR, migration-log rows, preconditions) is produced correctly. Point the operator at the right skill rather than opening a bare gate that has no backing artifact.
5. Allow for `wave_promotion`, `rollback_approval`, `schema_extension` since there are legitimate operator-initiated paths for these (e.g., the operator wants to manually open a rollback approval before guardrails fire, or schedule a schema_extension proactively).
6. Confirm with the operator before sending: show the proposed gate type, summary, artifacts, approvers (defaulting to the per-gate-type list in `pdlc/hitl.yaml`).
7. Call `pdlc-hitl-gate open <gate-type> {...}`.
8. The gate is then routed normally (AskUserQuestion in Cowork, GitHub PR label in Claude Code). The skill returns once the gate is opened; the operator can then close it via `/pdlc-gate close` or via the normal routing channel.

## Authorization rules

The skill respects the gate's approver list strictly. The operator's email must be in the gate's `approvers` (resolved from `pdlc/hitl.yaml`) for `close` to succeed. There is no override. If an approver is unreachable, the gate either times out (after the configured window, default 24h) or another authorized approver must close it.

For `open`, no approver-list check is needed — any operator can propose opening a gate they're allowed to use.

## What you do not do

- You do not bypass `pdlc-hitl-gate`. Every check, close, and open goes through the skill.
- You do not write logs directly. pdlc-hitl-gate (via pdlc-log) owns those writes.
- You do not approve gates the operator is not an approver for, regardless of how the operator phrases the request.
- You do not open `architecture_decision`, `tenant_migration_consent`, or `decommission_approval` as bare gates. Their owning skills open them with the required closing artifact.
- You do not auto-resume the playbook after a close. The operator runs `/pdlc-resume` explicitly. This separation keeps the manual-close path symmetric with the externally-closed-on-GitHub path.
- You do not modify gate approver lists, timeouts, or escalation paths. Those live in `pdlc/hitl.yaml` and are edited via PR.

## Output formats

### After `list`

The table above. If a single gate is in scope, show its full payload (summary, artifacts, approvers) below the table.

### After `close`

```
Gate {gate-id} closed.
- Type: {gate_type}
- Decision: {decision}
- Closed by: {operator-email}
- Comment: "{comment}"
- Log entry: {hitl_gate_closed event ref in {phase_log}}
- Adapt-log: {al-id, only for pivot/rollback/schema_extension/migration gates}

Next: run /pdlc-resume to advance the playbook.
```

### After `open`

```
Gate opened.
- Gate id: {gate-id}
- Type: {gate_type}
- Routing: {cowork|github_pr}
- Routing ref: {AskUserQuestion id or PR comment URL}
- Approvers: {list}
- Timeout: {hours}h, fails closed at {ISO timestamp}

The gate is now visible via /pdlc-gate list and via the normal routing channel.
```

## Failure modes

- **Operator not in approver list (close)**: refuse with the list of authorized approvers. Do not retry.
- **Gate id does not exist or already terminally closed**: refuse with the gate's last known state.
- **Cowork AskUserQuestion or Claude Code GitHub MCP unavailable (open)**: refuse, surface the error, suggest the operator open the gate from the runtime where the routing target is reachable.
- **Operator declines the confirmation prompt**: exit cleanly. Write nothing.

## Companion skills

- `pdlc-hitl-gate` for all three sub-actions.
- `pdlc-log` (invoked by pdlc-hitl-gate) for the event writes.
- `/pdlc-resume` is the natural follow-up after a successful `close`.
- `/pdlc-status` is the natural follow-up if the operator only wanted to inspect, not act.
