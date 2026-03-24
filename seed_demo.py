"""Seed the database with realistic demo data for testing/demo purposes.

Usage: python seed_demo.py
"""
import json
import random
from datetime import datetime, timedelta
from app.database import init_db, engine
from app.models import Run, RunMember, Character, RunSong
from app.config import DUNGEONS, VIBES
from sqlmodel import Session, select

SPECS = {
    "Warrior": [("Arms", "dps"), ("Fury", "dps"), ("Protection", "tank")],
    "Paladin": [("Holy", "healer"), ("Protection", "tank"), ("Retribution", "dps")],
    "Death Knight": [("Blood", "tank"), ("Frost", "dps"), ("Unholy", "dps")],
    "Druid": [("Balance", "dps"), ("Feral", "dps"), ("Guardian", "tank"), ("Restoration", "healer")],
    "Monk": [("Brewmaster", "tank"), ("Mistweaver", "healer"), ("Windwalker", "dps")],
    "Demon Hunter": [("Havoc", "dps"), ("Vengeance", "tank")],
    "Evoker": [("Devastation", "dps"), ("Preservation", "healer"), ("Augmentation", "dps")],
    "Hunter": [("Beast Mastery", "dps"), ("Marksmanship", "dps"), ("Survival", "dps")],
    "Mage": [("Arcane", "dps"), ("Fire", "dps"), ("Frost", "dps")],
    "Priest": [("Discipline", "healer"), ("Holy", "healer"), ("Shadow", "dps")],
    "Rogue": [("Assassination", "dps"), ("Outlaw", "dps"), ("Subtlety", "dps")],
    "Shaman": [("Elemental", "dps"), ("Enhancement", "dps"), ("Restoration", "healer")],
    "Warlock": [("Affliction", "dps"), ("Demonology", "dps"), ("Destruction", "dps")],
}

RACES = ["Human", "Night Elf", "Dwarf", "Gnome", "Draenei", "Worgen", "Void Elf",
         "Orc", "Troll", "Tauren", "Blood Elf", "Goblin", "Nightborne",
         "Dark Iron Dwarf", "Dracthyr", "Earthen"]

GUILDS = ["Last Pull", "Keyboard Turners", "Wipe Club", "Loot Council Rejects",
          "AFK in Dalaran", "Casually Hardcore", "Two Chest Andy", None, None]

MOUNTS = ["Invincible", "Ashes of Al'ar", "Swift Spectral Tiger", "Headless Horseman's Mount",
          "Mighty Caravan Brutosaur", "X-53 Touring Rocket", "Llothien Prowler",
          "Black Qiraji Battle Tank", "Mimiron's Head", "Smoldering Ember Wyrm"]

PETS = ["Lil' Ragnaros", "Murky", "Mini Tyrael", "Pebble", "Xu-Fu", None, None, None]

SONGS = [
    ("Through the Fire and Flames", "DragonForce"),
    ("Eye of the Tiger", "Survivor"),
    ("Thunderstruck", "AC/DC"),
    ("Don't Stop Me Now", "Queen"),
    ("Immigrant Song", "Led Zeppelin"),
    ("Smells Like Teen Spirit", "Nirvana"),
    ("Lose Yourself", "Eminem"),
    ("Bohemian Rhapsody", "Queen"),
    ("Seven Nation Army", "The White Stripes"),
    ("Sandstorm", "Darude"),
]

NAMES = [
    "Saytees", "Grompus", "Fluffybuns", "Stabsworth", "Moonfire",
    "Tankbert", "Healzplz", "Zugzug", "Critmaster", "Loothoarder",
    "Keypusher", "Dpsbot", "Sheepgirl", "Rootbeard", "Facepull",
    "Bubblegirl", "Smashguy", "Zapmaster", "Dotweaver", "Shieldwall",
    "Arrowrain", "Holylight", "Shadowstep", "Lavaburster", "Icyveins",
]


