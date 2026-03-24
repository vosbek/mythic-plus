"""Tests for input validation, edge cases, and security."""
import json
from sqlmodel import Session, select
from app.database import engine
from app.models import Run, RunMember, Character


# ── XSS Prevention ──────────────────────────────────────────────

class TestXSSPrevention:
    """Ensure script injection is escaped in rendered output."""

    def test_xss_in_notes(self, client):
        resp = client.post("/runs/new", data={
            "dungeon_name": "Ara-Kara, City of Echoes",
            "key_level": "10",
            "result": "timed",
            "duration_minutes": "20",
            "duration_seconds": "0",
            "deaths": "0",
            "upgrade_count": "1",
            "notes": '<script>alert("xss")</script>',
            "rating": "0",
            "vibe": "",
            "started_hour": "-1",
            "started_minute": "0",
            "affixes": "",
            "my_mount": "",
            "companion_pet": "",
        }, follow_redirects=False)
        assert resp.status_code == 303

        with Session(engine) as session:
            run = session.exec(select(Run).where(Run.key_level == 10)).first()
            detail_resp = client.get(f"/runs/{run.id}")
            # Jinja2 autoescapes by default — raw <script> should not appear
            assert '<script>alert("xss")</script>' not in detail_resp.text
            # The escaped version should be there
            assert '&lt;script&gt;' in detail_resp.text or 'alert' in detail_resp.text

    def test_xss_in_character_name(self, client):
        resp = client.post("/runs/new", data={
            "dungeon_name": "Ara-Kara, City of Echoes",
            "key_level": "11",
            "result": "timed",
            "duration_minutes": "20",
            "duration_seconds": "0",
            "deaths": "0",
            "upgrade_count": "1",
            "notes": "",
            "rating": "0",
            "vibe": "",
            "started_hour": "-1",
            "started_minute": "0",
            "affixes": "",
            "my_mount": "",
            "companion_pet": "",
            "member_0_name": '<img src=x onerror=alert(1)>',
            "member_0_realm": "Stormrage",
            "member_0_class": "Mage",
            "member_0_spec": "Fire",
            "member_0_role": "dps",
        }, follow_redirects=False)
        assert resp.status_code == 303

        with Session(engine) as session:
            run = session.exec(select(Run).where(Run.key_level == 11)).first()
            detail_resp = client.get(f"/runs/{run.id}")
            assert '<img src=x onerror=alert(1)>' not in detail_resp.text

    def test_xss_in_affixes(self, client):
        resp = client.post("/runs/new", data={
            "dungeon_name": "Ara-Kara, City of Echoes",
            "key_level": "13",
            "result": "timed",
            "duration_minutes": "20",
            "duration_seconds": "0",
            "deaths": "0",
            "upgrade_count": "1",
            "notes": "",
            "rating": "0",
            "vibe": "",
            "started_hour": "-1",
            "started_minute": "0",
            "affixes": '<script>alert(1)</script>',
            "my_mount": "",
            "companion_pet": "",
        }, follow_redirects=False)
        assert resp.status_code == 303

        with Session(engine) as session:
            run = session.exec(select(Run).where(Run.key_level == 13)).first()
            detail_resp = client.get(f"/runs/{run.id}")
            assert '<script>' not in detail_resp.text


# ── Edge Cases ──────────────────────────────────────────────────

