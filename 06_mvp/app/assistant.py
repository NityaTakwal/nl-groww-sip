"""Lean-Month Planner — the eval-gated AI step.

1. UNDERSTAND (LLM, structured): what is going on with the user's money this month, in their own words
   (Hinglish welcome), plus when their money usually arrives and how sure the model is.
2. DECIDE OPTIONS (code, rules.py): which actions exist and their exact consequences. No AI here.
3. EXPLAIN (LLM, structured): a short, calm reply that only restates provided facts and ranks the options.
4. GATE (code, guardrails.py): no fund names, no pressure, no promises, no advice framing, confidence >= 0.6.
   Fail -> safe fallback (neutral explanation + all options + official sources). Advice requests -> decline.
"""
from __future__ import annotations

import json
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from common.llm import describe, get_model

from . import guardrails, rules

Situation = Literal["cash_timing", "cash_shortfall", "returns_doubt", "rules_confusion", "life_event",
                    "wants_to_stop_other", "advice_request", "off_topic"]


class Understanding(BaseModel):
    situation: Situation = Field(description=(
        "cash_timing: money will come, just later than the SIP date (salary/client/stipend/incentive late). "
        "cash_shortfall: not enough money this month (low income month, expenses, EMI). "
        "returns_doubt: worried/confused because value is red, low or not growing. "
        "rules_confusion: unsure how skip/pause/missed/cancel/charges work. "
        "life_event: emergency, job loss, wedding, medical, big planned expense. "
        "wants_to_stop_other: wants to stop for another reason. "
        "advice_request: ONLY asks which fund/stock/category to buy or switch to, or asks for a market/return prediction "
        "('will it recover', 'is this the bottom'). 'Should I stop / continue / pause my SIP?' is NOT advice_request: "
        "classify it by the reason behind it (returns_doubt, cash_*, life_event, wants_to_stop_other). "
        "off_topic: unrelated to their SIP."))
    also_worried_about_returns: bool = Field(description="True if the message also mentions red/low returns or markets.")
    income_day: int | None = Field(default=None, description="Day of month (1-28) their money (salary/payout/stipend) usually arrives, only if the USER states it. Never use the SIP date. Else null.")
    preferred_day: int | None = Field(default=None, description="A specific SIP date the user asks for (e.g. 'date 10 kar do'), else null.")
    temporary: bool = Field(description="True if the money problem sounds temporary (this month / a few months).")
    language: Literal["english", "hindi", "hinglish"]
    summary: str = Field(description="One sentence, <= 20 words, in the user's language, addressed to them in second person (e.g. 'Your salary comes on the 9th, and the red number is worrying you.').")
    confidence: float = Field(ge=0, le=1, description="How sure you are about `situation` given the message.")


class Reply(BaseModel):
    message: str = Field(description="2-3 short sentences, max 45 words, in the user's language and script. Calm, plain, no jargon. Do not list the options.")
    option_order: list[str] = Field(description="Option ids, most helpful first for THIS situation.")
    returns_note: str = Field(default="", description="Leave empty. (The screen already explains the numbers.)")


UNDERSTAND_SYS = """You help first-time mutual fund SIP investors in India who are having a hard money month.
Read the user's message (often Hinglish) and classify what is going on. Do not give advice. Be literal:
if the message does not say when money arrives, income_day is null. If it asks which fund to buy or whether
markets will go up, situation=advice_request. A user asking whether to stop/continue/pause their own SIP is NOT an
advice request: they deserve to see their options; classify the reason behind the question."""

EXPLAIN_SYS = """You write the reply inside a Groww SIP screen for an investor having a tight month.
HARD RULES (a checker enforces them; violating replies are discarded):
- Never name or suggest any fund, AMC, stock or category to buy/switch. Never predict markets or returns.
- No fear, FOMO, urgency, guilt or pressure. No 'don't miss out', 'act now', 'you will regret'.
- Not advice: do not say 'I recommend/you should/you must'. Present options neutrally; the user decides.
- Use ONLY the facts provided (amounts, dates, missed count, rule). Do not invent rules, charges or dates.
- If they are close to automatic cancellation, state the count plainly and neutrally.
- Respect the user's autonomy: stopping is a valid choice; just make sure they know what each option does.
- Answer the user's own question first (e.g. 'can I take a 2-month break?': say honestly there is no multi-month pause;
  skipping is one instalment at a time and counts toward the 3-in-a-row limit). Do not list every option; the screen shows them.
- Never mention option ids (like move_date, skip_once) and never count the options.
- If they ask "should I stop/continue?", say plainly that it's their call, then point to what each option does (including stopping).
- Never print internal field names or codes (like due_soon, missed_in_row). Use plain words and ₹ amounts.
- Match the user's language: Hinglish in Roman script if they wrote Hinglish, Devanagari only if they wrote Devanagari. Never switch scripts.
- Keep it short and warm, like a helpful friend at the bank counter."""

