import logging

from slidebuddy.config.defaults import get_api_key, load_preferences

_logger = logging.getLogger(__name__)


def get_embedding_function():
    """Get embedding function based on configured provider.

    Never returns None — avoids ChromaDB loading its heavy default
    ONNX embedding model into RAM (~500MB-1GB).
    """
    prefs = load_preferences()
    model = prefs.get("default_models", {}).get("embedding", "text-embedding-3-small")

    openai_key = get_api_key("openai")
    google_key = get_api_key("google")

    if openai_key:
        embed_model = model if "text-embedding" in model else "text-embedding-3-small"
        return _get_openai_embeddings(embed_model, openai_key)
    elif google_key:
        embed_model = model if "embedding" in model else "models/embedding-001"
        return _get_google_embeddings(embed_model, google_key)
    else:
        raise RuntimeError(
            "No embedding API key configured. "
            "Set an OpenAI or Google API key in Settings."
        )


def _get_openai_embeddings(model: str, api_key: str):
    from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
    return OpenAIEmbeddingFunction(api_key=api_key, model_name=model)


def _get_google_embeddings(model: str, api_key: str):
    from chromadb.utils.embedding_functions import GoogleGenerativeAiEmbeddingFunction
    return GoogleGenerativeAiEmbeddingFunction(api_key=api_key, model_name=model)
