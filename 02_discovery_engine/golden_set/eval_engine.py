"""Score the engine's tags against the hand-labelled golden set.

    python golden_set/eval_engine.py            # uses cached tags; tags any golden item not yet tagged

golden_set.csv columns: id, source, text, then one human label column per field in codebook.GOLDEN_FIELDS.
Writes eval_report.json (read by the dashboard) and eval_report.md.
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine import tag  # noqa: E402
from engine.codebook import GOLDEN_FIELDS  # noqa: E402

HERE = Path(__file__).resolve().parent


def norm(v):
    s = str(v).strip().lower()
    return {"true": "true", "false": "false", "1": "true", "0": "false"}.get(s, s)


def main():
    gold = pd.read_csv(HERE / "golden_set.csv", dtype=str).fillna("")
    cache = tag.load_cache()
    missing = gold[~gold["id"].isin(cache)]
    if len(missing):
        recs = [{"id": r.id, "source": r.source, "title": "", "text": r.text} for r in missing.itertuples()]
        cache = tag.tag_records(recs)

    per_field, disagreements, hits, total = {}, [], 0, 0
    for f in GOLDEN_FIELDS:
        agree = n = 0
        for r in gold.itertuples():
            if r.id not in cache:
                continue
            human, ai = norm(getattr(r, f)), norm(cache[r.id][f])
            n += 1
            if human == ai:
                agree += 1
            else:
                disagreements.append({"id": r.id, "field": f, "human": human, "ai": ai, "text": r.text[:160]})
        per_field[f] = {"agree": agree, "n": n, "agreement": round(agree / n, 3) if n else None}
        hits += agree; total += n
    report = {"overall_agreement": round(hits / total, 3), "items": len(gold), "per_field": per_field,
              "disagreements": disagreements}
    (HERE / "eval_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))

    md = [f"# Golden-set evaluation\n\nItems: {len(gold)} · overall field agreement: **{report['overall_agreement']:.0%}**\n",
          "| Field | Agree | N | Agreement |", "|---|---|---|---|"]
    md += [f"| {f} | {v['agree']} | {v['n']} | {v['agreement']:.0%} |" for f, v in per_field.items()]
    md += ["\n## Disagreements\n", "| id | field | human | engine | text |", "|---|---|---|---|---|"]
    md += [f"| {d['id']} | {d['field']} | {d['human']} | {d['ai']} | {d['text'].replace('|', '/')} |" for d in disagreements]
    (HERE / "eval_report.md").write_text("\n".join(md) + "\n")
    print("\n".join(md[:len(per_field) + 4]))


if __name__ == "__main__":
    main()
