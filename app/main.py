from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path
from datetime import datetime, timezone
import json
import os

app = FastAPI(title="MNQ Opportunity Engine", version="0.3.0")

BASE = Path(__file__).resolve().parent.parent
DEFAULT_DATA = BASE / "data"
DATA = Path(os.getenv("DATA_DIR", str(DEFAULT_DATA)))
DATA.mkdir(parents=True, exist_ok=True)
SIGNALS = DATA / "signals.jsonl"

app.mount("/static", StaticFiles(directory=str(BASE / "app" / "static")), name="static")


class Signal(BaseModel):
    symbol: str = "MNQ"
    side: str = "NONE"
    grade: str = ""
    event: str = "MANUAL"
    playbook: str = "NONE"
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
    return rows[-max(1, min(limit, 3000)):]


def append_payload(payload):
    row = {
        "received_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    with SIGNALS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")
    return row


def is_test_payload(payload) -> bool:
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


def latest_matching(predicate, limit=1000):
    for row in reversed(read_rows(limit)):
        payload = row.get("payload") or {}
        if not is_test_payload(payload) and predicate(payload):
            return row
    return None


@app.get("/health")
def health():
    return {"ok": True, "version": "0.3.0", "storage": str(DATA)}


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return (BASE / "app" / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/api/signals")
def get_signals(limit: int = 100):
    return read_rows(limit)[::-1]


@app.get("/api/latest-state")
def get_latest_state():
    # v0.3 emits a state snapshot every completed chart bar.
    return latest_matching(lambda p: bool(p.get("event")), 1500)


@app.get("/api/latest-action")
def get_latest_action():
    actionable = {"ENTRY_READY", "SETUP_ARMED", "SKIP_RISK", "SKIP_RR"}
    return latest_matching(lambda p: str(p.get("event") or "").upper() in actionable, 1500)


# Backward-compatible alias. This intentionally returns actions, not STATE heartbeats.
@app.get("/api/latest")
def get_latest():
    return get_latest_action()


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
