from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select, func
from app.database import engine
from app.models import Character, RunMember, Run
from app.services.raiderio import update_character_from_raiderio, fetch_character_profile

router = APIRouter(prefix="/characters", tags=["characters"])
templates = Jinja2Templates(directory="app/templates")


@router.get("")
async def list_characters(request: Request, q: str = ""):
    with Session(engine) as session:
        query = select(Character).order_by(Character.name)
        if q:
            query = query.where(Character.name.ilike(f"%{q}%"))
        characters = session.exec(query).all()

    return templates.TemplateResponse("characters/profile.html", {
        "request": request,
        "characters": characters,
        "selected": None,
        "search": q,
        "rio_data": None,
        "run_count": 0,
        "timed_count": 0,
    })


@router.get("/{char_id}")
async def character_detail(request: Request, char_id: int):
    with Session(engine) as session:
        char = session.get(Character, char_id)
        if not char:
            return RedirectResponse("/characters")

        # Update from Raider.IO if stale (>1 hour) or never fetched
        from datetime import datetime, timedelta
        if not char.raiderio_last_fetched or \
           datetime.utcnow() - char.raiderio_last_fetched > timedelta(hours=1):
            char = await update_character_from_raiderio(session, char)

        # Get run stats for this character
        run_count = session.exec(
            select(func.count(RunMember.id)).where(RunMember.character_id == char_id)
        ).one()
        timed_count = session.exec(
            select(func.count(RunMember.id))
            .join(Run, RunMember.run_id == Run.id)
            .where(RunMember.character_id == char_id, Run.result == "timed")
        ).one()

        # Get full raider.io data for display
        rio_data = await fetch_character_profile(char.name, char.realm, char.region)

        characters = session.exec(select(Character).order_by(Character.name)).all()

    return templates.TemplateResponse("characters/profile.html", {
        "request": request,
        "characters": characters,
        "selected": char,
        "rio_data": rio_data,
        "run_count": run_count,
        "timed_count": timed_count,
        "search": "",
    })


@router.get("/lookup/{region}/{realm}/{name}")
async def lookup_character(request: Request, region: str, realm: str, name: str):
    """Look up a character and add to DB if not exists."""
    with Session(engine) as session:
        char = session.exec(
            select(Character).where(
                Character.name == name,
                Character.realm == realm,
                Character.region == region,
            )
        ).first()

        if not char:
            char = Character(name=name, realm=realm, region=region)
            session.add(char)
            session.commit()
            session.refresh(char)

        char = await update_character_from_raiderio(session, char)

    return RedirectResponse(f"/characters/{char.id}", status_code=303)
