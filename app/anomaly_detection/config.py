# config.py - 
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg2://postgres:Simmi%40123@localhost:5432/maritime_digital_twin"

    class Config:
        env_file = ".env"

settings = Settings()