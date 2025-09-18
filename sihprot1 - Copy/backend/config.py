import os
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # API Settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True
    
    # Database Settings
    DATABASE_URL: str = "sqlite:///./timetable_scheduler.db"
    
    # JWT Settings
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Default Passwords
    DEFAULT_TEACHER_PASSWORD: str = "12345"
    DEFAULT_ADMIN_PASSWORD: str = "123456"
    
    # GA Parameters
    POPULATION_SIZE: int = 100
    MAX_GENERATIONS: int = 100
    MUTATION_RATE: float = 0.02
    ELITISM_RATE: float = 0.05
    TOURNAMENT_SIZE: int = 5
    
    # Timetable Parameters
    DAYS: List[str] = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    HOURS_PER_DAY: int = 6
    MAX_CONSECUTIVE_CLASSES: int = 4
    
    # File Upload Settings
    UPLOAD_DIR: str = "./data/uploads"
    MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50MB
    ALLOWED_EXTENSIONS: List[str] = [".csv", ".xlsx", ".xls"]
    
    # Generated Files
    TIMETABLES_DIR: str = "./generated/timetables"
    REPORTS_DIR: str = "./generated/reports"
    
    # Performance Settings
    MAX_PARALLEL_RUNS: int = 3
    CACHE_TTL: int = 300  # 5 minutes
    
    class Config:
        env_file = ".env"

# Create settings instance
settings = Settings()

# Ensure directories exist
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.TIMETABLES_DIR, exist_ok=True)
os.makedirs(settings.REPORTS_DIR, exist_ok=True)
os.makedirs("./data", exist_ok=True)