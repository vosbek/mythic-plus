# Mythic+ Tracker

A personal companion app for tracking WoW Mythic+ dungeon runs during Midnight Season 1. Automatically captures run data from in-game via a lightweight addon, enriches it with Warcraft Logs and Raider.IO data, and tracks what music you were listening to on Spotify.

## What It Does

- **Auto-capture runs** from a WoW addon (dungeon, key, time, deaths, group comp, buffs, gold, durability, mounts, pets)
- **Manual run logging** with vibe ratings, fun scores, and notes
- **20+ analytics** including dungeon tier list, affix performance, buff compliance, time margins, lucky charms, group chemistry, gold economy
- **Character profiles** via Raider.IO (scores, best runs, gear)
- **Warcraft Logs integration** to pull DPS/HPS data for your runs
- **Spotify integration** to capture your soundtrack during keys
- **Weekly vault tracker** based on this week's completed runs

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Start the app
uvicorn app.main:app --reload
```

Open **http://localhost:8000**

That's it. The app creates a SQLite database automatically and seeds the season 1 dungeon list on first run.

### Try it with demo data

```bash
python seed_demo.py
```

This generates 60 realistic runs with 25 characters, complete with affixes, buffs, gold costs, mounts, pets, songs, and vibes. Great for exploring the UI before connecting your own data.

## Getting Your Data In

There are three ways to get run data into the tracker:

### 1. WoW Addon (recommended)

The addon captures everything automatically when you finish a key.

**Install:**

1. Copy the `wow_addon/MythicPlusTracker` folder into your WoW addons directory:
   - **Windows:** `C:\Program Files\World of Warcraft\_retail_\Interface\AddOns\`
   - **Mac:** `/Applications/World of Warcraft/_retail_/Interface/AddOns/`
2. Restart WoW or type `/reload`
3. You should see `[M+Tracker] Loaded` in chat

**Use:**

Just run keys. The addon automatically saves data when a key completes. Use `/mpt status` to check how many runs are saved.

**Import:**

1. Go to **Import > Addon** in the app
2. Enter your SavedVariables path (or set `WOW_SAVEDVARIABLES_PATH` in `.env`)
   - **Windows:** `C:\Program Files\World of Warcraft\_retail_\WTF\Account\YOURACCOUNT\SavedVariables\MythicPlusTracker.lua`
   - **Mac:** `/Applications/World of Warcraft/_retail_/WTF/Account/YOURACCOUNT/SavedVariables/MythicPlusTracker.lua`
3. Click Import. Duplicate runs are automatically skipped.

**What the addon captures per run:**

| Data | Details |
|------|---------|
| Run info | Dungeon, key level, result, time, deaths, affixes, upgrade stars |
| Group | Name, realm, class, race, spec, role, ilvl, guild, title, mount for each member |
| Economy | Gold before/after, durability before/after |
| Buffs | Pre-key flask/food/rune check for each player |
| Fun | Your mount, companion pet, /played time |

### 2. Warcraft Logs (optional)

Pulls run data from your WCL reports and enriches runs with DPS/HPS numbers.

1. Create an API client at https://www.warcraftlogs.com/api/clients/
2. Add to `.env`:
   ```
   WCL_CLIENT_ID=your_client_id
   WCL_CLIENT_SECRET=your_client_secret
   ```
3. Go to **Import > Warcraft Logs** and enter your character name/realm

### 3. Manual Entry

Go to **Log a Run** and fill in the form. Supports all fields including group composition (5 players), affixes, vibe, fun rating, and notes.

## Spotify Integration (optional)

Captures what songs were playing during your runs.

1. Create an app at https://developer.spotify.com/dashboard
2. Set the redirect URI to `http://localhost:8000/spotify/callback`
3. Add to `.env`:
   ```
   SPOTIFY_CLIENT_ID=your_client_id
   SPOTIFY_CLIENT_SECRET=your_client_secret
   ```
4. Go to the **Spotify** page in the app and click Connect
5. Start tracking before a run, stop after — captured songs appear on the run detail page

## Configuration

Copy `.env.example` to `.env` and fill in what you need:

