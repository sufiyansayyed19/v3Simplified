from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    SERVICE_NAME: str = "vehicle-service"
    HOST: str = "0.0.0.0"
    PORT: int = 8002
    DATABASE_URL: str = "postgresql+psycopg://vehicle_user:vehicle_pass@localhost:5432/vehicle_db"

    JWT_SECRET_KEY: str = "super-secret-jwt-key-for-corporate-parking"
    JWT_ALGORITHM: str = "HS256"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
