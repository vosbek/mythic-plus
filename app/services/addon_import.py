"""
Parse WoW SavedVariables .lua files and import M+ run data.

SavedVariables format is a strict subset of Lua:
  MythicPlusTrackerDB = { ["runs"] = { { ... }, { ... } }, ["version"] = 1 }

Values are strings, numbers, booleans, nil, or nested tables.
"""

import re
from datetime import datetime
from pathlib import Path
from sqlmodel import Session, select
from app.models import Run, RunMember, Character

# WoW class tokens to readable names
CLASS_TOKEN_MAP = {
    "DEATHKNIGHT": "Death Knight",
    "DEMONHUNTER": "Demon Hunter",
    "DRUID": "Druid",
    "EVOKER": "Evoker",
    "HUNTER": "Hunter",
    "MAGE": "Mage",
    "MONK": "Monk",
    "PALADIN": "Paladin",
    "PRIEST": "Priest",
    "ROGUE": "Rogue",
    "SHAMAN": "Shaman",
    "WARLOCK": "Warlock",
    "WARRIOR": "Warrior",
}

ROLE_MAP = {
    "TANK": "tank",
    "HEALER": "healer",
    "DAMAGER": "dps",
    "NONE": "dps",
}


# ---------------------------------------------------------------
# Lua table parser (recursive descent)
# ---------------------------------------------------------------

