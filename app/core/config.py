from functools import lru_cache
from uuid import UUID

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


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
    jwt_secret_key: str = Field(default="", alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_access_token_expire_minutes: int = Field(default=60, alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES")
    environment: str = Field(default="local", alias="ENVIRONMENT")
    cors_origins: str = Field(default="", alias="CORS_ORIGINS")
    demo_athlete_password: str = Field(default="", alias="DEMO_ATHLETE_PASSWORD")
    demo_coach_password: str = Field(default="", alias="DEMO_COACH_PASSWORD")

    def model_post_init(self, __context: object) -> None:
        if self.environment != "test" and not self.jwt_secret_key:
            raise ValueError("JWT_SECRET_KEY must be set outside test environments.")
        if self.environment not in {"local", "test"} and self.jwt_secret_key == "change-me":
            raise ValueError("JWT_SECRET_KEY must be changed outside local/test environments.")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def database_url(self) -> URL:
        return URL.create(
            "postgresql+psycopg",
            username=self.database_user or None,
            password=self.database_password or None,
            host=self.database_host or None,
            port=self.database_port,
            database=self.database_name,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
