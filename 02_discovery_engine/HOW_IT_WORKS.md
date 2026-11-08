### How the engine works

**1 · Gather** (`engine/sources/`): verbatim public conversations, each with a source URL.
- Play Store and App Store reviews of Groww
- Reddit (r/mutualfunds, r/IndiaInvestments, r/IndianStockMarket, r/FIREIndia, …)
- TradingQ&A and ValuePickr forums
- YouTube comments on SIP videos
- Quora / X

`source_mode: local` reads the snapshot in `data/store/`. `source_mode: live` re-pulls from the sources first.

**2 · Filter**: a keyword gate drops app reviews that are about trading rather than MFs. The LLM then flags anything else that is irrelevant.

**3 · Code** (`engine/tag.py`, `engine/codebook.py`): an LLM tags every item against a fixed codebook derived from the brief's questions:
- journey stage, primary and secondary theme
- action taken and stop driver
- checking behaviour and outside-app help
- segment signals: income type, age, influencer
- severity, unmet need, verbatim evidence quote

Fixed categories make the output **countable and comparable**, unlike free-form summaries.

**4 · Quantify** (`engine/analyze.py`): theme frequency, theme × segment, theme × journey stage, and the voluntary vs involuntary split of stop signals. Each theme is mapped to a node of the metric tree.

**5 · Rank opportunities**: `score = reach × (0.5 + threat) × (0.5 + first-time share) × addressability`.
- Reach: how common the theme is.
- Threat: how often it comes with wavering or stopping.
- First-time share: how often it comes from self-declared first-time investors.
- Addressability: can Groww act within the constraints (no fund picks, no fear or FOMO)?

**6 · Ask** (`engine/ask.py`): answers the brief's discovery questions from tagged evidence only, with item-id citations. A grounding check flags any cited id that is not in the evidence, and the engine declines when there are fewer than 5 supporting items.

**7 · Validate** (`golden_set/`): 20 items are labelled by hand, before seeing engine output, and the engine's tags are scored field by field (agreement %). Disagreements are listed and reviewed. Spot-checks of source URLs confirm the data is real.

**Model-agnostic**: LangChain `init_chat_model`. Set `LLM_PROVIDER` to anthropic, openai, google_genai or ollama with no code change.
