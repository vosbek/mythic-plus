"""Tests for app/services/analytics.py — all analytics functions."""
import json
from datetime import datetime, timedelta
from sqlmodel import Session
from tests.conftest import _engine as engine
from app.models import Run, RunMember, Character, RunSong
from app.services.analytics import (
    get_overview_stats,
    get_nemesis_dungeon,
    get_best_dungeon,
    get_streaks,
    get_vibe_stats,
    get_group_chemistry,
    get_lucky_song,
    get_time_of_day_stats,
    get_weekly_vault,
    get_affix_stats,
    get_lucky_mount,
    get_lucky_pet,
    get_time_margin_stats,
    get_buff_compliance_stats,
    get_gold_stats,
    get_role_stats,
    get_ilvl_analysis,
    get_dungeon_tier_list,
    get_guild_stats,
    get_rating_analysis,
)


# ── Overview Stats ──────────────────────────────────────────────

class TestOverviewStats:
    def test_empty_db(self, session):
        stats = get_overview_stats(session)
        assert stats["total_runs"] == 0
        assert stats["timed_pct"] == 0
        assert stats["highest_timed_key"] == 0
        assert stats["total_gold_spent"] == 0
        assert stats["total_played_hours"] == 0

    def test_with_runs(self, session, multiple_runs):
        stats = get_overview_stats(session)
        assert stats["total_runs"] == 4
        assert stats["timed_runs"] == 3
        assert stats["depleted_runs"] == 1
        assert stats["timed_pct"] == 75.0
        assert stats["highest_timed_key"] == 15

    def test_gold_tracking(self, session, multiple_runs):
        stats = get_overview_stats(session)
        # Two runs have gold data: 50000 + 50000 = 100000 copper
        assert stats["total_gold_spent"] == 100000

    def test_played_time(self, session, multiple_runs):
        stats = get_overview_stats(session)
        assert stats["total_played_hours"] > 0


# ── Nemesis & Best Dungeon ──────────────────────────────────────

class TestNemesisDungeon:
    def test_empty(self, session):
        assert get_nemesis_dungeon(session) is None

    def test_most_depletions(self, session, multiple_runs):
        result = get_nemesis_dungeon(session)
        assert result is not None
        assert result["dungeon"] == "Ara-Kara, City of Echoes"
        assert result["depletions"] == 1


class TestBestDungeon:
    def test_empty(self, session):
        assert get_best_dungeon(session) is None

    def test_needs_min_2_runs(self, session):
        session.add(Run(dungeon_name="Test", key_level=10, result="timed"))
        session.commit()
        assert get_best_dungeon(session) is None

    def test_highest_timed_pct(self, session, multiple_runs):
        result = get_best_dungeon(session)
        assert result is not None
        # City of Threads: 2/2 = 100%, Ara-Kara: 1/2 = 50%
        assert result["dungeon"] == "City of Threads"
        assert result["timed_pct"] == 100.0


# ── Streaks ─────────────────────────────────────────────────────

class TestStreaks:
    def test_empty(self, session):
        streaks = get_streaks(session)
        assert streaks["current_streak"] == 0
        assert streaks["longest_timed_streak"] == 0
        assert streaks["longest_depletion_streak"] == 0

    def test_streak_tracking(self, session):
        for i, result in enumerate(["timed", "timed", "timed", "depleted", "timed"]):
            session.add(Run(
                dungeon_name="Test", key_level=10, result=result,
                created_at=datetime(2024, 1, 1) + timedelta(hours=i),
            ))
        session.commit()
        streaks = get_streaks(session)
        assert streaks["longest_timed_streak"] == 3
        assert streaks["longest_depletion_streak"] == 1
        assert streaks["current_streak"] == 1
        assert streaks["current_streak_type"] == "timed"


# ── Vibe Stats ──────────────────────────────────────────────────

class TestVibeStats:
    def test_empty(self, session):
        assert get_vibe_stats(session) == []

    def test_vibe_breakdown(self, session, multiple_runs):
        vibes = get_vibe_stats(session)
        assert len(vibes) > 0
        vibe_names = {v["vibe"] for v in vibes}
        assert "chill" in vibe_names
        assert "tilting" in vibe_names

    def test_null_vibes_excluded(self, session):
        session.add(Run(dungeon_name="Test", key_level=10, result="timed", vibe=None))
        session.commit()
        assert get_vibe_stats(session) == []


# ── Group Chemistry ─────────────────────────────────────────────

