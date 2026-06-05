"""Config — every knob is an env var. Swapping a provider == changing one var.

Defaults are the *offline-safe* choices (``stub``) so the service boots and the
test suite runs with no API keys. ``.env.example`` documents the hosted defaults
(Gemini / Deepgram) that a real deployment turns on.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- service ---
    service_api_key: str = "dev-key"          # SERVICE_API_KEY — shared bearer
    host: str = "0.0.0.0"
    port: int = 8080
    require_auth: bool = False                 # REQUIRE_AUTH — enforce bearer on calls

    # --- provider selection (the seam) ---
    llm_provider: str = "stub"                 # LLM_PROVIDER: gemini | stub | catalog
    stt_provider: str = "stub"                 # STT_PROVIDER: deepgram | stub
    tts_provider: str = "stub"                 # TTS_PROVIDER: deepgram | stub

    # --- LLM keys / models ---
    gemini_api_key: str = ""                   # GEMINI_API_KEY
    gemini_model: str = "gemini-2.5-flash-lite"
    ollama_base_url: str = "http://localhost:11434"   # local swap target for stub->ollama
    ollama_model: str = "llama3.2:1b"

    # --- multi-provider catalog (operation_files/MODELS.md) ---
    # A provider is only selectable (in GET /llm/options and per-run overrides)
    # when its key is present here. Attribute names mirror MODELS.md `key_env`
    # lower-cased, so the catalog can look them up generically.
    openai_api_key: str = ""                   # OPENAI_API_KEY
    xai_api_key: str = ""                       # XAI_API_KEY
    anthropic_api_key: str = ""                 # ANTHROPIC_API_KEY
    # role -> provider, then provider -> model (see MODELS.md "Env scheme")
    convo_provider: str = ""                    # CONVO_PROVIDER
    extract_provider: str = ""                  # EXTRACT_PROVIDER
    convo_model: str = ""                       # CONVO_MODEL (role override, wins)
    extract_model: str = ""                     # EXTRACT_MODEL
    openai_model: str = ""                      # OPENAI_MODEL (explicit override)
    xai_model: str = ""                         # XAI_MODEL
    anthropic_model: str = ""                   # ANTHROPIC_MODEL
    openai_model_default: str = "gpt-5.4-nano"   # OPENAI_MODEL_DEFAULT
    xai_model_default: str = "grok-4.3"          # XAI_MODEL_DEFAULT
    anthropic_model_default: str = "claude-haiku-4-5"  # ANTHROPIC_MODEL_DEFAULT

    # --- STT / TTS keys ---
    deepgram_api_key: str = ""                 # DEEPGRAM_API_KEY
    deepgram_stt_model: str = "nova-3"
    deepgram_tts_model: str = "aura-asteria-en"

    # --- LiveKit (live audio transport) ---
    livekit_url: str = ""                      # LIVEKIT_URL  e.g. wss://x.livekit.cloud
    livekit_api_key: str = ""                  # LIVEKIT_API_KEY
    livekit_api_secret: str = ""               # LIVEKIT_API_SECRET

    @property
    def provider_summary(self) -> dict[str, str]:
        return {
            "llm": self.llm_provider,
            "stt": self.stt_provider,
            "tts": self.tts_provider,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    """Tests flip env vars then call this to pick up the new provider selection."""
    get_settings.cache_clear()
