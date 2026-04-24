"""
app.py — FastAPI entry point for Hex Battle Simulator.

Serves both the API/WebSocket backend AND the static frontend.
Single process — no separate static file server needed.

Run locally:
    uvicorn app:app --reload --port 8000
    Open http://localhost:8000

For deployment (Render, Railway, etc.):
    uvicorn app:app --host 0.0.0.0 --port $PORT
"""

import os
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from hex_battle import (
    HOST, PORT, ALLOWED_ORIGINS, DATABASE_URL,
    FRONTEND_CONFIG, MOVE_REGISTRY,
    DatabaseLayer, SessionManager, ConnectionManager,
    TurnEngine, handle_websocket,
)

# ─────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────

FRONTEND_DIR = Path(__file__).parent / "Frontend"

# ─────────────────────────────────────────────
# GLOBALS (initialized in lifespan)
# ─────────────────────────────────────────────

db: DatabaseLayer       = None
sm: SessionManager      = None
cm: ConnectionManager   = None
te: TurnEngine          = None

# ─────────────────────────────────────────────
# LIFESPAN (startup / shutdown)
# ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db, sm, cm, te

    db = await DatabaseLayer.create(DATABASE_URL)
    sm = SessionManager(db)
    cm = ConnectionManager()
    te = TurnEngine()

    # Background cleanup task
    async def cleanup_loop():
        while True:
            await asyncio.sleep(300)  # every 5 minutes
            try:
                removed = await sm.cleanup_timed_out()
                if removed:
                    print(f"[Cleanup] Removed {len(removed)} "
                          f"timed-out sessions: {removed}")
            except Exception as e:
                print(f"[Cleanup] Error: {e}")

    cleanup_task = asyncio.create_task(cleanup_loop())

    port = os.environ.get("PORT", "8000")
    print(f"\n{'='*50}")
    print(f"  Hex Battle Simulator — Trial 3")
    print(f"  Server:   http://0.0.0.0:{port}")
    print(f"  Frontend: {FRONTEND_DIR}")
    print(f"  Serving frontend static files from /")
    print(f"{'='*50}\n")

    yield

    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass


# ─────────────────────────────────────────────
# APP
# ─────────────────────────────────────────────

app = FastAPI(
    title="Hex Battle Simulator",
    version="3.0",
    lifespan=lifespan,
)

# CORS — allow all origins for deployment flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
# REST ENDPOINTS
# ─────────────────────────────────────────────

@app.get("/api/config")
async def get_config():
    """Frontend config (colors, fonts, anim durations, moves)."""
    move_defs = {
        name.value: defn.to_dict()
        for name, defn in MOVE_REGISTRY.items()
    }
    return JSONResponse({
        **FRONTEND_CONFIG,
        "moves": move_defs,
    })


@app.post("/api/session/create")
async def create_session():
    """Create a new game session. Returns session_id."""
    try:
        session_id = await sm.create_session()
        return JSONResponse({
            "session_id": session_id,
            "message": "Session created. Share this ID with "
                       "your opponent.",
        })
    except RuntimeError as e:
        return JSONResponse(
            {"error": str(e)}, status_code=503)


@app.post("/api/session/join")
async def join_session(session_id: str = Query(...),
                       player_id: int = Query(None)):
    """
    Join an existing session.
    player_id is auto-assigned if not specified.
    """
    try:
        assigned = await sm.join_session(
            session_id, player_id)
        return JSONResponse({
            "session_id": session_id,
            "player_id": assigned,
            "message": f"Joined as Player {assigned}.",
        })
    except KeyError:
        return JSONResponse(
            {"error": f"Session \'{session_id}\' not found."},
            status_code=404)
    except ValueError as e:
        return JSONResponse(
            {"error": str(e)}, status_code=409)


@app.get("/api/session/{session_id}")
async def get_session_status(session_id: str):
    """Session status (connected players, phase, etc.)."""
    try:
        status = await sm.get_status(session_id)
        return JSONResponse(status)
    except KeyError:
        return JSONResponse(
            {"error": f"Session \'{session_id}\' not found."},
            status_code=404)


@app.get("/api/sessions")
async def list_sessions():
    """Debug: list all active sessions."""
    summary = await sm.get_manager_summary()
    return JSONResponse(summary)


@app.get("/api/health")
async def health():
    count = await sm.active_session_count()
    return JSONResponse({
        "status": "ok",
        "active_sessions": count,
    })


# ─────────────────────────────────────────────
# WEBSOCKET ROUTE
# ─────────────────────────────────────────────

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    player_id: int = Query(...),
):
    """
    WebSocket endpoint for game communication.
    URL: ws://host/ws/{session_id}?player_id=N
    """
    # Verify session exists
    if not await sm.session_exists(session_id):
        await websocket.close(code=4004,
                              reason="Session not found")
        return

    await handle_websocket(
        ws=websocket,
        session_id=session_id,
        player_id=player_id,
        db=db, sm=sm, cm=cm, te=te,
    )


# ─────────────────────────────────────────────
# STATIC FILES — serve Frontend/ at root
# Must be AFTER API routes so /api/* takes priority
# ─────────────────────────────────────────────

@app.get("/")
async def root():
    """Redirect root to lobby page."""
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return RedirectResponse("/index.html")


# Mount static files last — catches all non-API routes
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
