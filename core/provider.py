import os
from enum import Enum
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"


class ModelProvider(str, Enum):
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    GEMINI = "gemini"
    OPENAI = "openai"
    OPENAI_CODEX = "openai-codex"


def reload_env() -> None:
    """Refresh process env from the project .env for long-running processes."""
    if ENV_PATH.exists():
        load_dotenv(ENV_PATH, override=True)


def get_provider() -> ModelProvider:
    reload_env()
    val = os.getenv("MODEL_PROVIDER", "anthropic").strip().lower()
    if val == "ollama":
        return ModelProvider.OLLAMA
    elif val == "gemini":
        return ModelProvider.GEMINI
    elif val == "openai":
        return ModelProvider.OPENAI
    elif val == "openai-codex":
        return ModelProvider.OPENAI_CODEX
    return ModelProvider.ANTHROPIC


def create_client(provider: ModelProvider | None = None):
    reload_env()
    if provider is None:
        provider = get_provider()

    if provider == ModelProvider.OLLAMA:
        from core.ollama_client import OllamaClient
        return OllamaClient()
    elif provider == ModelProvider.GEMINI:
        from core.gemini_client import GeminiClient
        return GeminiClient()
    elif provider == ModelProvider.OPENAI:
        from core.openai_client import OpenAIClient
        return OpenAIClient()
    elif provider == ModelProvider.OPENAI_CODEX:
        from core.openai_codex_client import OpenAICodexClient
        return OpenAICodexClient()
    else:
        from core.client import ClaudeClient
        return ClaudeClient()
