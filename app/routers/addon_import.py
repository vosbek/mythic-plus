from pathlib import Path
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session
from app.database import engine
from app.config import WOW_SAVEDVARIABLES_PATH
from app.services.addon_import import import_addon_runs

router = APIRouter(prefix="/import", tags=["import"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/addon")
async def addon_import_page(
    request: Request,
    imported: int = 0,
    skipped: int = 0,
    error: str = "",
):
    return templates.TemplateResponse("import/addon.html", {
        "request": request,
        "default_path": WOW_SAVEDVARIABLES_PATH,
        "imported": imported,
        "skipped": skipped,
        "error": error,
    })


@router.post("/addon")
async def do_addon_import(
    request: Request,
    wow_path: str = Form(""),
):
    file_path = wow_path.strip() or WOW_SAVEDVARIABLES_PATH

    if not file_path:
        return RedirectResponse(
            "/import/addon?error=No+SavedVariables+path+configured.+Set+WOW_SAVEDVARIABLES_PATH+in+.env",
            status_code=303,
        )

    path = Path(file_path)
    if not path.exists():
        return RedirectResponse(
            f"/import/addon?error=File+not+found:+{file_path}",
            status_code=303,
        )

    with Session(engine) as session:
        result = import_addon_runs(session, str(path))

    errors = "; ".join(result["errors"]) if result["errors"] else ""
    return RedirectResponse(
        f"/import/addon?imported={result['imported']}&skipped={result['skipped']}&error={errors}",
        status_code=303,
    )
