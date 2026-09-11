# Shipping Adapter Contract

A shipping adapter declares how increments are exposed and rolled out, independent of the architecture they run on. Separating it from the architecture adapter lets the same architecture carry different shipping risk profiles, and lets a shipping strategy be reused across architectures.

## Manifest fields

| Field | Required | Notes |
|---|---|---|
| `shipping_id` | yes | Stable id, kebab-case. |
| `version` | yes | Semver. |
| `strategy` | yes | One of `tenant-wave`, `user-flag-wave`, `shadow-strangler`, `direct`, `env-promotion`. |
| `requires` | yes | Typed predicate block the pairing must satisfy (grammar below). Replaces the former free-text `compatible_architectures`. Discovery and re-validation evaluate it mechanically. |
| `exposure_unit` | yes | What a step exposes to, e.g. `tenant-cohort`, `user-percent`, `task-class`, `environment`. |
| `step_plan` | yes | The ordered exposure steps, e.g. `[10, 30, 50, 100]` percent, or `[shadow, route-task-class, route-tenant]`. |
| `rollback_model` | yes | `revert` (undo the step), or `stop-routing` (incumbent stays hot, used by shadow-strangler). |
| `observation_windows` | yes | Per-step window before the promotion decision. |
| `promotion_gate` | yes | The gate opened between steps, default `wave_promotion`. |

## The `requires` grammar

A `requires` block is one combinator (`all_of` or `any_of`) over clauses. Each clause is `{ fact, op, value }`.

- `fact` is a dotted path in one of two namespaces: `architecture.*` reads the bound architecture adapter's manifest (for example `architecture.capabilities`, `architecture.rollback_constraints.non_revertible`); `project.*` reads project state at evaluation time (defined facts: `project.live_customers`, `project.incumbent_present`, `project.tenant_count`).
- `op` is one of `eq`, `contains`, `gte`, `lte`.
- Combinators may nest one level.

```yaml
requires:
  any_of:
    - { fact: architecture.rollback_constraints.non_revertible, op: eq, value: true }
    - { fact: project.incumbent_present, op: eq, value: true }
```

Project facts make explicit what the old free text hid: some pairing validity depends on the project, not the architecture, so it must be re-evaluated when project facts change.

## The pairing check

Not every shipping strategy works on every architecture. Examples:
- `tenant-wave` requires `architecture.capabilities contains multi-tenant`.
- `user-flag-wave` requires a single-deployment, flaggable surface.
- `shadow-strangler` requires a non-revertible target or a present incumbent.
- `direct` requires `project.live_customers eq false` (typical for an MVP).
- `env-promotion` requires `architecture.capabilities contains infrastructure`.

Discovery resolves the architecture adapter first, then selects a shipping adapter whose `requires` block evaluates true. If none holds, it proposes a shipping approach rather than forcing an invalid pairing. The pairing is recorded in the ADR and in `.pdlc/shipping.txt`.

The pairing is re-validated, not checked once: at every `migrate` stage entry, and whenever a project fact the predicate references changes (for example live customers appear on a project bound to `direct`). A failed re-validation opens an `architecture_decision` gate to re-pair. When more than one strategy is valid, prefer the lightest that satisfies the risk profile; a heavier binding must be justified in the ADR and flagged as over-heavy.

## Propose or reuse

Same pattern as architecture adapters. Reuse a proven shipping reference when one fits the opportunity's risk profile, propose a new one only when none does.
