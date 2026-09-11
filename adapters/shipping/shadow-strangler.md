# Shipping Adapter: shadow-strangler

For Class B paradigm-shift migrations. Drives `pdlc-coexist`.

```yaml
shipping_id: shadow-strangler
version: 0.1.0
strategy: shadow-strangler
requires:
  any_of:
    - { fact: architecture.rollback_constraints.non_revertible, op: eq, value: true }
    - { fact: project.incumbent_present, op: eq, value: true }
exposure_unit: task-class
step_plan: [shadow, route-task-class, route-tenant]
rollback_model: stop-routing
observation_windows: { shadow_hours: 72, per_route_hours: 48 }
promotion_gate: wave_promotion
```

Rollback is stop-routing because the incumbent stays hot. Promotion between steps requires green equivalence and, where contracted behavior changes, a `tenant_migration_consent` gate.
