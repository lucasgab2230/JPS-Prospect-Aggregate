import os
import pathlib
from typing import Any, Dict, List

from dotenv import load_dotenv

# Environment variables loading
load_dotenv()

# Base paths
BASE_DIR = pathlib.Path(__file__).parent.parent.absolute()
LOGS_DIR = os.path.join(BASE_DIR, "logs")
DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_DATA_DIR = os.path.join(DATA_DIR, "raw")
TEMP_DIR = os.path.join(BASE_DIR, "temp")
ERROR_SCREENSHOTS_DIR = os.path.join(LOGS_DIR, "error_screenshots")
ERROR_HTML_DIR = os.path.join(LOGS_DIR, "error_html")

# Ensure directories exist (directly, without using file_utils to avoid circular imports)
for directory in [
    LOGS_DIR,
    DATA_DIR,
    RAW_DATA_DIR,
    TEMP_DIR,
    ERROR_SCREENSHOTS_DIR,
    ERROR_HTML_DIR,
]:
    os.makedirs(directory, exist_ok=True)

# Database configuration paths
DEFAULT_BUSINESS_DB_PATH = os.path.join(DATA_DIR, "jps_aggregate.db")
DEFAULT_USER_DB_PATH = os.path.join(DATA_DIR, "jps_users.db")


# Application configuration
class Config:
    """Base configuration class with common settings."""

    # Flask settings - Use fixed fallback for development, require env var for production
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY", "dev-secret-key-change-in-production-4f8a5c6e9b1d3a7f"
    )
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", 5001))

    # Session configuration for authentication
    SESSION_COOKIE_SECURE: bool = (
        os.getenv("SESSION_COOKIE_SECURE", "False").lower() == "true"
    )  # Set to True in production with HTTPS
    SESSION_COOKIE_HTTPONLY: bool = True  # Prevent JavaScript access to session cookies
    SESSION_COOKIE_SAMESITE: str = "Lax"  # CSRF protection
    SESSION_PERMANENT: bool = False  # Sessions expire when browser closes
    PERMANENT_SESSION_LIFETIME: int = 3600  # 1 hour if permanent sessions are used

    # Directory paths
    BASE_DIR: str = BASE_DIR
    LOGS_DIR: str = LOGS_DIR
    DATA_DIR: str = DATA_DIR
    RAW_DATA_DIR: str = RAW_DATA_DIR
    TEMP_DIR: str = TEMP_DIR
    ERROR_SCREENSHOTS_DIR: str = ERROR_SCREENSHOTS_DIR
    ERROR_HTML_DIR: str = ERROR_HTML_DIR

    # Playwright timeouts (in milliseconds)
    PAGE_NAVIGATION_TIMEOUT: int = int(
        os.getenv("PAGE_NAVIGATION_TIMEOUT", 60000)
    )  # 60 seconds
    PAGE_ELEMENT_TIMEOUT: int = int(
        os.getenv("PAGE_ELEMENT_TIMEOUT", 30000)
    )  # 30 seconds
    TABLE_LOAD_TIMEOUT: int = int(os.getenv("TABLE_LOAD_TIMEOUT", 60000))  # 60 seconds
    DOWNLOAD_TIMEOUT: int = int(os.getenv("DOWNLOAD_TIMEOUT", 60000))  # 60 seconds

    # File processing
    CSV_ENCODINGS: list[str] = ["utf-8", "latin-1", "cp1252"]
    FILE_FRESHNESS_SECONDS: int = int(
        os.getenv("FILE_FRESHNESS_SECONDS", 86400)
    )  # 24 hours

    # Scraper URLs
    ACQUISITION_GATEWAY_URL: str = "https://acquisitiongateway.gov/forecast"
    SSA_CONTRACT_FORECAST_URL: str = (
        "https://www.ssa.gov/osdbu/contract-forecast-intro.html"
    )
    COMMERCE_FORECAST_URL: str = (
        "https://www.commerce.gov/oam/industry/procurement-forecasts"
    )
    HHS_FORECAST_URL: str = "https://osdbu.hhs.gov/industry/opportunity-forecast"
    DHS_FORECAST_URL: str = "https://apfs-cloud.dhs.gov/forecast/"
    DOJ_FORECAST_URL: str = (
        "https://www.justice.gov/jmd/doj-forecast-contracting-opportunities"
    )
    DOS_FORECAST_URL: str = "https://www.state.gov/procurement-forecast"
    TREASURY_FORECAST_URL: str = "https://osdbu.forecast.treasury.gov/"
    DOT_FORECAST_URL: str = (
        "https://www.transportation.gov/osdbu/procurement-assistance/summary-forecast"
    )

    # Logging configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE_MAX_BYTES: int = int(
        os.getenv("LOG_FILE_MAX_BYTES", 5 * 1024 * 1024)
    )  # 5MB
    LOG_FILE_BACKUP_COUNT: int = int(
        os.getenv("LOG_FILE_BACKUP_COUNT", 3)
    )  # Keep only 3 log files

    # Database configuration
    # Use absolute paths (4 slashes) for SQLite to avoid path resolution issues
    SQLALCHEMY_DATABASE_URI: str = os.getenv(
        "DATABASE_URL", f"sqlite:///{os.path.abspath(DEFAULT_BUSINESS_DB_PATH)}"
    )
    USER_DATABASE_URI: str = os.getenv(
        "USER_DATABASE_URL", f"sqlite:///{os.path.abspath(DEFAULT_USER_DB_PATH)}"
    )

    # Scheduler configuration
    SCRAPE_INTERVAL_HOURS: int = int(os.getenv("SCRAPE_INTERVAL_HOURS", 24))
    HEALTH_CHECK_INTERVAL_MINUTES: int = int(
        os.getenv("HEALTH_CHECK_INTERVAL_MINUTES", 10)
    )

    # Scraper timeout configuration
    SCRAPER_TIMEOUT_HOURS: int = int(
        os.getenv("SCRAPER_TIMEOUT_HOURS", 2)
    )  # 2 hours default
    SCRAPER_CLEANUP_ENABLED: bool = (
        os.getenv("SCRAPER_CLEANUP_ENABLED", "true").lower() == "true"
    )

    # AI data preservation configuration
    PRESERVE_AI_DATA_ON_REFRESH: bool = (
        os.getenv("PRESERVE_AI_DATA_ON_REFRESH", "true").lower() == "true"
    )
    ENABLE_SMART_DUPLICATE_MATCHING: bool = (
        os.getenv("ENABLE_SMART_DUPLICATE_MATCHING", "true").lower() == "true"
    )

    # Duplicate matching thresholds
    DUPLICATE_MIN_CONFIDENCE: float = float(
        os.getenv("DUPLICATE_MIN_CONFIDENCE", "0.80")
    )  # Minimum confidence to consider a match
    DUPLICATE_NATIVE_ID_MIN_CONTENT_SIM: float = float(
        os.getenv("DUPLICATE_NATIVE_ID_MIN_CONTENT_SIM", "0.30")
    )  # Min content similarity for native_id matches
    DUPLICATE_TITLE_SIMILARITY_THRESHOLD: float = float(
        os.getenv("DUPLICATE_TITLE_SIMILARITY_THRESHOLD", "0.70")
    )  # Title similarity threshold
    DUPLICATE_FUZZY_CONTENT_THRESHOLD: float = float(
        os.getenv("DUPLICATE_FUZZY_CONTENT_THRESHOLD", "0.90")
    )  # Very high threshold for content-only matching

    # Backup configuration
    BACKUP_RETENTION_DAYS: int = int(os.getenv("BACKUP_RETENTION_DAYS", "7"))
    BACKUP_DIRECTORY: str = os.getenv(
        "BACKUP_DIRECTORY", os.path.join(BASE_DIR, "backups")
    )

    # SQLite configuration
    SQLITE_JOURNAL_MODE: str = os.getenv("SQLITE_JOURNAL_MODE", "WAL")
    SQLITE_SYNCHRONOUS: str = os.getenv("SQLITE_SYNCHRONOUS", "NORMAL")
    SQLITE_CACHE_SIZE: int = int(os.getenv("SQLITE_CACHE_SIZE", "-64000"))


