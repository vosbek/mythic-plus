import json
from sqlmodel import Session, select, func
from app.models import Run, RunMember, Character, RunSong


def get_overview_stats(session: Session) -> dict:
    total = session.exec(select(func.count(Run.id))).one()
    timed = session.exec(select(func.count(Run.id)).where(Run.result == "timed")).one()
    depleted = session.exec(select(func.count(Run.id)).where(Run.result == "depleted")).one()
    highest = session.exec(select(func.max(Run.key_level)).where(Run.result == "timed")).one()
    total_deaths = session.exec(select(func.sum(Run.deaths))).one() or 0

    # Gold spent
    total_gold_spent = 0
    gold_runs = session.exec(
        select(Run).where(Run.gold_before.isnot(None), Run.gold_after.isnot(None))
    ).all()
    for run in gold_runs:
        total_gold_spent += max(0, run.gold_before - run.gold_after)

    # Total played time in M+
    total_played = session.exec(
        select(func.sum(Run.played_seconds)).where(Run.played_seconds.isnot(None))
    ).one() or 0

    return {
        "total_runs": total,
        "timed_runs": timed,
        "depleted_runs": depleted,
        "timed_pct": round(timed / total * 100, 1) if total > 0 else 0,
        "highest_timed_key": highest or 0,
        "total_deaths": total_deaths,
        "avg_deaths": round(total_deaths / total, 1) if total > 0 else 0,
        "total_gold_spent": total_gold_spent,
        "total_played_hours": round(total_played / 3600, 1) if total_played else 0,
    }


def get_nemesis_dungeon(session: Session) -> dict | None:
    """Dungeon with most depletions."""
    result = session.exec(
        select(Run.dungeon_name, func.count(Run.id).label("cnt"))
        .where(Run.result == "depleted")
        .group_by(Run.dungeon_name)
        .order_by(func.count(Run.id).desc())
        .limit(1)
    ).first()
    if result:
        return {"dungeon": result[0], "depletions": result[1]}
    return None


def get_best_dungeon(session: Session) -> dict | None:
    """Dungeon with highest timed %."""
    runs = session.exec(select(Run.dungeon_name, Run.result)).all()
    dungeon_data = {}
    for name, result in runs:
        if name not in dungeon_data:
            dungeon_data[name] = {"total": 0, "timed": 0}
        dungeon_data[name]["total"] += 1
        if result == "timed":
            dungeon_data[name]["timed"] += 1

    best = None
    best_pct = -1
    for name, d in dungeon_data.items():
        if d["total"] >= 2:
            pct = d["timed"] / d["total"] * 100
            if pct > best_pct:
                best_pct = pct
                best = {"dungeon": name, "timed_pct": round(pct, 1), "total": d["total"]}
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

    for item in runs:
        r = item if isinstance(item, str) else item[0]
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
    runs = session.exec(
        select(Run.vibe, Run.result).where(Run.vibe.isnot(None))
    ).all()

    vibe_data = {}
    for vibe, result in runs:
        if vibe not in vibe_data:
            vibe_data[vibe] = {"total": 0, "timed": 0}
        vibe_data[vibe]["total"] += 1
        if result == "timed":
            vibe_data[vibe]["timed"] += 1

    return [
        {
            "vibe": vibe,
            "total": d["total"],
            "timed": d["timed"],
            "timed_pct": round(d["timed"] / d["total"] * 100, 1) if d["total"] > 0 else 0,
        }
        for vibe, d in vibe_data.items()
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
        .order_by(func.count(RunMember.id).desc())
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
        select(RunSong.track_name, RunSong.artist_name, Run.result)
        .join(Run, RunSong.run_id == Run.id)
    ).all()

    song_data = {}
    for track, artist, result in songs:
        key = (track, artist)
        if key not in song_data:
            song_data[key] = {"total": 0, "timed": 0}
        song_data[key]["total"] += 1
        if result == "timed":
            song_data[key]["timed"] += 1

    best = None
    best_pct = -1
    for (track, artist), d in song_data.items():
        if d["total"] >= 3:
            pct = d["timed"] / d["total"] * 100
            if pct > best_pct:
                best_pct = pct
                best = {
                    "track": track,
                    "artist": artist,
                    "appearances": d["total"],
                    "timed": d["timed"],
                    "timed_pct": round(pct, 1),
                }
    return best


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


