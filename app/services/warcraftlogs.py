"""
Warcraft Logs API v2 integration.
Uses OAuth2 client credentials + GraphQL to fetch M+ run data.
"""

import httpx
from datetime import datetime, timedelta
from sqlmodel import Session, select
from app.config import WCL_CLIENT_ID, WCL_CLIENT_SECRET, DEFAULT_CHARACTER
from app.models import WarcraftLogsToken, Run, RunMember, Character

WCL_TOKEN_URL = "https://www.warcraftlogs.com/oauth/token"
WCL_API_URL = "https://www.warcraftlogs.com/api/v2/client"


def is_configured() -> bool:
    return bool(WCL_CLIENT_ID and WCL_CLIENT_SECRET)


async def _get_access_token(session: Session) -> str | None:
    """Get a valid access token, refreshing if needed."""
    token = session.exec(select(WarcraftLogsToken)).first()
    if token and token.expires_at > datetime.utcnow():
        return token.access_token

    if not is_configured():
        return None

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            WCL_TOKEN_URL,
            data={"grant_type": "client_credentials"},
            auth=(WCL_CLIENT_ID, WCL_CLIENT_SECRET),
        )
        if resp.status_code != 200:
            return None

        data = resp.json()
        access_token = data["access_token"]
        expires_in = data.get("expires_in", 86400)

        # Store token
        if token:
            token.access_token = access_token
            token.expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        else:
            token = WarcraftLogsToken(
                access_token=access_token,
                expires_at=datetime.utcnow() + timedelta(seconds=expires_in),
            )
        session.add(token)
        session.commit()
        return access_token


async def _graphql_query(session: Session, query: str, variables: dict = None) -> dict | None:
    """Execute a GraphQL query against the WCL API."""
    token = await _get_access_token(session)
    if not token:
        return None

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            WCL_API_URL,
            json={"query": query, "variables": variables or {}},
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code == 200:
            return resp.json()
    return None


# GraphQL query to get recent M+ reports for a character
RECENT_REPORTS_QUERY = """
query ($name: String!, $server: String!, $region: String!) {
  characterData {
    character(name: $name, serverSlug: $server, serverRegion: $region) {
      name
      classID
      recentReports(limit: 15) {
        data {
          code
          title
          startTime
          endTime
          zone {
            name
          }
          fights(killType: Encounters) {
            id
            name
            keystoneLevel
            keystoneTime
            keystoneBonus
            startTime
            endTime
            kill
            friendlyPlayers
          }
        }
      }
    }
  }
}
"""

# Query to get player details for a specific fight in a report
FIGHT_DETAILS_QUERY = """
query ($code: String!, $fightIDs: [Int!]!) {
  reportData {
    report(code: $code) {
      playerDetails(fightIDs: $fightIDs)
      table(dataType: DamageDone, fightIDs: $fightIDs)
      fights(fightIDs: $fightIDs) {
        id
        keystoneLevel
        keystoneTime
        keystoneAffixes
        startTime
        endTime
        kill
      }
    }
  }
}
"""

HEALING_TABLE_QUERY = """
query ($code: String!, $fightIDs: [Int!]!) {
  reportData {
    report(code: $code) {
      table(dataType: Healing, fightIDs: $fightIDs)
    }
  }
}
"""


def _find_or_create_character(session: Session, name: str, realm: str, class_name: str = None) -> Character:
    char = session.exec(
        select(Character).where(
            Character.name == name,
            Character.realm == realm,
        )
    ).first()
    if not char:
        char = Character(name=name, realm=realm, region="us", class_name=class_name)
        session.add(char)
        session.commit()
        session.refresh(char)
    return char


