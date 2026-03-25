from slidebuddy.config.defaults import load_preferences


def get_embedding_function():
    """Get embedding function based on configured provider."""
    prefs = load_preferences()
    api_keys = prefs.get("api_keys", {})
    model = prefs.get("default_models", {}).get("embedding", "text-embedding-3-small")

    if "text-embedding" in model or api_keys.get("openai"):
        return _get_openai_embeddings(model, api_keys.get("openai", ""))
    elif "embedding" in model and api_keys.get("google"):
        return _get_google_embeddings(model, api_keys.get("google", ""))
    else:
        # Fallback: use ChromaDB's default embedding
        return None


def _get_openai_embeddings(model: str, api_key: str):
    from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
    return OpenAIEmbeddingFunction(api_key=api_key, model_name=model)


def _get_google_embeddings(model: str, api_key: str):
    from chromadb.utils.embedding_functions import GoogleGenerativeAiEmbeddingFunction
    return GoogleGenerativeAiEmbeddingFunction(api_key=api_key, model_name=model)
