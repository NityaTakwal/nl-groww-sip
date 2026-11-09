# Lean-Month Planner: AI-native MVP

A feature concept for Groww's SIP screen. A first-time investor with irregular income gets **one calm, honest planning moment** when a lean month threatens their SIP, instead of a silent failure, a bank bounce charge and a hidden 3-strike auto-cancel.

## Try it
```bash
cd 06_mvp
../.venv/bin/uvicorn app.main:app --port 8000      # FastAPI version
../.venv/bin/streamlit run streamlit_app.py        # same UI on Streamlit (used for hosting)
```
Live app (no install): **https://nl-groww-mvp.streamlit.app**. Choose a situation on the left, tap **Plan this month**, and describe your month in your own words. Running locally, the FastAPI version is at http://localhost:8000.

## Where it sits in the journey
It has three entry points: the at-risk moments from the research.
1. **Two days before the debit** (card on the SIP screen, at most 1 a month): "₹2,000 goes out on the 5th…"
2. **Right after a failed instalment**, so the user hears it from Groww before the bank SMS. The card states the missed count.
3. **When the user taps Skip or Cancel** (next iteration): the same planner, showing what each option does to the SIP.

## How it works
| Step | Done by | Why |
|---|---|---|
| 1. Understand the message (situation, when money arrives, temporary or not, language) | **LLM**, structured output | People describe their month in messy Hinglish, mixing reasons ("client ne payment nahi kiya, portfolio bhi red") |
| 2. Decide the options and their exact consequences (move date, pay pending, lower, keep + reminder, skip once with its count, stop) | **Rules** (`rules.py`) | Facts must be right every time. The AI never invents a rule, date or charge |
| 3. Write a short, calm reply and rank the options | **LLM**, structured output | Tone and order matter for someone anxious, and the reply matches the user's language |
| 4. Quality gate: no fund or stock names, no fear/FOMO/urgency, no return promises, not framed as advice, confidence ≥ 0.6 | **Code** (`guardrails.py`) | A visible check is shown to the user. If any check fails, a **neutral fallback** shows all options plus official sources |
| Advice or market-prediction requests | **Declined**, with links to AMFI/SEBI investor education | Not investment advice, by design |

## Where AI earns its place, and what a non-AI version misses
- **A non-AI version** is a cancel-reason dropdown plus a generic "your SIP is due" push.
- **R4 could not pick a reason from such a dropdown.** Choosing "losing money" felt "like admitting I was dumb".
- **Generic pushes get muted:** R1 and R5 turned notifications off.
- **The AI reads the reason in the user's words.** It separates *timing* ("salary on the 9th"), a real *shortfall*, *returns doubt* and *rules confusion*, often mixed in one sentence.
- **It extracts when money arrives,** which turns into a concrete date-move option. 100% exact match on the golden set.
- **It replies in the user's language,** which matters for R5 ("Hindi mein bata do").
- **It refuses advice and keeps facts exact,** because the rules engine owns every fact.

## Quality: measured against the golden set (Evidence Log)
- **Eval:** `eval/eval_mvp.py` runs 20 labelled utterances (8 real corpus quotes, 12 written, including adversarial and prompt-injection items) plus 16 guardrail unit cases.
- **Report:** final results are in `eval/eval_mvp_report_final_run1.json` and `_run2.json`, summarised in the Evidence Log.
- **Model:** set by environment variable (`LLM_PROVIDER_SMART`, `LLM_MODEL_SMART`) through LangChain, so you can switch between OpenAI, Gemini, Anthropic and Ollama without code changes.

## Disclaimer
Shown on every screen: *Not investment advice. This helps you plan your SIP instalment; it does not tell you what to invest in.* Amounts are illustrative, and no real account or mandate is touched.