async def import_from_warcraftlogs(
    session: Session,
    char_name: str = None,
    char_realm: str = None,
    char_region: str = None,
) -> dict:
    """
    Import recent M+ runs from Warcraft Logs.
    Returns { "imported": int, "enriched": int, "skipped": int, "errors": list[str] }
    """
    result = {"imported": 0, "enriched": 0, "skipped": 0, "errors": []}

    name = char_name or DEFAULT_CHARACTER["name"]
    realm = char_realm or DEFAULT_CHARACTER["realm"]
    region = char_region or DEFAULT_CHARACTER["region"]

    # Fetch recent reports
    data = await _graphql_query(session, RECENT_REPORTS_QUERY, {
        "name": name,
        "server": realm.lower().replace(" ", "-").replace("'", ""),
        "region": region.upper(),
    })

    if not data:
        result["errors"].append("Failed to fetch data from Warcraft Logs API")
        return result

    if "errors" in data:
        for err in data["errors"]:
            result["errors"].append(err.get("message", str(err)))
        return result

    char_data = data.get("data", {}).get("characterData", {}).get("character")
    if not char_data:
        result["errors"].append(f"Character {name}-{realm} not found on Warcraft Logs")
        return result

    reports = char_data.get("recentReports", {}).get("data", [])

    for report in reports:
        report_code = report.get("code", "")
        fights = report.get("fights", [])

        for fight in fights:
            keystone_level = fight.get("keystoneLevel")
            if not keystone_level or keystone_level < 2:
                continue  # Not an M+ fight

            fight_id = fight.get("id")
            dungeon_name = fight.get("name", "Unknown")
            keystone_time = fight.get("keystoneTime")  # milliseconds
            keystone_bonus = fight.get("keystoneBonus", 0)
            is_kill = fight.get("kill", False)

            # Check for existing import by WCL report+fight
            existing = session.exec(
                select(Run).where(
                    Run.wcl_report_id == report_code,
                    Run.wcl_fight_id == fight_id,
                )
            ).first()

            if existing:
                # Try to enrich with DPS/HPS if not already done
                if not any_members_have_stats(session, existing.id):
                    await _enrich_run(session, existing, report_code, fight_id, fight)
                    result["enriched"] += 1
                else:
                    result["skipped"] += 1
                continue

            # Also check for matching addon-imported run (by timestamp + dungeon)
            fight_start = fight.get("startTime")  # epoch ms
            if fight_start:
                fight_start_dt = datetime.utcfromtimestamp(fight_start / 1000)
                # Look for runs within 5 minutes
                window_start = fight_start_dt - timedelta(minutes=5)
                window_end = fight_start_dt + timedelta(minutes=5)
                match = session.exec(
                    select(Run).where(
                        Run.dungeon_name == dungeon_name,
                        Run.key_level == keystone_level,
                        Run.started_at >= window_start,
                        Run.started_at <= window_end,
                    )
                ).first()
                if match:
                    match.wcl_report_id = report_code
                    match.wcl_fight_id = fight_id
                    session.add(match)
                    session.commit()
                    await _enrich_run(session, match, report_code, fight_id, fight)
                    result["enriched"] += 1
                    continue

            # Create new run from WCL data
            duration_seconds = None
            if keystone_time:
                duration_seconds = int(keystone_time / 1000)

            timed = is_kill and keystone_bonus > 0
            run_result = "timed" if timed else ("completed" if is_kill else "depleted")

            started_at = None
            completed_at = None
            if fight.get("startTime"):
                started_at = datetime.utcfromtimestamp(fight["startTime"] / 1000)
            if fight.get("endTime"):
                completed_at = datetime.utcfromtimestamp(fight["endTime"] / 1000)

            run = Run(
                dungeon_name=dungeon_name,
                key_level=keystone_level,
                result=run_result,
                duration_seconds=duration_seconds,
                upgrade_count=keystone_bonus if timed else None,
                started_at=started_at,
                completed_at=completed_at,
                season="midnight-1",
                wcl_report_id=report_code,
                wcl_fight_id=fight_id,
                source="warcraftlogs",
            )
            session.add(run)
            session.commit()
            session.refresh(run)

            # Fetch and add player details
            await _enrich_run(session, run, report_code, fight_id, fight)
            result["imported"] += 1

    return result


