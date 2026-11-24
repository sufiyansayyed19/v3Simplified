from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    SERVICE_NAME: str = "payment-service"
    HOST: str = "0.0.0.0"
    PORT: int = 8004
    DATABASE_URL: str = "postgresql+psycopg://payment_user:payment_pass@localhost:5432/payment_db"

    JWT_SECRET_KEY: str = "super-secret-jwt-key-for-corporate-parking"
    JWT_ALGORITHM: str = "HS256"

    PARKING_SERVICE_URL: str = "http://127.0.0.1:8003"
    INTERNAL_SERVICE_TOKEN: str = "dev-internal-service-token"

    PAYMENT_SIMULATION_DEFAULT_OUTCOME: str = "SUCCESS"
    ENABLE_TEST_PAYMENT_OVERRIDE: bool = True
    ENVIRONMENT: str = "development"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