class DevelopmentConfig(Config):
    """Development configuration."""

    DEBUG: bool = True
    LOG_LEVEL: str = "DEBUG"


class ProductionConfig(Config):
    """Production configuration."""

    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Enforce secure session cookies in production
    SESSION_COOKIE_SECURE: bool = True
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "Lax"

    # Force HTTPS URL generation in production
    PREFERRED_URL_SCHEME: str = "https"

    def __init__(self):
        """Initialize production config and validate critical settings."""
        super().__init__()
        # Ensure SECRET_KEY is set and not using the default
        if (
            not os.getenv("SECRET_KEY")
            or self.SECRET_KEY == "dev-secret-key-change-in-production-4f8a5c6e9b1d3a7f"
        ):
            raise ValueError(
                "SECRET_KEY must be set in production environment! "
                'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
            )


class TestingConfig(Config):
    """Testing configuration."""

    TESTING: bool = True
    DEBUG: bool = True
    # Use in-memory SQLite for testing
    SQLALCHEMY_DATABASE_URI: str = "sqlite:///:memory:"
    USER_DATABASE_URI: str = "sqlite:///:memory:"


# Configuration dictionary
config_by_name: dict[str, Any] = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}

# Get current configuration based on environment
active_config = config_by_name[os.getenv("FLASK_ENV", "default")]

# Export selected configuration variables
__all__ = ["active_config", "BASE_DIR", "LOGS_DIR", "DATA_DIR", "RAW_DATA_DIR"]
