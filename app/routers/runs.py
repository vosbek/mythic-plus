from datetime import datetime
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from app.database import get_session, engine
from app.models import Run, RunMember, Character, Dungeon
from app.config import RESULTS, VIBES, WOW_CLASSES, ROLES

router = APIRouter(prefix="/runs", tags=["runs"])
templates = Jinja2Templates(directory="app/templates")


@router.get("")
async def list_runs(
    request: Request,
    dungeon: str = "",
    result: str = "",
    min_key: int = 0,
):
    with Session(engine) as session:
        query = select(Run).order_by(Run.created_at.desc())
        if dungeon:
            query = query.where(Run.dungeon_name == dungeon)
        if result:
            query = query.where(Run.result == result)
        if min_key:
            query = query.where(Run.key_level >= min_key)
        runs = session.exec(query).all()
        dungeons = session.exec(select(Dungeon).order_by(Dungeon.name)).all()

    return templates.TemplateResponse("runs/list.html", {
        "request": request,
        "runs": runs,
        "dungeons": dungeons,
        "filter_dungeon": dungeon,
        "filter_result": result,
        "filter_min_key": min_key,
        "results": RESULTS,
    })


@router.get("/new")
async def new_run_form(request: Request):
    with Session(engine) as session:
        dungeons = session.exec(select(Dungeon).order_by(Dungeon.name)).all()
        characters = session.exec(
            select(Character).order_by(Character.name)
        ).all()

    return templates.TemplateResponse("runs/form.html", {
        "request": request,
        "dungeons": dungeons,
        "results": RESULTS,
        "vibes": VIBES,
        "wow_classes": WOW_CLASSES,
        "roles": ROLES,
        "characters": characters,
    })


@router.post("/new")
async def create_run(
    request: Request,
    dungeon_name: str = Form(...),
    key_level: int = Form(...),
    result: str = Form(...),
    duration_minutes: int = Form(0),
    duration_seconds: int = Form(0),
    deaths: int = Form(0),
    upgrade_count: int = Form(0),
    notes: str = Form(""),
    rating: int = Form(0),
    vibe: str = Form(""),
    started_hour: int = Form(-1),
    started_minute: int = Form(0),
    affixes: str = Form(""),
    my_mount: str = Form(""),
    companion_pet: str = Form(""),
):
    total_seconds = duration_minutes * 60 + duration_seconds if duration_minutes else None

    # Build started_at from today + hour/minute if provided
    started_at = None
    if started_hour >= 0:
        now = datetime.now()
        started_at = now.replace(hour=started_hour, minute=started_minute, second=0, microsecond=0)

    # Parse affixes
    import json as _json
    affixes_json = None
    if affixes.strip():
        affix_list = [a.strip() for a in affixes.split(",") if a.strip()]
        affixes_json = _json.dumps(affix_list)

    with Session(engine) as session:
        # Get dungeon time limit
        dungeon = session.exec(
            select(Dungeon).where(Dungeon.name == dungeon_name)
        ).first()
        time_limit = dungeon.time_limit_seconds if dungeon else None

        run = Run(
            dungeon_name=dungeon_name,
            key_level=key_level,
            result=result,
            duration_seconds=total_seconds,
            time_limit_seconds=time_limit,
            upgrade_count=upgrade_count if result == "timed" else None,
            deaths=deaths,
            started_at=started_at,
            completed_at=datetime.utcnow(),
            affixes=affixes_json,
            notes=notes if notes else None,
            rating=rating if rating else None,
            vibe=vibe if vibe else None,
            my_mount=my_mount if my_mount else None,
            companion_pet=companion_pet if companion_pet else None,
            source="manual",
        )
        session.add(run)
        session.commit()
        session.refresh(run)

        # Process group members from form data
        form_data = await request.form()
        for i in range(5):
            member_name = form_data.get(f"member_{i}_name", "").strip()
            if not member_name:
                continue

            member_realm = form_data.get(f"member_{i}_realm", "").strip() or "Unknown"
            member_class = form_data.get(f"member_{i}_class", "").strip()
            member_spec = form_data.get(f"member_{i}_spec", "").strip()
            member_role = form_data.get(f"member_{i}_role", "").strip()
            member_is_me = form_data.get(f"member_{i}_is_me") == "on"

            # Find or create character
            char = session.exec(
                select(Character).where(
                    Character.name == member_name,
                    Character.realm == member_realm,
                )
            ).first()
            if not char:
                char = Character(
                    name=member_name,
                    realm=member_realm,
                    region="us",
                    class_name=member_class or None,
                    spec=member_spec or None,
                    role=member_role or None,
                )
                session.add(char)
                session.commit()
                session.refresh(char)
            else:
                # Update class/spec if provided and not set
                if member_class and not char.class_name:
                    char.class_name = member_class
                if member_spec:
                    char.spec = member_spec
                if member_role:
                    char.role = member_role
                session.add(char)
                session.commit()

            run_member = RunMember(
                run_id=run.id,
                character_id=char.id,
                spec=member_spec or None,
                role=member_role or None,
                was_me=member_is_me,
            )
            session.add(run_member)

        session.commit()
        run_id = run.id

    return RedirectResponse(f"/runs/{run_id}", status_code=303)


@router.get("/{run_id}")
async def run_detail(request: Request, run_id: int):
    with Session(engine) as session:
        run = session.get(Run, run_id)
        if not run:
            return templates.TemplateResponse("runs/detail.html", {
                "request": request, "run": None,
            })

        members = session.exec(
            select(RunMember).where(RunMember.run_id == run_id)
        ).all()

        # Load character info for each member
        member_data = []
        for m in members:
            char = session.get(Character, m.character_id)
            member_data.append({"member": m, "character": char})

        from app.models import RunSong
        songs = session.exec(
            select(RunSong).where(RunSong.run_id == run_id).order_by(RunSong.played_at)
        ).all()

    # Format duration
    duration_str = None
    if run.duration_seconds:
        mins = run.duration_seconds // 60
        secs = run.duration_seconds % 60
        duration_str = f"{mins}:{secs:02d}"

    # Parse affixes JSON
    import json
    affixes = []
    if run.affixes:
        try:
            affixes = json.loads(run.affixes)
        except (json.JSONDecodeError, TypeError):
            pass

    # Parse buffs JSON
    buffs = None
    if run.buffs_json:
        try:
            buffs = json.loads(run.buffs_json)
        except (json.JSONDecodeError, TypeError):
            pass

    # Calculate time margin
    time_margin = None
    if run.duration_seconds and run.time_limit_seconds:
        time_margin = run.time_limit_seconds - run.duration_seconds

    return templates.TemplateResponse("runs/detail.html", {
        "request": request,
        "run": run,
        "member_data": member_data,
        "songs": songs,
        "duration_str": duration_str,
        "affixes": affixes,
        "buffs": buffs,
        "time_margin": time_margin,
    })


@router.get("/search/characters")
async def search_characters(q: str = ""):
    """HTMX endpoint for character autocomplete."""
    if len(q) < 2:
        return ""
    with Session(engine) as session:
        chars = session.exec(
            select(Character)
            .where(Character.name.ilike(f"%{q}%"))
            .limit(10)
        ).all()

    html = ""
    for c in chars:
        html += f'<option value="{c.name}" data-realm="{c.realm}" data-class="{c.class_name or ""}" data-role="{c.role or ""}">{c.name}-{c.realm}</option>'
    return html
