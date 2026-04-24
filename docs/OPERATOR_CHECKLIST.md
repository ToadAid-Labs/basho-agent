# Operator Checklist

This checklist is for routine operation of the current system.

## Daily

1. Confirm the process is alive.
   - Telegram bot responds to `/start` or a plain message.
   - Web dashboard loads.

2. Confirm provider health.
   - Ask for a plain system status response.
   - Check recent logs for provider auth errors or long timeouts.

3. Confirm Forge watch health.
   - List active watches.
   - Verify the expected watch set is present.
   - Check last recorded times for watched assets.

4. Confirm alerts are healthy.
   - List active smart alerts.
   - Check whether any alerts are stuck active without updates.

5. Confirm mission context is present.
   - Read `mission_briefing_strategy` if the agent is operating in a special domain mode.

## Per Trading Session

1. Check current provider.
2. Check current wallet mode:
   - paper
   - live
3. Confirm risk controls:
   - risk limits
   - position sizing
   - on-chain/token risk if trading live
4. Run market structure / multi-timeframe checks before acting on discretionary setups.

## After Auth Changes

1. Re-login the provider if needed.
2. Restart the running agent process.
3. Send a plain conversational message.
4. Send one tool-using request.
5. Verify there are no timeout or auth-refresh loops in logs.

## After Code Deployments

1. Pull latest `main`.
2. Restart the bot/backend.
3. Run a smoke test:
   - plain chat
   - price check
   - watchlist listing
   - strategy read
4. Verify no new startup or import errors in logs.

## Weekly

1. Review prediction ledger summary.
   - pending count
   - evaluated count
   - directional accuracy
   - mean score error

2. Review active watches.
   - remove stale watches
   - confirm critical watches still exist

3. Review alerts.
   - remove stale alerts
   - confirm wallet activity alerts still have valid targets

4. Review strategy memory.
   - update mission briefing if operating context changed
   - update asset-specific strategy files
   - prune stale or contradictory guidance

5. Review provider/runtime stability.
   - auth failures
   - long response stalls
   - repeated restarts
   - Telegram conflicts

## When Something Looks Wrong

Check these first:
- provider auth timeout
- stale cached runtime state after relogin
- missing or global-only Forge watches
- strategy path mismatch
- duplicate Telegram bot instances
- background alert loop triggering unexpected agent calls

## Current High-Value Smoke Tests

Use plain prompts like:

```text
Give me a plain system health check with no lore.
```

```text
List active Forge watches and last recorded times.
```

```text
Read mission_briefing_strategy.
```

```text
Give me a prediction ledger summary for the last 10 records.
```
