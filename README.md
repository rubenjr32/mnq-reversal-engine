# MNQ Reversal-Expansion Engine

Current build: **v0.2** — manual execution / rich signal logging.

## Core sequence

1. Higher-timeframe premium / discount location
2. Liquidity sweep
3. Displacement / market-structure shift
4. Fresh FVG
5. Retrace to FVG CE and close back through CE
6. Structural stop from the sweep extreme
7. At least 2R room to the nearest external objective
8. Planned risk capped at $35 for 1 MNQ
9. Manual chart confirmation before any order

This is an experimental scanner/decision assistant, **not a proven profitable strategy** and not an auto-trader.

## v0.2 event flow

- `SETUP_ARMED` — location + sweep + MSS + fresh FVG confirmed; wait for retrace.
- `ENTRY_READY` — CE retrace/hold confirmed and risk/R:R filters pass.
- `SKIP_RISK` — structural stop would exceed the $35 planned-risk cap for 1 MNQ.
- `SKIP_RR` — less than 2R room to the structural objective.

## Files

- `pine/mnq_reversal_v0_2.pine` — current TradingView indicator
- `pine/mnq_reversal_v0_1.pine` — original build / rollback copy
- `app/main.py` — FastAPI webhook receiver
- `app/static/index.html` — dark decision dashboard
- `railway.toml` — Railway deployment config

## TradingView alert for v0.2

Use **one** alert:

- Condition: `MNQ Reversal-Expansion v0.2`
- Trigger source: `Any alert() function call`
- Frequency: once per bar close
- Webhook: `https://mnq-reversal-engine-production.up.railway.app/webhook/tradingview`

The Pine script builds the JSON payload itself, so the TradingView alert message does not need a custom LONG/SHORT JSON template.

## Railway

Health endpoint:

`https://mnq-reversal-engine-production.up.railway.app/health`

Dashboard:

`https://mnq-reversal-engine-production.up.railway.app/`

### Persistence note

Railway service files can be ephemeral across redeploys. The backend now supports a `DATA_DIR` environment variable so a Railway Volume can be mounted later and used for durable signal history.

## Current risk policy

- 1 MNQ maximum
- $35 maximum planned risk per setup in the scanner
- $60 TopstepX personal daily loss limit
- no pyramiding / averaging down
- manual execution only
