from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path
from datetime import datetime, timezone
import json
import os

app = FastAPI(title="MNQ Reversal Engine", version="0.2.1")

BASE = Path(__file__).resolve().parent.parent
DEFAULT_DATA = BASE / "data"
DATA = Path(os.getenv("DATA_DIR", str(DEFAULT_DATA)))
DATA.mkdir(parents=True, exist_ok=True)
SIGNALS = DATA / "signals.jsonl"

app.mount("/static", StaticFiles(directory=str(BASE / "app" / "static")), name="static")


class Signal(BaseModel):
    symbol: str = "MNQ"
    side: str
    grade: str = "A"
    event: str = "MANUAL"
    price: float | None = None
    stop: float | None = None
    target: float | None = None
    notes: str | None = None


def read_rows(limit: int = 100):
    if not SIGNALS.exists():
        return []
    rows = []
    with SIGNALS.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows[-max(1, min(limit, 1000)):]


def append_payload(payload):
    row = {
        "received_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    with SIGNALS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")
    return row


def is_test_payload(payload) -> bool:
    """Never allow synthetic/manual test events to become the live trade decision."""
    if not isinstance(payload, dict):
        return True

    event = str(payload.get("event") or "").strip().upper()
    session = str(payload.get("session") or "").strip().upper()
    grade = str(payload.get("grade") or "").strip().upper()
    source = str(payload.get("source") or "").strip().lower()
    side = str(payload.get("side") or "").strip().upper()

    return (
        event == "TEST"
        or session == "TEST"
        or grade == "TEST"
        or side == "TEST"
        or source in {"manual-test", "test", "synthetic-test"}
    )


@app.get("/health")
def health():
    return {
        "ok": True,
        "version": "0.2.1",
        "storage": str(DATA),
    }


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return (BASE / "app" / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/api/signals")
def get_signals(limit: int = 50):
    return read_rows(limit)[::-1]


@app.get("/api/latest")
def get_latest():
    rows = read_rows(500)
    for row in reversed(rows):
        payload = row.get("payload") or {}
        if not is_test_payload(payload) and payload.get("event"):
            return row
    return None


@app.post("/webhook/tradingview")
async def tradingview_webhook(request: Request):
    try:
        payload = await request.json()
    except Exception:
        payload = {"raw": (await request.body()).decode("utf-8", errors="ignore")}

    return {"ok": True, "signal": append_payload(payload)}


@app.post("/api/manual-signal")
def manual_signal(signal: Signal):
    return {"ok": True, "signal": append_payload(signal.model_dump())}
