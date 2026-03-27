from slidebuddy.config.defaults import get_api_key, load_preferences


def get_embedding_function():
    """Get embedding function based on configured provider."""
    prefs = load_preferences()
    model = prefs.get("default_models", {}).get("embedding", "text-embedding-3-small")

    openai_key = get_api_key("openai")
    google_key = get_api_key("google")

    if "text-embedding" in model or openai_key:
        return _get_openai_embeddings(model, openai_key)
    elif "embedding" in model and google_key:
        return _get_google_embeddings(model, google_key)
    else:
        # Fallback: use ChromaDB's default embedding
        return None


def _get_openai_embeddings(model: str, api_key: str):
    from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
    return OpenAIEmbeddingFunction(api_key=api_key, model_name=model)


def _get_google_embeddings(model: str, api_key: str):
    from chromadb.utils.embedding_functions import GoogleGenerativeAiEmbeddingFunction
    return GoogleGenerativeAiEmbeddingFunction(api_key=api_key, model_name=model)
