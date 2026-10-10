from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        extra="ignore",
    )

    openrouter_api_key: str = ""
    openrouter_model: str = "openai/gpt-4o-mini"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    database_url: str = "sqlite:///./portfly.db"
    max_history_messages: int = 16
    max_agent_steps: int = 12  # LangGraph recursion limit: bounds tool loops
    llm_max_tokens: int = 700  # bounds cost and latency per model call
    frontend_origin: str = "http://localhost:5173"
    # Shared secret for the business desk and conversation endpoints. Empty = those endpoints refuse every request.
    desk_token: str = ""
    data_dir: Path = ROOT / "data"


settings = Settings()
