"""
llm_provider.py — Phase 7: swap the LLM provider by configuration.

Both Ollama and Gemini expose OpenAI-COMPATIBLE endpoints, so the provider is a
config value, not a code path -- the same idea that made the databases
swappable in Phase 1. Only base_url / api_key / model differ.

    LLM_PROVIDER=gemini   -> deployment (default)
    LLM_PROVIDER=ollama   -> local development

The SYSTEM_PROMPT and clean_sql are IMPORTED READ-ONLY from the frozen agent.py
so deployment and the Phase 6 experiment cannot drift apart. Copying the prompt
here would silently invalidate the recorded baseline.

Secrets: the Gemini key comes only from the environment (GEMINI_API_KEY), which
python-dotenv loads from .env. It is never hardcoded, never logged, never
committed (.env is gitignored).
"""

from __future__ import annotations

import os
import time
import urllib.request
import json

from dotenv import load_dotenv
from openai import OpenAI

from agent import SYSTEM_PROMPT, clean_sql      # read-only import of frozen code

load_dotenv()

# Verified against https://ai.google.dev/gemini-api/docs/models (2026-09-25):
# the current Flash-tier text model. Override with GEMINI_MODEL, or call
# list_models() to confirm against the live endpoint.
DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

PROVIDERS = {
    "gemini": dict(
        base_url=os.getenv("GEMINI_BASE_URL", GEMINI_BASE_URL),
        api_key_env="GEMINI_API_KEY",
        model_env="GEMINI_MODEL",
        default_model=DEFAULT_GEMINI_MODEL,
    ),
    "ollama": dict(
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        api_key_env=None,                        # Ollama ignores the key
        model_env="OLLAMA_MODEL",
        default_model="qwen2.5-coder:7b",
    ),
}

RETRY_WAITS = (2, 8, 20)      # 429 / transient backoff (Gemini free tier is rate limited)

# Falling back to the other provider answers with a DIFFERENT MODEL, so it is
# reported explicitly (never silently) and can be turned off with LLM_FALLBACK=false.
def fallback_enabled() -> bool:
    return (os.getenv("LLM_FALLBACK", "true").strip().lower() != "false")


class ProviderError(RuntimeError):
    """The provider could not be used (missing key, unknown name, all retries failed)."""


def default_provider() -> str:
    return (os.getenv("LLM_PROVIDER") or "gemini").strip().lower()


def _mask(secret: str | None) -> str:
    """For logs only. Never print a raw key."""
    if not secret:
        return "<unset>"
    return f"{secret[:4]}...{secret[-2:]} (len {len(secret)})"


def provider_status() -> dict:
    """Safe-to-log view of the configuration. Contains no secret values."""
    out = {"default": default_provider()}
    for name, cfg in PROVIDERS.items():
        key = os.getenv(cfg["api_key_env"]) if cfg["api_key_env"] else "n/a"
        out[name] = {
            "base_url": cfg["base_url"],
            "model": os.getenv(cfg["model_env"] or "", "") or cfg["default_model"],
            "key_present": bool(key),
            "key_masked": _mask(key) if cfg["api_key_env"] else "n/a",
        }
    return out


def build_client(provider: str | None = None):
    """Return (OpenAI client, model_id) for the chosen provider."""
    provider = (provider or default_provider()).lower()
    cfg = PROVIDERS.get(provider)
    if not cfg:
        raise ProviderError(f"unknown LLM_PROVIDER {provider!r}; expected one of {list(PROVIDERS)}")

    if cfg["api_key_env"]:
        api_key = os.getenv(cfg["api_key_env"])
        if not api_key:
            raise ProviderError(
                f"{cfg['api_key_env']} is not set. Put it in .env (gitignored) or the "
                f"deploy host's environment settings. Never hardcode it.")
    else:
        api_key = "ollama"                       # placeholder; the client requires a value

    model = os.getenv(cfg["model_env"] or "", "") or cfg["default_model"]
    return OpenAI(base_url=cfg["base_url"], api_key=api_key), model


