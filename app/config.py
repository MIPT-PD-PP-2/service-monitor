from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://monitor:monitor@db:5432/monitoring"
    check_interval_seconds: int = 60
    checker_timeout_seconds: int = 10
    smtp_host: str = "mailhog"
    smtp_port: int = 1025
    smtp_from: str = "monitoring@company.ru"
    smtp_user: str = ""
    smtp_password: str = ""
    notify_repeat_minutes: int = 30

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
