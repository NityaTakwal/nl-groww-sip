"""Source layer. Two modes, picked in config.yaml (`source_mode`):

- local: read the verbatim records already collected in data/store/*.jsonl (default; reproducible)
- live:  re-pull from each source's fetch() and refresh the store first (needs network; Reddit/YouTube best-effort)
"""
from __future__ import annotations

import importlib
import json
from pathlib import Path

STORE = Path(__file__).resolve().parents[2] / "data/store"

# store file -> (module, kwargs for fetch) used in live mode
LIVE = {
    "playstore": ("playstore", {"max_items": 2500}),
    "appstore": ("appstore", {"max_items": 500}),
    "reddit": ("reddit", {}),
    "tradingqna": ("discourse", {"base_url": "https://tradingqna.com"}),
    "valuepickr": ("discourse", {"base_url": "https://forum.valuepickr.com"}),
}


def load_local(sources: list[str] | None = None) -> list[dict]:
    records, seen = [], set()
    for path in sorted(STORE.glob("*.jsonl")):
        if sources and path.stem not in sources:
            continue
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if r["id"] in seen or not r.get("text") or not r.get("url"):
                continue
            seen.add(r["id"])
            records.append(r)
    return records


def refresh_live(sources: list[str]) -> None:
    for name in sources:
        if name not in LIVE:
            print(f"[live] {name}: no live fetcher, keeping local store")
            continue
        module, kwargs = LIVE[name]
        try:
            fetch = importlib.import_module(f"engine.sources.{module}").fetch
            rows = fetch(**kwargs)
        except Exception as e:  # keep the stored snapshot if a live pull fails
            print(f"[live] {name}: failed ({e}); keeping local store")
            continue
        if rows:
            (STORE / f"{name}.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")
            print(f"[live] {name}: {len(rows)} records")


def load(mode: str = "local", sources: list[str] | None = None) -> list[dict]:
    if mode == "live":
        refresh_live(sources or list(LIVE))
    return load_local(sources)
