import httpx
from datetime import datetime
from sqlmodel import Session
from app.config import RAIDERIO_BASE_URL
from app.models import Character


async def fetch_character_profile(name: str, realm: str, region: str = "us") -> dict | None:
    url = f"{RAIDERIO_BASE_URL}/characters/profile"
    params = {
        "region": region,
        "realm": realm,
        "name": name,
        "fields": "mythic_plus_scores_by_season:current,mythic_plus_best_runs,mythic_plus_recent_runs,gear,class,guild",
    }
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                return resp.json()
        except httpx.RequestError:
            pass
    return None


async def update_character_from_raiderio(session: Session, character: Character) -> Character:
    data = await fetch_character_profile(character.name, character.realm, character.region)
    if not data:
        return character

    character.class_name = data.get("class", character.class_name)
    character.race = data.get("race", character.race)
    character.spec = data.get("active_spec_name", character.spec)
    character.role = data.get("active_spec_role", character.role)
    if data.get("guild"):
        character.guild = data["guild"].get("name", character.guild)

    seasons = data.get("mythic_plus_scores_by_season", [])
    if seasons:
        scores = seasons[0].get("scores", {})
        character.raiderio_score = scores.get("all", 0)

    character.raiderio_last_fetched = datetime.utcnow()
    session.add(character)
    session.commit()
    session.refresh(character)
    return character
