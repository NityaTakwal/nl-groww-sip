"""Groww App Store (India) reviews via public iTunes RSS -> JSONL. Run: python3 appstore.py"""
import hashlib, json, re, sys, time, urllib.request
from pathlib import Path

APP_ID = "1404871703"
OUT = Path(__file__).resolve().parents[2] / "data/store/appstore.jsonl"
KEYWORDS = ["sip", "mutual fund", "mf", "autopay", "auto pay", "mandate", "instalment", "installment", "nach",
            "e-mandate", "pause", "skip", "cancel sip", "stop sip", "step up", "xirr", "returns", "nav", "redeem",
            "redemption", "withdraw", "portfolio", "invested", "debit", "bounce", "insufficient", "units", "folio",
            "elss", "lumpsum"]
sha = lambda s, n: hashlib.sha1(s.encode()).hexdigest()[:n]
URL = "https://itunes.apple.com/in/rss/customerreviews/page={p}/id={a}/sortby={s}/json"

def fetch(max_items: int = 2000, keywords: list[str] | None = None, keep_all: bool = False) -> list[dict]:
    pats = [(k, re.compile(r"(?<![a-z0-9])" + re.escape(k) + r"(?![a-z0-9])", re.I)) for k in (keywords or KEYWORDS)]
    out, raw = {}, 0
    for sort in ("mostrecent", "mosthelpful"):
        for page in range(1, 11):
            try:
                req = urllib.request.Request(URL.format(p=page, a=APP_ID, s=sort), headers={"User-Agent": "Mozilla/5.0"})
                entries = json.load(urllib.request.urlopen(req, timeout=30))["feed"].get("entry", [])
            except Exception as e:
                print(f"error {sort} p{page}: {e}", file=sys.stderr); break
            if not entries: break
            for e in entries:
                if "im:rating" not in e: continue  # skip app-metadata entry
                raw += 1
                text = e["content"]["label"].strip()
                if len(text) < 25: continue
                q = next((k for k, p in pats if p.search(e["title"]["label"] + " " + text)), None)
                if not q and not keep_all: continue
                date = e["updated"]["label"][:10]
                rid = "appstore-" + sha(text + date, 12)
                out.setdefault(rid, {"id": rid, "source": "appstore",
                    "url": f"https://apps.apple.com/in/app/id{APP_ID}?see-all=reviews&review_id={e['id']['label']}",
                    "date": date, "title": e["title"]["label"], "text": text, "rating": int(e["im:rating"]["label"]),
                    "score": int(e.get("im:voteSum", {}).get("label", 0)), "author_hash": sha(e["author"]["name"]["label"], 10),
                    "collected_via": "live_api", "query": q or ""})
            time.sleep(0.5)
    fetch.raw_count = raw
    return list(out.values())[:max_items]

if __name__ == "__main__":
    recs = fetch()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in recs))
    print(f"raw={raw if (raw:=fetch.raw_count) else 0} kept={len(recs)} -> {OUT}")
