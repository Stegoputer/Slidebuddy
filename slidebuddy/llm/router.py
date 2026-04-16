import logging
from typing import Optional

from slidebuddy.config.defaults import get_all_api_keys, get_api_key, load_preferences

logger = logging.getLogger(__name__)

# Temperature per task: planning needs consistency, generation needs creativity
_TASK_TEMPERATURES = {
    "planning": 0.3,
    "generation": 0.7,
    "master_analysis": 0.2,
}

# Request timeout per task (seconds): longer for planning (large prompts)
_TASK_TIMEOUTS = {
    "planning": 120,
    "generation": 90,
    "master_analysis": 60,
}

# LLM instance cache — keyed by (model_name, temperature).
_llm_cache: dict[tuple[str, float], object] = {}

# Model list cache — fetched once per session from APIs
_models_cache: dict[str, list[str]] | None = None

# Fallback models if API listing fails
_FALLBACK_MODELS = {
    "anthropic": [
        "claude-sonnet-4-20250514",
        "claude-opus-4-20250514",
    ],
    "openai": [
        "gpt-4o",
        "gpt-4o-mini",
        "o3-mini",
    ],
    "google": [
        "gemini-2.0-flash",
        "gemini-2.5-flash",
        "gemini-2.5-pro",
    ],
}


def get_llm(task: str = "generation", model_override: Optional[str] = None):
    """Get LLM instance for the given task (cached per model+temperature)."""
    prefs = load_preferences()
    model_name = model_override or prefs.get("default_models", {}).get(task, "claude-sonnet-4-20250514")
    temperature = _TASK_TEMPERATURES.get(task, 0.7)
    timeout = _TASK_TIMEOUTS.get(task, 90)

    cache_key = (model_name, temperature, timeout)
    if cache_key in _llm_cache:
        return _llm_cache[cache_key]

    provider = _detect_provider(model_name)
    api_key = get_api_key(provider)

    if provider == "anthropic":
        llm = _get_anthropic(model_name, api_key, temperature, timeout)
    elif provider == "openai":
        llm = _get_openai(model_name, api_key, temperature, timeout)
    elif provider == "google":
        llm = _get_google(model_name, api_key, temperature, timeout)
    else:
        llm = _get_anthropic(model_name, api_key, temperature, timeout)

    _llm_cache[cache_key] = llm
    return llm


def _detect_provider(model_name: str) -> str:
    """Detect provider from model name."""
    lower = model_name.lower()
    if "claude" in lower or "anthropic" in lower:
        return "anthropic"
    if "gpt" in lower or "o1" in lower or "o3" in lower or "o4" in lower:
        return "openai"
    if "gemini" in lower:
        return "google"
    return "anthropic"


def clear_llm_cache():
    """Clear cached LLM instances (call after settings change)."""
    _llm_cache.clear()


def clear_models_cache():
    """Clear cached model lists (call after API key change)."""
    global _models_cache
    _models_cache = None


def _get_anthropic(model: str, api_key: str, temperature: float, timeout: int = 90):
    from langchain_anthropic import ChatAnthropic
    return ChatAnthropic(model=model, api_key=api_key, temperature=temperature, max_tokens=16000, timeout=timeout)


def _get_openai(model: str, api_key: str, temperature: float, timeout: int = 90):
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model=model, api_key=api_key, temperature=temperature, timeout=timeout)


def _get_google(model: str, api_key: str, temperature: float, timeout: int = 90):
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(model=model, google_api_key=api_key, temperature=temperature, timeout=timeout)


def get_available_providers() -> list[str]:
    """Return list of providers with configured API keys."""
    keys = get_all_api_keys()
    return [p for p in keys if keys[p]]


def get_provider_models() -> dict[str, list[str]]:
    """Get available models per provider. Fetches from APIs on first call, then caches.

    Falls back to static list if API call fails.
    """
    global _models_cache
    if _models_cache is not None:
        return _models_cache

    api_keys = get_all_api_keys()
    result: dict[str, list[str]] = {}

    # Anthropic — fetch from API
    if api_keys.get("anthropic"):
        try:
            result["anthropic"] = _fetch_anthropic_models(api_keys["anthropic"])
        except Exception as e:
            logger.warning(f"Failed to fetch Anthropic models: {e}")
            result["anthropic"] = _FALLBACK_MODELS["anthropic"]
    else:
        result["anthropic"] = _FALLBACK_MODELS["anthropic"]

    # OpenAI — fetch from API
    if api_keys.get("openai"):
        try:
            result["openai"] = _fetch_openai_models(api_keys["openai"])
        except Exception as e:
            logger.warning(f"Failed to fetch OpenAI models: {e}")
            result["openai"] = _FALLBACK_MODELS["openai"]
    else:
        result["openai"] = _FALLBACK_MODELS["openai"]

    # Google — fetch from API
    if api_keys.get("google"):
        try:
            result["google"] = _fetch_google_models(api_keys["google"])
        except Exception as e:
            logger.warning(f"Failed to fetch Google models: {e}")
            result["google"] = _FALLBACK_MODELS["google"]
    else:
        result["google"] = _FALLBACK_MODELS["google"]

    _models_cache = result
    return result


def _fetch_anthropic_models(api_key: str) -> list[str]:
    """Fetch available models from Anthropic API."""
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    models = client.models.list()
    # Filter to chat models, sort by name
    model_ids = sorted(m.id for m in models.data)
    return model_ids if model_ids else _FALLBACK_MODELS["anthropic"]


def _fetch_openai_models(api_key: str) -> list[str]:
    """Fetch available chat models from OpenAI API."""
    import openai
    client = openai.OpenAI(api_key=api_key)
    models = client.models.list()
    # Filter to relevant chat models
    chat_prefixes = ("gpt-4", "gpt-3.5", "o1", "o3", "o4")
    chat_models = sorted(
        m.id for m in models.data
        if any(m.id.startswith(p) for p in chat_prefixes)
    )
    return chat_models if chat_models else _FALLBACK_MODELS["openai"]


def _fetch_google_models(api_key: str) -> list[str]:
    """Fetch available Gemini models from Google AI API."""
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    models = genai.list_models()
    # Filter: only current gemini models that support generateContent
    # Exclude deprecated/old versions (1.0, 001, embedding, aqa, etc.)
    _SKIP_PATTERNS = ("gemini-1.0", "embedding", "aqa", "bisheng")
    gemini_models = []
    for m in models:
        name = m.name.replace("models/", "")
        if "gemini" not in name:
            continue
        if "generateContent" not in (m.supported_generation_methods or []):
            continue
        if any(skip in name for skip in _SKIP_PATTERNS):
            continue
        gemini_models.append(name)
    return sorted(gemini_models) if gemini_models else _FALLBACK_MODELS["google"]