class LuaParser:
    """Parse WoW SavedVariables Lua table syntax into Python dicts/lists."""

    def __init__(self, text: str):
        self.text = text
        self.pos = 0

    def parse(self) -> dict:
        """Parse entire file, return dict of global variable assignments."""
        result = {}
        while self.pos < len(self.text):
            self._skip_whitespace_and_comments()
            if self.pos >= len(self.text):
                break
            # Look for: VarName = value
            match = re.match(r'([A-Za-z_]\w*)\s*=\s*', self.text[self.pos:])
            if match:
                var_name = match.group(1)
                self.pos += match.end()
                value = self._parse_value()
                result[var_name] = value
            else:
                self.pos += 1  # skip unrecognized chars
        return result

    def _skip_whitespace_and_comments(self):
        while self.pos < len(self.text):
            # Skip whitespace
            if self.text[self.pos] in ' \t\r\n':
                self.pos += 1
            # Skip single-line comments
            elif self.text[self.pos:self.pos + 2] == '--':
                if self.text[self.pos:self.pos + 4] == '--[[':
                    # Block comment
                    end = self.text.find(']]', self.pos + 4)
                    self.pos = end + 2 if end != -1 else len(self.text)
                else:
                    end = self.text.find('\n', self.pos)
                    self.pos = end + 1 if end != -1 else len(self.text)
            else:
                break

    def _parse_value(self):
        self._skip_whitespace_and_comments()
        if self.pos >= len(self.text):
            return None

        ch = self.text[self.pos]

        if ch == '{':
            return self._parse_table()
        elif ch == '"':
            return self._parse_string()
        elif ch == "'":
            return self._parse_single_string()
        elif self.text[self.pos:self.pos + 4] == 'true':
            self.pos += 4
            return True
        elif self.text[self.pos:self.pos + 5] == 'false':
            self.pos += 5
            return False
        elif self.text[self.pos:self.pos + 3] == 'nil':
            self.pos += 3
            return None
        elif ch == '-' or ch.isdigit():
            return self._parse_number()
        else:
            # Try to read as identifier (for unquoted string references)
            match = re.match(r'[A-Za-z_]\w*', self.text[self.pos:])
            if match:
                self.pos += match.end()
                return match.group(0)
            return None

    def _parse_table(self):
        self.pos += 1  # skip '{'
        items = {}
        array_index = 1
        is_array = True

        while True:
            self._skip_whitespace_and_comments()
            if self.pos >= len(self.text) or self.text[self.pos] == '}':
                self.pos += 1  # skip '}'
                break

            # Check for explicit key: ["key"] = value or [num] = value or key = value
            key = None
            saved_pos = self.pos

            if self.text[self.pos] == '[':
                self.pos += 1
                self._skip_whitespace_and_comments()
                if self.text[self.pos] == '"' or self.text[self.pos] == "'":
                    key = self._parse_string() if self.text[self.pos] == '"' else self._parse_single_string()
                    is_array = False
                elif self.text[self.pos].isdigit() or self.text[self.pos] == '-':
                    key = self._parse_number()
                self._skip_whitespace_and_comments()
                if self.pos < len(self.text) and self.text[self.pos] == ']':
                    self.pos += 1
                self._skip_whitespace_and_comments()
                if self.pos < len(self.text) and self.text[self.pos] == '=':
                    self.pos += 1
                else:
                    # Wasn't a key, rewind
                    self.pos = saved_pos
                    key = None
            elif re.match(r'[A-Za-z_]\w*\s*=', self.text[self.pos:]):
                match = re.match(r'([A-Za-z_]\w*)\s*=\s*', self.text[self.pos:])
                if match:
                    key = match.group(1)
                    self.pos += match.end()
                    is_array = False

            value = self._parse_value()

            if key is not None:
                items[key] = value
            else:
                items[array_index] = value
                array_index += 1

            # Skip comma or semicolon separator
            self._skip_whitespace_and_comments()
            if self.pos < len(self.text) and self.text[self.pos] in ',;':
                self.pos += 1

        # Convert to list if all keys are sequential integers starting at 1
        if is_array and items:
            max_key = max(k for k in items if isinstance(k, (int, float)))
            if all(i in items for i in range(1, int(max_key) + 1)):
                return [items[i] for i in range(1, int(max_key) + 1)]

        return items

    def _parse_string(self):
        self.pos += 1  # skip opening "
        result = []
        while self.pos < len(self.text):
            ch = self.text[self.pos]
            if ch == '\\':
                self.pos += 1
                if self.pos < len(self.text):
                    esc = self.text[self.pos]
                    if esc == 'n':
                        result.append('\n')
                    elif esc == 't':
                        result.append('\t')
                    elif esc == '"':
                        result.append('"')
                    elif esc == '\\':
                        result.append('\\')
                    else:
                        result.append(esc)
                    self.pos += 1
            elif ch == '"':
                self.pos += 1
                break
            else:
                result.append(ch)
                self.pos += 1
        return ''.join(result)

    def _parse_single_string(self):
        self.pos += 1  # skip opening '
        result = []
        while self.pos < len(self.text) and self.text[self.pos] != "'":
            result.append(self.text[self.pos])
            self.pos += 1
        if self.pos < len(self.text):
            self.pos += 1  # skip closing '
        return ''.join(result)

    def _parse_number(self):
        match = re.match(r'-?\d+\.?\d*(?:[eE][+-]?\d+)?', self.text[self.pos:])
        if match:
            self.pos += match.end()
            num_str = match.group(0)
            if '.' in num_str or 'e' in num_str or 'E' in num_str:
                return float(num_str)
            return int(num_str)
        return 0


def parse_savedvariables(file_path: str) -> dict:
    """Parse a WoW SavedVariables .lua file into Python dict."""
    text = Path(file_path).read_text(encoding='utf-8', errors='replace')
    parser = LuaParser(text)
    return parser.parse()


# ---------------------------------------------------------------
# Import logic
# ---------------------------------------------------------------

def _find_or_create_character(session: Session, name: str, realm: str,
                               class_token: str = None, guild: str = None) -> Character:
    """Find existing character or create a new one."""
    char = session.exec(
        select(Character).where(
            Character.name == name,
            Character.realm == realm,
        )
    ).first()

    class_name = CLASS_TOKEN_MAP.get(class_token, class_token) if class_token else None

    if not char:
        char = Character(
            name=name,
            realm=realm,
            region="us",
            class_name=class_name,
        )
        session.add(char)
        session.commit()
        session.refresh(char)
    else:
        if class_name and not char.class_name:
            char.class_name = class_name
        session.add(char)
        session.commit()

    return char


