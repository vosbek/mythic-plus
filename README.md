# Mythic+ Tracker

A personal companion app for tracking WoW Mythic+ dungeon runs during Midnight Season 1.

## Features

- **Run Logging** - Track dungeon, key level, result, time, deaths, and group composition
- **Character Profiles** - Look up any character via Raider.IO (scores, best runs)
- **Spotify Integration** - Capture what songs were playing during your runs
- **Fun Analytics** - Nemesis dungeon, lucky song, vibe correlation, streaks, group chemistry
- **Weekly Vault** - See your Great Vault options based on this week's runs

## Quick Start

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://localhost:8000

## Spotify Setup (Optional)

1. Create an app at https://developer.spotify.com/dashboard
2. Set redirect URI to `http://localhost:8000/spotify/callback`
3. Copy `.env.example` to `.env` and fill in your credentials
4. Restart the app and connect via the Spotify page

## Tech Stack

- Python + FastAPI
- SQLite (via SQLModel)
- Jinja2 + HTMX + Pico CSS
- Raider.IO API (free, no auth)
- Spotify Web API (OAuth2)

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
