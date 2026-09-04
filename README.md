# MNQ Opportunity Engine

Current build: **v0.3** — regime-aware multi-playbook scanner, manual execution.

The project started as a single confirmed liquidity-reversal model. v0.3 expands it into an opportunity engine so MNQ trend days, early reversals, VWAP reactions, and failed breakouts are not ignored simply because the original reversal sequence did not complete.

This is still experimental research software, **not a proven profitable strategy** and not an auto-trader.

## v0.3 market-regime layer

The Pine engine classifies the current environment using VWAP, EMA20/EMA50 structure, ATR-normalized trend strength, and extension from VWAP:

- `TREND_UP`
- `TREND_DOWN`
- `RANGE`
- `EXTENDED_UP`
- `EXTENDED_DOWN`

Session timing is a confidence modifier, not a hard permission gate.

## Five active playbooks

1. **Confirmed Liquidity Reversal** — premium/discount + liquidity sweep + 5m MSS/displacement + FVG + CE retrace/hold.
2. **Early Reversal** — sweep at useful location followed by faster 1m/3m or strong 5m reversal impulse, without waiting for the full 5m confirmed sequence.
3. **Trend Pullback** — directional regime + pullback to EMA20/structure + continuation close in the trend direction.
4. **VWAP Reclaim / Reject** — reclaim or rejection of session VWAP with directional candle confirmation and contextual scoring.
5. **Failed Breakout** — failed break through prior-day or opening-range external levels, followed by close back inside.

Each candidate receives a 0–10 quality score. The engine chooses the strongest valid opportunity on the bar instead of emitting every possible setup.

## Risk filters

Current default policy:

- 1 MNQ maximum
- $35 maximum planned structural risk per setup
- $60 TopstepX personal daily loss limit
- no averaging down
- no pyramiding yet
- manual chart verification before any order

Minimum room-to-objective varies by playbook:

- confirmed reversal: 2.0R
- early reversal: 1.5R
- trend pullback: 1.75R
- VWAP reclaim/reject: 1.75R
- failed breakout: 2.0R

## Event flow

v0.3 emits one JSON event per completed chart bar:

- `STATE` — current regime, bias, session, location, VWAP, and all five playbook statuses.
- `SETUP_ARMED` — confirmed liquidity-reversal structure exists and is waiting for its entry trigger.
- `ENTRY_READY` — best ranked playbook passed quality, structural risk, and room-to-objective filters.

The backend separates state heartbeats from actionable events so a later `STATE` update does not erase a still-fresh `ENTRY_READY` signal.

## Files

- `pine/mnq_opportunity_v0_3.pine` — current TradingView engine
- `pine/mnq_reversal_v0_2.pine` — prior conservative reversal model / rollback
- `pine/mnq_reversal_v0_1.pine` — original build / rollback
- `app/main.py` — FastAPI webhook receiver and state/action APIs
- `app/static/index.html` — v0.3 dark opportunity dashboard
- `railway.toml` — Railway deployment config

## TradingView alert for v0.3

Create **one** alert after adding `MNQ Opportunity Engine v0.3` to the MNQU2026 5-minute chart:

- Condition: `MNQ Opportunity Engine v0.3`
- Trigger source: `Any alert() function call`
- Frequency: once per bar close
- Webhook: `https://mnq-reversal-engine-production.up.railway.app/webhook/tradingview`

The Pine script builds the JSON payload itself. No custom LONG/SHORT alert message is required.

## Railway

Health endpoint:

`https://mnq-reversal-engine-production.up.railway.app/health`

Dashboard:

`https://mnq-reversal-engine-production.up.railway.app/`

### Persistence note

Railway service files can be ephemeral across redeploys. The backend supports a `DATA_DIR` environment variable so a Railway Volume can be mounted for durable signal history.