def get_affix_stats(session: Session) -> list[dict]:
    """Performance breakdown by affix."""
    runs = session.exec(
        select(Run).where(Run.affixes.isnot(None))
    ).all()

    affix_data = {}  # affix_name -> { total, timed }
    for run in runs:
        try:
            affixes = json.loads(run.affixes)
        except (json.JSONDecodeError, TypeError):
            continue
        for affix in affixes:
            if affix not in affix_data:
                affix_data[affix] = {"total": 0, "timed": 0}
            affix_data[affix]["total"] += 1
            if run.result == "timed":
                affix_data[affix]["timed"] += 1

    return sorted([
        {
            "affix": name,
            "total": d["total"],
            "timed": d["timed"],
            "timed_pct": round(d["timed"] / d["total"] * 100, 1) if d["total"] > 0 else 0,
        }
        for name, d in affix_data.items()
    ], key=lambda x: x["total"], reverse=True)


def get_lucky_mount(session: Session) -> dict | None:
    """Mount with highest timed % (min 2 appearances)."""
    runs = session.exec(
        select(Run.my_mount, Run.result)
        .where(Run.my_mount.isnot(None))
    ).all()

    mount_data = {}
    for mount, result in runs:
        if mount not in mount_data:
            mount_data[mount] = {"total": 0, "timed": 0}
        mount_data[mount]["total"] += 1
        if result == "timed":
            mount_data[mount]["timed"] += 1

    best = None
    best_pct = -1
    for name, d in mount_data.items():
        if d["total"] >= 2:
            pct = d["timed"] / d["total"] * 100
            if pct > best_pct:
                best_pct = pct
                best = {
                    "mount": name,
                    "total": d["total"],
                    "timed": d["timed"],
                    "timed_pct": round(pct, 1),
                }
    return best


def get_lucky_pet(session: Session) -> dict | None:
    """Companion pet with highest timed % (min 2 appearances)."""
    runs = session.exec(
        select(Run.companion_pet, Run.result)
        .where(Run.companion_pet.isnot(None))
    ).all()

    pet_data = {}
    for pet, result in runs:
        if pet not in pet_data:
            pet_data[pet] = {"total": 0, "timed": 0}
        pet_data[pet]["total"] += 1
        if result == "timed":
            pet_data[pet]["timed"] += 1

    best = None
    best_pct = -1
    for name, d in pet_data.items():
        if d["total"] >= 2:
            pct = d["timed"] / d["total"] * 100
            if pct > best_pct:
                best_pct = pct
                best = {
                    "pet": name,
                    "total": d["total"],
                    "timed": d["timed"],
                    "timed_pct": round(pct, 1),
                }
    return best


def get_time_margin_stats(session: Session) -> dict:
    """How close are timed runs? How badly are depletions missed?"""
    timed_margins = []
    depleted_margins = []

    runs = session.exec(
        select(Run).where(
            Run.duration_seconds.isnot(None),
            Run.time_limit_seconds.isnot(None),
        )
    ).all()

    for run in runs:
        margin = run.time_limit_seconds - run.duration_seconds  # positive = under time
        if run.result == "timed":
            timed_margins.append(margin)
        elif run.result in ("depleted", "completed"):
            depleted_margins.append(margin)

    return {
        "avg_timed_margin": round(sum(timed_margins) / len(timed_margins)) if timed_margins else None,
        "closest_time": min(timed_margins) if timed_margins else None,
        "biggest_time": max(timed_margins) if timed_margins else None,
        "avg_over_time": round(sum(depleted_margins) / len(depleted_margins)) if depleted_margins else None,
        "timed_count": len(timed_margins),
        "depleted_count": len(depleted_margins),
    }


