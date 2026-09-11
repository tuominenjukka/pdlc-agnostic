# deployment-log extension [v2]

The neutral deployment-log replaces per-architecture forked schemas with one schema plus an adapter namespace. Two columns are added; everything else is the base deployment-log.

## Added columns

| Column | Type | Required | Notes |
|---|---|---|---|
| `adapter_id` | string | yes | The architecture adapter that produced this event. Replaces hardcoded knowledge of image vs flag. |
| `shipping_id` | string | yes | The shipping adapter driving the wave. |
| `adapter_ext` | json | no | Adapter-specific fields that used to be top-level columns, now namespaced. Examples below. |

## adapter_ext examples

workflow-multitenant:
```json
{ "image_tag": "example/tenant-image:1.2.0",
  "previous_image_tag": "example/tenant-image:1.1.4",
  "k8s_deployment_refs": ["tenant-acme/worker"],
  "control_plane_call_ref": "https://control-plane.example/api/v1/...",
  "observed_pause_seconds_p95": 22 }
```

webapp-flags:
```json
{ "flag_key": "recipe-search", "rollout_pct": 30, "deploy_ref": "hosting://..." }
```

## Backfill

Existing rows get `adapter_id` inferred from their current columns (image columns imply workflow-multitenant, flag columns imply webapp-flags), and their old columns move under `adapter_ext`. This keeps existing projects working with no behavior change.
