"""Integration tests for all HTTP routes."""
import json
from datetime import datetime

import pytest
from sqlmodel import Session, select
from tests.conftest import _engine as engine
from app.models import Run, RunMember, Character, Dungeon


# ── Dashboard ───────────────────────────────────────────────────

class TestDashboard:
    def test_home_page_loads(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Mythic+" in resp.text

    def test_home_shows_stats(self, client, sample_run):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Ara-Kara" in resp.text

    def test_home_empty_state(self, client):
        resp = client.get("/")
        assert resp.status_code == 200


# ── Run List ────────────────────────────────────────────────────

class TestRunList:
    def test_runs_page_loads(self, client):
        resp = client.get("/runs")
        assert resp.status_code == 200

    def test_runs_show_data(self, client, sample_run):
        resp = client.get("/runs")
        assert "Ara-Kara" in resp.text
        assert "+15" in resp.text

    def test_filter_by_dungeon(self, client, multiple_runs):
        resp = client.get("/runs?dungeon=City+of+Threads")
        assert resp.status_code == 200
        assert "City of Threads" in resp.text

    def test_filter_by_result(self, client, multiple_runs):
        resp = client.get("/runs?result=depleted")
        assert resp.status_code == 200

    def test_filter_by_min_key(self, client, multiple_runs):
        resp = client.get("/runs?min_key=15")
        assert resp.status_code == 200

    def test_empty_filters(self, client, multiple_runs):
        resp = client.get("/runs?dungeon=&result=&min_key=0")
        assert resp.status_code == 200


# ── Run Detail ──────────────────────────────────────────────────

class TestRunDetail:
    def test_run_detail_loads(self, client, sample_run):
        resp = client.get(f"/runs/{sample_run.id}")
        assert resp.status_code == 200
        assert "Ara-Kara" in resp.text
        assert "+15" in resp.text

    def test_run_detail_shows_affixes(self, client, sample_run):
        resp = client.get(f"/runs/{sample_run.id}")
        assert "Fortified" in resp.text
        assert "Bursting" in resp.text

    def test_run_detail_shows_buffs(self, client, sample_run):
        resp = client.get(f"/runs/{sample_run.id}")
        assert "Flask" in resp.text

    def test_run_detail_shows_members(self, client, sample_run):
        resp = client.get(f"/runs/{sample_run.id}")
        assert "Testplayer" in resp.text
        assert "Tankfriend" in resp.text

    def test_run_detail_shows_guild(self, client, sample_run):
        resp = client.get(f"/runs/{sample_run.id}")
        assert "Test Guild" in resp.text

    def test_run_detail_shows_race(self, client, sample_run):
        resp = client.get(f"/runs/{sample_run.id}")
        assert "Night Elf" in resp.text

    def test_run_detail_shows_mount(self, client, sample_run):
        resp = client.get(f"/runs/{sample_run.id}")
        assert "Invincible" in resp.text

    def test_run_detail_shows_time_limit(self, client, sample_run):
        resp = client.get(f"/runs/{sample_run.id}")
        assert "30:00" in resp.text  # time limit = 1800s = 30:00

    def test_run_detail_shows_timer_margin(self, client, sample_run):
        resp = client.get(f"/runs/{sample_run.id}")
        assert "under" in resp.text  # timed run, should be under timer

    def test_run_detail_404_for_missing(self, client):
        resp = client.get("/runs/99999")
        assert resp.status_code == 200  # renders template with "not found"
        assert "not found" in resp.text.lower() or "Back to runs" in resp.text

    def test_run_detail_shows_gold_cost(self, client, sample_run):
        resp = client.get(f"/runs/{sample_run.id}")
        assert "Gold" in resp.text

    def test_run_detail_shows_durability(self, client, sample_run):
        resp = client.get(f"/runs/{sample_run.id}")
        assert "Durability" in resp.text
        assert "95" in resp.text


# ── Create Run ──────────────────────────────────────────────────

class TestCreateRun:
    def test_new_run_form_loads(self, client):
        resp = client.get("/runs/new")
        assert resp.status_code == 200
        assert "Dungeon" in resp.text
        assert "Key Level" in resp.text

    def test_new_run_form_has_affixes_field(self, client):
        resp = client.get("/runs/new")
        assert "Affixes" in resp.text

    def test_new_run_form_has_mount_pet_fields(self, client):
        resp = client.get("/runs/new")
        assert "Mount" in resp.text
        assert "Companion Pet" in resp.text or "Pet" in resp.text

    def test_create_run_basic(self, client):
        resp = client.post("/runs/new", data={
            "dungeon_name": "Ara-Kara, City of Echoes",
            "key_level": "10",
            "result": "timed",
            "duration_minutes": "25",
            "duration_seconds": "30",
            "deaths": "2",
            "upgrade_count": "1",
            "notes": "Test run",
            "rating": "3",
            "vibe": "chill",
            "started_hour": "-1",
            "started_minute": "0",
            "affixes": "",
            "my_mount": "",
            "companion_pet": "",
        }, follow_redirects=False)
        assert resp.status_code == 303

        with Session(engine) as session:
            run = session.exec(select(Run).where(Run.key_level == 10)).first()
            assert run is not None
            assert run.dungeon_name == "Ara-Kara, City of Echoes"
            assert run.duration_seconds == 25 * 60 + 30
            assert run.result == "timed"
            assert run.source == "manual"

    def test_create_run_with_affixes(self, client):
        resp = client.post("/runs/new", data={
            "dungeon_name": "City of Threads",
            "key_level": "12",
            "result": "timed",
            "duration_minutes": "20",
            "duration_seconds": "0",
            "deaths": "0",
            "upgrade_count": "3",
            "notes": "",
            "rating": "0",
            "vibe": "",
            "started_hour": "-1",
            "started_minute": "0",
            "affixes": "Fortified, Bursting",
            "my_mount": "Invincible",
            "companion_pet": "Lil Ragnaros",
        }, follow_redirects=False)
        assert resp.status_code == 303

        with Session(engine) as session:
            run = session.exec(select(Run).where(Run.key_level == 12)).first()
            assert run.my_mount == "Invincible"
            assert run.companion_pet == "Lil Ragnaros"
            affixes = json.loads(run.affixes)
            assert "Fortified" in affixes
            assert "Bursting" in affixes

    def test_create_run_with_members(self, client):
        resp = client.post("/runs/new", data={
            "dungeon_name": "Ara-Kara, City of Echoes",
            "key_level": "8",
            "result": "depleted",
            "duration_minutes": "35",
            "duration_seconds": "0",
            "deaths": "10",
            "upgrade_count": "0",
            "notes": "",
            "rating": "1",
            "vibe": "tilting",
            "started_hour": "-1",
            "started_minute": "0",
            "affixes": "",
            "my_mount": "",
            "companion_pet": "",
            "member_0_name": "NewPlayer",
            "member_0_realm": "Stormrage",
            "member_0_class": "Mage",
            "member_0_spec": "Fire",
            "member_0_role": "dps",
            "member_0_is_me": "on",
        }, follow_redirects=False)
        assert resp.status_code == 303

        with Session(engine) as session:
            run = session.exec(select(Run).where(Run.key_level == 8)).first()
            members = session.exec(
                select(RunMember).where(RunMember.run_id == run.id)
            ).all()
            assert len(members) == 1
            assert members[0].was_me is True
            char = session.get(Character, members[0].character_id)
            assert char.name == "NewPlayer"


# ── Stats Page ──────────────────────────────────────────────────

class TestStatsPage:
    def test_stats_page_loads_empty(self, client):
        resp = client.get("/stats")
        assert resp.status_code == 200
        assert "Stats" in resp.text

    def test_stats_page_with_data(self, client, multiple_runs):
        resp = client.get("/stats")
        assert resp.status_code == 200
        assert "Dungeon Tier List" in resp.text
        assert "Affix Performance" in resp.text
        assert "Vibe Check" in resp.text

    def test_stats_page_shows_overview(self, client, multiple_runs):
        resp = client.get("/stats")
        assert "Total Runs" in resp.text
        assert "Timed Rate" in resp.text
        assert "Highest Timed" in resp.text

    def test_stats_page_shows_time_margins(self, client, multiple_runs):
        resp = client.get("/stats")
        assert "Timing Margins" in resp.text

    def test_stats_page_shows_streaks(self, client, multiple_runs):
        resp = client.get("/stats")
        assert "Streak" in resp.text

    def test_stats_page_shows_buff_compliance(self, client, multiple_runs):
        resp = client.get("/stats")
        assert "Buff Compliance" in resp.text


# ── Characters ──────────────────────────────────────────────────

class TestCharacters:
    def test_characters_page_loads(self, client):
        resp = client.get("/characters")
        assert resp.status_code == 200
        assert "Characters" in resp.text
        assert "Saytees" in resp.text  # default character

    def test_character_detail(self, client, sample_run):
        with Session(engine) as session:
            char = session.exec(
                select(Character).where(Character.name == "Testplayer")
            ).first()
        resp = client.get(f"/characters/{char.id}")
        assert resp.status_code == 200
        assert "Testplayer" in resp.text

    def test_character_search(self, client, sample_run):
        resp = client.get("/characters?q=test")
        assert resp.status_code == 200

    def test_character_shows_race_guild(self, client, sample_run):
        with Session(engine) as session:
            char = session.exec(
                select(Character).where(Character.name == "Testplayer")
            ).first()
        resp = client.get(f"/characters/{char.id}")
        assert "Night Elf" in resp.text
        assert "Test Guild" in resp.text


# ── Addon Import Page ───────────────────────────────────────────

class TestAddonImportPage:
    def test_import_page_loads(self, client):
        resp = client.get("/import/addon")
        assert resp.status_code == 200
        assert "Import" in resp.text

    def test_import_with_bad_path(self, client):
        resp = client.post("/import/addon", data={
            "wow_path": "/nonexistent/path.lua",
        }, follow_redirects=False)
        # Should redirect back with error
        assert resp.status_code in (303, 307, 200)


# ── Warcraft Logs Import Page ───────────────────────────────────

class TestWarcraftLogsPage:
    def test_wcl_page_loads(self, client):
        resp = client.get("/import/warcraftlogs")
        assert resp.status_code == 200

    def test_wcl_import_without_token(self, client):
        resp = client.post("/import/warcraftlogs", data={
            "char_name": "Test",
            "char_realm": "Stormrage",
        }, follow_redirects=False)
        # Should redirect with error (no WCL token configured)
        assert resp.status_code in (303, 307, 200)


# ── Spotify Page ────────────────────────────────────────────────

class TestSpotifyPage:
    def test_spotify_page_loads(self, client):
        resp = client.get("/spotify")
        assert resp.status_code == 200
