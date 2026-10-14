from functools import lru_cache
from uuid import UUID

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_host: str = Field(default="localhost", alias="DATABASE_HOST")
    database_port: int = Field(default=5432, alias="DATABASE_PORT")
    database_name: str = Field(default="athlete_os", alias="DATABASE_NAME")
    database_user: str = Field(default="athlete_os", alias="DATABASE_USER")
    database_password: str = Field(default="", alias="DATABASE_PASSWORD")

    demo_athlete_id: UUID = Field(
        default=UUID("22222222-2222-4222-8222-222222222222"),
        alias="DEMO_ATHLETE_ID",
    )
    jwt_secret_key: str = Field(default="change-me", alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    environment: str = Field(default="local", alias="ENVIRONMENT")

    def model_post_init(self, __context: object) -> None:
        if self.environment not in {"local", "test"} and self.jwt_secret_key == "change-me":
            raise ValueError("JWT_SECRET_KEY must be changed outside local/test environments.")

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.database_user}:{self.database_password}"
            f"@{self.database_host}:{self.database_port}/{self.database_name}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
