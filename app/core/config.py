from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    secret_key: str
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    greenhouse_board_token: str | None = None
    greenhouse_api_key: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
