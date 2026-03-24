from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.database import init_db
from app.routers import runs, characters, spotify, stats, addon_import, warcraftlogs


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Mythic+ Tracker", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")

app.include_router(runs.router)
app.include_router(characters.router)
app.include_router(spotify.router)
app.include_router(stats.router)
app.include_router(addon_import.router)
app.include_router(warcraftlogs.router)


@app.get("/")
async def home(request: Request):
    from sqlmodel import Session, select, func
    from app.database import engine
    from app.models import Run

    with Session(engine) as session:
        total_runs = session.exec(select(func.count(Run.id))).one()
        timed_runs = session.exec(
            select(func.count(Run.id)).where(Run.result == "timed")
        ).one()
        highest_key = session.exec(
            select(func.max(Run.key_level)).where(Run.result == "timed")
        ).one()
        recent_runs = session.exec(
            select(Run).order_by(Run.created_at.desc()).limit(5)
        ).all()

    timed_pct = round(timed_runs / total_runs * 100, 1) if total_runs > 0 else 0

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "total_runs": total_runs,
        "timed_pct": timed_pct,
        "highest_key": highest_key or 0,
        "recent_runs": recent_runs,
    })
