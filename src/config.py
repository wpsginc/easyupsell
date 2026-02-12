from typing import Optional
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import tomllib


def _load_toml_config() -> dict:
    """Load config.toml if it exists, return flat dict for Settings defaults."""
    toml_path = Path(__file__).parent.parent / "config.toml"
    if not toml_path.exists():
        return {}
    
    with open(toml_path, "rb") as f:
        raw = tomllib.load(f)
    
    # Flatten nested TOML into Settings field names
    llm = raw.get("llm", {})
    analysis = raw.get("analysis", {})
    
    flat = {}
    
    # Top-level LLM
    if "default_provider" in llm:
        flat["DEFAULT_PROVIDER"] = llm["default_provider"]
    
    # Azure
    azure = llm.get("azure", {})
    if "api_version" in azure:
        flat["AZURE_OPENAI_API_VERSION"] = azure["api_version"]
    if "deployment" in azure:
        flat["AZURE_OPENAI_DEPLOYMENT"] = azure["deployment"]
    
    # Athena
    athena = llm.get("athena", {})
    if "host" in athena:
        flat["ATHENA_HOST"] = athena["host"]
    
    # Local LLM
    local = llm.get("local", {})
    if "host" in local:
        flat["LOCAL_LLM_HOST"] = local["host"]
    if "model" in local:
        flat["LOCAL_LLM_MODEL"] = local["model"]
    
    # Ollama
    ollama = llm.get("ollama", {})
    if "host" in ollama:
        flat["OLLAMA_HOST"] = ollama["host"]
    
    # LiteLLM
    litellm = llm.get("litellm", {})
    if "host" in litellm:
        flat["LITELLM_HOST"] = litellm["host"]
    if "model" in litellm:
        flat["LITELLM_MODEL"] = litellm["model"]
    
    # Analysis
    if "max_batch_size" in analysis:
        flat["MAX_BATCH_SIZE"] = analysis["max_batch_size"]
    if "batch_timeout_seconds" in analysis:
        flat["BATCH_TIMEOUT_SECONDS"] = analysis["batch_timeout_seconds"]
    
    return flat


# Load TOML once at import time
_toml_defaults = _load_toml_config()


class Settings(BaseSettings):
    # App Paths
    BASE_DIR: Path = Path(__file__).parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    LOGS_DIR: Path = BASE_DIR / "logs"

    # BigCommerce
    BC_STORE_HASH: Optional[str] = Field(None, alias="BIGCOMMERCE_STORE_HASH")
    BC_ACCESS_TOKEN: Optional[str] = Field(None, alias="BIGCOMMERCE_ACCESS_TOKEN")
    
    # BigQuery
    BQ_PROJECT_ID: Optional[str] = Field(None, alias="GOOGLE_CLOUD_PROJECT")
    
    # LLM Provider Configuration
    DEFAULT_PROVIDER: str = _toml_defaults.get("DEFAULT_PROVIDER", "azure")
    
    # Athena (Local GPT-OSS)
    ATHENA_HOST: str = _toml_defaults.get("ATHENA_HOST", "http://100.64.0.3:8081")
    
    # Azure OpenAI
    AZURE_OPENAI_API_KEY: Optional[str] = None
    AZURE_OPENAI_API_BASE: Optional[str] = None
    AZURE_OPENAI_API_VERSION: str = _toml_defaults.get("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")
    AZURE_OPENAI_DEPLOYMENT: str = _toml_defaults.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    
    # OpenAI
    OPENAI_API_KEY: Optional[str] = None
    
    # Ollama
    OLLAMA_HOST: str = _toml_defaults.get("OLLAMA_HOST", "http://localhost:11434")
    
    # LiteLLM
    LITELLM_HOST: str = _toml_defaults.get("LITELLM_HOST", "http://localhost:4000")
    LITELLM_API_KEY: Optional[str] = None
    LITELLM_MODEL: str = _toml_defaults.get("LITELLM_MODEL", "gpt-4o-mini")
    
    # Local LLM (Generic OpenAI Compatible)
    LOCAL_LLM_HOST: str = _toml_defaults.get("LOCAL_LLM_HOST", "http://localhost:1234/v1")
    LOCAL_LLM_MODEL: str = _toml_defaults.get("LOCAL_LLM_MODEL", "local-model")
    
    # Feature Flags / Parameters
    MAX_BATCH_SIZE: int = _toml_defaults.get("MAX_BATCH_SIZE", 50)
    BATCH_TIMEOUT_SECONDS: int = _toml_defaults.get("BATCH_TIMEOUT_SECONDS", 300)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

# Ensure directories exist
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
settings.LOGS_DIR.mkdir(parents=True, exist_ok=True)
