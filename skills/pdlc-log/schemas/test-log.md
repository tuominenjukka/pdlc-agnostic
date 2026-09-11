# test-log schema

**Prefix:** `TL`
**Owner phase:** `deliver`
**Purpose:** Record every simulated test run on a build artifact. The pre-deploy HITL gate reads this log to summarize results for the operator. For a Class B coexistence migration the task-acceptance suite results are recorded here and consumed by `pdlc-coexist` as the equivalence oracle input.

## When to append

One row per test scenario per run. Append:
- After every automated test pack execution.
- After every operator-specified edge-case scenario.
- After every regression test triggered by a back-log P0.
- After every task-acceptance-suite run used as an equivalence oracle (coexistence).

## Log-specific columns

| Column | Type | Required | Notes |
|---|---|---|---|
| `test_type` | enum | yes | `unit`, `integration`, `e2e`, `edge_case`, `regression`, `task_acceptance` |
| `scenario` | string | yes | Human-readable name. |
| `input_ref` | string | yes | Path or inline JSON of test input. |
| `expected_summary` | string | yes | Brief description of expected outcome. |
| `actual_summary` | string | yes | Brief description of actual outcome. |
| `pass_fail` | enum | yes | `pass`, `fail`, `error` |
| `duration_ms` | int | no | |
| `execution_ref` | string | no | Adapter-specific link to the underlying execution for traceback (e.g., a workflow execution id, an agent run id). |
| `triggered_by` | enum | yes | `delivery-agent`, `operator`, `regression-hook`, `coexist` |
| `related_log_refs` | string | no | Build-log entry of the artifact under test. |

## Example append

```
pdlc-log append test-log {
  project: "lead-routing-suite",
  agent_id: "territory-router",
  phase: "deliver",
  actor: "delivery-agent",
  session_ref: "claude-session-xyz",
  test_type: "e2e",
  scenario: "EMEA lead with missing country code routes to default EMEA owner",
  input_ref: "github://acme/lead-routing-suite/tests/emea-missing-country.json",
  expected_summary: "Lead created in CRM with owner = emea_default (per tenant entitlement)",
  actual_summary: "Lead created in CRM with owner = emea_default",
  pass_fail: "pass",
  duration_ms: 412,
  execution_ref: "exec://tenant-acme/7891",
  triggered_by: "delivery-agent",
  related_log_refs: "build-log:BU-20260519-9k3p2m4n"
}
```
