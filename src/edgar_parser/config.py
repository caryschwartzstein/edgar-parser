"""Configuration management for EDGAR parser"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Application configuration"""

    # Database
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", 5432))
    DB_NAME = os.getenv("DB_NAME", "edgar_financial_metrics")
    DB_USER = os.getenv("DB_USER", "edgar_user")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")

    @property
    def DATABASE_URL(self):
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # SEC EDGAR
    EDGAR_USER_AGENT = os.getenv("EDGAR_USER_AGENT", "")
    EDGAR_BASE_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

    # Application
    DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))

    def validate(self):
        """Validate required configuration"""
        errors = []

        # DB_PASSWORD can be empty for local development with trust authentication
        # if not self.DB_PASSWORD:
        #     errors.append("DB_PASSWORD not set in .env file")

        if not self.EDGAR_USER_AGENT:
            errors.append("EDGAR_USER_AGENT not set in .env file (required by SEC)")

        if errors:
            raise ValueError(f"Configuration errors: {', '.join(errors)}")

        return True

config = Config()
