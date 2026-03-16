from pydantic_settings import BaseSettings
from typing import List
import os

class Settings(BaseSettings):
    PROJECT_NAME: str = "E-Tebeka Platform"
    API_V1_STR: str = "/api/v1"
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:meronyeyenekonjo24@localhost:5432/e-tebeka_db")
    
    # JWT
    JWT_SECRET: str = os.getenv("JWT_SECRET", "yoursecrethashtag2026!@#$")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Gemini API
    # Rotating keys
    GEMINI_API_KEYS: List[str] = [
        "AIzaSyAdYiPm8H9g8NyygFqmU0jUQrYTGf6Cqrw",
        "AIzaSyBdYtAz1oD2URJnbwQ5tOgdOfIF-36OhOc",
        "AIzaSyBRZgFEdBxMGdq3kLkp8d3HGkV2rhNSPbg",
        "AIzaSyCkeAT1fUGXkWXnyaLZtB35SRuBu0VWLeY",
        "AIzaSyBbJmlkMgM-50fpMNTbhZkFbmepTWEHvN8"
    ]
    GEMINI_MODEL: str = "gemini-2.5-flash"
    
    # Email (Placeholder)
    EMAIL_API_KEY: str = os.getenv("EMAIL_API_KEY", "")
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "noreply@e-tebeka.gov.et")
    
    # Storage
    UPLOAD_DIR: str = "./uploads"

    class Config:
        env_file = ".env"

settings = Settings()
