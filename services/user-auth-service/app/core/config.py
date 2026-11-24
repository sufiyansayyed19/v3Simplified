from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    SERVICE_NAME: str = "user-auth-service"
    HOST: str = "0.0.0.0"
    PORT: int = 8001
    DATABASE_URL: str = "postgresql+psycopg://user_auth_user:user_auth_pass@localhost:5432/user_db"

    COMPANY_EMAIL_DOMAIN: str = "company.com"
    OTP_EXPIRE_MINUTES: int = 5
    EMAIL_SENDER_MODE: str = "console"
    ENVIRONMENT: str = "development"

    JWT_SECRET_KEY: str = "super-secret-jwt-key-for-corporate-parking"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
