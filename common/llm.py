"""Provider-agnostic chat model factory shared by the discovery engine and the MVP.

Switch providers with env vars (or .env at project root), no code change:
  LLM_PROVIDER = auto | anthropic | openai | google_genai | ollama
  LLM_MODEL_FAST / LLM_MODEL_SMART = optional model overrides
  LLM_RPM      = optional client-side requests/minute cap (free tiers)
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.rate_limiters import InMemoryRateLimiter

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):  # AI Studio's name for the same key
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

# "fast" tier for bulk tagging, "smart" tier for user-facing answers.
DEFAULT_MODELS = {
    "fast": {"anthropic": "claude-haiku-5-5", "openai": "gpt-5.4-nano",
             "google_genai": "gemini-3.5-flash-lite", "ollama": "qwen2.5:3b"},
    "smart": {"anthropic": "claude-sonnet-5-5", "openai": "gpt-5.4-nano",
              "google_genai": "gemini-3.5-flash", "ollama": "qwen2.5:3b"},
}
KEY_ENV = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY", "google_genai": "GOOGLE_API_KEY"}


def resolve_provider(provider: str | None = None, tier: str | None = None) -> str:
    # LLM_PROVIDER_FAST / LLM_PROVIDER_SMART let each tier use a different provider (e.g. quota limits)
    provider = provider or (tier and os.getenv(f"LLM_PROVIDER_{tier.upper()}")) or os.getenv("LLM_PROVIDER", "auto")
    if provider != "auto":
        return provider
    for name, env in KEY_ENV.items():
        if os.getenv(env):
            return name
    return "ollama"


def model_name(tier: str = "fast", provider: str | None = None) -> str:
    provider = resolve_provider(provider, tier)
    return os.getenv(f"LLM_MODEL_{tier.upper()}") or os.getenv("LLM_MODEL") or DEFAULT_MODELS[tier][provider]


@lru_cache(maxsize=8)
def get_model(tier: str = "fast", provider: str | None = None, temperature: float = 0.0):
    provider = resolve_provider(provider, tier)
    # client-side cap only for free-tier Google (e.g. 14 for a 15 RPM limit)
    rpm = float(os.getenv("LLM_RPM", "0")) if provider == "google_genai" else 0
    limiter = InMemoryRateLimiter(requests_per_second=rpm / 60, check_every_n_seconds=0.2) if rpm else None
    return init_chat_model(model_name(tier, provider), model_provider=provider,
                           temperature=temperature, max_retries=6, rate_limiter=limiter)


def describe(tier: str = "fast") -> str:
    return f"{resolve_provider(tier=tier)}:{model_name(tier)}"
