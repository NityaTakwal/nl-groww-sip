"""SIP Discovery Engine: product view.  Run: streamlit run app.py

Answer first, evidence second, method last. Every label is plain product language;
internal codebook names are mapped below and never shown to the reader.
"""
import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yaml

from engine import analyze, ask, sources, tag

ROOT = Path(__file__).resolve().parent
BLUE, ORANGE, GRAY, LIGHT = "#0072B2", "#D55E00", "#6E7781", "#C9D0CC"   # Okabe-Ito accents, colour-blind safe

# ---- plain-language names (internal codebook value -> what a PM would say) ----
THEME = {
    "payment_mandate_failure": "Autopay / payment failed",
    "app_trust_or_bug": "App problems (withdrawals, bugs)",
    "sip_management_friction": "Hard to pause, skip or change SIP",
    "advice_seeking": "Asking others what to do",
    "return_expectation_gap": "Returns lower than expected",
    "returns_understanding": "Confused by returns / XIRR",
    "market_volatility_anxiety": "Worried about market falls",
    "cashflow_income_stress": "Money is tight this month",
    "goal_clarity": "No clear goal",
    "start_motivation": "Why they started",
    "disengagement_habit": "Lost interest / forgot",
    "positive_continuation": "Happily continuing",
    "other": "Other",
}
DRIVER = {
    "platform_issue": "App or platform problem",
    "involuntary_payment_failure": "Payment failed (didn't choose to stop)",
    "voluntary_market_or_returns": "Markets or returns",
    "voluntary_confusion_or_doubt": "Confusion or doubt",
    "voluntary_cashflow": "Money tight (said so)",
    "life_event": "Life event",
    "not_applicable": "Unclear",
}
STAGE = [("pre_start", "Before starting"), ("first_month", "Month 1"), ("months_1_3", "Months 1–3"),
         ("months_3_6", "Months 3–6"), ("months_6_12", "Months 6–12"), ("beyond_12", "After a year")]
SOURCE = {"playstore": "Play Store", "appstore": "App Store", "reddit": "Reddit", "tradingqna": "TradingQ&A",
          "valuepickr": "ValuePickr", "youtube": "YouTube", "quora": "Quora", "x": "X"}
VERDICT = {   # the product call on each opportunity, and why
    "payment_mandate_failure": ("Our focus", BLUE, "Breaks the metric directly: a failed debit isn't a 'successful instalment'."),
    "app_trust_or_bug": ("Engineering fix", GRAY, "Mostly stuck withdrawals and bugs, after people decided to leave."),
    "sip_management_friction": ("Part of our fix", BLUE, "Skip, date and amount changes are the 'soft exits' we build on."),
    "advice_seeking": ("Out of bounds", GRAY, "Mostly 'which fund should I buy?', which we can't answer."),
    "return_expectation_gap": ("Next to explore", ORANGE, "Real, but smaller and closer to market framing."),
    "returns_understanding": ("Education", GRAY, "Clearer return explanations; covered by the MVP's numbers line."),
    "goal_clarity": ("Later", GRAY, "An onboarding problem, not a lapse problem."),
    "start_motivation": ("Context", GRAY, "Explains why people start, not why they stop."),
    "market_volatility_anxiety": ("Small", GRAY, "Less common than expected."),
    "cashflow_income_stress": ("Small (stated)", GRAY, "Rarely said out loud; research suggests it hides behind failures."),
    "disengagement_habit": ("Small", GRAY, ""),
}

