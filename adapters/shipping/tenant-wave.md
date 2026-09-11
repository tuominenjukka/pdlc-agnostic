# Shipping Adapter: tenant-wave

Standard wave rollout across multi-tenant cohorts.

```yaml
shipping_id: tenant-wave
version: 1.0.0
strategy: tenant-wave
requires:
  all_of:
    - { fact: architecture.capabilities, op: contains, value: multi-tenant }
exposure_unit: tenant-cohort
step_plan: [10, 30, 50, 100]
rollback_model: revert
observation_windows: { wave_1: 24, wave_2: 24, wave_3: 24, wave_4: 48 }
promotion_gate: wave_promotion
```
