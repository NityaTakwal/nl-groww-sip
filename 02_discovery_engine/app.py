"""SIP Continuation Discovery Engine — Streamlit dashboard.  Run: streamlit run app.py"""
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
import yaml

from engine import analyze, ask, sources, tag
from engine.codebook import THEME_TO_METRIC_NODE

ROOT = Path(__file__).resolve().parent
# Okabe-Ito: colour-blind-safe categorical palette
PALETTE = ["#0072B2", "#E69F00", "#009E73", "#D55E00", "#56B4E9", "#CC79A7", "#F0E442", "#000000"]

st.set_page_config(page_title="SIP Discovery Engine", page_icon="🔎", layout="wide")


@st.cache_data
def load():
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    records = tag.prefilter(sources.load_local(cfg.get("sources")))
    population = pd.Series([r["source"] for r in records]).value_counts().to_dict()
    if cfg.get("sample_per_source"):  # same stratified sample as `python -m engine.run`
        records = tag.stratified_sample(records, cfg["sample_per_source"], seed=cfg.get("seed", 42))
    df = analyze.build_frame(records, tag.load_cache(), population)
    return sources.load_local(cfg.get("sources")), df


raw, df = load()
rel = analyze.relevant(df)

st.title("SIP Continuation Discovery Engine")
_models = df["tagged_by"].value_counts().to_dict() if "tagged_by" in df else {}
st.caption(f"Why first-time Groww investors start, doubt, pause or drop their SIPs — built from "
           f"{len(raw):,} public conversations. Tagged by: " + " · ".join(f"`{m}` ({n})" for m, n in _models.items()))

if df.empty:
    st.warning("No tagged data yet. Run `python -m engine.run` first.")
    st.stop()

s = analyze.summary(df)
c = st.columns(5)
c[0].metric("Conversations collected", f"{len(raw):,}")
c[1].metric("Tagged by AI", f"{s['records_tagged']:,}")
c[2].metric("Relevant to SIP/MF", f"{s['relevant']:,}")
c[3].metric("First-time investors", f"{s['first_time']:,}")
c[4].metric("Stop / pause / miss signals", f"{s['drop_signals']:,}")

tabs = st.tabs(["Opportunities", "Themes", "Why SIPs break", "Segments", "Journey", "Evidence explorer",
                "Ask the corpus", "Quality (golden set)", "How it works"])

with tabs[0]:
    st.subheader("Ranked opportunity areas")
    st.caption("Shares are population-weighted: each tagged item counts for (records in its source ÷ tagged from its source).")
    st.markdown("**Score** = reach × (0.5 + threat) × (0.5 + first-time share) × addressability, scaled to 100. "
                "Reach = how common; threat = how often it comes with doubting/stopping; addressability = can Groww "
                "act on it without fund picks or fear/FOMO nudges.")
    opp = analyze.opportunities(df)
    st.dataframe(opp, use_container_width=True, hide_index=True)
    with st.expander("Robustness: ranking with every theme treated as fully addressable"):
        st.dataframe(analyze.opportunities(df, {t: 1.0 for t in analyze.ADDRESSABILITY})[["theme", "reach_%", "threat_%", "score"]],
                     hide_index=True)
    st.plotly_chart(px.bar(opp, x="score", y="theme", orientation="h", color="metric_node",
                           color_discrete_sequence=PALETTE).update_layout(yaxis={"categoryorder": "total ascending"}),
                    use_container_width=True)

with tabs[1]:
    tc = analyze.theme_counts(df).reset_index(names="theme")
    st.plotly_chart(px.bar(tc, x="primary_or_secondary", y="theme", orientation="h", color_discrete_sequence=PALETTE,
                           title="Theme frequency (relevant items)").update_layout(yaxis={"categoryorder": "total ascending"}),
                    use_container_width=True)
    by_src = pd.crosstab(rel["primary_theme"], rel["source"], normalize="columns").round(3)
    st.markdown("**Theme share by source** — checks a theme isn't an artefact of one platform")
    st.dataframe(by_src.style.format("{:.0%}").background_gradient(cmap="Blues"), use_container_width=True)