st.set_page_config(page_title="SIP Discovery Engine", page_icon="🔎", layout="wide")
st.markdown("""
<style>
.block-container { padding-top: 2rem; max-width: 1180px; }
h1 { font-size: 2.3rem !important; letter-spacing: -0.02em; }
.kpi { background: rgba(0,114,178,.07); border-radius: 16px; padding: 18px 20px; height: 100%; }
.kpi b { display: block; font-size: 2.2rem; line-height: 1.1; color: #0072B2; }
.kpi.hot { background: rgba(213,94,0,.08); } .kpi.hot b { color: #D55E00; }
.kpi span { opacity: .8; font-size: 0.95rem; }
.card { border: 1px solid rgba(120,130,125,.3); border-radius: 16px; padding: 18px 20px; height: 100%; }
.card .n { font-size: 2.6rem; font-weight: 800; line-height: 1; }
.card .t { font-weight: 600; margin: 6px 0 8px; }
.card q { opacity: .75; font-style: italic; font-size: 0.93rem; }
.pill { display: inline-block; font-size: 0.78rem; font-weight: 700; padding: 2px 10px; border-radius: 999px; color: #fff; }
.why { opacity: .75; font-size: .92rem; }
.quote { border-left: 4px solid #D55E00; padding: 4px 0 4px 14px; margin: 10px 0; }
.quote small { opacity: .7; }
.step { background: rgba(120,130,125,.10); border-radius: 14px; padding: 14px; text-align: center; height: 100%; }
.step b { display: block; font-size: 1.6rem; color: #0072B2; }
.step small { opacity: .75; }
</style>""", unsafe_allow_html=True)


@st.cache_data
def load():
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    raw = sources.load_local(cfg.get("sources"))
    records = tag.prefilter(raw)
    n_filtered = len(records)
    population = pd.Series([r["source"] for r in records]).value_counts().to_dict()
    if cfg.get("sample_per_source"):  # same stratified sample as `python -m engine.run`
        records = tag.stratified_sample(records, cfg["sample_per_source"], seed=cfg.get("seed", 42))
    return raw, n_filtered, analyze.build_frame(records, tag.load_cache(), population)


raw, n_filtered, df = load()
if df.empty:
    st.warning("No tagged data yet. Run `python -m engine.run` first.")
    st.stop()
df["evidence_quote"] = df["evidence_quote"].fillna("").str.strip(" \"'“”")  # quotes are added on display
rel = analyze.relevant(df)
stops = rel[rel["drop_signal"]]
drivers = analyze.stop_driver_shares(df)
mechanical = drivers.get("platform_issue", 0) + drivers.get("involuntary_payment_failure", 0)
NOCHART = {"displayModeBar": False}


def wshare(d: pd.DataFrame, col: str) -> pd.Series:
    """Share of rows by `col`, weighted back to each source's real size."""
    return (d.groupby(col)["w"].sum() / d["w"].sum()).sort_values(ascending=False)


def quotes_for(d: pd.DataFrame, n: int = 1) -> list:
    """Most telling real quotes: most serious first, readable length."""
    q = d[d["evidence_quote"].str.len().between(35, 170)].sort_values("severity", ascending=False)
    return [r for _, r in q.head(n).iterrows()]


