# Shipping Adapter: env-promotion

Environment-by-environment promotion across a fixed chain. For infrastructure changes that promote dev → staging → prod rather than rolling across customer cohorts.

```yaml
shipping_id: env-promotion
version: 1.0.0
strategy: env-promotion
requires:
  all_of:
    - { fact: architecture.capabilities, op: contains, value: infrastructure }
exposure_unit: environment
step_plan: [dev, staging, prod]
rollback_model: revert
observation_windows: { dev: 0, staging: 24, prod: 48 }
promotion_gate: wave_promotion
```

Promotion is one direction only; to revert an environment, use rollback, not "promote backwards." The `wave_promotion` gate is reused for cross-plugin schema consistency; semantically here it gates an environment promotion.