def get_buff_compliance_stats(session: Session) -> dict | None:
    """Do fully-buffed groups time keys more often?"""
    runs = session.exec(
        select(Run).where(Run.buffs_json.isnot(None))
    ).all()

    if not runs:
        return None

    full_buff = {"total": 0, "timed": 0}
    partial_buff = {"total": 0, "timed": 0}
    no_buff = {"total": 0, "timed": 0}

    for run in runs:
        try:
            buffs = json.loads(run.buffs_json)
        except (json.JSONDecodeError, TypeError):
            continue

        flask_count = len(buffs.get("flask", []))
        food_count = len(buffs.get("food", []))

        # 5 flasks + 5 food = fully buffed
        if flask_count >= 5 and food_count >= 5:
            bucket = full_buff
        elif flask_count > 0 or food_count > 0:
            bucket = partial_buff
        else:
            bucket = no_buff

        bucket["total"] += 1
        if run.result == "timed":
            bucket["timed"] += 1

    return {
        "full_buff": {**full_buff, "timed_pct": round(full_buff["timed"] / full_buff["total"] * 100, 1) if full_buff["total"] > 0 else 0},
        "partial_buff": {**partial_buff, "timed_pct": round(partial_buff["timed"] / partial_buff["total"] * 100, 1) if partial_buff["total"] > 0 else 0},
        "no_buff": {**no_buff, "timed_pct": round(no_buff["timed"] / no_buff["total"] * 100, 1) if no_buff["total"] > 0 else 0},
    }


def get_gold_stats(session: Session) -> dict | None:
    """Gold economy analysis."""
    runs = session.exec(
        select(Run).where(
            Run.gold_before.isnot(None),
            Run.gold_after.isnot(None),
        )
    ).all()

    if not runs:
        return None

    costs = []
    timed_costs = []
    depleted_costs = []

    for run in runs:
        cost = max(0, run.gold_before - run.gold_after)
        costs.append(cost)
        if run.result == "timed":
            timed_costs.append(cost)
        else:
            depleted_costs.append(cost)

    return {
        "total_spent": sum(costs),
        "avg_cost": round(sum(costs) / len(costs)) if costs else 0,
        "avg_timed_cost": round(sum(timed_costs) / len(timed_costs)) if timed_costs else 0,
        "avg_depleted_cost": round(sum(depleted_costs) / len(depleted_costs)) if depleted_costs else 0,
        "runs_tracked": len(costs),
    }


def get_role_stats(session: Session) -> list[dict]:
    """Performance by role composition — which specs do you time most with?"""
    # Get spec performance across all runs
    spec_data = {}
    members = session.exec(
        select(RunMember.spec, RunMember.role, Run.result)
        .join(Run, RunMember.run_id == Run.id)
        .where(RunMember.was_me == False, RunMember.spec.isnot(None))
    ).all()

    for spec, role, result in members:
        key = f"{spec} ({role})" if role else spec
        if key not in spec_data:
            spec_data[key] = {"total": 0, "timed": 0}
        spec_data[key]["total"] += 1
        if result == "timed":
            spec_data[key]["timed"] += 1

    results = [
        {
            "spec": name,
            "total": d["total"],
            "timed": d["timed"],
            "timed_pct": round(d["timed"] / d["total"] * 100, 1) if d["total"] > 0 else 0,
        }
        for name, d in spec_data.items()
        if d["total"] >= 2
    ]
    return sorted(results, key=lambda x: x["total"], reverse=True)[:15]


def get_ilvl_analysis(session: Session) -> dict | None:
    """How does group ilvl relate to key timing?"""
    runs_with_ilvl = session.exec(
        select(Run.id, Run.key_level, Run.result)
    ).all()

    data_points = []
    for row in runs_with_ilvl:
        run_id = row[0] if isinstance(row, tuple) else row.id
        key_level = row[1] if isinstance(row, tuple) else row.key_level
        result = row[2] if isinstance(row, tuple) else row.result
        ilvl_rows = session.exec(
            select(RunMember.ilvl)
            .where(RunMember.run_id == run_id, RunMember.ilvl.isnot(None))
        ).all()
        if len(ilvl_rows) >= 3:  # need at least 3 members with ilvl data
            ilvl_vals = [i[0] if isinstance(i, tuple) else i for i in ilvl_rows]
            avg_ilvl = sum(ilvl_vals) / len(ilvl_vals)
            data_points.append({
                "key_level": key_level,
                "avg_ilvl": round(avg_ilvl, 1),
                "timed": result == "timed",
            })

    if not data_points:
        return None

    timed_ilvls = [d["avg_ilvl"] for d in data_points if d["timed"]]
    depleted_ilvls = [d["avg_ilvl"] for d in data_points if not d["timed"]]

    return {
        "data_points": len(data_points),
        "avg_timed_ilvl": round(sum(timed_ilvls) / len(timed_ilvls), 1) if timed_ilvls else None,
        "avg_depleted_ilvl": round(sum(depleted_ilvls) / len(depleted_ilvls), 1) if depleted_ilvls else None,
    }


