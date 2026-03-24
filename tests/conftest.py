"""Shared test fixtures for Mythic+ Tracker."""
import json
import os
import tempfile
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

# Use in-memory SQLite for speed — StaticPool ensures same DB across connections
os.environ["DATABASE_URL"] = "sqlite://"

from app.models import Run, RunMember, Character, Dungeon, RunSong  # noqa: E402
from app.config import DUNGEONS, DEFAULT_CHARACTER  # noqa: E402

_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)


def _patch_engine():
    """Replace all references to the DB engine with our in-memory engine."""
    import sys
    import app.database as db_mod
    db_mod.engine = _engine
    # Patch every loaded app module that has an 'engine' attribute from app.database
    for name, mod in sys.modules.items():
        if name.startswith("app.") and mod and hasattr(mod, "engine"):
            mod.engine = _engine

_patch_engine()


@pytest.fixture(autouse=True)
def reset_db():
    """Fresh in-memory database for every test."""
    _patch_engine()
    SQLModel.metadata.drop_all(_engine)
    SQLModel.metadata.create_all(_engine)
    with Session(_engine) as session:
        for d in DUNGEONS:
            session.add(Dungeon(**d))
        session.add(Character(
            name=DEFAULT_CHARACTER["name"],
            realm=DEFAULT_CHARACTER["realm"],
            region=DEFAULT_CHARACTER["region"],
            is_mine=True,
        ))
        session.commit()
    yield


@pytest.fixture
def session():
    """Provide a database session."""
    with Session(_engine) as s:
        yield s


