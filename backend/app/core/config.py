"""Backend configuration."""

from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_name: str = "Vici 10-K Extraction API"
    api_prefix: str = "/api/v1"
    confidence_threshold: float = 0.90
    sec_user_agent: str = (
        "vici-task2/0.1 (educational SEC filing extractor)"
    )
    sec_timeout_seconds: float = 30.0
    llm_model_layer2: str = "claude-haiku-4-5"
    llm_model_layer3: str = "claude-sonnet-5"

settings = Settings()
