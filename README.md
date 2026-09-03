# MNQ Reversal-Expansion Engine v0.1

First-pass research/execution assistant for MNQ.

## Philosophy

This version intentionally does **not** auto-trade.

Core sequence:

1. Higher-timeframe location (premium/discount)
2. Liquidity sweep
3. Displacement / market-structure shift
4. FVG / consequent encroachment for entry refinement
5. Structural stop
6. Real target with >= ~2R room
7. Manual execution, initially 1 MNQ maximum

The Pine logic is deliberately conservative and incomplete. It is a scanner/assistant, not a proven profitable strategy.

## Files

- `pine/mnq_reversal_v0_1.pine` — TradingView indicator
- `app/main.py` — FastAPI webhook receiver
- `app/static/index.html` — dark dashboard
- `data/signals.jsonl` — created at runtime
- `railway.toml` — Railway config

## Local run

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

## Railway

1. Push this repo to GitHub.
2. Create a new Railway project from the repo.
3. Railway should use `railway.toml`.
4. Confirm `/health` returns `{"ok":true,...}`.
5. Your TradingView webhook endpoint will be:

`https://YOUR-RAILWAY-DOMAIN/webhook/tradingview`

## TradingView

Paste `pine/mnq_reversal_v0_1.pine` into Pine Editor and add it to an MNQ chart.

Create alerts for:
- `MNQ LONG A`
- `MNQ SHORT A`

For the first day, use TradingView alerts as **notifications only**. We will refine webhook JSON after we see live examples.

## Important

v0.1 is a research assistant. Do not assume a signal has positive expectancy merely because it is labeled A. The whole point of logging is to discover which components actually matter.
