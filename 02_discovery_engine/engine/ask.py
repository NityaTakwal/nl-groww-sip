"""Stage 4: 'Ask the corpus' — answers a research question using only tagged evidence, with citations.

Retrieval is deliberately simple and inspectable: filter by codebook fields that match the question,
then rank by keyword overlap. The model must cite record ids; if fewer than MIN_EVIDENCE items are
retrieved, it refuses instead of guessing.
"""
from __future__ import annotations

import re

import pandas as pd
from langchain_core.messages import HumanMessage, SystemMessage

from common.llm import get_model

MIN_EVIDENCE = 5

# The brief's discovery questions -> codebook filters that pull the right evidence.
PRESETS = {
    "Why do people start a SIP, and what do they expect to happen?": {"primary_theme": ["start_motivation", "return_expectation_gap", "goal_clarity"]},
    "What changes in their behaviour in the months after starting?": {"journey_stage": ["months_1_3", "months_3_6", "months_6_12"]},
    "What leads investors to pause, reduce or stop a SIP?": {"drop_signal": [True]},
    "What do investors check, and how often, once they have started?": {"checking_behaviour": ["daily", "weekly", "monthly", "rarely"]},
    "What confuses or worries them inside the app?": {"primary_theme": ["returns_understanding", "payment_mandate_failure", "sip_management_friction", "app_trust_or_bug"]},
    "What do they do outside the app when they feel unsure?": {"outside_app_help": ["reddit_forums", "youtube_finfluencer", "friends_family", "advisor_or_ca"]},
    "What separates investors who continue from those who quietly drop off?": {"action_taken": ["continuing", "stopped_or_cancelled", "missed_involuntarily", "paused_or_skipped"]},
    "How do these patterns differ across user segments?": {"income_type": ["salaried", "variable_or_gig", "student_or_no_income", "business"]},
    "What unmet needs emerge consistently across conversations?": {"severity": [2, 3]},
}

SYSTEM = """You are a product research analyst. Answer the question using ONLY the evidence items provided.
- Every claim must cite item ids in square brackets, e.g. [reddit-abc123].
- Give counts where the evidence supports them ("7 of 25 items...").
- Separate what is well supported (many items) from weak signals (1-2 items).
- If the evidence does not answer the question, say so plainly. Never invent facts or numbers.
- Output: 4-7 short bullet points, then one line 'Confidence: high/medium/low — why'."""


def retrieve(df: pd.DataFrame, question: str, k: int = 40) -> pd.DataFrame:
    rel = df[df["relevant"]]
    filters = PRESETS.get(question, {})
    for col, vals in filters.items():
        rel = rel[rel[col].isin(vals)]
    words = {w for w in re.findall(r"[a-z]{4,}", question.lower())} - {"what", "they", "with", "does", "their", "after", "investors"}
    text = (rel["title"].fillna("") + " " + rel["text"] + " " + rel["unmet_need"].fillna("")).str.lower()
    rel = rel.assign(_hits=text.apply(lambda t: sum(w in t for w in words)) + rel["severity"] * 0.5)
    return rel.sort_values("_hits", ascending=False).head(k)


def answer(df: pd.DataFrame, question: str) -> dict:
    ev = retrieve(df, question)
    if len(ev) < MIN_EVIDENCE:
        return {"answer": f"Not enough evidence in the corpus to answer this ({len(ev)} matching items). "
                          "Try a broader question.", "evidence": ev, "refused": True}
    lines = [f"[{i}] ({r.source}, {r.journey_stage}, {r.primary_theme}) {r.text[:500]}" for i, r in ev.iterrows()]
    msg = f"Question: {question}\n\nEvidence ({len(ev)} items):\n" + "\n".join(lines)
    out = get_model("smart").invoke([SystemMessage(SYSTEM), HumanMessage(msg)]).text
    cited = set(re.findall(r"\[([a-z]+-[\w.-]+)\]", out))
    unknown = cited - set(ev.index)
    for uid in unknown:  # make mis-citations visible instead of letting them pass as evidence
        out = out.replace(f"[{uid}]", f"[{uid} ⚠ not in evidence]")
    return {"answer": out, "evidence": ev, "refused": False, "cited": len(cited & set(ev.index)),
            "hallucinated_ids": sorted(unknown)}