def seed_demo_data():
    init_db()

    with Session(engine) as session:
        # Check if data already exists
        existing = session.exec(select(Run)).first()
        if existing:
            print("Database already has runs. Use 'python seed_demo.py --force' to override.")
            import sys
            if "--force" not in sys.argv:
                return
            # Clear existing data
            for model in [RunSong, RunMember, Run]:
                for obj in session.exec(select(model)).all():
                    session.delete(obj)
            session.commit()
            print("Cleared existing run data.")

        # Create characters
        chars = []
        for i, name in enumerate(NAMES):
            cls = random.choice(list(SPECS.keys()))
            spec_name, role = random.choice(SPECS[cls])
            char = session.exec(
                select(Character).where(Character.name == name, Character.realm == "Stormrage")
            ).first()
            if not char:
                char = Character(
                    name=name,
                    realm="Stormrage",
                    region="us",
                    class_name=cls,
                    race=random.choice(RACES),
                    spec=spec_name,
                    role=role,
                    guild=random.choice(GUILDS),
                    is_mine=(name == "Saytees"),
                    raiderio_score=random.uniform(1800, 3200) if random.random() > 0.3 else None,
                )
                session.add(char)
            chars.append((char, cls, spec_name, role))
        session.commit()
        for i, (char, _, _, _) in enumerate(chars):
            session.refresh(char)

        my_char = chars[0]  # Saytees

        # Generate 60 runs over 6 weeks
        base_date = datetime.now() - timedelta(weeks=6)
        dungeon_names = [d["name"] for d in DUNGEONS]

        for run_idx in range(60):
            dungeon_cfg = random.choice(DUNGEONS)
            dungeon_name = dungeon_cfg["name"]
            time_limit = dungeon_cfg["time_limit_seconds"]
            key_level = random.choices(
                range(8, 22),
                weights=[1, 2, 4, 6, 8, 8, 6, 4, 3, 2, 1, 1, 1, 1],
            )[0]

            # Higher keys are harder to time
            time_pct = max(0.2, 0.85 - (key_level - 10) * 0.05 + random.uniform(-0.15, 0.15))
            timed = random.random() < time_pct
            if timed:
                result = "timed"
                duration = int(time_limit * random.uniform(0.7, 0.98))
                upgrade_count = 3 if duration < time_limit * 0.6 else (2 if duration < time_limit * 0.8 else 1)
            else:
                if random.random() < 0.85:
                    result = "depleted"
                    duration = int(time_limit * random.uniform(1.01, 1.4))
                else:
                    result = "abandoned"
                    duration = int(time_limit * random.uniform(0.3, 0.9))
                upgrade_count = None

            deaths = 0 if timed and random.random() < 0.3 else random.randint(0, 3 if timed else 12)

            run_date = base_date + timedelta(
                days=run_idx * 0.7 + random.uniform(-0.3, 0.3),
                hours=random.choice([10, 14, 19, 20, 21, 22, 23, 1, 2]),
                minutes=random.randint(0, 59),
            )

            affix = random.choice(["Fortified", "Tyrannical"])
            secondary_affixes = random.sample(
                ["Bursting", "Bolstering", "Sanguine", "Raging", "Spiteful", "Grievous"],
                k=random.randint(0, 2),
            )

            vibe = random.choice(VIBES) if random.random() > 0.2 else None
            rating = random.choices([1, 2, 3, 4, 5], weights=[2, 3, 5, 6, 4])[0] if random.random() > 0.3 else None

            mount = random.choice(MOUNTS) if random.random() > 0.3 else None
            pet = random.choice(PETS)

            has_gold = random.random() > 0.4
            gold_before = random.randint(50000000, 200000000) if has_gold else None
            gold_cost = random.randint(10000, 80000) if has_gold else 0
            gold_after = (gold_before - gold_cost) if has_gold else None

            has_durability = random.random() > 0.5
            durability_before = round(random.uniform(85, 100), 1) if has_durability else None
            durability_after = round(random.uniform(20, durability_before or 80), 1) if has_durability else None

            has_buffs = random.random() > 0.3
            if has_buffs:
                num_flask = random.choices([0, 3, 5], weights=[1, 2, 7])[0]
                num_food = random.choices([0, 3, 5], weights=[1, 2, 7])[0]
                buffs = {
                    "flask": [NAMES[j] for j in random.sample(range(len(NAMES)), min(num_flask, 5))],
                    "food": [NAMES[j] for j in random.sample(range(len(NAMES)), min(num_food, 5))],
                    "rune": [],
                }
            else:
                buffs = None

            notes_options = [
                None, None, None, None,  # most runs have no notes
                "Clean run, good pulls",
                "Tank disconnected on boss 2",
                "WHAT A KEY",
                "Healer carried hard",
                "Should have played this better",
                "First time in this dungeon",
                "Bad pull on trash before last boss",
                "DPS was insane this group",
                "Never again at this key level",
                "Close one!",
            ]

            run = Run(
                dungeon_name=dungeon_name,
                key_level=key_level,
                result=result,
                duration_seconds=duration,
                time_limit_seconds=time_limit,
                upgrade_count=upgrade_count,
                deaths=deaths,
                started_at=run_date,
                completed_at=run_date + timedelta(seconds=duration),
                season="midnight-1",
                affixes=json.dumps([affix] + secondary_affixes),
                notes=random.choice(notes_options),
                rating=rating,
                vibe=vibe,
                source="addon",
                addon_run_id=f"demo-{run_idx}",
                gold_before=gold_before,
                gold_after=gold_after,
                durability_before=durability_before,
                durability_after=durability_after,
                companion_pet=pet,
                my_mount=mount,
                played_seconds=duration + random.randint(30, 180) if random.random() > 0.4 else None,
                buffs_json=json.dumps(buffs) if buffs else None,
                created_at=run_date,
            )
            session.add(run)
            session.commit()
            session.refresh(run)

            # Add 5 group members
            group_indices = [0]  # always include Saytees
            available = list(range(1, len(chars)))
            # Bias towards picking the same people
            regulars = available[:6]
            puggers = available[6:]
            num_regulars = random.randint(1, min(3, len(regulars)))
            num_puggers = 4 - num_regulars
            group_indices.extend(random.sample(regulars, num_regulars))
            group_indices.extend(random.sample(puggers, min(num_puggers, len(puggers))))

            for idx in group_indices[:5]:
                char, cls, spec_name, role = chars[idx]
                ilvl = round(random.uniform(600, 630) + key_level * 0.5, 1)
                member_mount = random.choice(MOUNTS) if random.random() > 0.5 else None

                rm = RunMember(
                    run_id=run.id,
                    character_id=char.id,
                    spec=spec_name,
                    role=role,
                    was_me=(idx == 0),
                    ilvl=ilvl,
                    mount=member_mount,
                )
                session.add(rm)

            # Add songs to ~40% of runs
            if random.random() < 0.4:
                num_songs = random.randint(1, 4)
                for _ in range(num_songs):
                    track, artist = random.choice(SONGS)
                    session.add(RunSong(
                        run_id=run.id,
                        track_name=track,
                        artist_name=artist,
                        album_name="Greatest Hits",
                        played_at=run_date + timedelta(minutes=random.randint(0, 30)),
                    ))

            session.commit()

        print(f"Seeded 60 demo runs with {len(chars)} characters.")
        print("Run the app with: uvicorn app.main:app --reload")


if __name__ == "__main__":
    seed_demo_data()
