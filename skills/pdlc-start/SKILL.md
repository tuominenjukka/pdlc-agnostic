---
name: pdlc-start
description: Bootstrap a new architecture-agnostic PDLC project. Trigger with `/pdlc-start`, "start a new PDLC project", "kick off a new project", "begin a discover phase for X", or when an operator hands over an unscoped brief and wants the meta-builder to take it from there. Creates the project's neutral folder set, seeds the empty log sheets, writes `.pdlc/project.txt`, and routes the brief to pdlc-orchestrator Mode 1 (Plugin). Greenfield only; use pdlc-adopt for an existing system, pdlc-fork for a lineage sibling, pdlc-rediscover to re-architect a live project.
---

# pdlc-start

Entry point for starting a brand-new, greenfield PDLC project. Use this skill exactly once per project. After bootstrap, every subsequent session resumes via `/pdlc-resume` or by addressing the orchestrator directly. The architecture and shipping approach are NOT chosen here; they are bound later in Discovery by `pdlc-architecture-decision` behind the `architecture_decision` gate.

## When to invoke

- Operator types `/pdlc-start` or asks Claude to start a new PDLC project.
- Operator hands over a brief without naming a project that already exists.
- Discovery on a regression has produced enough scope to spin up a sibling project (a lineage sibling uses `pdlc-fork` instead).

If the operator references a project that already has `.pdlc/project.txt` set, do NOT invoke this skill. Switch to `/pdlc-status` or address the orchestrator with the existing project context. For a system that already exists outside the PDLC, use `pdlc-adopt`, not this skill.

## Required input

The skill needs three pieces of information from the operator. Ask via `AskUserQuestion` in Cowork, or via interactive prompts in Claude Code. Do not invent values.

