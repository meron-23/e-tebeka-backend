from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    PROJECT_NAME: str = "E-Tebeka Platform"
    API_V1_STR: str = "/api/v1"
    
    # JWT
    JWT_SECRET: str = os.getenv("JWT_SECRET", "yoursecrethashtag2026!@#$")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Email (EmailJS)
    EMAILJS_SERVICE_ID: str = os.getenv("EMAILJS_SERVICE_ID", "")
    EMAILJS_TEMPLATE_ID: str = os.getenv("EMAILJS_TEMPLATE_ID", "")
    EMAILJS_PUBLIC_KEY: str = os.getenv("EMAILJS_PUBLIC_KEY", "")
    EMAILJS_PRIVATE_KEY: str = os.getenv("EMAILJS_PRIVATE_KEY", "")
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "noreply@e-tebeka.gov.et")
    
    # Storage
    UPLOAD_DIR: str = "./uploads"

    class Config:
        env_file = ".env"

settings = Settings()
