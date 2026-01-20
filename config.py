import os

class Config:
    SECRET_KEY = os.getenv("FLYTAU_SECRET_KEY", "dev-secret-key-change-me")
    
    # SQLite configuration
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DB_NAME = os.path.join(BASE_DIR, "flytau.db")
    
    # Keep these for compatibility if code references them, but they are unused for SQLite
    DB_HOST = "localhost"
    DB_PORT = 3306
    DB_USER = "root"
    DB_PASSWORD = ""
