"""Deterministic SIP facts and options. The AI never invents these; it only ranks and words them.

Only rules we can cite are stated as fact: SEBI/AMFI uniform SIP cancellation (from 1 Apr 2024) —
a monthly SIP is cancelled after 3 consecutive failed instalments. Groww counts skips the same way
(Groww help centre). Details that Groww's own help pages contradict (balance buffer days, cancel
cut-off days, minimum amounts) are deliberately NOT asserted.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

CANCEL_AFTER = 3
SOURCES = {
    "amfi_faq": ("AMFI FAQ: uniform SIP cancellation rules",
                 "https://taurusmutualfund.com/sites/default/files/downloads/FAQs_on_Uniform_SIP_cancellation.pdf"),
    "groww_skip": ("Groww help: skipping a SIP instalment", "https://groww.in/help/mutual-funds/mf-sip/how-to-skip-an-sip-instalment--79"),
    "amfi_learn": ("AMFI investor education (Mutual Funds Sahi Hai)", "https://www.mutualfundssahihai.com/en"),
    "sebi_investor": ("SEBI investor website", "https://investor.sebi.gov.in/"),
}


@dataclass
class SipState:
    amount: int = 2000
    sip_day: int = 5
    months_active: int = 4
    missed_in_row: int = 0          # failed or skipped, consecutively
    status: str = "due_soon"        # due_soon | failed | ok
    invested: int = 8000
    current_value: int = 7650


@dataclass
class Option:
    id: str
    title: str
    detail: str
    keeps_sip_alive: bool
    warning: str = ""
    allowed: bool = True
    amounts: list[int] | None = None   # concrete choices for lower_amount
    new_day: int | None = None         # target day for move_date


def facts(s: SipState) -> dict:
    change = s.current_value - s.invested
    return {
        "amount": s.amount, "sip_day": s.sip_day, "months_active": s.months_active,
        "missed_in_row": s.missed_in_row, "cancel_after": CANCEL_AFTER,
        "misses_left_before_cancel": max(CANCEL_AFTER - s.missed_in_row, 0),
        "status": {"due_soon": "next instalment due in 2 days", "failed": "this month's instalment failed (not enough balance)",
                   "ok": "all instalments on track"}[s.status], "invested": s.invested, "current_value": s.current_value,
        "change_rupees": change, "change_pct": round(100 * change / s.invested, 1) if s.invested else 0.0,
    }


def returns_line(s: SipState) -> str:
    """Rules-generated, so the explanation of a red number never depends on the model (MVP test, R4)."""
    change = s.current_value - s.invested
    if change >= 0:
        return f"You've put in ₹{s.invested:,}; it's worth ₹{s.current_value:,} today."
    return (f"You've put in ₹{s.invested:,}; today it's worth ₹{s.current_value:,} ({100 * change / s.invested:.1f}%). "
            "That is today's value of the units you hold. It changes as prices move, and nothing is sold unless you redeem.")


def options(s: SipState, income_day: int | None, preferred_day: int | None = None) -> list[Option]:
    out: list[Option] = []
    nxt = s.missed_in_row + 1
    if s.status == "failed":
        out.append(Option("pay_now", "Pay this instalment yourself",
                          f"Pay ₹{s.amount:,} from 'Pending SIP payments' before the last date the app shows. "
                          "A successful payment resets the missed count; paying after that date counts as missed.",
                          True))
    if income_day == s.sip_day:
        income_day = None  # the SIP date is not evidence of when money arrives (MVP test, R1)
    target = preferred_day or (min(income_day + 2, 28) if income_day else None)
    if target and 1 <= target <= 28 and target != s.sip_day:
        why = (f"You asked for the {_ord(target)}." if preferred_day else
               f"Your money usually arrives around the {_ord(income_day)}; debiting 2 days later gives it time to land.")
        out.append(Option("move_date", f"Move SIP date to the {_ord(target)}",
                          f"{why} The new date applies from your next instalment; Groww shows the exact first debit date before you confirm.",
                          True, new_day=target))
    lower = sorted({max(100, round(s.amount * f / 100) * 100) for f in (0.5, 0.25)} - {s.amount}, reverse=True)
    out.append(Option("lower_amount", "Lower the amount for now",
                      "Invest less while money is tight and raise it again later. The SIP and its history continue.",
                      True, amounts=lower))
    if s.status != "failed":
        out.append(Option("keep_and_prepare", f"Keep ₹{s.amount:,} on the {_ord(s.sip_day)}",
                          "Get a reminder 2 days before the debit with the amount due, so you can check your balance in time.", True))
    skip_warn = (f"This would be {nxt} of {CANCEL_AFTER} in a row. "
                 + ("At 3 in a row the SIP is cancelled automatically." if nxt < CANCEL_AFTER
                    else "This would cancel your SIP automatically."))
    out.append(Option("skip_once", "Skip just this instalment",
                      "Nothing is debited this month. Skips count the same as missed payments.", nxt < CANCEL_AFTER,
                      warning=skip_warn, allowed=nxt < CANCEL_AFTER))
    out.append(Option("stop", "Stop the SIP",
                      "Future instalments stop. Money already invested stays invested. You can start a new SIP any time.", False))
    return out


def to_dict(opts: list[Option]) -> list[dict]:
    return [asdict(o) for o in opts]


def _ord(n: int) -> str:
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"