1. **Project slug** (kebab-case, lowercase, no spaces). Example: `lead-routing-suite`. This becomes the partition key for every log and the folder name.
2. **One-paragraph brief**: the operator's framing of the problem. Pass to discovery-agent verbatim.
3. **Initial scope hint** (optional): "single artifact", "multi-component product line", "regression follow-up to {existing-project}".
4. **Mode** (optional, default `discover`): `discover` for a greenfield item that needs a real architecture decision and full opportunity framing; `formalize` for an item that hardens an artifact already present in-repo as a skeleton and needs no architecture decision. `formalize` is opt-in: it tells the orchestrator to skip the heavy Discover framing (market scan, full PR-FAQ) and go straight to a spec + build behind a single `delivery_to_deploy` gate, while still producing the spec artifact (see the orchestrator's "Formalize lane"). Pass the chosen mode to the orchestrator on hand-off. Greenfield projects with a real architecture decision must use `discover`.

## Procedure

0. **Connector preflight (blocking).** Before doing anything else, invoke `pdlc-preflight`. If it returns `REFUSE`, stop and relay its remediation message to the operator; do not create any project state. If it returns `CLEAR (local-only, operator-approved)`, proceed but carry the local-only banner on every subsequent message and skip the canonical-store-write steps (write artifacts and logs to `.pdlc/` and the repo working tree only). Only continue to step 1 on a `CLEAR` verdict (or an operator-approved local-only verdict). This step exists because a silent local-only fallback once caused discovery artifacts to land on a laptop while the operator believed they were in the shared store.

1. Confirm the project slug doesn't already exist:
   - Check `Product/Portfolio/{project-slug}/` in the canonical store.
   - Check `.pdlc/project.txt` in the current repo or plugin scratch.
   - If either exists, stop and ask the operator whether they meant to resume or whether they want a different slug.

2. Create the neutral project folder structure under `Product/Portfolio/{project-slug}/`. These folders are architecture-neutral; the architecture decision happens later in Discovery and may add adapter-specific discovery artifacts then.
   - `pdlc-logs/` with empty log stores for back-log, build-log, learn-log, test-log, deployment-log, user-behavior-log, error-log, feedback-log. Use the column headers from each schema in `skills/pdlc-log/schemas/`. Do NOT create `adapt-log` here; adapt-log lives at `Product/Portfolio/_meta/adapt-log` and is shared across all projects. Do NOT create `migration-log` here; it is created on demand only when a cross-architecture migration begins.
   - `product/` (the opportunity-framing folder; the PR-FAQ or PRD lives here. Discovery-agent will fill it; some adapters call it `pr-faq/`).
   - `c4/` (empty, discovery-agent and `pdlc-architecture-decision` will fill, including the ADR).
   - `risks/` (empty, discovery-agent will fill).
   - `market/` (empty, discovery-agent will fill).

3. If `Product/Portfolio/_meta/adapt-log` does not exist yet (first-ever project on this plugin install), create it with the adapt-log schema headers.

4. Write `.pdlc/project.txt` with the slug. Write `.pdlc/log-store.txt` with the log-store mode: `repo` when the repo is the canonical home for the audit trail (the default for greenfield and any project without a shared document connector) or `shared` when a shared document store, e.g. a Google Drive of Sheets, is canonical (see `pdlc-log` "Storage model"). Also create `.pdlc/logs/` (in `repo` mode this is the durable, git-tracked audit trail; in `shared` mode it is a write-through cache), `.pdlc/reconciliation-queue.jsonl` (empty), and `.pdlc/open-gates.jsonl` (empty). Do NOT write `.pdlc/adapter.txt` or `.pdlc/shipping.txt` yet; those are written by `pdlc-architecture-decision` on `architecture_decision` gate approval. For a multi-component project the bindings are written per component under `.pdlc/components/{component}/` (DESIGN 4.3); the flat top-level files remain the single-component case.

5. Write `.pdlc/phase.txt` with the value `discover` (or `formalize` if the operator selected the formalize mode).

5a. **Scaffold a pre-commit guard against direct commits to `main`.** Direct-to-`main` commits after a post-merge branch switch are a recurring failure for this meta-builder; the scaffold installs a guard so new projects refuse them by construction. When creating the project repo (the delivery-agent owns repo scaffolding; this step describes what to include), add `.githooks/pre-commit` that exits non-zero when the current branch is `main`, unless an explicit override env var is set, and point `core.hooksPath` at `.githooks`:

   ```sh
   #!/bin/sh
   # .githooks/pre-commit — refuse commits made directly on main.
   branch="$(git branch --show-current)"
   if [ "$branch" = "main" ] && [ "$PDLC_ALLOW_MAIN_COMMIT" != "1" ]; then
     echo "pdlc: refusing to commit directly on main. Cut an item branch first," >&2
     echo "      or set PDLC_ALLOW_MAIN_COMMIT=1 to override (discouraged)." >&2
     exit 1
   fi
   ```

   Make it executable (`chmod +x .githooks/pre-commit`) and run `git config core.hooksPath .githooks` so the hook is active without per-clone setup. This mirrors the orchestrator's "Branch and merge discipline" rule at the plumbing level. Existing repos should add the same `.githooks/pre-commit` guard and set `core.hooksPath` once; it is architecture-independent and safe to add to any project.

5b. **Scaffold a Claude Code permissions profile (`.claude/settings.json`).** So that routine, reversible work runs without per-action prompts and the operator's attention is reserved for the PDLC HITL gates, write a conservative permissions profile to `.claude/settings.json` at the project repo root. This pairs with the CTO agent (the in-session reviewer) and the PDLC gates: the auto-allow set is reversible/in-repo, while everything irreversible, spending, external, or security-critical stays human-gated (Claude Code's `ask`/`deny`). The `deny`/`ask` set is the **irreducible human set** written as policy in the orchestrator ("Irreducible human set"); settings and policy agree, so neither alone can erode the backbone. Use Claude Code's permissions shape (`allow` / `ask` / `deny` lists):

   ```json
   {
     "permissions": {
       "allow": [
         "Read", "Edit", "Write", "Glob", "Grep",
         "Bash(git add:*)", "Bash(git commit:*)", "Bash(git status:*)",
         "Bash(git diff:*)", "Bash(git log:*)", "Bash(git checkout:*)",
         "Bash(git branch:*)", "Bash(git pull:*)",
         "Bash(gh pr create:*)", "Bash(gh pr merge:*)",
         "Bash(python validate.py:*)", "Bash(./run_tests.sh:*)",
         "Bash(pytest:*)", "Bash(npm test:*)", "Bash(terraform plan:*)"
       ],
       "ask": [
         "Bash(terraform apply:*)", "Bash(terraform destroy:*)",
         "Bash(kubectl delete:*)",
         "Bash(git push --force:*)", "Bash(git push -f:*)", "Bash(git rebase:*)",
         "Bash(npm install:*)", "Bash(pip install:*)", "Bash(brew install:*)"
       ],
       "deny": [
         "Bash(rm -rf:*)",
         "Bash(*DROP DATABASE*)", "Bash(*DROP TABLE*)", "Bash(*TRUNCATE*)"
       ]
     }
   }
   ```

   - **Auto-allow (no prompt):** repo Read/Edit/Write, Grep/Glob, running the project's validators/tests, `git add/commit/status/diff/log/checkout/branch/pull`, and `gh pr create/merge` (the gated activation — the `delivery_to_deploy` gate is the human checkpoint, so the merge itself need not re-prompt). The pre-commit guard (5a) still blocks any direct-to-`main` commit.
   - **Always ask (the irreducible human set — never auto-allowed):** `terraform apply`/`destroy`, `kubectl delete`, destructive SQL (`DROP DATABASE` and friends), `git push --force` / history rewrite, any external/outward send, anything that spends money or touches prod/tenants, network package installs, `rm -rf`. The most irreversible of these (`rm -rf`, destructive SQL) are placed in `deny` so they hard-stop; the rest are in `ask`. Tune the validator/test command names to the project's actual tooling; keep the `ask`/`deny` set intact.
   - **Existing repos** adopt the same profile: add `.claude/settings.json` with these lists once. It is architecture-independent. Do not weaken the `ask`/`deny` set; that is the safety backbone the orchestrator enforces as policy.

