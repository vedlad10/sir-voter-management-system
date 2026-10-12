"""Configuration module for the SIR Electoral Roll Management System."""
import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "sir-electoral-system-secret-key-2026")
    
    # MySQL Database Configuration
    MYSQL_HOST = os.environ.get("MYSQL_HOST", "localhost")
    MYSQL_USER = os.environ.get("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
    MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE", "sir_electoral_db")
    MYSQL_PORT = int(os.environ.get("MYSQL_PORT", 3306))
    
    # SQLite Fallback Configuration (guarantees standalone operation without live MySQL daemon)
    SQLITE_DB_PATH = os.path.join(os.path.dirname(__file__), "sir_electoral.db")
    
    # Business Rules Parameters
    BOOTH_MAX_CAPACITY = 1200
    APPEAL_WINDOW_DAYS = 15
    MINIMUM_VOTER_AGE = 18
