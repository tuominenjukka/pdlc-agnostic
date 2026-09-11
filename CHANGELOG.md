# Changelog

All notable changes to this project are documented here. The format follows Keep a Changelog and the project follows semantic versioning.

## Unreleased

## 0.6.0 - 2026-09-10

First public release under the MIT License.

- Published as a standalone repository with its own marketplace.
- Removed vendor-specific reference adapters (a multi-tenant workflow-engine adapter and a cloud-provider-specific IaC adapter). The core is now free of product names; reference adapters for other stacks are welcome as contributions.
- Generalized the agentic-harness reference adapter and all example adapter ids and log samples so nothing in the core names a specific product.
- Added LICENSE, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, and a CI validator for manifests and frontmatter.

## 0.5.2

- Log-store home is explicit: `.pdlc/log-store.txt` is `repo` or `shared`.
- `pdlc-start` scaffolds a `.gitignore` that tracks `.pdlc/logs/` and `.pdlc/bin/` in repo-canonical mode, so the audit trail survives a fresh clone.

## 0.5.1

- Safe-write mechanics: log appends and the pre-commit secret guard run through two committed helper scripts in `.pdlc/bin/` (`pdlc_append.py`, `pdlc_guard.py`) instead of inline heredocs, so autonomous runs do not stall on obfuscation prompts and the safe commands can be allowlisted.
- The commit guard scans for secrets only; prose style rules are scoped to human-facing output.

## 0.5.0

- Build-time CTO agent (`pdlc-cto`): independent re-verification of the project's own validators and tests plus a consistency, security and GDPR lint at every HITL gate, with a narrow low-risk auto-advance.
- Git baked into the gates: gate approval authorizes and runs the merge, sync and next-branch sequence; destructive git stays on explicit ask.
- Claude Code permissions profile scaffolded for new projects: auto-allow reversible in-repo work, always ask for the irreducible human set.
- The irreducible human set is hard orchestrator policy.
- Auto-checkpoint `.pdlc/CHECKPOINT.md` written at every gate for single-read resume.

## 0.4.0

- Deploy preflight (plan lint against the adapter guardrail catalog).
- Branch and merge discipline with a pre-commit guard.
- Activation-by-merge for non-deployed assets.
- Formalized lanes.

## 0.3.0 and earlier

- Architecture-neutral process spine, Target and Shipping adapter contracts, Class A and Class B migration classification, fork-with-lineage, coexist (shadow or strangler) stage, decommission gate, per-tenant migration ledger, nine canonical logs.
