"""Generic Discourse fetcher (tradingqna, valuepickr). Uses public search.json + t/<id>.json."""
import hashlib, html, json, re, subprocess, time, urllib.parse
from html.parser import HTMLParser

UA = {"User-Agent": "Mozilla/5.0 (research; discovery-engine)", "Accept": "application/json"}
REL = re.compile(r"\bsips?\b|mutual fund|\bmf\b|mandate|autopay|auto-pay|groww|\bcoin\b|nav\b|xirr", re.I)

class _T(HTMLParser):
    def __init__(s): super().__init__(); s.o = []; s.skip = 0
    def handle_starttag(s, t, a):
        if t in ("blockquote", "aside"): s.skip += 1  # drop quoted text of other posts
        if t in ("br", "p", "li"): s.o.append("\n")
    def handle_endtag(s, t):
        if t in ("blockquote", "aside"): s.skip = max(0, s.skip - 1)
    def handle_data(s, d):
        if not s.skip: s.o.append(d)

def clean(cooked):
    p = _T(); p.feed(cooked)
    return re.sub(r"\n\s*\n+", "\n", html.unescape("".join(p.o))).strip()

def _get(url):
    # curl instead of urllib: system CA bundle works where Python's strict OpenSSL rejects some proxies' CAs
    for i in range(3):
        r = subprocess.run(["curl", "-sS", "-m", "30", "-A", UA["User-Agent"], "-H", "Accept: application/json", url], capture_output=True, text=True)
        try:
            return json.loads(r.stdout)
        except Exception:
            time.sleep(2 * (i + 1))
    return None

def fetch(base_url, queries, max_items=600, pages=3, source=None, min_year=2021, delay=0.7):
    base = base_url.rstrip("/"); source = source or re.sub(r"\W", "", urllib.parse.urlparse(base).netloc.split(".")[-2] if "forum." in base else urllib.parse.urlparse(base).netloc.split(".")[0])
    out, seen, tids = [], set(), {}
    for q in queries:
        for pg in range(1, pages + 1):
            d = _get(f"{base}/search.json?q={urllib.parse.quote(q)}&page={pg}"); time.sleep(delay)
            if not d or not d.get("posts"): break
            for t in d.get("topics", []): tids.setdefault(t["id"], q)
    for tid, q in tids.items():
        if len(out) >= max_items: break
        d = _get(f"{base}/t/{tid}.json"); time.sleep(delay)
        if not d: continue
        title = d.get("title", "")
        for p in d.get("post_stream", {}).get("posts", []):
            text = clean(p.get("cooked", ""))
            date = (p.get("created_at") or "")[:10]
            if len(text) < 30 or (date and int(date[:4]) < min_year) or not REL.search(text + " " + title): continue
            h = hashlib.sha1(text.encode()).hexdigest()
            if h in seen: continue
            seen.add(h)
            out.append({"id": f"{source}-{p['id']}", "source": source, "url": f"{base}/t/{d.get('slug')}/{tid}/{p['post_number']}",
                        "date": date, "title": title, "text": text, "rating": None, "score": p.get("like_count"),
                        "author_hash": hashlib.sha1((p.get("username") or "").encode()).hexdigest()[:10],
                        "collected_via": "live_api", "query": q})
    return out[:max_items]

if __name__ == "__main__":
    import sys
    base, outp, *qs = sys.argv[1:]
    rows = fetch(base, qs)
    with open(outp, "w") as f:
        for r in rows: f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(len(rows))