def import_addon_runs(session: Session, file_path: str) -> dict:
    """
    Import runs from a WoW SavedVariables file.
    Returns { "imported": int, "skipped": int, "errors": list[str] }
    """
    result = {"imported": 0, "skipped": 0, "errors": []}

    try:
        data = parse_savedvariables(file_path)
    except Exception as e:
        result["errors"].append(f"Failed to parse file: {e}")
        return result

    db = data.get("MythicPlusTrackerDB")
    if not db or not isinstance(db, dict):
        result["errors"].append("MythicPlusTrackerDB not found in file")
        return result

    runs = db.get("runs", [])
    if not isinstance(runs, list):
        result["errors"].append("runs is not a list")
        return result

    for run_data in runs:
        if not isinstance(run_data, dict):
            continue

        run_id = run_data.get("runId", "")
        if not run_id:
            result["errors"].append("Run missing runId, skipping")
            continue

        # Check for existing import
        existing = session.exec(
            select(Run).where(Run.addon_run_id == str(run_id))
        ).first()
        if existing:
            result["skipped"] += 1
            continue

        # Determine result
        timed = run_data.get("timed", False)
        completed = run_data.get("completed", False)
        if timed:
            run_result = "timed"
        elif completed:
            run_result = "completed"
        else:
            run_result = "depleted"

        # Build started_at from epoch
        started_at = None
        start_time = run_data.get("startTime")
        if start_time and isinstance(start_time, (int, float)):
            started_at = datetime.utcfromtimestamp(start_time)

        completed_at = None
        end_time = run_data.get("endTime")
        if end_time and isinstance(end_time, (int, float)):
            completed_at = datetime.utcfromtimestamp(end_time)

        # Affixes as JSON string
        import json
        affixes = run_data.get("affixes", [])
        affixes_json = json.dumps(affixes) if affixes else None

        # Buff check as JSON
        buff_check = run_data.get("buffCheck")
        buffs_json = json.dumps(buff_check) if buff_check else None

        # Played time delta
        played_before = run_data.get("playedBefore")
        played_after = run_data.get("playedAfter")
        played_seconds = None
        if played_before and played_after:
            played_seconds = int(played_after - played_before)

        run = Run(
            dungeon_name=run_data.get("dungeon", "Unknown"),
            key_level=int(run_data.get("keyLevel", 0)),
            result=run_result,
            duration_seconds=run_data.get("durationSeconds"),
            time_limit_seconds=run_data.get("timeLimitSeconds"),
            upgrade_count=run_data.get("upgradeCount", 0) if timed else None,
            deaths=int(run_data.get("deaths", 0)),
            started_at=started_at,
            completed_at=completed_at,
            season=run_data.get("season", "midnight-1"),
            affixes=affixes_json,
            addon_run_id=str(run_id),
            source="addon",
            gold_before=run_data.get("goldBefore"),
            gold_after=run_data.get("goldAfter"),
            durability_before=run_data.get("durabilityBefore"),
            durability_after=run_data.get("durabilityAfter"),
            companion_pet=run_data.get("companionPet"),
            my_mount=run_data.get("myMount"),
            played_seconds=played_seconds,
            buffs_json=buffs_json,
        )
        session.add(run)
        session.commit()
        session.refresh(run)

        # Import members
        members = run_data.get("members", [])
        if isinstance(members, list):
            for member_data in members:
                if not isinstance(member_data, dict):
                    continue

                name = member_data.get("name", "")
                realm = member_data.get("realm", "Unknown")
                if not name:
                    continue

                char = _find_or_create_character(
                    session, name, realm,
                    class_token=member_data.get("class"),
                    guild=member_data.get("guild"),
                )

                role = ROLE_MAP.get(member_data.get("role", ""), "dps")

                run_member = RunMember(
                    run_id=run.id,
                    character_id=char.id,
                    spec=member_data.get("spec"),
                    role=role,
                    was_me=bool(member_data.get("isMe", False)),
                    ilvl=member_data.get("ilvl"),
                )
                session.add(run_member)

        session.commit()
        result["imported"] += 1

    return result
