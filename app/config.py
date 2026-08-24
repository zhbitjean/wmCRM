from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "sqlite:///./wmcrm.db"
    secret_key: str = "development-only-change-me"
    admin_email: str = "admin@example.com"
    admin_password: str = "admin-change-me"
    field_email: str = "field@example.com"
    field_password: str = "field-change-me"
    access_token_minutes: int = 480
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
settings = Settings()