5c. **Scaffold the `.pdlc` gitignore policy.** `.pdlc/` mixes ephemeral session state with the durable audit trail, so a blanket ignore silently drops the record on a fresh clone. Write (or extend) the project repo's `.gitignore` with a stanza that ignores the local session state but keeps the audit trail and the committed helper scripts. In `repo` log-store mode:

   ```gitignore
   # PDLC orchestrator state: ignore local session state, keep the durable audit trail + helper scripts
   .pdlc/*
   !.pdlc/logs/
   !.pdlc/logs/**
   !.pdlc/bin/
   !.pdlc/bin/**
   !.pdlc/log-store.txt
   ```

   This tracks `.pdlc/logs/` (the record) and `.pdlc/bin/` (the v0.5.1 append + guard helpers, so a clone does not re-bootstrap them) while ignoring `project.txt`, `phase.txt`, `open-gates.jsonl`, `reconciliation-queue.jsonl`, `CHECKPOINT.md`, the adapter/shipping bindings, and the rest of the session state. In `shared` log-store mode, `.pdlc/logs/` is a cache, so instead ignore all of `.pdlc/` except the helper scripts (`.pdlc/*`, then `!.pdlc/bin/` and `!.pdlc/bin/**`). The delivery-agent owns repo scaffolding; existing repos should add the matching stanza once. Never rely on a per-commit `git add -f` for the logs; that is the failure this stanza removes.

6. Resolve the operator email. In Cowork, read the `user.email` field from the operator preferences block injected into the system prompt. In Claude Code, read `git config user.email` or fall back to the `USER_EMAIL` env var if set. If neither is available, prompt the operator for it (it's required for the `actor` column on the learn-log entry).

7. Append an initial `learn-log` entry via `pdlc-log append`:
   - `phase: discover`
   - `actor: {operator-email}`
   - `topic: project-bootstrap`
   - `insight`: paste the operator's brief verbatim.
   - `applies_to: {project-slug}`.

8. Hand off to `pdlc-orchestrator` Mode 1 (Plugin), passing the selected mode (`discover` or `formalize`). The orchestrator will:
   - Validate the bootstrap state.
   - In `discover` mode: delegate the brief to `pdlc-discovery-agent`, which frames the opportunity and then runs `pdlc-architecture-decision` to choose and bind the architecture and shipping adapters behind the `architecture_decision` gate, then surface the discovery hand-off and open the `discovery_to_delivery` HITL gate.
   - In `formalize` mode: take the orchestrator's Formalize lane instead, producing a scoped spec and going straight to the build behind a single `delivery_to_deploy` gate (no architecture decision, no `discovery_to_delivery` gate).

## What you do not do

- You do not choose or bind an architecture. That is `pdlc-architecture-decision`, run inside Discovery, behind the `architecture_decision` gate.
- You do not write code, scaffold artifacts, or open PRs. Those belong to delivery-agent.
- You do not produce PR-FAQs or other Discover artifacts. Those belong to discovery-agent.
- You do not open HITL gates. The orchestrator and `pdlc-architecture-decision` open them once Discover produces something to gate.
- You do not retry on canonical-store errors more than twice. On second failure, fall through to the adapt-log path and surface to the operator.

## Output to the operator

After bootstrap, print:

```
Project {project-slug} bootstrapped (greenfield).
Store: {url to Product/Portfolio/{project-slug}/}
Phase: discover
Architecture: unbound (decided in Discovery via pdlc-architecture-decision)
Initial learn-log: {ll-id}
Now delegating to pdlc-orchestrator Mode 1 with your brief.
```

Then yield to the orchestrator. The operator's next interaction will land in the orchestrator's context.

## Failure modes

- **Folder creation fails**: retry once. If it fails again, write an `adapt-log` entry with `failure_type: drive_write_failed`, leave `.pdlc/project.txt` unset, surface the error to the operator. The bootstrap is not partial: either everything is set or nothing is.
- **Slug already exists**: stop and ask. Do not append a suffix; that would silently fork a project.
- **Operator brief is empty**: ask the operator to provide one. The skill does not invent context.

## Companion skills

- `pdlc-preflight` runs first (step 0) and gates everything else. Never create project state if preflight refuses.
- `pdlc-log` for the bootstrap learn-log entry and for verifying the log sheets are seeded with correct headers.
- `pdlc-architecture-decision` runs inside Discovery (via the discovery-agent) and binds the architecture and shipping adapters.
- `pdlc-orchestrator` (agent) takes over after the final step.
- `pdlc-adopt` (existing system), `pdlc-fork` (lineage sibling), `pdlc-rediscover` (re-architect a live project) are the non-greenfield alternatives.
