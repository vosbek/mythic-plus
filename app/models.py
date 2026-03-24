from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship


class Dungeon(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    short_name: str
    time_limit_seconds: int
    season: str


class Character(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    realm: str
    region: str = "us"
    class_name: Optional[str] = None
    spec: Optional[str] = None
    role: Optional[str] = None
    raiderio_score: Optional[float] = None
    raiderio_last_fetched: Optional[datetime] = None
    is_mine: bool = False

    run_memberships: list["RunMember"] = Relationship(back_populates="character")

    class Config:
        unique_together = ("name", "realm", "region")


class Run(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    dungeon_name: str = Field(index=True)
    key_level: int
    result: str  # timed, completed, depleted, abandoned
    duration_seconds: Optional[int] = None
    time_limit_seconds: Optional[int] = None
    upgrade_count: Optional[int] = None  # 0-3 stars
    deaths: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    season: str = "midnight-1"
    affixes: Optional[str] = None  # JSON string
    notes: Optional[str] = None
    rating: Optional[int] = None  # 1-5
    vibe: Optional[str] = None  # chill, sweaty, chaotic, tilting, cracked
    created_at: datetime = Field(default_factory=datetime.utcnow)

    members: list["RunMember"] = Relationship(back_populates="run")
    songs: list["RunSong"] = Relationship(back_populates="run")


class RunMember(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="run.id")
    character_id: int = Field(foreign_key="character.id")
    spec: Optional[str] = None
    role: Optional[str] = None
    was_me: bool = False

    run: Optional[Run] = Relationship(back_populates="members")
    character: Optional[Character] = Relationship(back_populates="run_memberships")


class RunSong(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="run.id")
    track_name: str
    artist_name: str
    album_name: Optional[str] = None
    spotify_uri: Optional[str] = None
    played_at: Optional[datetime] = None

    run: Optional[Run] = Relationship(back_populates="songs")


class SpotifyToken(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    access_token: str
    refresh_token: str
    expires_at: datetime
