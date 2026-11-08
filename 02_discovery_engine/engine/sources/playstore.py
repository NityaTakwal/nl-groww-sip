"""Groww Play Store reviews -> MF/SIP-relevant JSONL records. Run: uv run --python 3.12 --with google-play-scraper python playstore.py"""
import hashlib, json, re, sys, time
from pathlib import Path
from google_play_scraper import Sort, reviews

APP_ID = "com.nextbillion.groww"
OUT = Path(__file__).resolve().parents[2] / "data/store/playstore.jsonl"
KEYWORDS = ["sip", "mutual fund", "mf", "autopay", "auto pay", "mandate", "instalment", "installment", "nach",
            "e-mandate", "pause", "skip", "cancel sip", "stop sip", "step up", "xirr", "returns", "nav", "redeem",
            "redemption", "withdraw", "portfolio", "invested", "debit", "bounce", "insufficient", "units", "folio",
            "elss", "lumpsum"]
sha = lambda s, n: hashlib.sha1(s.encode()).hexdigest()[:n]

def _matcher(keywords):
    # word-boundary match so "mf"/"nav"/"nach" don't hit inside other words
    pats = [(k, re.compile(r"(?<![a-z0-9])" + re.escape(k) + r"(?![a-z0-9])", re.I)) for k in keywords]
    return lambda text: next((k for k, p in pats if p.search(text)), None)

def fetch(max_items: int = 2000, keywords: list[str] | None = None, raw_limit: int = 30000) -> list[dict]:
    match, seen, raw, out = _matcher(keywords or KEYWORDS), set(), 0, {}
    for sort in (Sort.NEWEST, Sort.MOST_RELEVANT):
        token, pulled = None, 0
        while pulled < raw_limit and len(out) < max_items:
            try:
                batch, token = reviews(APP_ID, lang="en", country="in", sort=sort, count=200, continuation_token=token)
            except Exception as e:  # transient/rate-limit: back off once, then stop this sort
                print("error:", e, file=sys.stderr); time.sleep(5)
                break
            if not batch: break
            pulled += len(batch); raw += len(batch)
            for r in batch:
                text = (r.get("content") or "").strip()
                if len(text) < 25: continue
                q = match(text)
                if not q: continue
                date = r["at"].strftime("%Y-%m-%d")
                rid = "playstore-" + sha(text + date, 12)
                if rid in out: continue
                out[rid] = {"id": rid, "source": "playstore",
                            "url": f"https://play.google.com/store/apps/details?id={APP_ID}&reviewId={r['reviewId']}",
                            "date": date, "title": "", "text": text, "rating": r["score"],
                            "score": r.get("thumbsUpCount"), "author_hash": sha(r.get("userName") or "", 10),
                            "collected_via": "live_api", "query": q}
            if not token: break
            time.sleep(0.3)
        print(f"{sort.name}: pulled {pulled}, relevant so far {len(out)}", file=sys.stderr)
    fetch.raw_count = raw
    return list(out.values())[:max_items]

if __name__ == "__main__":
    recs = fetch(max_items=2500)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in recs))
    print(f"raw={fetch.raw_count} kept={len(recs)} -> {OUT}")
