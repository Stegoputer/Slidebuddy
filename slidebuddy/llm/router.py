import logging
from typing import Optional

from langchain_core.language_models import BaseChatModel

from slidebuddy.config.defaults import load_preferences

logger = logging.getLogger(__name__)

# Temperature per task: planning needs consistency, generation needs creativity
_TASK_TEMPERATURES = {
    "planning": 0.3,
    "generation": 0.7,
    "master_analysis": 0.2,
}

# LLM instance cache — keyed by (model_name, temperature).
_llm_cache: dict[tuple[str, float], BaseChatModel] = {}

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
        "gemini-2.5-pro-preview-06-05",
    ],
}


def get_llm(task: str = "generation", model_override: Optional[str] = None) -> BaseChatModel:
    """Get LLM instance for the given task (cached per model+temperature)."""
    prefs = load_preferences()
    api_keys = prefs.get("api_keys", {})
    model_name = model_override or prefs.get("default_models", {}).get(task, "claude-sonnet-4-20250514")
    temperature = _TASK_TEMPERATURES.get(task, 0.7)

    cache_key = (model_name, temperature)
    if cache_key in _llm_cache:
        return _llm_cache[cache_key]

    provider = _detect_provider(model_name)
    api_key = api_keys.get(provider, "")

    if provider == "anthropic":
        llm = _get_anthropic(model_name, api_key, temperature)
    elif provider == "openai":
        llm = _get_openai(model_name, api_key, temperature)
    elif provider == "google":
        llm = _get_google(model_name, api_key, temperature)
    else:
        llm = _get_anthropic(model_name, api_key, temperature)

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


def _get_anthropic(model: str, api_key: str, temperature: float) -> BaseChatModel:
    from langchain_anthropic import ChatAnthropic
    return ChatAnthropic(model=model, api_key=api_key, temperature=temperature, max_tokens=4096)


def _get_openai(model: str, api_key: str, temperature: float) -> BaseChatModel:
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model=model, api_key=api_key, temperature=temperature, max_tokens=4096)


def _get_google(model: str, api_key: str, temperature: float) -> BaseChatModel:
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(model=model, google_api_key=api_key, temperature=temperature, max_output_tokens=4096)


def get_available_providers() -> list[str]:
    """Return list of providers with configured API keys."""
    prefs = load_preferences()
    keys = prefs.get("api_keys", {})
    available = []
    if keys.get("anthropic"):
        available.append("anthropic")
    if keys.get("openai"):
        available.append("openai")
    if keys.get("google"):
        available.append("google")
    return available


def get_provider_models() -> dict[str, list[str]]:
    """Get available models per provider. Fetches from APIs on first call, then caches.

    Falls back to static list if API call fails.
    """
    global _models_cache
    if _models_cache is not None:
        return _models_cache

    prefs = load_preferences()
    api_keys = prefs.get("api_keys", {})
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
    # Filter to generative models that support generateContent
    gemini_models = sorted(
        m.name.replace("models/", "")
        for m in models
        if "generateContent" in (m.supported_generation_methods or [])
        and "gemini" in m.name
    )
    return gemini_models if gemini_models else _FALLBACK_MODELS["google"]

