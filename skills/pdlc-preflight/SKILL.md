---
name: pdlc-preflight
description: Verify that the connectors the architecture-agnostic PDLC meta-builder needs are actually reachable before any phase runs, and re-verify after a plugin update or reload. Checks the canonical document store first as a blocking gate, since the nine logs and the Discover artifacts live there and a silent fallback to local-only writes is a known failure mode. Also checks the version-control/PR surface, the notification surface, and the connectors the bound architecture adapter declares (build, deploy/control, and metrics sources). Trigger at the start of pdlc-start, at the start of every orchestrator session, and immediately after `/reload-plugins` or a plugin update. Returns a connector report and either clears the run, enters an explicitly operator-approved local-only mode, or refuses with a clear remediation message.
---

# pdlc-preflight

The connector gate. Nothing in the PDLC meta-builder should touch a phase until this skill confirms the meta-builder can reach its canonical store and toolchain. This skill exists because a silent fallback to local-only writes (the document-store MCP can be absent in a Claude Code session) is worse than a loud refusal: the operator believes artifacts are in the shared store when they are on a laptop.

The product-specific connectors are **not hardcoded** here. The core checks the universal surfaces (store, version control, notifications); the architecture-specific connectors are read from the bound architecture adapter's manifest (its `metrics_sources`, its control surface, its `build_artifact_kind` toolchain). Before an architecture is bound (greenfield Discovery), only the universal surfaces are checked.

## When to invoke

- At the very start of `pdlc-start`, before creating any folder, log store, or artifact.
- At the start of every `pdlc-orchestrator` session, before resuming any playbook step.
- Immediately after `/reload-plugins` or any plugin install/update.
- On operator request: "check my connectors", "preflight".

## What it checks, in priority order

### 1. Canonical document store (BLOCKING)

The canonical store for the nine logs and the Discover artifacts is the shared document store at `Product/Portfolio/{project}/`. Without write access there, the meta-builder cannot do its job correctly.

Check, in order:

1. **Document-store MCP present?** Look for a store tool in the current tool surface (a `create_file` / `read_file_content` / `search_files` style tool). If present, store access is available via MCP.
2. **Store CLI present?** If no MCP, probe Bash for a configured store CLI (for example an `rclone` remote, or a cloud-storage CLI authenticated to the shared store).
3. **Neither?** Store access is UNAVAILABLE.

Outcomes:

- **Available via MCP**: clear to proceed in normal mode. Report which MCP.
- **Available via CLI only**: clear to proceed; note store writes go through the CLI path.
- **Unavailable**: do NOT silently continue. Choose one:
  - **Refuse (default)**: stop and tell the operator how to fix it (install the document-store MCP in this runtime, or configure a store CLI for the shared store). Create no project state.
  - **Local-only mode (operator opt-in only)**: only if the operator explicitly says "proceed local-only". Write a prominent `.pdlc/LOCAL_ONLY_MODE` marker with timestamp and confirmation, append an `adapt-log` entry with `failure_type: connector_unavailable`, and proceed writing to `.pdlc/` and the repo working tree only. Every operator-facing message in this mode carries the banner: "LOCAL-ONLY MODE: artifacts are on this machine, not in the shared store. Reconcile before sharing." When store access returns, the orchestrator runs a reconciliation pass.

Local-only mode is never a silent default. It is a deliberate, logged, banner-flagged operator choice.

### 2. Version-control / PR surface (BLOCKING in Claude Code, recommended in Cowork)

HITL gates in Claude Code route through PR labels, and the build artifacts live in a repo. Check:

1. A version-control MCP present, or
2. `gh auth status` (or the equivalent) authenticated via Bash, or
3. `git remote -v` plus working SSH for push access.

Outcome: in Claude Code, this is BLOCKING. In Cowork, gates fall back to AskUserQuestion so it is recommended; note degraded gate routing in the report.

### 3. Adapter build toolchain (BLOCKING for Deliver, not for Discover)

