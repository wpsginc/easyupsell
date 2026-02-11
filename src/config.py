from typing import Optional
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

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
    DEFAULT_PROVIDER: str = "azure"
    
    # Athena (Local GPT-OSS)
    ATHENA_HOST: str = "http://100.64.0.3:8081"
    
    # Azure OpenAI
    AZURE_OPENAI_API_KEY: Optional[str] = None
    AZURE_OPENAI_API_BASE: Optional[str] = None
    AZURE_OPENAI_API_VERSION: str = "2025-04-01-preview"
    AZURE_OPENAI_DEPLOYMENT: str = "gpt-4o"
    
    # OpenAI
    OPENAI_API_KEY: Optional[str] = None
    
    # Ollama
    OLLAMA_HOST: str = "http://localhost:11434"
    
    # LiteLLM
    LITELLM_HOST: str = "http://localhost:4000"
    LITELLM_API_KEY: Optional[str] = None
    LITELLM_MODEL: str = "gpt-4o-mini"
    
    # Local LLM (Generic OpenAI Compatible)
    LOCAL_LLM_HOST: str = "http://localhost:1234/v1"
    LOCAL_LLM_MODEL: str = "local-model"
    
    # Feature Flags / Parameters
    MAX_BATCH_SIZE: int = 50
    BATCH_TIMEOUT_SECONDS: int = 300

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

# Ensure directories exist
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
settings.LOGS_DIR.mkdir(parents=True, exist_ok=True)