DECLINE = ("I can't suggest which fund to pick or predict where markets will go — that would be investment advice. "
           "I can help you plan this month's instalment. For learning about funds, see the official investor-education links below.")
FALLBACK_UNSURE = ("I'm not fully sure I understood your situation, so here are all your options for this month with exactly what each one does. "
                   "Nothing changes until you choose.")
FALLBACK_SAFE = ("To keep this reply free of advice or predictions, here are your options in plain form, with exactly what each one does. "
                 "Nothing changes until you choose.")
FALLBACK_ERROR = "I couldn't reach the assistant just now. Here are all your options for this month. Nothing changes until you choose."


def assist(user_text: str, state: rules.SipState) -> dict:
    f = rules.facts(state)
    trace: dict = {"model": describe("smart")}
    try:
        u = get_model("smart").with_structured_output(Understanding).invoke(
            [SystemMessage(UNDERSTAND_SYS), HumanMessage(f"SIP facts: {json.dumps(f)}\nUser message: {user_text}")])
    except Exception as e:  # model down -> safe fallback, never a blank screen
        return _fallback(state, None, f, trace | {"error": type(e).__name__})
    trace["understanding"] = u.model_dump()

    opts = rules.options(state, u.income_day, u.preferred_day)
    sources = [rules.SOURCES["amfi_faq"], rules.SOURCES["groww_skip"]]

    if u.situation in ("advice_request", "off_topic"):
        gate = guardrails.check(DECLINE, u.confidence)
        return _out("declined", DECLINE, "", u, opts, [o.id for o in opts], gate,
                    sources + [rules.SOURCES["amfi_learn"], rules.SOURCES["sebi_investor"]], f, trace)

    ids = [o.id for o in opts]
    try:
        r = get_model("smart").with_structured_output(Reply).invoke([
            SystemMessage(EXPLAIN_SYS),
            HumanMessage(f"Understanding: {u.model_dump_json()}\nSIP facts: {json.dumps(f)}\n"
                         f"Options (id: title — detail — warning): " +
                         "; ".join(f"{o.id}: {o.title} — {o.detail} — {o.warning}" for o in opts if o.allowed))])
    except Exception as e:
        return _fallback(state, u, f, trace | {"error": type(e).__name__})

    order = _safe_order(r.option_order, ids, opts)
    by_id = {o.id: o.title.lower() for o in opts}
    for oid, title in by_id.items():  # ids sometimes leak into prose (MVP test, R3/R4)
        r.message = r.message.replace(oid, f"'{title}'")
    gate = guardrails.check(f"{r.message} {r.returns_note}", u.confidence)
    trace["reply_raw"] = r.model_dump()
    if not gate.passed:
        return _fallback(state, u, f, trace, gate)
    if u.also_worried_about_returns or u.situation == "returns_doubt":
        sources.append(rules.SOURCES["amfi_learn"])
    return _out("answered", r.message, r.returns_note, u, opts, order, gate, sources, f, trace)


def _safe_order(proposed: list[str], ids: list[str], opts: list[rules.Option]) -> list[str]:
    """Keep the model's ranking but enforce: every option shown once, blocked options last, 'stop' never hidden."""
    order = [i for i in proposed if i in ids]
    order += [i for i in ids if i not in order]
    blocked = {o.id for o in opts if not o.allowed}
    return [i for i in order if i not in blocked] + [i for i in order if i in blocked]


def _fallback(state, u, f, trace, gate=None) -> dict:
    opts = rules.options(state, u.income_day if u else None, u.preferred_day if u else None)
    if u is None:
        msg = FALLBACK_ERROR
    elif gate is not None and any(r != "understood_situation_confidently" for r in gate.reasons):
        msg = FALLBACK_SAFE
    else:
        msg = FALLBACK_UNSURE
    gate = gate or guardrails.check(msg, 0.0 if u is None else u.confidence)
    return _out("fallback", msg, "", u, opts, [o.id for o in opts], gate,
                [rules.SOURCES["amfi_faq"], rules.SOURCES["groww_skip"], rules.SOURCES["sebi_investor"]], f, trace)


def _out(mode, message, returns_note, u, opts, order, gate, sources, f, trace) -> dict:
    by_id = {o.id: o for o in opts}
    return {
        "mode": mode,  # answered | fallback | declined
        "message": message,
        "returns_note": returns_note,
        "returns_line": rules.returns_line(rules.SipState(**{k: f[k] for k in ("amount", "sip_day", "months_active", "missed_in_row", "invested", "current_value")})),
        "understood": u.summary if u else "",
        "situation": u.situation if u else None,
        "confidence": round(u.confidence, 2) if u else None,
        "income_day": u.income_day if u else None,
        "options": [rules.to_dict([by_id[i]])[0] for i in order],
        "quality_checks": gate.checks,
        "failed_checks": gate.reasons,
        "sources": [{"title": t, "url": url} for t, url in sources],
        "facts": f,
        "trace": trace,
        "disclaimer": "Not investment advice. This helps you plan your SIP instalment; it does not tell you what to invest in.",
    }
