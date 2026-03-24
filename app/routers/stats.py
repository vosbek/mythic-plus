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
    get_affix_stats,
    get_lucky_mount,
    get_lucky_pet,
    get_time_margin_stats,
    get_buff_compliance_stats,
    get_gold_stats,
    get_role_stats,
    get_ilvl_analysis,
    get_dungeon_tier_list,
    get_guild_stats,
    get_rating_analysis,
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
        affixes = get_affix_stats(session)
        lucky_mount = get_lucky_mount(session)
        lucky_pet = get_lucky_pet(session)
        time_margins = get_time_margin_stats(session)
        buff_compliance = get_buff_compliance_stats(session)
        gold = get_gold_stats(session)
        role_stats = get_role_stats(session)
        ilvl = get_ilvl_analysis(session)
        tier_list = get_dungeon_tier_list(session)
        guilds = get_guild_stats(session)
        ratings = get_rating_analysis(session)

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
        "affixes": affixes,
        "lucky_mount": lucky_mount,
        "lucky_pet": lucky_pet,
        "time_margins": time_margins,
        "buff_compliance": buff_compliance,
        "gold": gold,
        "role_stats": role_stats,
        "ilvl": ilvl,
        "tier_list": tier_list,
        "guilds": guilds,
        "ratings": ratings,
    })