with tabs[2]:
    st.subheader("What leads to pause, reduce, stop or miss")
    sd = analyze.stop_driver_shares(df).reset_index()
    sd.columns = ["stop_driver", "share"]
    st.plotly_chart(px.pie(sd, names="stop_driver", values="share", hole=0.45, color_discrete_sequence=PALETTE,
                           title="Population-weighted share of stop/pause/miss signals"), use_container_width=True)
    drops = rel[rel["drop_signal"]]
    st.markdown(f"{len(drops)} items show a stop/pause/miss/consider-stopping signal. Voluntary vs involuntary split:")
    vol = drops["stop_driver"].map(lambda x: "involuntary" if x == "involuntary_payment_failure" else
                                   ("platform" if x == "platform_issue" else "voluntary"))
    st.dataframe(vol.value_counts().rename("items"))

with tabs[3]:
    seg = st.selectbox("Segment by", ["income_type", "age_band", "influence_source", "is_first_time_investor", "source"])
    st.markdown("Share of each segment's relevant items by primary theme (columns sum to 100%).")
    ct = analyze.crosstab(df, seg)
    st.plotly_chart(px.imshow(ct, text_auto=".0%", color_continuous_scale="Blues", aspect="auto"), use_container_width=True)
    st.caption("Segment fields are only filled when the text states or clearly implies them — 'unknown' rows are excluded.")

with tabs[4]:
    j = rel[rel["journey_stage"] != "unclear"]
    order = ["pre_start", "first_month", "months_1_3", "months_3_6", "months_6_12", "beyond_12"]
    jt = pd.crosstab(j["journey_stage"], j["primary_theme"]).reindex(order).fillna(0)
    st.plotly_chart(px.bar(jt, barmode="stack", color_discrete_sequence=PALETTE, title="Themes across the first year"),
                    use_container_width=True)
    ck = rel[rel["checking_behaviour"] != "not_mentioned"]["checking_behaviour"].value_counts()
    st.markdown("**How often people check (when mentioned)**")
    st.bar_chart(ck)

with tabs[5]:
    f1, f2, f3 = st.columns(3)
    th = f1.multiselect("Theme", sorted(rel["primary_theme"].unique()))
    src = f2.multiselect("Source", sorted(rel["source"].unique()))
    act = f3.multiselect("Action", sorted(rel["action_taken"].unique()))
    view = rel
    if th: view = view[view["primary_theme"].isin(th)]
    if src: view = view[view["source"].isin(src)]
    if act: view = view[view["action_taken"].isin(act)]
    st.caption(f"{len(view)} items")
    for i, r in view.sort_values("severity", ascending=False).head(60).iterrows():
        with st.expander(f"[{r.source}] {r.primary_theme} · {r.action_taken} · {r.journey_stage} — “{r.evidence_quote[:90]}”"):
            st.write(r.text)
            st.caption(f"Unmet need: {r.unmet_need or '—'} · segment: {r.income_type}/{r.age_band}/{r.influence_source} · "
                       f"[source]({r.url}) · id `{i}`")

with tabs[6]:
    st.subheader("Ask the corpus")
    st.caption("Answers only from tagged evidence, with citations. Declines when evidence is thin.")
    q = st.selectbox("Discovery question", list(ask.PRESETS))
    custom = st.text_input("…or ask your own")
    if st.button("Answer", type="primary"):
        with st.spinner("Reading the evidence…"):
            res = ask.answer(df, custom or q)
        if res["refused"]:
            st.warning(res["answer"])
        else:
            st.markdown(res["answer"])
            st.caption(f"Grounding check: {res['cited']} cited ids found in evidence; "
                       f"{len(res['hallucinated_ids'])} unknown ids {res['hallucinated_ids'] or ''}")
        with st.expander(f"Evidence used ({len(res['evidence'])})"):
            st.dataframe(res["evidence"][["source", "primary_theme", "action_taken", "evidence_quote", "url"]])

with tabs[7]:
    rep = ROOT / "golden_set/eval_report.json"
    if rep.exists():
        e = json.loads(rep.read_text())
        st.metric("Overall field agreement with human labels", f"{e['overall_agreement']:.0%}")
        st.dataframe(pd.DataFrame(e["per_field"]).T, use_container_width=True)
        st.markdown("**Disagreements**")
        st.dataframe(pd.DataFrame(e["disagreements"]), use_container_width=True, hide_index=True)
    else:
        st.info("Run `python golden_set/eval_engine.py` to score the engine against the golden set.")

with tabs[8]:
    st.markdown((ROOT / "HOW_IT_WORKS.md").read_text() if (ROOT / "HOW_IT_WORKS.md").exists() else "See README.")
