from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session
from app.database import engine
from app.config import DEFAULT_CHARACTER
from app.services import warcraftlogs as wcl_service

router = APIRouter(prefix="/import", tags=["import"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/warcraftlogs")
async def wcl_import_page(
    request: Request,
    imported: int = 0,
    enriched: int = 0,
    skipped: int = 0,
    error: str = "",
):
    return templates.TemplateResponse("import/warcraftlogs.html", {
        "request": request,
        "configured": wcl_service.is_configured(),
        "character": DEFAULT_CHARACTER,
        "imported": imported,
        "enriched": enriched,
        "skipped": skipped,
        "error": error,
    })


@router.post("/warcraftlogs")
async def do_wcl_import(
    request: Request,
    char_name: str = Form(""),
    char_realm: str = Form(""),
):
    name = char_name.strip() or None
    realm = char_realm.strip() or None

    with Session(engine) as session:
        result = await wcl_service.import_from_warcraftlogs(
            session,
            char_name=name,
            char_realm=realm,
        )

    errors = "; ".join(result["errors"]) if result["errors"] else ""
    return RedirectResponse(
        f"/import/warcraftlogs?imported={result['imported']}&enriched={result['enriched']}"
        f"&skipped={result['skipped']}&error={errors}",
        status_code=303,
    )
