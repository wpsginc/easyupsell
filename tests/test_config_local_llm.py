import os
import pytest
from src.config import Settings

def test_local_llm_config_defaults():
    """Test default values for local LLM config."""
    # Create settings without env vars
    settings = Settings(_env_file=None)
    assert hasattr(settings, "LOCAL_LLM_HOST")
    assert hasattr(settings, "LOCAL_LLM_MODEL")
    assert settings.LOCAL_LLM_HOST == "http://localhost:1234/v1"  # Default expectation
    assert settings.LOCAL_LLM_MODEL == "local-model"

def test_local_llm_config_env_vars():
    """Test loading from environment variables."""
    os.environ["LOCAL_LLM_HOST"] = "http://my-local-gpu:8000/v1"
    os.environ["LOCAL_LLM_MODEL"] = "llama-3-70b"
    
    settings = Settings(_env_file=None)
    assert settings.LOCAL_LLM_HOST == "http://my-local-gpu:8000/v1"
    assert settings.LOCAL_LLM_MODEL == "llama-3-70b"
    
    # Cleanup
    del os.environ["LOCAL_LLM_HOST"]
    del os.environ["LOCAL_LLM_MODEL"]