Discover needs none of these; Deliver does. Read the bound architecture adapter's `build_artifact_kind` and check for the toolchain it implies (for example a workflow runtime MCP for a deterministic-workflow adapter, an app-build connector for a consumer-app adapter, an agent-harness connector for an agentic adapter). Before an architecture is bound, this check is skipped with a note. Missing the bound toolchain is a WARNING for Discover, BLOCKING for Deliver.

When the bound adapter's build/validate toolchain includes a Python validator, verify the validator's declared dependency *versions*, not just presence. A present-but-too-old package can read as missing: a `jsonschema` 3.x install once produced a misleading "not installed" message when the validator needed `Draft202012Validator` (4.x). Surface a version-aware result such as "needs jsonschema >= 4.18" rather than a bare present/absent. Treat a too-old version the same as missing for the WARNING/BLOCKING outcome above.

### 4. Adapter control and metrics connectors (NON-BLOCKING, degrades Deploy and Evolve)

Read from the bound architecture adapter's manifest:
- The adapter's **control/deploy surface** (whatever `deploy`/`rollback`/`assign_cohort` call under the hood) for wave rollouts.
- The adapter's declared **`metrics_sources`** for guardrail evaluation and the equivalence harness.

Outcome: missing these does not block Discover or Deliver. They degrade `pdlc-deploy` guardrail evaluation and the evolve-agent to Phase 0 mode (operator-confirmed). The adapter's `phase0_fallback` runbook applies. Note in the report. Before an architecture is bound, skip with a note.

### 5. Notification surface (NON-BLOCKING)

Operator notifications and gate-timeout escalation (for example Slack). Missing it means notifications are skipped; note it.

## Report format

```
PDLC PREFLIGHT (pdlc-agnostic) @ {timestamp}
Runtime: {cowork | claude_code}
Bound architecture: {adapter_id@version | unbound (greenfield)}

BLOCKING:
- Canonical store:   {OK via MCP <name> | OK via CLI <remote> | UNAVAILABLE}
- Version control:   {OK via MCP | OK via gh | OK via git+ssh | UNAVAILABLE (blocking in Claude Code)}
- Adapter build:     {OK | missing (blocking for Deliver, warning for Discover) | n/a (unbound)}

NON-BLOCKING:
- Adapter control:   {OK | missing -> wave rollout degrades to Phase 0 | n/a (unbound)}
- Metrics sources:   {OK <list> | missing -> guardrails manual | n/a (unbound)}
- Notifications:     {OK | missing -> notifications skipped}

VERDICT: {CLEAR | CLEAR (local-only, operator-approved) | REFUSE: <reason and remediation>}
```

## Remediation messages

- **Store unavailable**: "The document-store MCP isn't connected in this runtime. In Claude Code: install a store plugin/MCP, then `/reload-plugins`. Or configure a store CLI for the shared store. Re-run preflight after. To proceed without the store (artifacts stay on this machine), say 'proceed local-only'."
- **Version control unavailable (Claude Code)**: "HITL gates route through PRs in Claude Code, and I can't reach the version-control host. Authenticate (`gh auth login` or confirm SSH), then re-run preflight."
- **Adapter build toolchain missing for Deliver**: "Deliver needs the bound architecture's build connector to scaffold and test artifacts. Connect it and re-run preflight, or scope this session to Discover only."

## What you do not do

- You do not create any project state. You only check and report. pdlc-start does creation after you clear it.
- You do not silently degrade. Every degradation is reported; store degradation requires explicit operator opt-in.
- You do not name a specific product as a required core connector. Product-specific connectors are read from the bound adapter manifest.
- You do not cache a stale "all clear". Re-run on every session start and after every reload.

## Companion skills

- `pdlc-start` calls this first, before any creation.
- `pdlc-orchestrator` (agent) calls this at session start and after `/reload-plugins`.
- `pdlc-log` consumes the local-only-mode marker to decide whether to attempt store writes or queue for reconciliation.
