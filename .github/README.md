# Groww · 12-month SIP continuation

**Goal:** increase the share of first-time mutual fund investors who still have an active SIP 12 months after their first one.

For first-time investors with irregular cash flow, SIPs mostly *lapse* rather than get quit. A fixed-date instalment hits a lean week, the debit fails quietly, and Skip silently counts toward a 3-strike auto-cancel. The **Lean-Month Planner** gives them one calm, honest planning moment instead.

## Submission
| Deliverable | File |
|---|---|
| Deck | [`submission/NL_Groww.pdf`](../submission/NL_Groww.pdf) |
| Evidence Log | [`submission/NL_Groww_Evidence_Log.pdf`](../submission/NL_Groww_Evidence_Log.pdf) |
| Discovery engine: how it works | [`submission/NL_Groww_Discovery_Engine_How_It_Works.pdf`](../submission/NL_Groww_Discovery_Engine_How_It_Works.pdf) |
| Discovery engine: cited answers to the brief's questions | [`submission/NL_Groww_Discovery_Answers.pdf`](../submission/NL_Groww_Discovery_Answers.pdf) |
| MVP: Lean-Month Planner | [`submission/NL_Groww_MVP_Lean_Month_Planner.pdf`](../submission/NL_Groww_MVP_Lean_Month_Planner.pdf) |

## Apps
| App | Live | Code | Run locally |
|---|---|---|---|
| Discovery engine (Streamlit dashboard) | [nl-groww-sip-discovery-engine.streamlit.app](https://nl-groww-sip-discovery-engine.streamlit.app) | [`02_discovery_engine/`](../02_discovery_engine) | `cd 02_discovery_engine && streamlit run app.py` |
| Lean-Month Planner MVP | [nl-groww-mvp.streamlit.app](https://nl-groww-mvp.streamlit.app) | [`06_mvp/`](../06_mvp) | `cd 06_mvp && streamlit run streamlit_app.py` |

Each app has its own `requirements.txt`. Both read the model provider and API key from environment variables (or Streamlit secrets):

```toml
OPENAI_API_KEY = "..."
GEMINI_API_KEY = "..."
LLM_PROVIDER = "google_genai"
LLM_PROVIDER_SMART = "openai"
LLM_RPM = "14"
```

Nothing here is investment advice.
