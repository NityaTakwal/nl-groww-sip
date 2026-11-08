"""YouTube comments via yt-dlp. Run: uv run --python 3.12 --with yt-dlp python youtube.py out.jsonl VIDEO_ID..."""
import hashlib, json, os, re, subprocess, sys, tempfile
from datetime import datetime, timezone

def fetch(video_ids, max_comments=300, raw_dir=None, query=""):
    raw_dir = raw_dir or tempfile.mkdtemp(prefix="yt_raw_")  # raw dumps kept apart from scripts
    out, seen = [], set()
    for vid in video_ids:
        cmd = [sys.executable, "-m", "yt_dlp", "--skip-download", "--write-comments", "--write-info-json",
               "--extractor-args", f"youtube:max_comments={max_comments},all,100",
               "-o", os.path.join(raw_dir, "%(id)s"), f"https://www.youtube.com/watch?v={vid}"]
        subprocess.run(cmd, capture_output=True, timeout=600)
        p = os.path.join(raw_dir, f"{vid}.info.json")
        if not os.path.exists(p): continue
        info = json.load(open(p))
        for c in info.get("comments") or []:
            text = (c.get("text") or "").strip()
            h = hashlib.sha1(text.encode()).hexdigest()
            if len(text) < 30 or h in seen: continue
            seen.add(h)
            ts = c.get("timestamp")
            out.append({"id": f"youtube-{c.get('id') or h[:12]}", "source": "youtube",
                        "url": f"https://www.youtube.com/watch?v={vid}&lc={c.get('id')}",
                        "date": datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d") if ts else "",
                        "title": info.get("title", ""), "text": text, "rating": None, "score": c.get("like_count"),
                        "author_hash": hashlib.sha1((c.get("author") or "").encode()).hexdigest()[:10],
                        "collected_via": "live_api", "query": query})
    return out

if __name__ == "__main__":
    rows = fetch(sys.argv[2:])
    with open(sys.argv[1], "w") as f:
        for r in rows: f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(len(rows))