class TestGroupChemistry:
    def test_empty(self, session):
        assert get_group_chemistry(session) == []

    def test_needs_3_runs(self, session):
        char = Character(name="Friend", realm="Test", region="us")
        session.add(char)
        session.commit()
        session.refresh(char)
        for i in range(2):
            run = Run(dungeon_name="Test", key_level=10, result="timed")
            session.add(run)
            session.commit()
            session.refresh(run)
            session.add(RunMember(run_id=run.id, character_id=char.id, was_me=False))
        session.commit()
        assert get_group_chemistry(session) == []

    def test_titles(self, session):
        char = Character(name="BestFriend", realm="Test", region="us")
        session.add(char)
        session.commit()
        session.refresh(char)
        for i in range(50):
            run = Run(dungeon_name="Test", key_level=10, result="timed",
                      created_at=datetime(2024, 1, 1) + timedelta(hours=i))
            session.add(run)
            session.commit()
            session.refresh(run)
            session.add(RunMember(run_id=run.id, character_id=char.id, was_me=False))
        session.commit()
        chem = get_group_chemistry(session)
        assert len(chem) == 1
        assert chem[0]["title"] == "Ride or Die"


# ── Lucky Song ──────────────────────────────────────────────────

class TestLuckySong:
    def test_empty(self, session):
        assert get_lucky_song(session) is None

    def test_needs_3_appearances(self, session):
        for i in range(2):
            run = Run(dungeon_name="Test", key_level=10, result="timed")
            session.add(run)
            session.commit()
            session.refresh(run)
            session.add(RunSong(run_id=run.id, track_name="Song", artist_name="Artist"))
        session.commit()
        assert get_lucky_song(session) is None

    def test_lucky_song_found(self, session):
        for i in range(3):
            run = Run(dungeon_name="Test", key_level=10, result="timed",
                      created_at=datetime(2024, 1, 1) + timedelta(hours=i))
            session.add(run)
            session.commit()
            session.refresh(run)
            session.add(RunSong(run_id=run.id, track_name="Banger", artist_name="Artist"))
        session.commit()
        song = get_lucky_song(session)
        assert song is not None
        assert song["track"] == "Banger"
        assert song["timed_pct"] == 100.0


# ── Time of Day ─────────────────────────────────────────────────

class TestTimeOfDay:
    def test_empty(self, session):
        assert get_time_of_day_stats(session) == []

    def test_buckets(self, session, multiple_runs):
        stats = get_time_of_day_stats(session)
        assert len(stats) > 0
        periods = {s["period"] for s in stats}
        # We have runs at 20:30 (evening), 14:00 (afternoon), 2:00 (late night), 9:00 (morning)
        assert "Evening (6pm-12am)" in periods
        assert "Afternoon (12pm-6pm)" in periods


# ── Weekly Vault ────────────────────────────────────────────────

class TestWeeklyVault:
    def test_empty(self, session):
        vault = get_weekly_vault(session)
        assert vault["runs_this_week"] == 0
        assert not vault["slot1_unlocked"]

    def test_counts_recent_runs(self, session):
        now = datetime.utcnow()
        for i in range(4):
            session.add(Run(
                dungeon_name="Test", key_level=15 - i, result="timed",
                created_at=now - timedelta(hours=i),
            ))
        session.commit()
        vault = get_weekly_vault(session)
        assert vault["runs_this_week"] == 4
        assert vault["slot1_unlocked"]
        assert vault["slot2_unlocked"]
        assert not vault["slot3_unlocked"]


# ── Affix Stats ─────────────────────────────────────────────────

class TestAffixStats:
    def test_empty(self, session):
        assert get_affix_stats(session) == []

    def test_affix_breakdown(self, session, multiple_runs):
        stats = get_affix_stats(session)
        affix_names = {a["affix"] for a in stats}
        assert "Fortified" in affix_names
        assert "Tyrannical" in affix_names
        fort = next(a for a in stats if a["affix"] == "Fortified")
        assert fort["total"] == 2  # two runs with Fortified
        assert fort["timed"] == 2

    def test_bad_json_ignored(self, session):
        session.add(Run(dungeon_name="Test", key_level=10, result="timed",
                        affixes="not valid json"))
        session.commit()
        assert get_affix_stats(session) == []


# ── Lucky Mount/Pet ─────────────────────────────────────────────

class TestLuckyMountPet:
    def test_mount_empty(self, session):
        assert get_lucky_mount(session) is None

    def test_pet_empty(self, session):
        assert get_lucky_pet(session) is None

    def test_mount_found(self, session, multiple_runs):
        mount = get_lucky_mount(session)
        assert mount is not None
        assert mount["mount"] == "Invincible"

    def test_pet_found(self, session, multiple_runs):
        pet = get_lucky_pet(session)
        assert pet is not None
        assert pet["pet"] == "Lil Ragnaros"


