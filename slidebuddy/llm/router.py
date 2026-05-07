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
    "cerebras": [
        "gpt-oss-120b",
    ],
}


def get_llm(task: str = "generation", model_override: Optional[str] = None):
    """Get LLM instance for the given task (cached per model+temperature)."""
    prefs = load_preferences()
    model_spec = model_override or prefs.get("default_models", {}).get(task, "claude-sonnet-4-20250514")
    temperature = _TASK_TEMPERATURES.get(task, 0.7)
    timeout = _TASK_TIMEOUTS.get(task, 90)

    cache_key = (model_spec, temperature, timeout)
    if cache_key in _llm_cache:
        return _llm_cache[cache_key]

    provider = _detect_provider(model_spec)
    model_name = model_spec.split(":", 1)[1] if ":" in model_spec else model_spec

    api_key = get_api_key(provider)
    if not api_key:
        raise ValueError(
            f"Kein API-Schlüssel für '{provider}' konfiguriert. "
            f"Modell '{model_name}' (Task: {task}) benötigt einen {provider}-Key. "
            f"Bitte unter Einstellungen → API-Keys eintragen."
        )

    if provider == "anthropic":
        llm = _get_anthropic(model_name, api_key, temperature, timeout)
    elif provider == "openai":
        llm = _get_openai(model_name, api_key, temperature, timeout)
    elif provider == "google":
        llm = _get_google(model_name, api_key, temperature, timeout)
    elif provider == "cerebras":
        llm = _get_cerebras(model_name, api_key, temperature, timeout)
    else:
        raise ValueError(f"Unbekannter Provider: {provider}")

    _llm_cache[cache_key] = llm
    return llm


_VALID_PROVIDERS = ("anthropic", "openai", "google", "cerebras")


def _detect_provider(model_spec: str) -> str:
    """Detect provider from model spec.

    Supports "provider:model" prefix (preferred) and legacy bare model names.
    Raises ValueError for unrecognized models instead of silently defaulting.
    """
    if ":" in model_spec:
        provider = model_spec.split(":", 1)[0].lower()
        if provider in _VALID_PROVIDERS:
            return provider
        raise ValueError(
            f"Unbekannter Provider '{provider}' in '{model_spec}'. "
            f"Gültige Provider: {', '.join(_VALID_PROVIDERS)}."
        )

    lower = model_spec.lower()
    if "claude" in lower or "anthropic" in lower:
        return "anthropic"
    if "gpt" in lower or "o1" in lower or "o3" in lower or "o4" in lower:
        return "openai"
    if "gemini" in lower:
        return "google"

    raise ValueError(
        f"Provider für Modell '{model_spec}' nicht erkennbar. "
        f"Bitte unter Einstellungen → Modelle neu auswählen."
    )


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


def _get_cerebras(model: str, api_key: str, temperature: float, timeout: int = 90):
    from langchain_openai import ChatOpenAI
    # Cerebras is OpenAI-compatible; runs ~30x faster → aggressive timeout
    cerebras_timeout = max(15, timeout // 4)
    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url="https://api.cerebras.ai/v1",
        temperature=temperature,
        timeout=cerebras_timeout,
    )


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

    # Cerebras — fetch from API
    if api_keys.get("cerebras"):
        try:
            result["cerebras"] = _fetch_cerebras_models(api_keys["cerebras"])
        except Exception as e:
            logger.warning(f"Failed to fetch Cerebras models: {e}")
            result["cerebras"] = _FALLBACK_MODELS["cerebras"]
    else:
        result["cerebras"] = _FALLBACK_MODELS["cerebras"]

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
    """Fetch all chat/reasoning models from OpenAI API."""
    import openai
    client = openai.OpenAI(api_key=api_key)
    models = client.models.list()
    _SKIP_PATTERNS = (
        "embedding", "whisper", "tts", "dall-e", "moderation",
        "audio", "image", "realtime", "transcribe", "search",
        "babbage", "davinci-002", "curie", "ada",
    )
    chat_models = sorted(
        m.id for m in models.data
        if not any(skip in m.id.lower() for skip in _SKIP_PATTERNS)
        and not m.id.startswith("ft:")
    )
    return chat_models if chat_models else _FALLBACK_MODELS["openai"]


def _fetch_cerebras_models(api_key: str) -> list[str]:
    """Fetch available models from Cerebras API (OpenAI-compatible endpoint)."""
    import openai
    client = openai.OpenAI(api_key=api_key, base_url="https://api.cerebras.ai/v1")
    models = client.models.list()
    model_ids = sorted(m.id for m in models.data)
    return model_ids if model_ids else _FALLBACK_MODELS["cerebras"]


def _fetch_google_models(api_key: str) -> list[str]:
    """Fetch available Gemini models via the modern google-genai SDK."""
    from google import genai
    client = genai.Client(api_key=api_key)
    models = list(client.models.list())

    _SKIP_PATTERNS = ("embedding", "aqa", "imagen", "veo", "tts", "image-generation")
    gemini_models: list[str] = []
    for m in models:
        name = (getattr(m, "name", "") or "").replace("models/", "")
        if not name:
            continue
        actions = getattr(m, "supported_actions", None) or getattr(m, "supported_generation_methods", None) or []
        if "generateContent" not in actions:
            continue
        if any(skip in name.lower() for skip in _SKIP_PATTERNS):
            continue
        gemini_models.append(name)
    return sorted(set(gemini_models)) if gemini_models else _FALLBACK_MODELS["google"]

