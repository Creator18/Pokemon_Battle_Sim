# Hex Battle Simulator

Local 2-player tactical hex-grid Pokemon battle game.

**Tech:** Python (FastAPI + WebSockets + SQLAlchemy) backend,
single-file HTML frontend (PixiJS + vanilla JS).

## Play Online

Visit the deployed URL and open in **two browser tabs**:
- Tab 1: Click "Create Session" → copy the code
- Tab 2: Click "Join" → paste code → "Join Session"
- Both tabs enter the battle screen automatically

## Run Locally

```bash
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```

Open http://localhost:8000 in two browser tabs.

## Deploy to Render

1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → New → Web Service
3. Connect your GitHub repo
4. Render auto-detects `render.yaml` and deploys
5. Share the public URL with your opponent

## Game Mechanics

- **61-tile hex grid** (radius 4) with rocks and trees
- **4 moves:** Thunderbolt (AOE), Quick Attack (priority), 
  Electro Web (speed debuff), Volt Tackle (momentum melee)
- **Stat stages:** Mainline-style -6 to +6 system
- **Movement costs:** Rocks cost 2 steps, Electro Web reduces speed on field entry
- **Turn-based:** Both players declare simultaneously, 
  priority queue resolves actions

## Project Structure

```
app.py              ← FastAPI server (API + WebSocket + static files)
hex_battle.py       ← Game engine (constants, terrain, pokemon, moves, DB, turns, sessions, WS)
requirements.txt    ← Python dependencies
Procfile            ← Deployment start command
render.yaml         ← Render auto-deploy config
atk_moves.json      ← Physical move definitions
spatk_moves.json    ← Special move definitions
Frontend/
  index.html        ← Lobby page
  game.html         ← Battle page (all JS/CSS inline)
  assets/sprites/   ← Pokemon sprites
```
