"""Stage 2: structured tagging of every record against the codebook (LLM, cached, resumable)."""
from __future__ import annotations

import json
import re
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from common.llm import describe, get_model
from engine.codebook import Tag

PROCESSED = Path(__file__).resolve().parents[1] / "data/processed/tagged.jsonl"

# Cheap pre-gate for app-store reviews, which mix trading/stocks with MF content.
MF_TERMS = re.compile(r"\b(sip|sips|mutual\s*funds?|mf|autopay|auto\s*pay|mandate|e-?nach|nach|instal+ments?|"
                      r"xirr|nav|elss|folio|lumpsum|step[- ]?up|redeem|redemption|fund)\b", re.I)

SYSTEM = """You are a senior UX researcher coding public Indian investor conversations about mutual-fund SIPs
(Systematic Investment Plans), mostly about the Groww app. Code the text with the schema exactly.

Rules:
- Base every field only on what the text says or clearly implies. If not stated, use unclear/unknown/not_mentioned.
- relevant=false for content not about the author's (or asker's) own MF/SIP investing: stock trading, F&O, IPO,
  generic app praise, KYC-only issues. Still fill other fields with defaults when irrelevant.
- payment_mandate_failure = autopay/mandate/e-NACH not set up, failed, bounced, SIP missed or auto-cancelled due to payment.
  If the author did not choose to stop, action_taken=missed_involuntarily and stop_driver=involuntary_payment_failure.
- return_expectation_gap = disappointed that returns are low/negative versus what they expected.
  returns_understanding = confused about what the numbers mean (XIRR, absolute returns, NAV, red numbers, units).
- advice_seeking = the post mainly asks others what to do (stop? continue? which fund?).
- journey_stage: infer from tenure mentions (e.g., "6 months back" -> months_3_6; "1 year" -> beyond_12 if > 12 months).
- severity: 1 no threat to continuing, 2 doubt/wavering, 3 stopped/paused/missed or about to.
- evidence_quote must be copied verbatim from the text.
- Hinglish is common; interpret it normally."""


def _prompt(r: dict) -> list:
    body = f"Source: {r['source']}\nTitle: {r.get('title') or '-'}\nText: {r['text'][:2500]}"
    return [SystemMessage(SYSTEM), HumanMessage(body)]


def prefilter(records: list[dict]) -> list[dict]:
    keep = []
    for r in records:
        if r["source"] in ("playstore", "appstore") and not MF_TERMS.search(r["text"]):
            continue
        keep.append(r)
    return keep


def stratified_sample(records: list[dict], per_source: dict[str, int], seed: int = 42) -> list[dict]:
    """Fixed-size random sample per source (deterministic); sources not listed are kept whole."""
    import random
    rng, out = random.Random(seed), []
    for src in sorted({r["source"] for r in records}):
        rows = sorted((r for r in records if r["source"] == src), key=lambda r: r["id"])
        n = per_source.get(src)
        out += rows if n is None or n >= len(rows) else rng.sample(rows, n)
    return out


def load_cache() -> dict[str, dict]:
    if not PROCESSED.exists():
        return {}
    rows = (json.loads(l) for l in PROCESSED.read_text().splitlines() if l.strip())
    return {r["id"]: r for r in rows}


class _Numbered(Tag):
    item: int = Field(description="The item number this coding belongs to.")


class _Batch(BaseModel):
    items: list[_Numbered]


def _batch_prompt(chunk: list[dict]) -> list:
    body = "\n\n".join(f"### Item {n}\nSource: {r['source']}\nTitle: {r.get('title') or '-'}\nText: {r['text'][:1800]}"
                       for n, r in enumerate(chunk, 1))
    return [SystemMessage(SYSTEM + "\n\nCode EVERY item independently; return one coding per item with its item number."),
            HumanMessage(body)]


def tag_records(records: list[dict], batch_size: int = 40, concurrency: int = 4, limit: int | None = None,
                items_per_call: int = 1) -> dict[str, dict]:
    """Several items per LLM call keeps request count low on rate-limited free tiers."""
    cache = load_cache()
    todo = [r for r in records if r["id"] not in cache][:limit]
    print(f"[tag] model={describe('fast')} cached={len(cache)} to_tag={len(todo)} items_per_call={items_per_call}")
    model = get_model("fast").with_structured_output(_Batch)
    PROCESSED.parent.mkdir(parents=True, exist_ok=True)
    groups = [todo[i:i + items_per_call] for i in range(0, len(todo), items_per_call)]
    step = max(1, batch_size // items_per_call)
    with PROCESSED.open("a") as f:
        for g in range(0, len(groups), step):
            wave = groups[g:g + step]
            results = model.batch([_batch_prompt(c) for c in wave], config={"max_concurrency": concurrency},
                                  return_exceptions=True)
            for chunk, res in zip(wave, results):
                if isinstance(res, Exception) or res is None:
                    print(f"[tag] call failed: {type(res).__name__}")
                    continue  # retried on the next run
                for t in res.items:
                    if not 1 <= t.item <= len(chunk):
                        continue
                    r = chunk[t.item - 1]
                    row = {"id": r["id"], **t.model_dump(exclude={"item"}), "tagged_by": describe("fast")}
                    cache[r["id"]] = row
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            print(f"[tag] {sum(len(c) for c in groups[:g + step])}/{len(todo)}")
    return cache


def tag_one(text: str, source: str = "manual", title: str = "") -> Tag:
    return get_model("fast").with_structured_output(Tag).invoke(_prompt({"source": source, "title": title, "text": text}))
