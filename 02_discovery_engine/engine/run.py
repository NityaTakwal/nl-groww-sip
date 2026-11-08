"""Pipeline CLI.

    python -m engine.run                 # local store -> tag (cached) -> report
    python -m engine.run --source live   # refresh store from live sources first
    python -m engine.run --limit 50      # tag at most 50 new items (smoke test)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import yaml

from engine import analyze, sources, tag

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/processed"


def main() -> None:
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    p = argparse.ArgumentParser()
    p.add_argument("--source", default=cfg["source_mode"], choices=["local", "live"])
    p.add_argument("--limit", type=int, default=None)
    args = p.parse_args()

    records = sources.load(args.source, cfg.get("sources"))
    kept = tag.prefilter(records)
    print(f"[load] {len(records)} records, {len(kept)} after MF pre-filter")
    population = pd.Series([r["source"] for r in kept]).value_counts().to_dict()
    if cfg.get("sample_per_source"):
        kept = tag.stratified_sample(kept, cfg["sample_per_source"], seed=cfg.get("seed", 42))
        print(f"[sample] {len(kept)} records in stratified sample")
    tags = tag.tag_records(kept, batch_size=cfg["tagging"]["batch_size"],
                           concurrency=cfg["tagging"]["concurrency"], limit=args.limit,
                           items_per_call=cfg["tagging"]["items_per_call"])

    df = analyze.build_frame(kept, tags, population)
    s = analyze.summary(df)
    opp = analyze.opportunities(df)
    opp.to_csv(OUT / "opportunities.csv", index=False)
    flat = analyze.opportunities(df, {t: 1.0 for t in analyze.ADDRESSABILITY})
    flat.to_csv(OUT / "opportunities_unweighted_addressability.csv", index=False)
    analyze.stop_driver_shares(df).to_csv(OUT / "stop_drivers.csv")
    (OUT / "population.json").write_text(json.dumps(population, indent=2))
    analyze.theme_counts(df).to_csv(OUT / "themes.csv")
    (OUT / "summary.json").write_text(json.dumps({**s, "pre_filter_in": len(records)}, indent=2, default=str))
    print(json.dumps(s, indent=2, default=str))
    print(opp[["theme", "mentions", "reach_%", "threat_%", "first_time_%", "score"]].to_string())
    print("\n[robustness: addressability=1 for all]\n", flat[["theme", "score"]].head(6).to_string())
    print("\n[stop drivers, weighted]\n", analyze.stop_driver_shares(df).to_string())


if __name__ == "__main__":
    main()