@pytest.fixture
def client():
    """FastAPI test client."""
    from app.main import app
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def sample_run(session):
    """Create a single timed run with 2 members."""
    char1 = Character(name="Testplayer", realm="Stormrage", region="us",
                      class_name="Druid", race="Night Elf", spec="Restoration",
                      role="healer", guild="Test Guild", title="the Undying",
                      is_mine=True)
    char2 = Character(name="Tankfriend", realm="Stormrage", region="us",
                      class_name="Warrior", race="Human", spec="Protection",
                      role="tank", guild="Test Guild")
    session.add(char1)
    session.add(char2)
    session.commit()
    session.refresh(char1)
    session.refresh(char2)

    run = Run(
        dungeon_name="Ara-Kara, City of Echoes",
        key_level=15,
        result="timed",
        duration_seconds=1500,
        time_limit_seconds=1800,
        upgrade_count=2,
        deaths=1,
        started_at=datetime(2024, 3, 15, 20, 30),
        completed_at=datetime(2024, 3, 15, 20, 55),
        season="midnight-1",
        affixes=json.dumps(["Fortified", "Bursting"]),
        notes="Clean run",
        rating=4,
        vibe="chill",
        source="addon",
        addon_run_id="test-run-1",
        gold_before=100000000,
        gold_after=99950000,
        durability_before=95.0,
        durability_after=42.0,
        companion_pet="Lil Ragnaros",
        my_mount="Invincible",
        played_seconds=1523,
        buffs_json=json.dumps({
            "flask": ["Testplayer", "Tankfriend"],
            "food": ["Testplayer", "Tankfriend"],
            "rune": [],
        }),
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    m1 = RunMember(run_id=run.id, character_id=char1.id, spec="Restoration",
                   role="healer", was_me=True, ilvl=623.0, mount="Invincible")
    m2 = RunMember(run_id=run.id, character_id=char2.id, spec="Protection",
                   role="tank", was_me=False, ilvl=618.0, mount="Swift Spectral Tiger")
    session.add(m1)
    session.add(m2)
    session.commit()

    return run


@pytest.fixture
def multiple_runs(session):
    """Create a set of runs with varied data for analytics testing."""
    char = session.exec(
        select(Character).where(Character.is_mine == True)
    ).first()

    char2 = Character(name="Buddy", realm="Stormrage", region="us",
                      class_name="Mage", race="Human", guild="Other Guild")
    session.add(char2)
    session.commit()
    session.refresh(char2)

    runs_data = [
        {"dungeon_name": "Ara-Kara, City of Echoes", "key_level": 15, "result": "timed",
         "duration_seconds": 1500, "time_limit_seconds": 1800, "upgrade_count": 2,
         "deaths": 1, "vibe": "chill", "rating": 5,
         "started_at": datetime(2024, 3, 15, 20, 30),
         "affixes": json.dumps(["Fortified"]),
         "gold_before": 100000000, "gold_after": 99950000,
         "my_mount": "Invincible", "companion_pet": "Lil Ragnaros",
         "played_seconds": 1500,
         "buffs_json": json.dumps({"flask": ["a","b","c","d","e"], "food": ["a","b","c","d","e"], "rune": []})},
        {"dungeon_name": "Ara-Kara, City of Echoes", "key_level": 16, "result": "depleted",
         "duration_seconds": 1900, "time_limit_seconds": 1800, "deaths": 5,
         "vibe": "tilting", "rating": 1,
         "started_at": datetime(2024, 3, 15, 14, 0),
         "affixes": json.dumps(["Tyrannical"]),
         "gold_before": 99950000, "gold_after": 99900000,
         "my_mount": "Invincible", "companion_pet": "Lil Ragnaros",
         "buffs_json": json.dumps({"flask": [], "food": [], "rune": []})},
        {"dungeon_name": "City of Threads", "key_level": 12, "result": "timed",
         "duration_seconds": 1400, "time_limit_seconds": 1800, "upgrade_count": 3,
         "deaths": 0, "vibe": "cracked", "rating": 5,
         "started_at": datetime(2024, 3, 16, 2, 0),
         "affixes": json.dumps(["Fortified"]),
         "my_mount": "Ashes of Al'ar"},
        {"dungeon_name": "City of Threads", "key_level": 14, "result": "timed",
         "duration_seconds": 1700, "time_limit_seconds": 1800, "upgrade_count": 1,
         "deaths": 3, "vibe": "sweaty",
         "started_at": datetime(2024, 3, 16, 9, 0),
         "affixes": json.dumps(["Tyrannical"])},
    ]

    created_runs = []
    for rd in runs_data:
        run = Run(season="midnight-1", source="addon", **rd)
        session.add(run)
        session.commit()
        session.refresh(run)
        created_runs.append(run)

        m1 = RunMember(run_id=run.id, character_id=char.id,
                       spec="Restoration", role="healer", was_me=True, ilvl=623.0)
        m2 = RunMember(run_id=run.id, character_id=char2.id,
                       spec="Fire", role="dps", was_me=False, ilvl=615.0)
        session.add(m1)
        session.add(m2)

    session.commit()
    return created_runs


@pytest.fixture
def sample_lua_file():
    """Create a temp file with valid addon SavedVariables data."""
    content = '''
MythicPlusTrackerDB = {
    ["version"] = 1,
    ["runs"] = {
        {
            ["runId"] = "test-import-1",
            ["dungeon"] = "Ara-Kara, City of Echoes",
            ["keyLevel"] = 15,
            ["timed"] = true,
            ["completed"] = true,
            ["durationSeconds"] = 1500,
            ["timeLimitSeconds"] = 1800,
            ["upgradeCount"] = 2,
            ["deaths"] = 1,
            ["startTime"] = 1711234567,
            ["endTime"] = 1711236067,
            ["affixes"] = { "Fortified", "Bursting" },
            ["goldBefore"] = 100000000,
            ["goldAfter"] = 99950000,
            ["durabilityBefore"] = 95.5,
            ["durabilityAfter"] = 42.3,
            ["companionPet"] = "Lil Ragnaros",
            ["myMount"] = "Invincible",
            ["playedBefore"] = 100000,
            ["playedAfter"] = 101523,
            ["season"] = "midnight-1",
            ["buffCheck"] = {
                ["flask"] = { "Testplayer", "Tankfriend" },
                ["food"] = { "Testplayer" },
                ["rune"] = {},
            },
            ["members"] = {
                {
                    ["name"] = "Testplayer",
                    ["realm"] = "Stormrage",
                    ["class"] = "DRUID",
                    ["race"] = "NightElf",
                    ["spec"] = "Restoration",
                    ["role"] = "HEALER",
                    ["ilvl"] = 623,
                    ["guild"] = "Test Guild",
                    ["title"] = "the Undying",
                    ["mount"] = "Invincible",
                    ["isMe"] = true,
                },
                {
                    ["name"] = "Tankfriend",
                    ["realm"] = "Stormrage",
                    ["class"] = "WARRIOR",
                    ["race"] = "DarkIronDwarf",
                    ["spec"] = "Protection",
                    ["role"] = "TANK",
                    ["ilvl"] = 618,
                    ["guild"] = "Test Guild",
                    ["mount"] = "Swift Spectral Tiger",
                    ["isMe"] = false,
                },
            },
        },
        {
            ["runId"] = "test-import-2",
            ["dungeon"] = "City of Threads",
            ["keyLevel"] = 12,
            ["timed"] = false,
            ["completed"] = true,
            ["durationSeconds"] = 1900,
            ["timeLimitSeconds"] = 1740,
            ["deaths"] = 7,
            ["startTime"] = 1711240000,
            ["endTime"] = 1711241900,
            ["affixes"] = { "Tyrannical" },
            ["season"] = "midnight-1",
            ["members"] = {
                {
                    ["name"] = "Testplayer",
                    ["realm"] = "Stormrage",
                    ["class"] = "DRUID",
                    ["race"] = "NightElf",
                    ["spec"] = "Restoration",
                    ["role"] = "HEALER",
                    ["isMe"] = true,
                },
            },
        },
    },
}
'''
    with tempfile.NamedTemporaryFile(mode='w', suffix='.lua', delete=False) as f:
        f.write(content)
        return f.name
