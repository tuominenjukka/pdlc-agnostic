# feedback-log schema

**Prefix:** `FL`
**Owner phase:** `evolve`
**Purpose:** Persist user feedback captured by the conversational feedback module embedded in every shipped agent. Used by the `pdlc-deploy` sentiment guardrail and by `evolve-agent` to propose back-log items.

## When to append

Append:
- On every feedback event received from a shipped agent's feedback module.
- On unsolicited feedback an operator triages into the system.

One row per feedback event. Do not aggregate at write time; aggregation happens at query time.

## Log-specific columns

| Column | Type | Required | Notes |
|---|---|---|---|
| `channel` | enum | yes | `whatsapp`, `sms`, `email`, `chat_ui`, `slack`, `operator_triage` |
| `user_ref` | string | no | Anonymized or hashed user id. Never PII. |
| `sentiment_score` | int | yes | -100 to 100. Classified by lightweight model in the feedback module. |
| `sentiment_label` | enum | yes | `very_negative`, `negative`, `neutral`, `positive`, `very_positive` |
| `summary` | string | yes | One-sentence agent-generated summary. |
| `raw_excerpt` | string | yes | Up to 500 chars of verbatim user text. Strip PII. |
| `category` | enum | no | `bug`, `feature_request`, `praise`, `confusion`, `other` |
| `action_taken` | enum | no | `none_yet`, `linked_to_backlog`, `acknowledged_to_user`, `dismissed` |
| `linked_back_log_id` | string | no | Set when action is `linked_to_backlog`. |
| `wave_id` | string | no | If the feedback came from a cohort during a wave. |
| `related_log_refs` | string | no | |

## PII policy

The feedback module strips names, phone numbers, emails, and account ids before writing here. If raw text contains PII the module could not detect, the evolve-agent should rewrite the excerpt before logging. Do not commit raw PII to this log.

## Example append

```
pdlc-log append feedback-log {
  project: "lead-routing-suite",
  agent_id: "territory-router",
  customer: "acme",
  phase: "evolve",
  actor: "evolve-agent",
  session_ref: "claude-session-xyz",
  channel: "chat_ui",
  user_ref: "u_8f3e9c1",
  sentiment_score: -40,
  sentiment_label: "negative",
  summary: "User confused about why their EMEA lead was assigned to a US rep.",
  raw_excerpt: "Why did my lead from Germany go to a US rep? That's the third time this week.",
  category: "bug",
  action_taken: "linked_to_backlog",
  linked_back_log_id: "BL-20260519-cz3p2m4n",
  wave_id: "lead-routing-suite-1.2.0-w1"
}
```
