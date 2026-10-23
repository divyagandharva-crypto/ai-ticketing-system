from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_hostname: str
    database_port: str
    database_password: str
    database_name: str
    database_username: str
    secret_key: str
    algorithm: str
    access_token_expire_minutes: int
    anthropic_api_key: str
    # Background jobs. Set RUN_BACKGROUND_WORKER=false if you run `python worker.py` separately.
    run_background_worker: bool = True
    # Queue an AI triage (category/urgency/summary) job for every new ticket.
    auto_analyze_tickets: bool = True

    class Config:
        env_file = ".env"

settings = Settings()