def any_members_have_stats(session: Session, run_id: int) -> bool:
    """Check if any run members already have DPS/HPS data."""
    member = session.exec(
        select(RunMember).where(
            RunMember.run_id == run_id,
            RunMember.dps.isnot(None),
        )
    ).first()
    return member is not None


async def _enrich_run(session: Session, run: Run, report_code: str, fight_id: int, fight_data: dict):
    """Fetch DPS/HPS data from WCL and update run members."""
    # Get damage table
    damage_data = await _graphql_query(session, FIGHT_DETAILS_QUERY, {
        "code": report_code,
        "fightIDs": [fight_id],
    })

    if not damage_data or "errors" in damage_data:
        return

    report = damage_data.get("data", {}).get("reportData", {}).get("report", {})

    # Parse player details
    player_details = report.get("playerDetails", {})
    if isinstance(player_details, dict):
        player_details = player_details.get("data", {})

    # Parse damage table
    damage_table = report.get("table", {})
    if isinstance(damage_table, dict):
        damage_table = damage_table.get("data", {})
    damage_entries = damage_table.get("entries", []) if isinstance(damage_table, dict) else []

    # Get fight duration for DPS calc
    fights = report.get("fights", [])
    fight_duration = None
    if fights:
        f = fights[0]
        if f.get("startTime") and f.get("endTime"):
            fight_duration = (f["endTime"] - f["startTime"]) / 1000  # seconds

    # Get healing table
    healing_data = await _graphql_query(session, HEALING_TABLE_QUERY, {
        "code": report_code,
        "fightIDs": [fight_id],
    })
    healing_entries = []
    if healing_data and "data" in healing_data:
        ht = healing_data["data"].get("reportData", {}).get("report", {}).get("table", {})
        if isinstance(ht, dict):
            ht = ht.get("data", {})
        healing_entries = ht.get("entries", []) if isinstance(ht, dict) else []

    # Build DPS/HPS lookup by player name
    dps_map = {}
    for entry in damage_entries:
        player_name = entry.get("name", "")
        total_damage = entry.get("total", 0)
        if fight_duration and fight_duration > 0:
            dps_map[player_name] = round(total_damage / fight_duration, 1)

    hps_map = {}
    for entry in healing_entries:
        player_name = entry.get("name", "")
        total_healing = entry.get("total", 0)
        if fight_duration and fight_duration > 0:
            hps_map[player_name] = round(total_healing / fight_duration, 1)

    # Parse player roles/specs from playerDetails
    player_info = {}
    if isinstance(player_details, dict):
        for role_group in ["tanks", "healers", "dps"]:
            role_name = "tank" if role_group == "tanks" else ("healer" if role_group == "healers" else "dps")
            for player in player_details.get(role_group, []):
                pname = player.get("name", "")
                player_info[pname] = {
                    "role": role_name,
                    "spec": player.get("specs", [None])[0] if player.get("specs") else None,
                    "class": player.get("type", ""),
                    "server": player.get("server", ""),
                }

    # Get existing members for this run
    existing_members = session.exec(
        select(RunMember).where(RunMember.run_id == run.id)
    ).all()

    if existing_members:
        # Update existing members with DPS/HPS
        for member in existing_members:
            char = session.get(Character, member.character_id)
            if char and char.name in dps_map:
                member.dps = dps_map[char.name]
            if char and char.name in hps_map:
                member.hps = hps_map[char.name]
            session.add(member)
    else:
        # Create members from WCL player data
        for pname, info in player_info.items():
            server = info.get("server", "Unknown")
            char = _find_or_create_character(session, pname, server, info.get("class"))

            is_me = (pname.lower() == DEFAULT_CHARACTER["name"].lower())

            member = RunMember(
                run_id=run.id,
                character_id=char.id,
                spec=info.get("spec"),
                role=info.get("role", "dps"),
                was_me=is_me,
                dps=dps_map.get(pname),
                hps=hps_map.get(pname),
            )
            session.add(member)

    session.commit()
