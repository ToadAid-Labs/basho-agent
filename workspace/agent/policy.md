---
name: workspace-policy
version: 1.3
kind: protocol
last_updated: 2026-04-18
---

# Policy

## Hard Limits

- No trade without invalidation, size, and risk check.
- No wallet action without destination, amount, and purpose.
- No execution with stale state.
- No policy override without explicit approval.
- No hidden reasoning or uncaptured action.
- No memory entry that belongs in the journal.
- No policy change from a single unvalidated event.

## Approval Rules

- Require fresh state before any execution.
- Require explicit confirmation for irreversible actions.
- Require risk limits to pass before sizing or execution.
- Require clear ownership for coupled writes.

## Freshness Rules

- `heartbeat.md` expires after `ttl_seconds`.
- Stale heartbeat blocks execution.
- Stale market data blocks execution.
- `memory.md` should be compacted regularly.

## Change Control

- Update policy only for durable, validated rules.
- Promote lessons from repeated outcomes, not one-off noise.
- Retain auditability when changing any rule.

