"""Tests for Lua parser and addon import logic."""
import os
import json
import tempfile

import pytest
from sqlmodel import Session, select
from app.database import engine
from app.models import Run, RunMember, Character
from app.services.addon_import import (
    LuaParser,
    parse_savedvariables,
    import_addon_runs,
)


# ── Lua Parser ──────────────────────────────────────────────────

class TestLuaParser:
    def test_simple_string(self):
        p = LuaParser('x = "hello"')
        result = p.parse()
        assert result["x"] == "hello"

    def test_single_quote_string(self):
        p = LuaParser("x = 'world'")
        result = p.parse()
        assert result["x"] == "world"

    def test_integer(self):
        p = LuaParser("x = 42")
        result = p.parse()
        assert result["x"] == 42

    def test_float(self):
        p = LuaParser("x = 3.14")
        result = p.parse()
        assert result["x"] == 3.14

    def test_negative_number(self):
        p = LuaParser("x = -5")
        result = p.parse()
        assert result["x"] == -5

    def test_boolean_true(self):
        p = LuaParser("x = true")
        result = p.parse()
        assert result["x"] is True

    def test_boolean_false(self):
        p = LuaParser("x = false")
        result = p.parse()
        assert result["x"] is False

    def test_nil(self):
        p = LuaParser("x = nil")
        result = p.parse()
        assert result["x"] is None

    def test_empty_table(self):
        p = LuaParser("x = {}")
        result = p.parse()
        assert result["x"] == {} or result["x"] == []

    def test_array_table(self):
        p = LuaParser('x = { "a", "b", "c" }')
        result = p.parse()
        assert result["x"] == ["a", "b", "c"]

    def test_dict_table(self):
        p = LuaParser('x = { ["key"] = "value" }')
        result = p.parse()
        assert result["x"]["key"] == "value"

    def test_nested_table(self):
        p = LuaParser('x = { ["inner"] = { ["deep"] = 42 } }')
        result = p.parse()
        assert result["x"]["inner"]["deep"] == 42

    def test_mixed_table(self):
        p = LuaParser('x = { "a", ["k"] = "v", "b" }')
        result = p.parse()
        # Mixed table behavior - should at least not crash
        assert "x" in result

    def test_string_escapes(self):
        p = LuaParser(r'x = "hello \"world\""')
        result = p.parse()
        assert '"' in result["x"]

    def test_comment_handling(self):
        p = LuaParser('-- this is a comment\nx = 42')
        result = p.parse()
        assert result["x"] == 42

    def test_multiline_comment(self):
        p = LuaParser('--[[ block comment ]]x = 42')
        result = p.parse()
        assert result["x"] == 42

    def test_multiple_assignments(self):
        p = LuaParser('a = 1\nb = 2\nc = 3')
        result = p.parse()
        assert result["a"] == 1
        assert result["b"] == 2
        assert result["c"] == 3

    def test_realistic_addon_structure(self, sample_lua_file):
        result = parse_savedvariables(sample_lua_file)
        db = result["MythicPlusTrackerDB"]
        assert db["version"] == 1
        runs = db["runs"]
        assert len(runs) == 2
        assert runs[0]["dungeon"] == "Ara-Kara, City of Echoes"
        assert runs[0]["keyLevel"] == 15
        assert runs[0]["timed"] is True
        assert len(runs[0]["members"]) == 2
        os.unlink(sample_lua_file)


# ── Import Logic ────────────────────────────────────────────────

