"""Application configuration loaded from environment / .env file."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root if present
load_dotenv(Path(__file__).parent.parent / ".env")


class Config:
    # OKCountyRecords
    OKCOUNTY_API_BASE_URL: str = os.getenv("OKCOUNTY_API_BASE_URL", "https://api.okcountyrecords.com/v1")
    OKCOUNTY_COST_PER_IMAGE: float = float(os.getenv("OKCOUNTY_COST_PER_IMAGE", "0.50"))
    OKCOUNTY_COST_PER_SEARCH: float = float(os.getenv("OKCOUNTY_COST_PER_SEARCH", "0.10"))

    # OpenAI
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")
    OPENAI_MAX_TOKENS: int = int(os.getenv("OPENAI_MAX_TOKENS", "4096"))

    # Storage
    DOWNLOADS_DIR: Path = Path(os.getenv("DOWNLOADS_DIR", "./downloads"))
    IMAGES_DIR: Path = Path(os.getenv("IMAGES_DIR", "./images"))
    REPORTS_DIR: Path = Path(os.getenv("REPORTS_DIR", "./reports"))
    DB_PATH: Path = Path(os.getenv("DB_PATH", "./doto_commander.db"))
    AUDIT_LOG_PATH: Path = Path(os.getenv("AUDIT_LOG_PATH", "./audit.log"))

    # Instrument type normalization map
    INSTRUMENT_TYPE_MAP: dict = {
        "wd": "Warranty Deed",
        "warranty deed": "Warranty Deed",
        "qcd": "Quit Claim Deed",
        "quit claim": "Quit Claim Deed",
        "quitclaim": "Quit Claim Deed",
        "ol": "Oil and Gas Lease",
        "oil lease": "Oil and Gas Lease",
        "oil and gas lease": "Oil and Gas Lease",
        "om": "Mineral Deed",
        "mineral deed": "Mineral Deed",
        "asgn": "Assignment",
        "assignment": "Assignment",
        "rel": "Release",
        "release": "Release",
        "mort": "Mortgage",
        "mortgage": "Mortgage",
        "affidavit": "Affidavit",
        "aff": "Affidavit",
        "plat": "Plat",
        "easement": "Easement",
        "ease": "Easement",
        "jdgmt": "Judgment",
        "judgment": "Judgment",
        "lien": "Lien",
        "decree": "Decree",
        "dec": "Decree",
    }

    # Oklahoma counties
    OK_COUNTIES: list = [
        "Adair", "Alfalfa", "Atoka", "Beaver", "Beckham", "Blaine", "Bryan",
        "Caddo", "Canadian", "Carter", "Cherokee", "Choctaw", "Cimarron",
        "Cleveland", "Coal", "Comanche", "Cotton", "Craig", "Creek", "Custer",
        "Delaware", "Dewey", "Ellis", "Garfield", "Garvin", "Grady", "Grant",
        "Greer", "Harmon", "Harper", "Haskell", "Hughes", "Jackson", "Jefferson",
        "Johnston", "Kay", "Kingfisher", "Kiowa", "Latimer", "Le Flore", "Lincoln",
        "Logan", "Love", "Major", "Marshall", "Mayes", "McClain", "McCurtain",
        "McIntosh", "Murray", "Muskogee", "Noble", "Nowata", "Okfuskee",
        "Oklahoma", "Okmulgee", "Osage", "Ottawa", "Pawnee", "Payne", "Pittsburg",
        "Pontotoc", "Pottawatomie", "Pushmataha", "Roger Mills", "Rogers",
        "Seminole", "Sequoyah", "Stephens", "Texas", "Tillman", "Tulsa",
        "Wagoner", "Washington", "Washita", "Woods", "Woodward",
    ]


config = Config()


def ensure_dirs() -> None:
    for d in (config.DOWNLOADS_DIR, config.IMAGES_DIR, config.REPORTS_DIR):
        d.mkdir(parents=True, exist_ok=True)