def list_models(provider: str = "gemini") -> list[str]:
    """Query the provider's live model list, so the model id is never a blind guess."""
    cfg = PROVIDERS[provider]
    url = cfg["base_url"].rstrip("/") + "/models"
    req = urllib.request.Request(url)
    if cfg["api_key_env"]:
        key = os.getenv(cfg["api_key_env"])
        if not key:
            raise ProviderError(f"{cfg['api_key_env']} is not set")
        req.add_header("Authorization", f"Bearer {key}")
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    return sorted(m.get("id", "") for m in data.get("data", []))


def _complete(client, model: str, messages: list, timeout: float = 120) -> str:
    """One completion with backoff. Minimal params: the compat endpoint ignores
    OpenAI-only fields, so we send only model / messages / temperature."""
    last = None
    for attempt, wait in enumerate((0,) + RETRY_WAITS):
        if wait:
            time.sleep(wait)
        try:
            resp = client.chat.completions.create(
                model=model, messages=messages, temperature=0, timeout=timeout)
            return resp.choices[0].message.content or ""
        except Exception as exc:                 # rate limit / transient network
            last = exc
            msg = str(exc)
            transient = ("429" in msg or "rate" in msg.lower() or "timeout" in msg.lower()
                         or "503" in msg or "500" in msg or "connection" in msg.lower())
            if not transient:
                raise
    raise ProviderError(f"all retries exhausted: {type(last).__name__}: {str(last)[:200]}")


def generate_sql_via(question: str, schema: str, dialect: str,
                     provider: str | None = None, examples: list | None = None,
                     allow_fallback: bool | None = None) -> tuple[str, str, str | None]:
    """Generate SQL for one question. Returns (sql, provider_used, fallback_reason).

    Uses the frozen SYSTEM_PROMPT and clean_sql, so prompt parity with the
    Phase 6 experiment is guaranteed.
    """
    messages = [{"role": "system",
                 "content": SYSTEM_PROMPT.format(schema=schema, dialect=dialect)}]
    for ex in examples or []:                    # retrieved worked examples (Phase 4)
        messages.append({"role": "user", "content": ex["question"]})
        messages.append({"role": "assistant", "content": ex["sql"]})
    messages.append({"role": "user", "content": question})
    return continue_via(messages, provider=provider, allow_fallback=allow_fallback)


def continue_via(messages: list, provider: str | None = None,
                 allow_fallback: bool | None = None) -> tuple[str, str, str | None]:
    """Send an existing message list (used by the self-correction retry loop).

    Returns (sql, provider_used, fallback_reason). fallback_reason is None when the
    primary provider answered, otherwise it says why the primary failed -- a fallback
    answers with a different model, so it must never be silent.
    """
    primary = (provider or default_provider()).lower()
    if allow_fallback is None:
        allow_fallback = fallback_enabled()
    order = [primary] + ([p for p in PROVIDERS if p != primary] if allow_fallback else [])

    errors = []
    for name in order:
        try:
            client, model = build_client(name)
            raw = _complete(client, model, messages)
            reason = None if name == primary else (
                f"primary provider {primary!r} failed ({errors[0] if errors else 'unknown'}); "
                f"answered with {name!r} instead")
            return clean_sql(raw), name, reason
        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {str(exc)[:140]}")
    raise ProviderError("no provider could answer -> " + " | ".join(errors))


if __name__ == "__main__":
    import sys

    print("provider status (no secrets shown):")
    for k, v in provider_status().items():
        print(f"  {k}: {v}")

    if "--list-models" in sys.argv:
        prov = "gemini"
        if "--provider" in sys.argv:
            prov = sys.argv[sys.argv.index("--provider") + 1]
        print(f"\nlive model list for {prov}:")
        try:
            ids = list_models(prov)
            flash = [m for m in ids if "flash" in m and not any(
                x in m for x in ("tts", "image", "live", "audio", "transcribe"))]
            print(f"  total {len(ids)} models; text-flash candidates:")
            for m in flash:
                print(f"    {m}")
        except Exception as exc:
            print(f"  could not list: {type(exc).__name__}: {str(exc)[:160]}")
