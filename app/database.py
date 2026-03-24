import sqlite3
from sqlmodel import SQLModel, Session, create_engine, select
from app.config import DATABASE_URL, DUNGEONS, DEFAULT_CHARACTER
from app.models import Dungeon, Character

engine = create_engine(DATABASE_URL, echo=False)


def init_db():
    SQLModel.metadata.create_all(engine)
    _migrate_columns()
    seed_dungeons()
    seed_default_character()


def _migrate_columns():
    """Add new columns to existing tables (idempotent)."""
    db_path = DATABASE_URL.replace("sqlite:///", "")
    try:
        conn = sqlite3.connect(db_path)
        migrations = [
            ("run", "addon_run_id", "TEXT"),
            ("run", "wcl_report_id", "TEXT"),
            ("run", "wcl_fight_id", "INTEGER"),
            ("run", "source", "TEXT"),
            ("run", "gold_before", "INTEGER"),
            ("run", "gold_after", "INTEGER"),
            ("run", "durability_before", "REAL"),
            ("run", "durability_after", "REAL"),
            ("run", "companion_pet", "TEXT"),
            ("run", "my_mount", "TEXT"),
            ("run", "played_seconds", "INTEGER"),
            ("run", "buffs_json", "TEXT"),
            ("runmember", "ilvl", "REAL"),
            ("runmember", "dps", "REAL"),
            ("runmember", "hps", "REAL"),
            ("runmember", "performance_score", "REAL"),
        ]
        for table, col, dtype in migrations:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {dtype}")
            except sqlite3.OperationalError:
                pass  # column already exists
        conn.commit()
        conn.close()
    except Exception:
        pass  # DB doesn't exist yet, create_all will handle it


def get_session():
    with Session(engine) as session:
        yield session


def seed_dungeons():
    with Session(engine) as session:
        existing = session.exec(select(Dungeon)).first()
        if existing:
            return
        for d in DUNGEONS:
            session.add(Dungeon(**d))
        session.commit()


def seed_default_character():
    with Session(engine) as session:
        existing = session.exec(
            select(Character).where(
                Character.name == DEFAULT_CHARACTER["name"],
                Character.realm == DEFAULT_CHARACTER["realm"],
                Character.region == DEFAULT_CHARACTER["region"],
            )
        ).first()
        if existing:
            return
        char = Character(
            name=DEFAULT_CHARACTER["name"],
            realm=DEFAULT_CHARACTER["realm"],
            region=DEFAULT_CHARACTER["region"],
            is_mine=True,
        )
        session.add(char)
        session.commit()
