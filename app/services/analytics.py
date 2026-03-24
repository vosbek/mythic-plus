from sqlmodel import Session, select, func, col
from app.models import Run, RunMember, Character, RunSong


def get_overview_stats(session: Session) -> dict:
    total = session.exec(select(func.count(Run.id))).one()
    timed = session.exec(select(func.count(Run.id)).where(Run.result == "timed")).one()
    depleted = session.exec(select(func.count(Run.id)).where(Run.result == "depleted")).one()
    highest = session.exec(select(func.max(Run.key_level)).where(Run.result == "timed")).one()
    total_deaths = session.exec(select(func.sum(Run.deaths))).one() or 0

    return {
        "total_runs": total,
        "timed_runs": timed,
        "depleted_runs": depleted,
        "timed_pct": round(timed / total * 100, 1) if total > 0 else 0,
        "highest_timed_key": highest or 0,
        "total_deaths": total_deaths,
        "avg_deaths": round(total_deaths / total, 1) if total > 0 else 0,
    }


def get_nemesis_dungeon(session: Session) -> dict | None:
    """Dungeon with most depletions."""
    result = session.exec(
        select(Run.dungeon_name, func.count(Run.id).label("cnt"))
        .where(Run.result == "depleted")
        .group_by(Run.dungeon_name)
        .order_by(col(func.count(Run.id)).desc())
        .limit(1)
    ).first()
    if result:
        return {"dungeon": result[0], "depletions": result[1]}
    return None


def get_best_dungeon(session: Session) -> dict | None:
    """Dungeon with highest timed %."""
    dungeons = session.exec(
        select(
            Run.dungeon_name,
            func.count(Run.id).label("total"),
            func.sum(func.cast(Run.result == "timed", int)).label("timed"),
        )
        .group_by(Run.dungeon_name)
    ).all()

    best = None
    best_pct = -1
    for name, total, timed in dungeons:
        if total >= 2:  # need at least 2 runs
            pct = (timed or 0) / total * 100
            if pct > best_pct:
                best_pct = pct
                best = {"dungeon": name, "timed_pct": round(pct, 1), "total": total}
    return best


def get_streaks(session: Session) -> dict:
    """Current and longest timed/depletion streaks."""
    runs = session.exec(select(Run.result).order_by(Run.created_at)).all()

    current_streak = 0
    current_type = None
    longest_timed = 0
    longest_depleted = 0
    streak = 0
    streak_type = None

    for (result,) in runs:
        r = result if isinstance(result, str) else result
        if r == streak_type:
            streak += 1
        else:
            if streak_type == "timed":
                longest_timed = max(longest_timed, streak)
            elif streak_type == "depleted":
                longest_depleted = max(longest_depleted, streak)
            streak = 1
            streak_type = r

    # Final streak
    if streak_type == "timed":
        longest_timed = max(longest_timed, streak)
    elif streak_type == "depleted":
        longest_depleted = max(longest_depleted, streak)

    return {
        "current_streak": streak,
        "current_streak_type": streak_type,
        "longest_timed_streak": longest_timed,
        "longest_depletion_streak": longest_depleted,
    }


def get_vibe_stats(session: Session) -> list[dict]:
    """Timed % by vibe."""
    results = session.exec(
        select(
            Run.vibe,
            func.count(Run.id),
            func.sum(func.cast(Run.result == "timed", int)),
        )
        .where(Run.vibe.isnot(None))
        .group_by(Run.vibe)
    ).all()

    return [
        {
            "vibe": vibe,
            "total": total,
            "timed": timed or 0,
            "timed_pct": round((timed or 0) / total * 100, 1) if total > 0 else 0,
        }
        for vibe, total, timed in results
    ]