def get_dungeon_tier_list(session: Session) -> list[dict]:
    """Personal dungeon tier list based on timed % and avg key level."""
    runs = session.exec(select(Run)).all()

    dungeon_data = {}
    for run in runs:
        name = run.dungeon_name
        if name not in dungeon_data:
            dungeon_data[name] = {"total": 0, "timed": 0, "keys": [], "max_key": 0}
        dungeon_data[name]["total"] += 1
        if run.result == "timed":
            dungeon_data[name]["timed"] += 1
        dungeon_data[name]["keys"].append(run.key_level)
        dungeon_data[name]["max_key"] = max(dungeon_data[name]["max_key"], run.key_level)

    results = []
    for name, d in dungeon_data.items():
        total = d["total"]
        timed = d["timed"]
        pct = round(timed / total * 100, 1) if total > 0 else 0
        avg_key = round(sum(d["keys"]) / len(d["keys"]), 1) if d["keys"] else 0
        # Tier based on timed %
        if pct >= 80:
            tier = "S"
        elif pct >= 60:
            tier = "A"
        elif pct >= 40:
            tier = "B"
        elif pct >= 20:
            tier = "C"
        else:
            tier = "D"

        results.append({
            "dungeon": name,
            "total": total,
            "timed": timed,
            "timed_pct": pct,
            "avg_key": avg_key,
            "max_key": d["max_key"],
            "tier": tier,
        })

    return sorted(results, key=lambda x: x["timed_pct"], reverse=True)


def get_guild_stats(session: Session) -> list[dict]:
    """Performance grouped by guild of party members."""
    members = session.exec(
        select(Character.guild, Run.result)
        .join(RunMember, RunMember.character_id == Character.id)
        .join(Run, RunMember.run_id == Run.id)
        .where(RunMember.was_me == False, Character.guild.isnot(None))
    ).all()

    guild_data = {}
    for guild, result in members:
        if not guild:
            continue
        if guild not in guild_data:
            guild_data[guild] = {"total": 0, "timed": 0}
        guild_data[guild]["total"] += 1
        if result == "timed":
            guild_data[guild]["timed"] += 1

    results = [
        {
            "guild": name,
            "runs": d["total"],
            "timed": d["timed"],
            "timed_pct": round(d["timed"] / d["total"] * 100, 1) if d["total"] > 0 else 0,
        }
        for name, d in guild_data.items()
        if d["total"] >= 2
    ]
    return sorted(results, key=lambda x: x["runs"], reverse=True)[:10]


def get_rating_analysis(session: Session) -> list[dict]:
    """Does your fun rating correlate with timing keys?"""
    runs = session.exec(
        select(Run.rating, Run.result)
        .where(Run.rating.isnot(None), Run.rating > 0)
    ).all()

    rating_data = {}
    for rating, result in runs:
        if rating not in rating_data:
            rating_data[rating] = {"total": 0, "timed": 0}
        rating_data[rating]["total"] += 1
        if result == "timed":
            rating_data[rating]["timed"] += 1

    labels = {1: "Pain", 2: "Meh", 3: "Fine", 4: "Fun", 5: "Banger"}
    return sorted([
        {
            "rating": r,
            "label": labels.get(r, str(r)),
            "total": d["total"],
            "timed": d["timed"],
            "timed_pct": round(d["timed"] / d["total"] * 100, 1) if d["total"] > 0 else 0,
        }
        for r, d in rating_data.items()
    ], key=lambda x: x["rating"])
