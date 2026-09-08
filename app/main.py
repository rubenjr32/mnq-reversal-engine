from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path
from datetime import datetime, timezone
import json
import os
import uuid

app = FastAPI(title="MNQ Opportunity Engine", version="0.4.1")

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
    return rows[-max(1, min(limit, 5000)):]


def append_payload(payload):
    payload = dict(payload) if isinstance(payload, dict) else {"raw": payload}
    if str(payload.get("event") or "").upper() == "ENTRY_READY" and not payload.get("signal_id"):
        payload["signal_id"] = uuid.uuid4().hex[:12]
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


def parse_dt(value):
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def row_age_seconds(row) -> float:
    if not row or not row.get("received_at"):
        return float("inf")
    received = parse_dt(row["received_at"])
    if received is None:
        return float("inf")
    return max(0.0, (datetime.now(timezone.utc) - received.astimezone(timezone.utc)).total_seconds())


def action_ttl_seconds(payload) -> float:
    try:
        explicit = float(payload.get("ttl_seconds"))
        if explicit > 0:
            return min(explicit, 600.0)
    except Exception:
        pass
    source = str(payload.get("source") or "").strip().lower()
    if source == "exec1m":
        return 150.0
    return 600.0


def to_float(v):
    try:
        return float(v)
    except Exception:
        return None


def grade_open_signals(bar_row):
    """Use each completed 1m OHLC heartbeat to grade unresolved ENTRY_READY signals.

    WIN = target touched before stop can be disproven on this bar.
    LOSS = stop touched before target can be disproven on this bar.
    AMBIGUOUS = both stop and target touched inside the same 1m bar; ordering is unknowable.
    EXPIRED = 60 minutes elapsed without either level touching.
    """
    bar = bar_row.get("payload") or {}
    if str(bar.get("event") or "").upper() != "BAR":
        return []
    hi, lo = to_float(bar.get("high")), to_float(bar.get("low"))
    if hi is None or lo is None:
        return []
    now = parse_dt(bar_row.get("received_at")) or datetime.now(timezone.utc)
    rows = read_rows(5000)
    resolved = {
        str((r.get("payload") or {}).get("signal_id"))
        for r in rows
        if str((r.get("payload") or {}).get("event") or "").upper() == "TRADE_RESULT"
    }
    results = []
    for r in rows:
        p = r.get("payload") or {}
        if str(p.get("event") or "").upper() != "ENTRY_READY" or is_test_payload(p):
            continue
        sid = str(p.get("signal_id") or "")
        if not sid or sid in resolved:
            continue
        entered = parse_dt(r.get("received_at"))
        if entered is None or entered >= now:
            continue
        side = str(p.get("side") or "").upper()
        entry, stop, target = to_float(p.get("price")), to_float(p.get("stop")), to_float(p.get("target"))
        if side not in {"LONG", "SHORT"} or entry is None or stop is None or target is None:
            continue
        age_min = (now - entered).total_seconds() / 60.0
        stop_hit = lo <= stop if side == "LONG" else hi >= stop
        target_hit = hi >= target if side == "LONG" else lo <= target
        result = None
        exit_price = None
        if stop_hit and target_hit:
            result = "AMBIGUOUS"
        elif target_hit:
            result, exit_price = "WIN", target
        elif stop_hit:
            result, exit_price = "LOSS", stop
        elif age_min >= 60:
            result, exit_price = "EXPIRED", to_float(bar.get("close"))
        if result is None:
            continue
        risk_usd = abs(entry - stop) * 2.0
        pnl_usd = None
        if result == "WIN":
            pnl_usd = abs(target - entry) * 2.0
        elif result == "LOSS":
            pnl_usd = -risk_usd
        elif result == "EXPIRED" and exit_price is not None:
            pnl_usd = ((exit_price - entry) if side == "LONG" else (entry - exit_price)) * 2.0
        out = {
            "source": "grader1m",
            "event": "TRADE_RESULT",
            "signal_id": sid,
            "symbol": p.get("symbol", bar.get("symbol", "MNQ")),
            "side": side,
            "playbook": p.get("playbook", "NONE"),
            "grade": p.get("grade", ""),
            "score": p.get("score"),
            "entry": entry,
            "stop": stop,
            "target": target,
            "exit_price": exit_price,
            "result": result,
            "pnl_usd_1mnq": pnl_usd,
            "minutes_open": round(age_min, 2),
            "notes": "Both stop and target touched in same 1m bar; ordering unknown." if result == "AMBIGUOUS" else None,
        }
        results.append(append_payload(out))
        resolved.add(sid)
    return results


@app.get("/health")
def health():
    return {"ok": True, "version": "0.4.1", "storage": str(DATA)}


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return (BASE / "app" / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/api/signals")
def get_signals(limit: int = 100):
    return read_rows(limit)[::-1]


@app.get("/api/results")
def get_results(limit: int = 100):
    out = []
    for row in reversed(read_rows(5000)):
        p = row.get("payload") or {}
        if str(p.get("event") or "").upper() == "TRADE_RESULT" and not is_test_payload(p):
            out.append(row)
            if len(out) >= max(1, min(limit, 500)):
                break
    return out


@app.get("/api/latest-state")
def get_latest_state():
    return latest_matching(lambda p: str(p.get("event") or "").upper() == "STATE", 1500)


@app.get("/api/latest-action")
def get_latest_action():
    actionable = {"ENTRY_READY", "SETUP_ARMED", "SKIP_RISK", "SKIP_RR"}
    row = latest_matching(lambda p: str(p.get("event") or "").upper() in actionable, 1500)
    if row is None:
        return None
    payload = row.get("payload") or {}
    if row_age_seconds(row) > action_ttl_seconds(payload):
        return None
    return row


@app.get("/api/latest")
def get_latest():
    return get_latest_action()


@app.post("/webhook/tradingview")
async def tradingview_webhook(request: Request):
    try:
        payload = await request.json()
    except Exception:
        payload = {"raw": (await request.body()).decode("utf-8", errors="ignore")}
    row = append_payload(payload)
    graded = grade_open_signals(row)
    return {"ok": True, "signal": row, "graded": graded}


@app.post("/api/manual-signal")
def manual_signal(signal: Signal):
    return {"ok": True, "signal": append_payload(signal.model_dump())}
