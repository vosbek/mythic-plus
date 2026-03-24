import httpx
from datetime import datetime, timedelta
from sqlmodel import Session, select
from app.config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI
from app.models import SpotifyToken, RunSong

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_URL = "https://api.spotify.com/v1"
SCOPES = "user-read-currently-playing user-read-playback-state"

# In-memory tracking state
_tracking_run_id: int | None = None


def get_auth_url() -> str:
    params = {
        "client_id": SPOTIFY_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "scope": SCOPES,
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{SPOTIFY_AUTH_URL}?{query}"


async def exchange_code(code: str, session: Session) -> bool:
    async with httpx.AsyncClient() as client:
        resp = await client.post(SPOTIFY_TOKEN_URL, data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": SPOTIFY_REDIRECT_URI,
            "client_id": SPOTIFY_CLIENT_ID,
            "client_secret": SPOTIFY_CLIENT_SECRET,
        })
        if resp.status_code != 200:
            return False
        data = resp.json()
        # Remove old tokens
        old = session.exec(select(SpotifyToken)).all()
        for t in old:
            session.delete(t)
        token = SpotifyToken(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=datetime.utcnow() + timedelta(seconds=data["expires_in"]),
        )
        session.add(token)
        session.commit()
        return True


async def refresh_access_token(session: Session) -> str | None:
    token = session.exec(select(SpotifyToken)).first()
    if not token:
        return None
    if token.expires_at > datetime.utcnow():
        return token.access_token

    async with httpx.AsyncClient() as client:
        resp = await client.post(SPOTIFY_TOKEN_URL, data={
            "grant_type": "refresh_token",
            "refresh_token": token.refresh_token,
            "client_id": SPOTIFY_CLIENT_ID,
            "client_secret": SPOTIFY_CLIENT_SECRET,
        })
        if resp.status_code != 200:
            return None
        data = resp.json()
        token.access_token = data["access_token"]
        token.expires_at = datetime.utcnow() + timedelta(seconds=data["expires_in"])
        if "refresh_token" in data:
            token.refresh_token = data["refresh_token"]
        session.add(token)
        session.commit()
        return token.access_token


async def get_currently_playing(session: Session) -> dict | None:
    access_token = await refresh_access_token(session)
    if not access_token:
        return None
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{SPOTIFY_API_URL}/me/player/currently-playing",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if resp.status_code == 200 and resp.text:
            return resp.json()
    return None


async def capture_current_track(session: Session, run_id: int) -> RunSong | None:
    data = await get_currently_playing(session)
    if not data or not data.get("item") or not data.get("is_playing"):
        return None

    item = data["item"]
    track_name = item.get("name", "Unknown")
    artists = item.get("artists", [])
    artist_name = ", ".join(a["name"] for a in artists) if artists else "Unknown"
    album_name = item.get("album", {}).get("name")
    spotify_uri = item.get("uri")

    # Don't duplicate if same song still playing
    existing = session.exec(
        select(RunSong).where(
            RunSong.run_id == run_id,
            RunSong.spotify_uri == spotify_uri,
        )
    ).first()
    if existing:
        return None

    song = RunSong(
        run_id=run_id,
        track_name=track_name,
        artist_name=artist_name,
        album_name=album_name,
        spotify_uri=spotify_uri,
        played_at=datetime.utcnow(),
    )
    session.add(song)
    session.commit()
    session.refresh(song)
    return song


def start_tracking(run_id: int):
    global _tracking_run_id
    _tracking_run_id = run_id


def stop_tracking():
    global _tracking_run_id
    _tracking_run_id = None


def get_tracking_run_id() -> int | None:
    return _tracking_run_id


def is_configured() -> bool:
    return bool(SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET)