# ── Time Margins ────────────────────────────────────────────────

class TestTimeMargins:
    def test_empty(self, session):
        margins = get_time_margin_stats(session)
        assert margins["timed_count"] == 0
        assert margins["avg_timed_margin"] is None

    def test_margins_calculated(self, session, multiple_runs):
        margins = get_time_margin_stats(session)
        assert margins["timed_count"] >= 1
        assert margins["avg_timed_margin"] is not None
        assert margins["avg_timed_margin"] > 0  # timed runs are under time


# ── Buff Compliance ─────────────────────────────────────────────

class TestBuffCompliance:
    def test_empty(self, session):
        assert get_buff_compliance_stats(session) is None

    def test_full_vs_no_buffs(self, session, multiple_runs):
        stats = get_buff_compliance_stats(session)
        assert stats is not None
        assert stats["full_buff"]["total"] >= 1
        assert stats["no_buff"]["total"] >= 1


# ── Gold Stats ──────────────────────────────────────────────────

class TestGoldStats:
    def test_empty(self, session):
        assert get_gold_stats(session) is None

    def test_gold_tracking(self, session, multiple_runs):
        stats = get_gold_stats(session)
        assert stats is not None
        assert stats["total_spent"] > 0
        assert stats["runs_tracked"] >= 1


# ── Role Stats ──────────────────────────────────────────────────

class TestRoleStats:
    def test_empty(self, session):
        assert get_role_stats(session) == []

    def test_spec_breakdown(self, session, multiple_runs):
        stats = get_role_stats(session)
        # Buddy (Mage/Fire) has 4 runs, should appear
        spec_names = {s["spec"] for s in stats}
        assert any("Fire" in s for s in spec_names)


# ── ilvl Analysis ───────────────────────────────────────────────

class TestIlvlAnalysis:
    def test_empty(self, session):
        assert get_ilvl_analysis(session) is None

    def test_needs_3_members(self, session, sample_run):
        # sample_run has 2 members, needs 3 for analysis
        result = get_ilvl_analysis(session)
        assert result is None


# ── Dungeon Tier List ───────────────────────────────────────────

class TestDungeonTierList:
    def test_empty(self, session):
        assert get_dungeon_tier_list(session) == []

    def test_tier_assignment(self, session, multiple_runs):
        tiers = get_dungeon_tier_list(session)
        assert len(tiers) == 2
        # City of Threads: 100% = S tier
        cot = next(t for t in tiers if t["dungeon"] == "City of Threads")
        assert cot["tier"] == "S"
        assert cot["timed_pct"] == 100.0
        # Ara-Kara: 50% = B tier
        ak = next(t for t in tiers if "Ara-Kara" in t["dungeon"])
        assert ak["tier"] == "B"

    def test_includes_avg_and_max_key(self, session, multiple_runs):
        tiers = get_dungeon_tier_list(session)
        for t in tiers:
            assert "avg_key" in t
            assert "max_key" in t
            assert t["max_key"] >= t["avg_key"]


# ── Guild Stats ─────────────────────────────────────────────────

class TestGuildStats:
    def test_empty(self, session):
        assert get_guild_stats(session) == []

    def test_guild_breakdown(self, session, multiple_runs):
        stats = get_guild_stats(session)
        guild_names = {g["guild"] for g in stats}
        assert "Other Guild" in guild_names


# ── Rating Analysis ─────────────────────────────────────────────

class TestRatingAnalysis:
    def test_empty(self, session):
        assert get_rating_analysis(session) == []

    def test_rating_breakdown(self, session, multiple_runs):
        ratings = get_rating_analysis(session)
        assert len(ratings) >= 1
        # We have ratings 1 and 5
        rating_values = {r["rating"] for r in ratings}
        assert 5 in rating_values
        assert 1 in rating_values

    def test_labels(self, session, multiple_runs):
        ratings = get_rating_analysis(session)
        for r in ratings:
            assert "label" in r
        r5 = next(r for r in ratings if r["rating"] == 5)
        assert r5["label"] == "Banger"
        r1 = next(r for r in ratings if r["rating"] == 1)
        assert r1["label"] == "Pain"

    def test_zero_ratings_excluded(self, session):
        session.add(Run(dungeon_name="Test", key_level=10, result="timed", rating=0))
        session.commit()
        assert get_rating_analysis(session) == []
