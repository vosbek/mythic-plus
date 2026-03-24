import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///mythicplus.db")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8000/spotify/callback")

RAIDERIO_BASE_URL = "https://raider.io/api/v1"

# Default user character
DEFAULT_CHARACTER = {
    "name": "Saytees",
    "realm": "Stormrage",
    "region": "us",
}

# Midnight Season 1 dungeons
SEASON = "midnight-1"
DUNGEONS = [
    {"name": "Windrunner Spire", "short_name": "WRS", "time_limit_seconds": 1800, "season": SEASON},
    {"name": "Maisara Caverns", "short_name": "MC", "time_limit_seconds": 1800, "season": SEASON},
    {"name": "Nexus Point Xenas", "short_name": "NPX", "time_limit_seconds": 1800, "season": SEASON},
    {"name": "Magister's Terrace", "short_name": "MT", "time_limit_seconds": 2010, "season": SEASON},
    {"name": "Algeth'ar Academy", "short_name": "AA", "time_limit_seconds": 1800, "season": SEASON},
    {"name": "Pit of Saron", "short_name": "POS", "time_limit_seconds": 1980, "season": SEASON},
    {"name": "Seat of the Triumvirate", "short_name": "SOTT", "time_limit_seconds": 1800, "season": SEASON},
    {"name": "Skyreach", "short_name": "SKY", "time_limit_seconds": 1800, "season": SEASON},
]

# WoW class/spec data
WOW_CLASSES = {
    "Death Knight": ["Blood", "Frost", "Unholy"],
    "Demon Hunter": ["Havoc", "Vengeance"],
    "Druid": ["Balance", "Feral", "Guardian", "Restoration"],
    "Evoker": ["Augmentation", "Devastation", "Preservation"],
    "Hunter": ["Beast Mastery", "Marksmanship", "Survival"],
    "Mage": ["Arcane", "Fire", "Frost"],
    "Monk": ["Brewmaster", "Mistweaver", "Windwalker"],
    "Paladin": ["Holy", "Protection", "Retribution"],
    "Priest": ["Discipline", "Holy", "Shadow"],
    "Rogue": ["Assassination", "Outlaw", "Subtlety"],
    "Shaman": ["Elemental", "Enhancement", "Restoration"],
    "Warlock": ["Affliction", "Demonology", "Destruction"],
    "Warrior": ["Arms", "Fury", "Protection"],
}

ROLES = ["tank", "healer", "dps"]
VIBES = ["chill", "sweaty", "chaotic", "tilting", "cracked"]
RESULTS = ["timed", "completed", "depleted", "abandoned"]
