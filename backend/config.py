"""Configuration management for the application"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Application
    APP_NAME: str = "Club50 Platform"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    
    # Database
    DATABASE_URL: str = "sqlite:///./club50.db"
    DATABASE_ECHO: bool = False
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    
    # JWT
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # API
    API_V1_STR: str = "/api/v1"
    BACKEND_CORS_ORIGINS: list = ["http://localhost:5173", "http://localhost:3000"]
    
    # Docker sandbox
    DOCKER_IMAGE: str = "club50-sandbox:latest"
    DOCKER_MEMORY_LIMIT: str = "512m"
    DOCKER_CPU_LIMIT: str = "1.0"
    DOCKER_TIMEOUT: int = 30
    
    # check50
    CHECK50_SLUG_BASE: str = "github.com"
    CHECK50_OFFLINE_MODE: bool = True
    
    # submit50
    SUBMIT50_ENABLED: bool = True
    SUBMIT50_GITHUB_URL: str = "https://github.com"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