def hbar(labels, values, colors, fmt="{:.0%}", height=None):
    fig = go.Figure(go.Bar(x=list(values), y=list(labels), orientation="h", marker_color=colors,
                           text=[fmt.format(v) for v in values], textposition="outside", cliponaxis=False,
                           hovertemplate="%{y}: %{text}<extra></extra>"))
    fig.update_layout(height=height or 60 + 46 * len(labels), margin=dict(l=10, r=70, t=10, b=10),
                      xaxis=dict(visible=False), yaxis=dict(autorange="reversed", tickfont=dict(size=14)),
                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", showlegend=False, bargap=0.35)
    return fig


def html(col, s):
    col.markdown(s, unsafe_allow_html=True)


# ---------------- header ----------------
st.title("What's breaking first-time SIPs?")
st.markdown("We used AI to read thousands of real investor reviews and posts, to find **why SIPs stop** "
            "and **where Groww can help**. Start with the answer below.")
k = st.columns(4)
html(k[0], f"<div class='kpi'><b>{len(raw):,}</b><span>real reviews & posts collected</span></div>")
html(k[1], f"<div class='kpi'><b>{len(rel):,}</b><span>are about someone's own SIP</span></div>")
html(k[2], f"<div class='kpi'><b>{len(stops):,}</b><span>describe stopping, pausing or missing</span></div>")
html(k[3], f"<div class='kpi hot'><b>{mechanical:.0%}</b><span>of those stops are mechanical: blamed on a failed payment or the app, not the market</span></div>")
st.write("")

tabs = st.tabs(["① The answer", "② Why SIPs stop", "③ Who & when", "④ Read the voices", "⑤ Ask a question",
                "⑥ Can we trust it?", "⑦ How it works"])

# ---------------- ① the answer ----------------
with tabs[0]:
    st.subheader("Most SIPs don't get quit. They lapse.")
    cards = [("involuntary_payment_failure", BLUE, "Payment failed", "Autopay or mandate failed. The person didn't choose to stop."),
             ("platform_issue", ORANGE, "App or platform problem", "Stuck withdrawals, bugs, order glitches."),
             ("voluntary_market_or_returns", GRAY, "Markets or returns", "The story everyone expects. It's the smaller one.")]
    for col, (key, color, title, sub) in zip(st.columns(3), cards):
        q = quotes_for(stops[stops["stop_driver"] == key])
        quote = f"<q>“{q[0].evidence_quote}”</q>" if q else ""
        html(col, f"<div class='card'><div class='n' style='color:{color}'>{drivers.get(key, 0):.0%}</div>"
                  f"<div class='t'>{title}</div><div style='font-size:.93rem'>{sub}</div><br>{quote}</div>")
    st.caption("Share of all stop, pause or miss stories, adjusted so each source counts at its real size.")

    st.subheader("Where should Groww act?")
    opp = analyze.opportunities(df).head(6)
    left, right = st.columns([1.15, 1])
    left.plotly_chart(hbar([THEME.get(t, t) for t in opp["theme"]], opp["score"],
                           [VERDICT.get(t, ("", LIGHT))[1] for t in opp["theme"]], fmt="{:.0f}"),
                      width="stretch", config=NOCHART)
    with right:
        for t in opp["theme"]:
            label, color, why = VERDICT.get(t, ("", LIGHT, ""))
            st.markdown(f"<span class='pill' style='background:{color}'>{label}</span> **{THEME.get(t, t)}**  \n"
                        f"<span class='why'>{why}</span>", unsafe_allow_html=True)
    st.caption("Score out of 100: how common the problem is × how often it's serious (wavering or stopping) × "
               "how many first-timers feel it × whether Groww can fix it without giving fund advice.")

# ---------------- ② why SIPs stop ----------------
with tabs[1]:
    st.subheader(f"Why {len(stops)} people stopped, paused or missed")
    d = drivers[drivers.index != "not_applicable"]
    colors = [BLUE if k == "involuntary_payment_failure" else ORANGE if k == "platform_issue" else GRAY for k in d.index]
    st.plotly_chart(hbar([DRIVER.get(k, k) for k in d.index], d.values, colors), width="stretch", config=NOCHART)
    chose = sum(drivers.get(k, 0) for k in ["voluntary_market_or_returns", "voluntary_confusion_or_doubt",
                                            "voluntary_cashflow", "life_event"])
    a, b = st.columns(2)
    html(a, f"<div class='kpi hot'><b>{mechanical:.0%}</b><span>mechanical: a failed payment or the app</span></div>")
    html(b, f"<div class='kpi'><b>{chose:.0%}</b><span>a personal choice: markets, doubt, money, life</span></div>")
    st.subheader("In their words")
    for key in ["involuntary_payment_failure", "platform_issue", "voluntary_market_or_returns"]:
        for r in quotes_for(stops[stops["stop_driver"] == key]):
            st.markdown(f"<div class='quote'>“{r.evidence_quote}”<br><small>{DRIVER[key]} · "
                        f"{SOURCE.get(r.source, r.source)} · <a href='{r.url}' target='_blank'>source</a></small></div>",
                        unsafe_allow_html=True)

# ---------------- ③ who & when ----------------
with tabs[2]:
    st.subheader("What's on the mind of first-timers vs everyone else")
    for col, flag, title in zip(st.columns(2), [True, False], ["Say they're first-time investors", "Everyone else"]):
        sub = rel[rel["is_first_time_investor"] == flag]
        sh = wshare(sub[sub["primary_theme"] != "other"], "primary_theme").head(4)
        col.markdown(f"**{title}** · {len(sub)} posts")
        col.plotly_chart(hbar([THEME.get(t, t) for t in sh.index], sh.values, [BLUE if flag else GRAY] * len(sh), height=230),
                         width="stretch", config=NOCHART, key=f"seg{flag}")
    st.caption("First-timers mostly ask what to do and why to start. Everyone else (experienced, or didn't say) "
               "talks more about problems with the app and payments.")

    st.subheader("Biggest worry at each point in the journey")
    timed = rel[rel["journey_stage"] != "unclear"]
    for col, (key, name) in zip(st.columns(len(STAGE)), STAGE):
        sub = timed[timed["journey_stage"] == key]
        top = wshare(sub, "primary_theme").index[0] if len(sub) else None
        note = "few posts" if len(sub) < 15 else "&nbsp;"
        html(col, f"<div class='step'><small>{name}</small><b>{len(sub)}</b>"
                  f"<span style='font-size:.9rem'>{THEME.get(top, '—')}</span><br><small>{note}</small></div>")
    st.caption(f"Only {timed['w'].sum() / rel['w'].sum():.0%} of posts (adjusted for source size) say how long the person has invested, "
               "so treat the middle months as directional.")

    a, b = st.columns(2)
    chk = wshare(rel[rel["checking_behaviour"] != "not_mentioned"], "checking_behaviour")
    a.markdown("**How often they check their SIP** (when mentioned)")
    a.plotly_chart(hbar([c.capitalize() for c in chk.index], chk.values, [BLUE] * len(chk), height=220),
                   width="stretch", config=NOCHART)
    helpd = wshare(rel[rel["outside_app_help"] != "none_mentioned"], "outside_app_help")
    names = {"reddit_forums": "Reddit & forums", "youtube_finfluencer": "YouTube creators",
             "friends_family": "Friends & family", "advisor_or_ca": "Advisor / CA"}
    b.markdown("**Where they go when unsure** (when mentioned)")
    b.plotly_chart(hbar([names.get(c, c) for c in helpd.index], helpd.values, [GRAY] * len(helpd), height=220),
                   width="stretch", config=NOCHART)

# ---------------- ④ read the voices ----------------
with tabs[3]:
    st.subheader("Read what people actually wrote")
    f1, f2 = st.columns(2)
    pick = f1.selectbox("Problem", ["All"] + [THEME[t] for t in THEME if t in set(rel["primary_theme"])])
    srcs = f2.multiselect("Where it was posted", sorted(SOURCE[s] for s in rel["source"].unique() if s in SOURCE))
    view = rel
    if pick != "All":
        view = view[view["primary_theme"] == {v: k for k, v in THEME.items()}[pick]]
    if srcs:
        view = view[view["source"].map(SOURCE).isin(srcs)]
    st.caption(f"{len(view)} posts · most serious first")
    for _, r in view.sort_values("severity", ascending=False).head(25).iterrows():
        with st.expander(f"“{(r.evidence_quote or r.text)[:110]}”"):
            st.write(r.text)
            st.caption(f"{THEME.get(r.primary_theme, r.primary_theme)} · {SOURCE.get(r.source, r.source)} · "
                       f"what they needed: {r.unmet_need or '—'} · [open source]({r.url})")

# ---------------- ⑤ ask ----------------
with tabs[4]:
    st.subheader("Ask the evidence a question")
    st.caption("Answers use only the collected posts and cite them. If there isn't enough evidence, it says so.")
    q = st.selectbox("Pick a research question", list(ask.PRESETS))
    custom = st.text_input("…or type your own")
    if st.button("Get answer", type="primary"):
        with st.spinner("Reading the posts…"):
            res = ask.answer(df, custom or q)
        if res["refused"]:
            st.warning(res["answer"])
        else:
            st.markdown(res["answer"])
            st.caption(f"Based on {len(res['evidence'])} posts · {res['cited']} cited"
                       + (f" · {len(res['hallucinated_ids'])} citation(s) not found, marked ⚠" if res["hallucinated_ids"] else ""))
    with st.expander("Saved answers to all 9 research questions"):
        p = ROOT / "DISCOVERY_ANSWERS.md"
        st.markdown(p.read_text() if p.exists() else "Run `python -m engine.answer_all`.")

# ---------------- ⑥ trust ----------------
with tabs[5]:
    st.subheader("How accurate is the AI's reading?")
    st.markdown("We checked the AI against a **golden set**: 20 posts labelled separately, without seeing the AI's answers. "
                "This is how often the two agreed.")
    rep = ROOT / "golden_set/eval_report.json"
    if rep.exists():
        e = json.loads(rep.read_text())
        plain = {"relevant": "Is the post about a SIP?", "journey_stage": "How far into their SIP",
                 "primary_theme": "Main problem", "action_taken": "What they did (stopped, paused…)",
                 "stop_driver": "Why they stopped", "income_type": "How they earn"}
        pf = {plain.get(k, k): v["agreement"] for k, v in e["per_field"].items()}
        a, b = st.columns([1, 1.6])
        html(a, f"<div class='kpi'><b>{e['overall_agreement']:.0%}</b><span>overall agreement</span></div>")
        b.plotly_chart(hbar(list(pf), list(pf.values()), [BLUE if v >= .75 else ORANGE for v in pf.values()], height=300),
                       width="stretch", config=NOCHART)
        st.caption("Weakest: 'what they did'. The AI sometimes assumes someone continued or stopped when they didn't say, "
                   "so stop counts are always read alongside how serious the post is.")
        with st.expander("See every disagreement"):
            st.dataframe(pd.DataFrame(e["disagreements"]).rename(columns={"human": "golden label", "ai": "engine said"}),
                         width="stretch", hide_index=True)
        st.caption("Shown: the model that read most posts (gemini-3.1-flash-lite). The second model used "
                   "(gemini-3.5-flash-lite) scored 82% on the same set.")

# ---------------- ⑦ how it works ----------------
with tabs[6]:
    st.subheader("How the engine works, in five steps")
    steps = [(f"{len(raw):,}", "1 · Collect", "Real reviews & posts from 8 places"),
             (f"{n_filtered:,}", "2 · Filter", "Keep only mutual-fund talk"),
             (f"{len(df):,}", "3 · Sample", "Fair random sample, re-weighted"),
             (f"{len(rel):,}", "4 · Read", "AI fills a 16-question form per post"),
             (f"{len(stops):,}", "5 · Rank", "Count, compare, score opportunities")]
    for col, (n, name, sub) in zip(st.columns(5), steps):
        html(col, f"<div class='step'><small>{name}</small><b>{n}</b><span style='font-size:.9rem'>{sub}</span></div>")
    st.write("")
    src = pd.Series([SOURCE.get(r["source"], r["source"]) for r in raw]).value_counts()
    st.markdown("**Where the posts came from**")
    st.plotly_chart(hbar(list(src.index), list(src.values), [GRAY] * len(src), fmt="{:,.0f}"),
                    width="stretch", config=NOCHART)
    st.caption("Plain-English guide to everything on this page: 09_deliverables/discovery_engine_guide.html")