```bash
cp .env.example .env
```

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | No | `sqlite:///mythicplus.db` | Database connection string |
| `WOW_SAVEDVARIABLES_PATH` | No | (empty) | Path to addon SavedVariables file |
| `SPOTIFY_CLIENT_ID` | No | (empty) | Spotify OAuth client ID |
| `SPOTIFY_CLIENT_SECRET` | No | (empty) | Spotify OAuth client secret |
| `SPOTIFY_REDIRECT_URI` | No | `http://localhost:8000/spotify/callback` | Spotify OAuth redirect |
| `WCL_CLIENT_ID` | No | (empty) | Warcraft Logs API client ID |
| `WCL_CLIENT_SECRET` | No | (empty) | Warcraft Logs API client secret |

Nothing is required. The app works out of the box with just manual run entry and Raider.IO lookups (no auth needed).

## Analytics

The stats page at `/stats` shows:

| Section | What it tells you |
|---------|-------------------|
| **Dungeon Tier List** | Your personal S/A/B/C/D tier for each dungeon based on timed % |
| **Timing Margins** | How close your times are — avg under timer, closest time, avg over on depletes |
| **Affix Performance** | Timed % per affix — find your kryptonite |
| **Buff Compliance** | Does being fully buffed actually matter? (spoiler: yes) |
| **Vibe Check** | Timed % by vibe — are you better chill or sweaty? |
| **Fun Rating vs Success** | Does having fun correlate with timing keys? |
| **Spec Performance** | Which specs you time most with |
| **Group Chemistry** | Win rates with frequent group members, with titles (Ride or Die, Regular, Buddy) |
| **Guild Performance** | Timed % by guild |
| **Lucky Charms** | Lucky song, mount, and pet (highest timed %) |
| **Gold Economy** | Total spent, avg cost per timed vs depleted key |
| **Item Level Analysis** | Avg ilvl on timed vs depleted runs |
| **Time of Day** | Performance by morning/afternoon/evening/late night |
| **Weekly Vault** | Current vault slot progress and unlock status |

## Addon Commands

| Command | Description |
|---------|-------------|
| `/mpt status` | Show run count and active run info |
| `/mpt last` | Show details of the last saved run |
| `/mpt clear` | Clear all saved run data |

## Running Tests

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
```

143 tests covering analytics, import parsing, all routes, input validation, and XSS prevention. Tests use an in-memory SQLite database and run in ~2 seconds.

## Project Structure

```
mythic-plus/
├── app/
│   ├── main.py              # FastAPI app, dashboard route
│   ├── config.py             # Environment vars, dungeon/class data
│   ├── database.py           # SQLite setup, migrations, seeding
│   ├── models.py             # SQLModel tables (Run, Character, RunMember, etc.)
│   ├── routers/
│   │   ├── runs.py           # Run CRUD, list, detail, search
│   │   ├── characters.py     # Character profiles, Raider.IO lookup
│   │   ├── stats.py          # Analytics page
│   │   ├── addon_import.py   # WoW addon import
│   │   ├── warcraftlogs.py   # WCL import
│   │   └── spotify.py        # Spotify OAuth + song tracking
│   ├── services/
│   │   ├── analytics.py      # 20 analytics functions
│   │   ├── addon_import.py   # Lua parser + import logic
│   │   ├── raiderio.py       # Raider.IO API client
│   │   └── warcraftlogs.py   # WCL GraphQL client
│   ├── templates/            # Jinja2 templates (HTMX + Pico CSS)
│   └── static/               # CSS + minimal JS
├── wow_addon/
│   └── MythicPlusTracker/    # WoW addon (copy to AddOns folder)
├── tests/                    # pytest test suite (143 tests)
├── seed_demo.py              # Generate demo data for testing
├── requirements.txt
└── .env.example
```

## Tech Stack

- **Backend:** Python, FastAPI, SQLModel (SQLAlchemy ORM), SQLite
- **Frontend:** Jinja2 templates, HTMX, Pico CSS
- **APIs:** Raider.IO (free, no auth), Spotify (OAuth2), Warcraft Logs (OAuth2)
- **Testing:** pytest with in-memory SQLite

## Season 1 Dungeons

| Dungeon | Short | Timer |
|---------|-------|-------|
| Windrunner Spire | WRS | 30:00 |
| Maisara Caverns | MC | 30:00 |
| Nexus Point Xenas | NPX | 30:00 |
| Magister's Terrace | MT | 33:30 |
| Algeth'ar Academy | AA | 30:00 |
| Pit of Saron | POS | 33:00 |
| Seat of the Triumvirate | SOTT | 30:00 |
| Skyreach | SKY | 30:00 |
