from sqlmodel import SQLModel, Session, create_engine, select
from app.config import DATABASE_URL, DUNGEONS, DEFAULT_CHARACTER
from app.models import Dungeon, Character

engine = create_engine(DATABASE_URL, echo=False)


def init_db():
    SQLModel.metadata.create_all(engine)
    seed_dungeons()
    seed_default_character()


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
