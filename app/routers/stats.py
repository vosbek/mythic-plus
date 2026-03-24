from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from sqlmodel import Session
from app.database import engine
from app.services.analytics import (
    get_overview_stats,
    get_nemesis_dungeon,
    get_best_dungeon,
    get_streaks,
    get_vibe_stats,
    get_group_chemistry,
    get_lucky_song,
    get_time_of_day_stats,
    get_weekly_vault,
)

router = APIRouter(prefix="/stats", tags=["stats"])
templates = Jinja2Templates(directory="app/templates")


@router.get("")
async def stats_page(request: Request):
    with Session(engine) as session:
        overview = get_overview_stats(session)
        nemesis = get_nemesis_dungeon(session)
        best = get_best_dungeon(session)
        streaks = get_streaks(session)
        vibes = get_vibe_stats(session)
        chemistry = get_group_chemistry(session)
        lucky_song = get_lucky_song(session)
        time_of_day = get_time_of_day_stats(session)
        vault = get_weekly_vault(session)

    return templates.TemplateResponse("stats/overview.html", {
        "request": request,
        "overview": overview,
        "nemesis": nemesis,
        "best": best,
        "streaks": streaks,
        "vibes": vibes,
        "chemistry": chemistry,
        "lucky_song": lucky_song,
        "time_of_day": time_of_day,
        "vault": vault,
    })
