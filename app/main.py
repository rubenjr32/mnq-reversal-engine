from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path
from datetime import datetime, timezone
import json

app = FastAPI(title="MNQ Reversal Engine", version="0.1.0")

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"
DATA.mkdir(exist_ok=True)
SIGNALS = DATA / "signals.jsonl"

app.mount("/static", StaticFiles(directory=str(BASE / "app" / "static")), name="static")

class Signal(BaseModel):
    symbol: str = "MNQ"
    side: str
    grade: str = "A"
    price: float | None = None
    stop: float | None = None
    target: float | None = None
    notes: str | None = None

@app.get("/health")
def health():
    return {"ok": True, "version": "0.1.0"}

@app.get("/", response_class=HTMLResponse)
def dashboard():
    return (BASE / "app" / "static" / "index.html").read_text(encoding="utf-8")

@app.get("/api/signals")
def get_signals(limit: int = 50):
    if not SIGNALS.exists():
        return []
    rows = []
    with SIGNALS.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows[-max(1, min(limit, 500)):][::-1]

@app.post("/webhook/tradingview")
async def tradingview_webhook(request: Request):
    try:
        payload = await request.json()
    except Exception:
        payload = {"raw": (await request.body()).decode("utf-8", errors="ignore")}

    row = {
        "received_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    with SIGNALS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    return {"ok": True}

@app.post("/api/manual-signal")
def manual_signal(signal: Signal):
    row = {
        "received_at": datetime.now(timezone.utc).isoformat(),
        "payload": signal.model_dump(),
    }
    with SIGNALS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    return {"ok": True, "signal": row}
