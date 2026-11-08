"""Lean-Month Planner API.  Run from 06_mvp/:  ../.venv/bin/uvicorn app.main:app --port 8000"""
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from . import assistant, rules  # noqa: E402

STATIC = Path(__file__).resolve().parent / "static"
app = FastAPI(title="Groww SIP Lean-Month Planner (MVP)")
app.mount("/static", StaticFiles(directory=STATIC), name="static")

# Demo states a tester can switch between (no real accounts; amounts illustrative).
SCENARIOS = {
    "due_soon": rules.SipState(amount=2000, sip_day=5, months_active=4, missed_in_row=0, status="due_soon",
                               invested=8000, current_value=7650),
    "failed": rules.SipState(amount=2000, sip_day=5, months_active=6, missed_in_row=1, status="failed",
                             invested=10000, current_value=9820),
    "two_missed": rules.SipState(amount=1000, sip_day=5, months_active=8, missed_in_row=2, status="due_soon",
                                 invested=6000, current_value=6240),
}
LABELS = {"due_soon": "Debit in 2 days", "failed": "Instalment just failed", "two_missed": "2 missed in a row"}


class AssistIn(BaseModel):
    text: str
    scenario: str = "due_soon"


class ActionIn(BaseModel):
    scenario: str
    option_id: str
    new_day: int | None = None
    amount: int | None = None


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/scenarios")
def scenarios():
    return {k: {"label": LABELS[k], **rules.facts(v)} for k, v in SCENARIOS.items()}


@app.post("/api/assist")
def assist(body: AssistIn):
    text = body.text.strip()[:1000]
    return assistant.assist(text, SCENARIOS.get(body.scenario, SCENARIOS["due_soon"]))


@app.post("/api/action")
def action(body: ActionIn):
    """Simulated confirmation — the MVP does not touch real mandates."""
    s = SCENARIOS.get(body.scenario, SCENARIOS["due_soon"])
    msgs = {
        "pay_now": f"Opening 'Pending SIP payments' for ₹{s.amount:,}. Pay before the last date shown so it counts.",
        "move_date": f"Done: from your next instalment the SIP debits on the {rules._ord(body.new_day) if body.new_day else '?'}. "
                     "Groww shows the exact first debit date on the confirmation screen.",
        "lower_amount": f"Done: your SIP is now ₹{body.amount or s.amount // 2:,}/month. Same SIP, same history; raise it any time.",
        "keep_and_prepare": f"Reminder set for 2 days before the {s.sip_day}: we'll show the amount due so you can check your balance.",
        "skip_once": f"This instalment is skipped. Missed in a row: {s.missed_in_row + 1} of {rules.CANCEL_AFTER}.",
        "stop": "Your SIP is stopped. Money already invested stays invested. You can start a new SIP any time.",
    }
    return {"ok": True, "message": msgs.get(body.option_id, "Done."), "state": asdict(s)}
