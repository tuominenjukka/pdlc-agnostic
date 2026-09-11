# Shipping Adapter: direct-mvp

Ship straight to the single environment. For MVPs with no live customers.

```yaml
shipping_id: direct-mvp
version: 0.1.0
strategy: direct
requires:
  all_of:
    - { fact: project.live_customers, op: eq, value: false }
exposure_unit: all
step_plan: [100]
rollback_model: revert
observation_windows: { only: 24 }
promotion_gate: none
```
