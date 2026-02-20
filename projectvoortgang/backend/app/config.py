from dataclasses import dataclass
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App Database
    app_db_host: str = "localhost"
    app_db_port: int = 5433
    app_db_name: str = "projectvoortgang"
    app_db_user: str = "postgres"
    app_db_password: str = "postgres"

    # Client DWH
    dwh_host: str = "10.3.152.9"
    dwh_port: int = 5432
    dwh_user: str = "postgres"
    dwh_password: str = ""

    # App
    debug: bool = True
    cors_origins: str = "http://localhost:5173"

    @property
    def app_db_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.app_db_user}:{self.app_db_password}"
            f"@{self.app_db_host}:{self.app_db_port}/{self.app_db_name}"
        )

    def dwh_db_url(self, klantnummer: int) -> str:
        return (
            f"postgresql://{self.dwh_user}:{self.dwh_password}"
            f"@{self.dwh_host}:{self.dwh_port}/{klantnummer}"
        )

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
