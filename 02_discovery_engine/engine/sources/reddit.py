"""Reddit fetcher for SIP-behaviour discovery. Uses Arctic Shift API (live), via curl
(python 3.14 ssl rejects the local CA chain; curl works). Verbatim text only.
Usage: python3 reddit.py  -> writes data/store/reddit.jsonl
"""
import json, subprocess, hashlib, datetime, time, urllib.parse, os, re, sys

BASE = "https://arctic-shift.photon-reddit.com/api"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36"
OUT = os.path.join(os.path.dirname(__file__), "..", "..", "data", "store", "reddit.jsonl")

def _get(path, **params):
    url = f"{BASE}/{path}?" + urllib.parse.urlencode(params)
    for _ in range(3):
        try:
            r = subprocess.run(["curl", "-s", "-m", "40", "-A", UA, url], capture_output=True, text=True)
            return json.loads(r.stdout)["data"]
        except Exception:
            time.sleep(2)
    return []

def _h(u): return hashlib.sha1((u or "").encode()).hexdigest()[:10]
def _d(ts): return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%d")
BAD = {"[deleted]", "[removed]", ""}
REL = re.compile(r"\bsips?\b|mutual fund|\bmf\b|mandate|xirr|nav\b|index fund|groww|autopay|step[- ]?up", re.I)

def fetch(queries, subreddits, max_items=500, after="2023-01-01"):
    out, seen = [], set()
    for sub in subreddits:
        for q in queries:
            if len(out) >= max_items: return out
            posts = _get("posts/search", subreddit=sub, query=q, limit=25, after=after, sort="desc")
            for p in posts or []:
                text = p.get("selftext") or ""
                title = p.get("title") or ""
                if p["id"] in seen or text in BAD or len(text) < 40 or not REL.search(title + " " + text):
                    continue
                seen.add(p["id"])
                perm = "https://www.reddit.com" + p["permalink"]
                out.append(dict(id="reddit-" + p["id"], source="reddit", url=perm, date=_d(p["created_utc"]),
                    title=title, text=text, rating=None, score=p.get("score"), author_hash=_h(p.get("author")),
                    collected_via="live_api", query=q, subreddit=p.get("subreddit", sub), kind="post"))
                if (p.get("num_comments") or 0) >= 3:
                    cs = _get("comments/search", link_id=p["id"], limit=100)
                    cs = [c for c in cs or [] if c.get("body") not in BAD and len(c["body"]) >= 150
                          and c.get("author") != "AutoModerator" and c["id"] not in seen]
                    cs.sort(key=lambda c: -(c.get("score") or 0))
                    for c in cs[:4]:
                        seen.add(c["id"])
                        out.append(dict(id="reddit-" + c["id"], source="reddit",
                            url=perm.rstrip("/") + "/" + c["id"] + "/", date=_d(c["created_utc"]),
                            title=title, text=c["body"], rating=None, score=c.get("score"),
                            author_hash=_h(c.get("author")), collected_via="live_api", query=q,
                            subreddit=p.get("subreddit", sub), kind="comment"))
    return out

QUERIES = ["first SIP","started SIP","stop SIP","stopped SIP","pause SIP","cancel SIP","SIP negative returns",
 "SIP in red","SIP not growing","missed SIP","SIP failed","autopay failed","mandate","Groww SIP",
 "should I stop SIP","SIP 1 year returns","new to mutual funds","beginner SIP","SIP step up",
 "SIP market fall","xirr","emergency withdraw SIP","lost job SIP","salary SIP","SIP continue"]
SUBS = ["mutualfunds","IndiaInvestments","personalfinanceindia","IndianStockMarket","FIREIndia","IndiaGrowthStocks"]

if __name__ == "__main__":
    recs = fetch(QUERIES, SUBS, max_items=1200)
    with open(OUT, "w") as f:
        for r in recs: f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(len(recs))