class TestEdgeCases:
    def test_zero_duration(self, client):
        resp = client.post("/runs/new", data={
            "dungeon_name": "Ara-Kara, City of Echoes",
            "key_level": "5",
            "result": "abandoned",
            "duration_minutes": "0",
            "duration_seconds": "0",
            "deaths": "0",
            "upgrade_count": "0",
            "notes": "",
            "rating": "0",
            "vibe": "",
            "started_hour": "-1",
            "started_minute": "0",
            "affixes": "",
            "my_mount": "",
            "companion_pet": "",
        }, follow_redirects=False)
        assert resp.status_code == 303

    def test_very_high_key_level(self, client):
        resp = client.post("/runs/new", data={
            "dungeon_name": "Ara-Kara, City of Echoes",
            "key_level": "35",
            "result": "depleted",
            "duration_minutes": "45",
            "duration_seconds": "0",
            "deaths": "99",
            "upgrade_count": "0",
            "notes": "",
            "rating": "1",
            "vibe": "tilting",
            "started_hour": "-1",
            "started_minute": "0",
            "affixes": "",
            "my_mount": "",
            "companion_pet": "",
        }, follow_redirects=False)
        assert resp.status_code == 303

        with Session(engine) as session:
            run = session.exec(select(Run).where(Run.key_level == 35)).first()
            assert run is not None
            assert run.deaths == 99

    def test_whitespace_only_notes(self, client):
        resp = client.post("/runs/new", data={
            "dungeon_name": "Ara-Kara, City of Echoes",
            "key_level": "7",
            "result": "timed",
            "duration_minutes": "20",
            "duration_seconds": "0",
            "deaths": "0",
            "upgrade_count": "1",
            "notes": "   ",
            "rating": "0",
            "vibe": "",
            "started_hour": "-1",
            "started_minute": "0",
            "affixes": "",
            "my_mount": "",
            "companion_pet": "",
        }, follow_redirects=False)
        assert resp.status_code == 303

    def test_empty_member_name_skipped(self, client):
        resp = client.post("/runs/new", data={
            "dungeon_name": "Ara-Kara, City of Echoes",
            "key_level": "9",
            "result": "timed",
            "duration_minutes": "20",
            "duration_seconds": "0",
            "deaths": "0",
            "upgrade_count": "1",
            "notes": "",
            "rating": "0",
            "vibe": "",
            "started_hour": "-1",
            "started_minute": "0",
            "affixes": "",
            "my_mount": "",
            "companion_pet": "",
            "member_0_name": "",
            "member_0_realm": "Stormrage",
            "member_0_class": "Mage",
            "member_0_spec": "Fire",
            "member_0_role": "dps",
        }, follow_redirects=False)
        assert resp.status_code == 303

        with Session(engine) as session:
            run = session.exec(select(Run).where(Run.key_level == 9)).first()
            members = session.exec(
                select(RunMember).where(RunMember.run_id == run.id)
            ).all()
            assert len(members) == 0

    def test_special_characters_in_dungeon_filter(self, client):
        resp = client.get("/runs?dungeon=Ara-Kara%2C+City+of+Echoes")
        assert resp.status_code == 200

    def test_negative_key_level(self, client):
        """Negative key level should still create (no server-side validation yet)."""
        resp = client.post("/runs/new", data={
            "dungeon_name": "Ara-Kara, City of Echoes",
            "key_level": "-1",
            "result": "timed",
            "duration_minutes": "20",
            "duration_seconds": "0",
            "deaths": "0",
            "upgrade_count": "0",
            "notes": "",
            "rating": "0",
            "vibe": "",
            "started_hour": "-1",
            "started_minute": "0",
            "affixes": "",
            "my_mount": "",
            "companion_pet": "",
        }, follow_redirects=False)
        # FastAPI should still accept the int, app creates the run
        assert resp.status_code == 303


# ── Analytics Edge Cases ────────────────────────────────────────

class TestAnalyticsEdgeCases:
    def test_stats_with_single_run(self, client, sample_run):
        """Stats page shouldn't crash with just 1 run."""
        resp = client.get("/stats")
        assert resp.status_code == 200

    def test_stats_with_no_optional_data(self, client):
        """Runs with no vibes, ratings, mounts, etc."""
        with Session(engine) as session:
            session.add(Run(
                dungeon_name="Ara-Kara, City of Echoes",
                key_level=10, result="timed",
            ))
            session.commit()

        resp = client.get("/stats")
        assert resp.status_code == 200

    def test_detail_with_no_optional_data(self, client):
        """Run detail with minimal data shouldn't crash."""
        with Session(engine) as session:
            run = Run(dungeon_name="Test", key_level=5, result="depleted")
            session.add(run)
            session.commit()
            session.refresh(run)
            run_id = run.id

        resp = client.get(f"/runs/{run_id}")
        assert resp.status_code == 200
        assert "--:--" in resp.text  # no duration

    def test_run_detail_with_bad_buffs_json(self, client):
        """Corrupted buffs_json shouldn't crash the detail page."""
        with Session(engine) as session:
            run = Run(dungeon_name="Test", key_level=5, result="timed",
                      buffs_json="not-valid-json")
            session.add(run)
            session.commit()
            session.refresh(run)
            run_id = run.id

        resp = client.get(f"/runs/{run_id}")
        assert resp.status_code == 200

    def test_run_detail_with_bad_affixes_json(self, client):
        """Corrupted affixes shouldn't crash the detail page."""
        with Session(engine) as session:
            run = Run(dungeon_name="Test", key_level=5, result="timed",
                      affixes="{bad json")
            session.add(run)
            session.commit()
            session.refresh(run)
            run_id = run.id

        resp = client.get(f"/runs/{run_id}")
        assert resp.status_code == 200


# ── Path Traversal (addon import) ──────────────────────────────

class TestPathTraversal:
    def test_import_nonexistent_path(self, client):
        resp = client.post("/import/addon", data={
            "wow_path": "../../../../etc/passwd",
        }, follow_redirects=False)
        # Should fail gracefully, not expose system files
        assert resp.status_code in (303, 307, 200)
