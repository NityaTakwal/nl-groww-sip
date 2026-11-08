"""Codebook: the fixed tagging schema. Every field maps to a question in the brief.

Fixed categories (not free-form themes) make the output countable, comparable across
segments, and checkable against a hand-labelled golden set.
"""
from typing import Literal

from pydantic import BaseModel, Field

Stage = Literal["pre_start", "first_month", "months_1_3", "months_3_6", "months_6_12", "beyond_12", "unclear"]
Theme = Literal[
    "start_motivation",            # why they started / what triggered the first SIP
    "return_expectation_gap",      # early returns low/negative vs what they expected
    "returns_understanding",       # confused by XIRR, absolute vs annualised, NAV, units, red numbers
    "market_volatility_anxiety",   # worry driven by market falls / news
    "payment_mandate_failure",     # autopay/mandate/e-NACH failed, bounce, SIP auto-cancelled
    "cashflow_income_stress",      # irregular income, job loss, emergency, expenses squeeze
    "sip_management_friction",     # hard to pause/skip/modify/cancel/restart, date issues
    "app_trust_or_bug",            # glitches, order delays, redemption/withdrawal problems, support
    "advice_seeking",              # asking others what to do, which fund, should I stop
    "goal_clarity",                # no clear goal/horizon, unsure why investing
    "disengagement_habit",         # forgot, stopped checking, lost interest, set-and-forget
    "positive_continuation",       # staying the course, discipline, satisfied
    "other",
]
Action = Literal["started", "continuing", "considering_stop", "paused_or_skipped", "reduced",
                 "stopped_or_cancelled", "missed_involuntarily", "redeemed", "none_mentioned"]
StopDriver = Literal["voluntary_market_or_returns", "voluntary_cashflow", "voluntary_confusion_or_doubt",
                     "involuntary_payment_failure", "life_event", "platform_issue", "not_applicable"]
Checking = Literal["daily", "weekly", "monthly", "rarely", "not_mentioned"]
OutsideHelp = Literal["reddit_forums", "youtube_finfluencer", "friends_family", "advisor_or_ca", "none_mentioned"]
Income = Literal["salaried", "variable_or_gig", "student_or_no_income", "business", "unknown"]
Age = Literal["under_25", "25_34", "35_plus", "unknown"]
Influence = Literal["friend_family", "finfluencer_social", "employer_colleague", "self_research", "ads_or_app", "unknown"]
Sentiment = Literal["negative", "neutral", "positive"]


class Tag(BaseModel):
    relevant: bool = Field(description="True only if the text is about an individual's own SIP/mutual-fund investing experience, intent or questions.")
    is_first_time_investor: bool = Field(description="True if the author signals they are new / first-time / beginner to mutual funds or SIPs.")
    journey_stage: Stage = Field(description="Where the author is relative to starting their first SIP.")
    primary_theme: Theme = Field(description="The single main theme of the text.")
    secondary_theme: Theme = Field(description="Second most important theme; use 'other' if none.")
    action_taken: Action = Field(description="What the author did or is considering doing with their SIP.")
    stop_driver: StopDriver = Field(description="Root driver if they stopped/paused/missed/reduced/considered stopping; else not_applicable.")
    checking_behaviour: Checking = Field(description="How often they check their portfolio/returns, if mentioned.")
    outside_app_help: OutsideHelp = Field(description="Where they go outside the app when unsure, if mentioned.")
    income_type: Income
    age_band: Age
    influence_source: Influence = Field(description="Who/what influenced them to start investing.")
    sentiment: Sentiment
    severity: int = Field(ge=1, le=3, description="1 = no threat to continuing SIP, 2 = doubt/wavering, 3 = stopped/paused/missed or about to.")
    unmet_need: str = Field(description="The underlying need not met, in <= 15 words, user's perspective. Empty if none.")
    evidence_quote: str = Field(description="Shortest verbatim span (<= 30 words) from the text that supports primary_theme.")


# Which node of the metric tree each theme pushes on (see 03_metric_decomposition).
THEME_TO_METRIC_NODE = {
    "start_motivation": "A. Activation quality (right SIP, right amount, clear goal)",
    "return_expectation_gap": "C. Voluntary stop — expectation vs early outcome",
    "returns_understanding": "C. Voluntary stop — expectation vs early outcome",
    "market_volatility_anxiety": "C. Voluntary stop — expectation vs early outcome",
    "payment_mandate_failure": "B. Involuntary lapse — instalment failure",
    "cashflow_income_stress": "D. Voluntary stop — affordability / cashflow",
    "sip_management_friction": "E. Flexibility — pause/skip/modify instead of cancel",
    "app_trust_or_bug": "F. Platform trust & reliability",
    "advice_seeking": "C. Voluntary stop — expectation vs early outcome",
    "goal_clarity": "A. Activation quality (right SIP, right amount, clear goal)",
    "disengagement_habit": "G. Engagement & salience",
    "positive_continuation": "(continuer signal)",
    "other": "(unmapped)",
}

# Can Groww address this within the brief's constraints (no fund picks, no fear/FOMO/urgency)?
# 1.0 fully addressable by product, 0.5 partially, 0.2 mostly outside product control.
ADDRESSABILITY = {
    "start_motivation": 0.5, "return_expectation_gap": 1.0, "returns_understanding": 1.0,
    "market_volatility_anxiety": 0.5, "payment_mandate_failure": 1.0, "cashflow_income_stress": 0.5,
    "sip_management_friction": 1.0, "app_trust_or_bug": 0.5, "advice_seeking": 0.5,
    "goal_clarity": 1.0, "disengagement_habit": 0.5, "positive_continuation": 0.0, "other": 0.0,
}

GOLDEN_FIELDS = ["relevant", "journey_stage", "primary_theme", "action_taken", "stop_driver", "income_type"]
