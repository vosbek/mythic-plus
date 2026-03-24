from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from app.database import engine
from app.models import SpotifyToken, RunSong, Run
from app.services import spotify as spotify_service

router = APIRouter(prefix="/spotify", tags=["spotify"])
templates = Jinja2Templates(directory="app/templates")


@router.get("")
async def spotify_page(request: Request):
    with Session(engine) as session:
        token = session.exec(select(SpotifyToken)).first()
        connected = token is not None

        # Get current tracking state
        tracking_run_id = spotify_service.get_tracking_run_id()
        tracking_run = None
        if tracking_run_id:
            tracking_run = session.get(Run, tracking_run_id)

        # Get recent songs
        recent_songs = session.exec(
            select(RunSong).order_by(RunSong.played_at.desc()).limit(20)
        ).all()

    return templates.TemplateResponse("spotify/index.html", {
        "request": request,
        "connected": connected,
        "configured": spotify_service.is_configured(),
        "auth_url": spotify_service.get_auth_url() if spotify_service.is_configured() else None,
        "tracking_run": tracking_run,
        "recent_songs": recent_songs,
    })


@router.get("/callback")
async def spotify_callback(request: Request, code: str = ""):
    if not code:
        return RedirectResponse("/spotify")
    with Session(engine) as session:
        success = await spotify_service.exchange_code(code, session)
    return RedirectResponse("/spotify")


@router.post("/track/start/{run_id}")
async def start_tracking(run_id: int):
    spotify_service.start_tracking(run_id)
    return RedirectResponse(f"/runs/{run_id}", status_code=303)


@router.post("/track/stop")
async def stop_tracking():
    spotify_service.stop_tracking()
    return RedirectResponse("/spotify", status_code=303)


@router.post("/track/capture")
async def capture_now():
    """Manually capture the currently playing track for the active run."""
    run_id = spotify_service.get_tracking_run_id()
    if not run_id:
        return RedirectResponse("/spotify", status_code=303)

    with Session(engine) as session:
        await spotify_service.capture_current_track(session, run_id)

    return RedirectResponse(f"/runs/{run_id}", status_code=303)
