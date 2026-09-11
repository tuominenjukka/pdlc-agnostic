# Architecture Adapter: agentic-harness-selfhosted

Reference adapter for a self-hosted LLM with a full agentic harness and no deterministic workflows. This is the target of the workflow-to-agentic stress test, and a Class B (paradigm shift) target relative to any deterministic workflow-engine adapter.

## Manifest

```yaml
adapter_id: agentic-harness-selfhosted
version: 0.1.0
capabilities:
  - multi-tenant
  - eu-residency
  - agentic
  - hierarchical-memory      # company, project, user
  - self-hosted-llm
discovery_artifacts: [pr-faq, c4, task-acceptance-suite]
build_artifact_kind: agent-definition+tools+memory-config
reference_architecture: ./refarch/agentic-harness-selfhosted.md
metrics_sources: [metrics-db, prometheus, llm-tracing]   # example sources; bind your own
guardrail_catalog:
  task_completion_rate_drop_pct: { red_above: 15, yellow_above: 7 }
  human_intervention_rate_pct:   { red_above: 25, yellow_above: 12 }
  cost_per_task_eur:             { red_above: 0.50, yellow_above: 0.25 }   # tune during hardening
  outcome_correctness_vs_incumbent_pct: { red_below: 90, yellow_below: 95 }
rollback_constraints:
  non_revertible: true          # cannot rollout-undo to a deterministic workflow
cost_ceiling_required: true      # mandatory for agentic adapters
phase0_fallback: ./runbooks/agentic-harness-manual.md
```

## Operations

- `provision(scope)`: stand up the harness runtime, the self-hosted LLM endpoint, the memory stores for the three layers, and the per-tenant isolation, from the reference architecture.
- `teardown(scope)`: remove the above for a tenant. Used only by `pdlc-decommission`.
- `assign_cohort(wave)`: not a percentage wave here. Returns task-class plus tenant routing units for `pdlc-coexist`.
- `deploy(wave)`: deploy or update an agent definition and its tools for a tenant.
- `rollback(wave)`: unavailable. `non_revertible` is true, so any migration onto this adapter must use `pdlc-coexist`, not the wave-based `migrate` stage.
- `fetch_metrics(window)`: read the agent-era metrics from the bound `metrics_sources` (an LLM tracing store, a metrics database, a Prometheus endpoint).

## Why this is Class B against a deterministic workflow engine

The build artifact is an agent with tools, memory, and a goal, not a workflow graph. There is no 1:1 mapping from a deterministic workflow to an agent, so there is nothing to revert to. Behavioral equivalence is non-deterministic and must be evaluated with the task-acceptance suite, not `workflow_success_rate`. The architecture decision must classify any workflow-engine-to-this move as Class B.

## Notes for building

- The `task-acceptance-suite` discovery artifact is mandatory for this adapter because `pdlc-coexist` uses it as the equivalence oracle against the incumbent.
- Memory layers map to the existing multi-tier memory work (company, project, user), with the source-of-truth index pattern.
