"""Deterministic quality gate applied to every AI reply before a user sees it.

Brief constraints: no fund/stock recommendations, no fear/FOMO/urgency nudges, never framed as advice.
Rules are cheap, explainable and can't be talked around by the model; anything that fails is replaced
by a safe fallback, and the UI shows which checks ran.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# AMC / fund-name fragments and buy/sell-a-security language -> specific recommendation risk.
FUND_TERMS = re.compile(
    r"\b(axis|hdfc|icici|sbi|nippon|kotak|parag parikh|ppfas|mirae|quant|motilal|uti|dsp|tata|aditya birla|"
    r"franklin|canara robeco|edelweiss|bandhan|invesco|hsbc|sundaram|groww (nifty|value|large))\b"
    r"|\b(nifty ?50 index fund|flexi ?cap fund|small ?cap fund|mid ?cap fund|elss fund)\b"
    r"|\b(you should (buy|invest in|switch to)|switch (your|to a) (fund|scheme)|better fund|best fund)\b", re.I)

# Fear / FOMO / urgency vocabulary.
PRESSURE_TERMS = re.compile(
    r"\b(hurry|act now|don'?t miss|last chance|limited time|before it'?s too late|you will regret|"
    r"missing out|fomo|losing money every day|crash(ing)? soon|everyone is investing|urgent(ly)?|today only|"
    r"jaldi karo|mauka (mat )?(chhod|gaya)|chhoot jayega|der mat karo|pachtaoge|sab log invest)\b", re.I)

# Return promises / predictions.
PROMISE_TERMS = re.compile(
    r"\b(guarantee[sd]?|assured returns?|will (definitely|surely) (grow|recover|give)|risk[- ]free|"
    r"sure[- ]shot|double your money|market will (go up|recover|rise)|you will earn \d+)", re.I)

# Honest uncertainty statements quote the promise words they deny ("no one can say the market will recover",
# "returns are not guaranteed"). Strip these spans before the promise check so the gate doesn't block the
# very disclaimer we want. A bare negated prediction ("the market won't fall") is still caught.
_CLAUSE = r"(?:(?!\b(?:but|lekin|par|however)\b)[^.!?\n,;])*"  # stays inside one clause
DISCLAIMER_SPANS = re.compile(
    r"\b(?:no ?one|nobody|(?:we|i|you) (?:can'?t|cannot|can not)|(?:can'?t|cannot) be)\s+(?:can |could )?"
    r"(?:say|predict|know|tell|guarantee|sure)" + _CLAUSE
    + r"|" + _CLAUSE + r"\b(?:is|are) not (?:guaranteed|assured|risk[- ]free)" + _CLAUSE
    + r"|" + _CLAUSE + r"\b(?:isn'?t|aren'?t) (?:guaranteed|assured|risk[- ]free)" + _CLAUSE
    + r"|\b(?:koi|kisi ko) (?:nahi|nahin) (?:bata|keh|jaan)" + _CLAUSE
    + r"|" + _CLAUSE + r"\b(?:pakka|guarantee) nahi" + _CLAUSE, re.I)

# Telling the user what to do with their money, as advice.
ADVICE_TERMS = re.compile(r"\b(i (recommend|advise|suggest you)|my advice|you must (continue|stop|invest))\b", re.I)


@dataclass
class GateResult:
    passed: bool
    checks: dict[str, bool] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)


def check(text: str, confidence: float | None = None, min_confidence: float = 0.6) -> GateResult:
    checks = {
        "no_fund_or_stock_names": not FUND_TERMS.search(text),
        "no_fear_fomo_urgency": not PRESSURE_TERMS.search(text),
        "no_return_promises": not PROMISE_TERMS.search(DISCLAIMER_SPANS.sub(" ", text)),
        "not_framed_as_advice": not ADVICE_TERMS.search(text),
    }
    if confidence is not None:
        checks["understood_situation_confidently"] = confidence >= min_confidence
    reasons = [k for k, ok in checks.items() if not ok]
    return GateResult(passed=not reasons, checks=checks, reasons=reasons)
