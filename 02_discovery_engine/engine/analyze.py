"""Stage 3: turn tags into countable insight — theme/segment/stage tables and a ranked opportunity table.

Opportunity score (per theme, relevant items only):
    reach     = share of relevant conversations where the theme is primary or secondary
    threat    = share of those items that show the SIP stopped/paused/missed or wavering (severity >= 2)
    first_time= share from self-declared first-time investors (the segment the metric is about)
    addressable = can Groww act on it within the brief's constraints (codebook.ADDRESSABILITY)
    score     = reach * (0.5 + threat) * (0.5 + first_time) * addressable   (scaled to 0-100)
Reach says how common, threat says how close it is to the metric breaking, addressability says whether
we can do anything about it without fund picks or fear/FOMO nudges.
"""
from __future__ import annotations

import pandas as pd

from engine.codebook import ADDRESSABILITY, THEME_TO_METRIC_NODE

DROP_ACTIONS = {"considering_stop", "paused_or_skipped", "reduced", "stopped_or_cancelled", "missed_involuntarily", "redeemed"}


def build_frame(records: list[dict], tags: dict[str, dict], population: dict[str, int] | None = None) -> pd.DataFrame:
    """population = records per source before sampling; each tagged row gets weight pop/tagged for its source,
    so per-source sampling rates don't distort corpus-level shares."""
    raw = pd.DataFrame(records).set_index("id")
    tg = pd.DataFrame(tags.values()).set_index("id")
    df = raw.join(tg, how="inner")
    df["year"] = pd.to_datetime(df["date"], errors="coerce").dt.year
    df["drop_signal"] = df["action_taken"].isin(DROP_ACTIONS)
    tagged = df["source"].value_counts()
    df["w"] = df["source"].map(lambda s: (population or {}).get(s, tagged[s]) / tagged[s])
    return df


def relevant(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["relevant"]]


def theme_counts(df: pd.DataFrame) -> pd.DataFrame:
    rel = relevant(df)
    prim = rel["primary_theme"].value_counts().rename("primary")
    any_ = pd.concat([rel["primary_theme"], rel.loc[rel["secondary_theme"] != rel["primary_theme"], "secondary_theme"]])
    out = pd.concat([prim, any_.value_counts().rename("primary_or_secondary")], axis=1).fillna(0).astype(int)
    return out.drop(index=["other"], errors="ignore").sort_values("primary_or_secondary", ascending=False)


def crosstab(df: pd.DataFrame, col: str, normalize: bool = True) -> pd.DataFrame:
    rel = relevant(df)
    rel = rel[~rel[col].isin(["unknown", "unclear", "not_mentioned", "none_mentioned", "not_applicable"])]
    return pd.crosstab(rel["primary_theme"], rel[col], normalize="columns" if normalize else False).round(3)


def stop_drivers(df: pd.DataFrame) -> pd.Series:
    rel = relevant(df)
    return rel.loc[rel["drop_signal"], "stop_driver"].value_counts()


def opportunities(df: pd.DataFrame, addressability: dict[str, float] | None = None) -> pd.DataFrame:
    """Population-weighted. Pass addressability={t: 1.0 ...} to check the ranking without the hand-set weights."""
    addressability = addressability or ADDRESSABILITY
    rel = relevant(df)
    total_w = rel["w"].sum()
    rows = []
    for theme, addr in addressability.items():
        if theme in ("other", "positive_continuation"):
            continue
        sub = rel[(rel["primary_theme"] == theme) | (rel["secondary_theme"] == theme)]
        if sub.empty:
            continue
        w = sub["w"]
        reach = w.sum() / total_w
        threat = (w * (sub["severity"] >= 2)).sum() / w.sum()
        first = (w * sub["is_first_time_investor"]).sum() / w.sum()
        rows.append({
            "theme": theme,
            "metric_node": THEME_TO_METRIC_NODE[theme],
            "mentions": len(sub),
            "reach_%": round(100 * reach, 1),
            "threat_%": round(100 * threat, 1),
            "first_time_%": round(100 * first, 1),
            "drop_signal_%": round(100 * (w * sub["drop_signal"]).sum() / w.sum(), 1),
            "addressable": addr,
            "score": reach * (0.5 + threat) * (0.5 + first) * addr,
            "top_unmet_need": sub["unmet_need"].replace("", pd.NA).dropna().value_counts().index[:1].tolist(),
        })
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["score"] = (100 * out["score"] / out["score"].max()).round(1)
    return out.sort_values("score", ascending=False).reset_index(drop=True)


def stop_driver_shares(df: pd.DataFrame) -> pd.Series:
    """Population-weighted share of stop/pause/miss signals by root driver."""
    d = relevant(df)
    d = d[d["drop_signal"]]
    return (d.groupby("stop_driver")["w"].sum() / d["w"].sum()).sort_values(ascending=False).round(3)


def summary(df: pd.DataFrame) -> dict:
    rel = relevant(df)
    return {
        "records_tagged": len(df),
        "relevant": len(rel),
        "first_time": int(rel["is_first_time_investor"].sum()),
        "drop_signals": int(rel["drop_signal"].sum()),
        "by_source": df["source"].value_counts().to_dict(),
        "relevant_by_source": rel["source"].value_counts().to_dict(),
    }