def get_group_chemistry(session: Session) -> list[dict]:
    """Win rate with frequent group members."""
    # Get characters who appear in 3+ runs and are not the user
    members = session.exec(
        select(
            RunMember.character_id,
            func.count(RunMember.id).label("run_count"),
        )
        .where(RunMember.was_me == False)
        .group_by(RunMember.character_id)
        .having(func.count(RunMember.id) >= 3)
        .order_by(col(func.count(RunMember.id)).desc())
        .limit(10)
    ).all()

    results = []
    for char_id, run_count in members:
        char = session.get(Character, char_id)
        if not char:
            continue
        # Count timed runs with this person
        timed = session.exec(
            select(func.count(RunMember.id))
            .join(Run, RunMember.run_id == Run.id)
            .where(RunMember.character_id == char_id, Run.result == "timed")
        ).one()

        title = ""
        if run_count >= 50:
            title = "Ride or Die"
        elif run_count >= 20:
            title = "Regular"
        elif run_count >= 10:
            title = "Buddy"
        else:
            title = "Acquaintance"

        results.append({
            "character": char,
            "run_count": run_count,
            "timed": timed,
            "timed_pct": round(timed / run_count * 100, 1) if run_count > 0 else 0,
            "title": title,
        })

    return results


def get_lucky_song(session: Session) -> dict | None:
    """Song with highest timed % (min 3 appearances)."""
    songs = session.exec(
        select(
            RunSong.track_name,
            RunSong.artist_name,
            func.count(RunSong.id).label("appearances"),
            func.sum(func.cast(Run.result == "timed", int)).label("timed"),
        )
        .join(Run, RunSong.run_id == Run.id)
        .group_by(RunSong.track_name, RunSong.artist_name)
        .having(func.count(RunSong.id) >= 3)
        .order_by(col(func.sum(func.cast(Run.result == "timed", int))).desc())
        .limit(1)
    ).first()

    if songs:
        return {
            "track": songs[0],
            "artist": songs[1],
            "appearances": songs[2],
            "timed": songs[3] or 0,
            "timed_pct": round((songs[3] or 0) / songs[2] * 100, 1) if songs[2] > 0 else 0,
        }
    return None


def get_time_of_day_stats(session: Session) -> list[dict]:
    """Performance by time of day (bucketed by hour blocks)."""
    runs = session.exec(select(Run).where(Run.started_at.isnot(None))).all()
    buckets = {
        "Morning (6am-12pm)": {"total": 0, "timed": 0},
        "Afternoon (12pm-6pm)": {"total": 0, "timed": 0},
        "Evening (6pm-12am)": {"total": 0, "timed": 0},
        "Late Night (12am-6am)": {"total": 0, "timed": 0},
    }
    for run in runs:
        hour = run.started_at.hour
        if 6 <= hour < 12:
            bucket = "Morning (6am-12pm)"
        elif 12 <= hour < 18:
            bucket = "Afternoon (12pm-6pm)"
        elif 18 <= hour < 24:
            bucket = "Evening (6pm-12am)"
        else:
            bucket = "Late Night (12am-6am)"
        buckets[bucket]["total"] += 1
        if run.result == "timed":
            buckets[bucket]["timed"] += 1

    return [
        {
            "period": k,
            "total": v["total"],
            "timed": v["timed"],
            "timed_pct": round(v["timed"] / v["total"] * 100, 1) if v["total"] > 0 else 0,
        }
        for k, v in buckets.items()
        if v["total"] > 0
    ]


def get_weekly_vault(session: Session) -> dict:
    """Calculate Great Vault options based on runs this week."""
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    # Start of this week (Tuesday reset)
    days_since_tuesday = (now.weekday() - 1) % 7
    week_start = (now - timedelta(days=days_since_tuesday)).replace(hour=15, minute=0, second=0, microsecond=0)
    if now < week_start:
        week_start -= timedelta(days=7)

    runs = session.exec(
        select(Run)
        .where(Run.created_at >= week_start, Run.result.in_(["timed", "completed"]))
        .order_by(Run.key_level.desc())
    ).all()

    key_levels = [r.key_level for r in runs]

    # Vault slots: top 1 for slot 1, top 4 avg for slot 2, top 8 avg for slot 3
    slot1 = key_levels[0] if len(key_levels) >= 1 else None
    slot2 = key_levels[3] if len(key_levels) >= 4 else None
    slot3 = key_levels[7] if len(key_levels) >= 8 else None

    return {
        "runs_this_week": len(runs),
        "slot1": slot1,
        "slot2": slot2,
        "slot3": slot3,
        "slot1_unlocked": len(runs) >= 1,
        "slot2_unlocked": len(runs) >= 4,
        "slot3_unlocked": len(runs) >= 8,
    }
