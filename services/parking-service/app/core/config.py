from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    SERVICE_NAME: str = "parking-service"
    HOST: str = "0.0.0.0"
    PORT: int = 8003
    DATABASE_URL: str = "postgresql+psycopg://parking_user:parking_pass@localhost:5432/parking_db"

    BUSINESS_TIMEZONE: str = "Asia/Kolkata"

    JWT_SECRET_KEY: str = "super-secret-jwt-key-for-corporate-parking"
    JWT_ALGORITHM: str = "HS256"

    VEHICLE_SERVICE_URL: str = "http://127.0.0.1:8002"
    PAYMENT_SERVICE_URL: str = "http://127.0.0.1:8004"
    INTERNAL_SERVICE_TOKEN: str = "dev-internal-service-token"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