class TestAddonImport:
    def test_successful_import(self, session, sample_lua_file):
        result = import_addon_runs(session, sample_lua_file)
        assert result["imported"] == 2
        assert result["skipped"] == 0
        assert result["errors"] == []
        os.unlink(sample_lua_file)

    def test_dedup_on_reimport(self, session, sample_lua_file):
        import_addon_runs(session, sample_lua_file)
        result = import_addon_runs(session, sample_lua_file)
        assert result["imported"] == 0
        assert result["skipped"] == 2
        os.unlink(sample_lua_file)

    def test_run_data_correct(self, session, sample_lua_file):
        import_addon_runs(session, sample_lua_file)
        run = session.exec(
            select(Run).where(Run.addon_run_id == "test-import-1")
        ).first()
        assert run is not None
        assert run.dungeon_name == "Ara-Kara, City of Echoes"
        assert run.key_level == 15
        assert run.result == "timed"
        assert run.deaths == 1
        assert run.duration_seconds == 1500
        assert run.time_limit_seconds == 1800
        assert run.upgrade_count == 2
        assert run.source == "addon"
        assert run.gold_before == 100000000
        assert run.gold_after == 99950000
        assert run.companion_pet == "Lil Ragnaros"
        assert run.my_mount == "Invincible"
        assert run.played_seconds == 1523
        os.unlink(sample_lua_file)

    def test_affixes_stored_as_json(self, session, sample_lua_file):
        import_addon_runs(session, sample_lua_file)
        run = session.exec(
            select(Run).where(Run.addon_run_id == "test-import-1")
        ).first()
        affixes = json.loads(run.affixes)
        assert "Fortified" in affixes
        assert "Bursting" in affixes
        os.unlink(sample_lua_file)

    def test_buffs_stored_as_json(self, session, sample_lua_file):
        import_addon_runs(session, sample_lua_file)
        run = session.exec(
            select(Run).where(Run.addon_run_id == "test-import-1")
        ).first()
        buffs = json.loads(run.buffs_json)
        assert "Testplayer" in buffs["flask"]
        assert "Testplayer" in buffs["food"]
        os.unlink(sample_lua_file)

    def test_character_created_with_race(self, session, sample_lua_file):
        import_addon_runs(session, sample_lua_file)
        char = session.exec(
            select(Character).where(Character.name == "Testplayer")
        ).first()
        assert char is not None
        assert char.race == "Night Elf"
        assert char.class_name == "Druid"
        assert char.guild == "Test Guild"
        assert char.title == "the Undying"
        os.unlink(sample_lua_file)

    def test_character_race_dark_iron_mapped(self, session, sample_lua_file):
        import_addon_runs(session, sample_lua_file)
        char = session.exec(
            select(Character).where(Character.name == "Tankfriend")
        ).first()
        assert char is not None
        assert char.race == "Dark Iron Dwarf"
        os.unlink(sample_lua_file)

    def test_member_mount_stored(self, session, sample_lua_file):
        import_addon_runs(session, sample_lua_file)
        member = session.exec(
            select(RunMember).join(Character).where(Character.name == "Tankfriend")
        ).first()
        assert member is not None
        assert member.mount == "Swift Spectral Tiger"
        os.unlink(sample_lua_file)

    def test_member_ilvl_stored(self, session, sample_lua_file):
        import_addon_runs(session, sample_lua_file)
        member = session.exec(
            select(RunMember).join(Character).where(Character.name == "Testplayer")
        ).first()
        assert member is not None
        assert member.ilvl == 623.0
        os.unlink(sample_lua_file)

    def test_depleted_run_correct(self, session, sample_lua_file):
        import_addon_runs(session, sample_lua_file)
        run = session.exec(
            select(Run).where(Run.addon_run_id == "test-import-2")
        ).first()
        # completed=true but timed=false maps to "completed" (not depleted)
        assert run.result == "completed"
        assert run.upgrade_count is None
        assert run.deaths == 7
        os.unlink(sample_lua_file)

    def test_invalid_file_returns_error(self, session):
        result = import_addon_runs(session, "/nonexistent/file.lua")
        assert len(result["errors"]) > 0
        assert result["imported"] == 0

    def test_empty_db_in_file(self, session):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.lua', delete=False) as f:
            f.write('SomeOtherDB = {}')
            path = f.name
        result = import_addon_runs(session, path)
        assert len(result["errors"]) > 0
        os.unlink(path)

    def test_run_missing_runid(self, session):
        lua = '''
MythicPlusTrackerDB = {
    ["runs"] = {
        { ["dungeon"] = "Test", ["keyLevel"] = 10, ["timed"] = true, ["completed"] = true },
    },
}
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.lua', delete=False) as f:
            f.write(lua)
            path = f.name
        result = import_addon_runs(session, path)
        assert result["imported"] == 0
        assert any("runId" in e for e in result["errors"])
        os.unlink(path)

    def test_character_updates_on_reimport(self):
        """If a character's guild changes, the import should update it."""
        from textwrap import dedent
        lua1 = dedent('''
            MythicPlusTrackerDB = {
                ["runs"] = {
                    { ["runId"] = "r1", ["dungeon"] = "Test", ["keyLevel"] = 10,
                      ["timed"] = true, ["completed"] = true,
                      ["members"] = {
                        { ["name"] = "Updater", ["realm"] = "Test", ["class"] = "MAGE",
                          ["guild"] = "Old Guild", ["role"] = "DAMAGER", ["isMe"] = false },
                      },
                    },
                },
            }
        ''')
        lua2 = dedent('''
            MythicPlusTrackerDB = {
                ["runs"] = {
                    { ["runId"] = "r2", ["dungeon"] = "Test", ["keyLevel"] = 11,
                      ["timed"] = true, ["completed"] = true,
                      ["members"] = {
                        { ["name"] = "Updater", ["realm"] = "Test", ["class"] = "MAGE",
                          ["guild"] = "New Guild", ["role"] = "DAMAGER", ["isMe"] = false },
                      },
                    },
                },
            }
        ''')
        paths = []
        for lua_content in [lua1, lua2]:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.lua', delete=False) as f:
                f.write(lua_content)
                paths.append(f.name)

        for p in paths:
            with Session(engine) as s:
                result = import_addon_runs(s, p)
            os.unlink(p)

        with Session(engine) as s:
            char = s.exec(
                select(Character).where(Character.name == "Updater")
            ).first()
            assert char is not None
            assert char.guild == "New Guild"
