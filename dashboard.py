"""FastAPI dashboard server for Andre.

Serves the static UI at "/" and a WebSocket at "/ws" that broadcasts every
event pushed into the shared asyncio.Queue (event_bus). Also exposes a
small HTTP API:

  GET  /api/runs                    — list past runs (scan outputs/)
  GET  /api/runs/<run_id>           — list files in a run
  GET  /api/runs/<run_id>/files/<f> — fetch raw Markdown for a file
  POST /api/stop                    — cancel the currently-running pipeline

The server runs in the same process as the orchestrator — `python
orchestrator.py` is the single entry point.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from contextlib import suppress
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles


DASHBOARD_DIR = Path(__file__).parent / "dashboard"
OUTPUTS_DIR = Path(__file__).parent / "outputs"

_RUN_ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}$")


def _scan_runs() -> list[dict]:
    """Scan outputs/ for completed and in-progress runs. Newest first."""
    if not OUTPUTS_DIR.exists():
        return []
    runs: list[dict] = []
    for d in OUTPUTS_DIR.iterdir():
        if not d.is_dir() or not _RUN_ID_RE.match(d.name):
            continue
        md_files = sorted(p.name for p in d.glob("*.md"))
        agent_files = [f for f in md_files if f != "MASTER_REPORT.md"]
        completed = len(agent_files)
        has_master = "MASTER_REPORT.md" in md_files
        winner = _extract_winner(d)
        try:
            mtime = max((d / f).stat().st_mtime for f in md_files) if md_files else d.stat().st_mtime
            ctime = min((d / f).stat().st_ctime for f in md_files) if md_files else d.stat().st_ctime
        except Exception:
            mtime = d.stat().st_mtime
            ctime = mtime
        runs.append(
            {
                "run_id":           d.name,
                "winner":           winner,
                "files":            md_files,
                "agents_completed": completed,
                "agents_total":     8,
                "has_master":       has_master,
                "status":           "done" if has_master else "incomplete",
                "started_ts":       ctime,
                "updated_ts":       mtime,
                "duration_seconds": max(0, int(mtime - ctime)),
            }
        )
    runs.sort(key=lambda r: r["updated_ts"], reverse=True)
    return runs


def _extract_winner(run_dir: Path) -> str:
    """Pull the winner app name out of 01_pmf_research.md if possible."""
    pmf = run_dir / "01_pmf_research.md"
    if not pmf.exists():
        return ""
    try:
        text = pmf.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""
    m = re.search(r"^##\s*Winner\s*:\s*(.+?)\s*$", text, re.MULTILINE)
    if m:
        return m.group(1).strip().strip("[]")
    return ""


async def start_dashboard(event_bus: asyncio.Queue, config: dict):
    """Start uvicorn + the event-broadcast loop, return when both stop."""
    app = FastAPI(title="Andre Dashboard")
    connected_clients: list[WebSocket] = []
    event_history: list[dict] = []
    history_lock = asyncio.Lock()
    MAX_HISTORY = 2000

    runtime = config.get("_runtime") or {}

    @app.get("/")
    async def root():
        return FileResponse(DASHBOARD_DIR / "index.html")

    @app.get("/healthz")
    async def healthz():
        return JSONResponse({"ok": True})

    # ── HTTP API: run history ────────────────────────────────────────────
    @app.get("/api/runs")
    async def api_runs():
        current_id = (runtime or {}).get("current_run_id") or config.get("run_id", "")
        task = (runtime or {}).get("pipeline_task")
        active = bool(task and not task.done())
        return JSONResponse(
            {
                "current_run_id": current_id,
                "pipeline_active": active,
                "runs": _scan_runs(),
            }
        )

    @app.get("/api/runs/{run_id}")
    async def api_run(run_id: str):
        if not _RUN_ID_RE.match(run_id):
            raise HTTPException(404, "invalid run id")
        run_dir = OUTPUTS_DIR / run_id
        if not run_dir.is_dir():
            raise HTTPException(404, "run not found")
        md_files = sorted(p.name for p in run_dir.glob("*.md"))
        return JSONResponse(
            {
                "run_id": run_id,
                "files":  md_files,
                "winner": _extract_winner(run_dir),
            }
        )

    @app.get("/api/runs/{run_id}/files/{filename}")
    async def api_run_file(run_id: str, filename: str):
        if not _RUN_ID_RE.match(run_id):
            raise HTTPException(404, "invalid run id")
        if "/" in filename or ".." in filename or not filename.endswith(".md"):
            raise HTTPException(400, "invalid filename")
        path = OUTPUTS_DIR / run_id / filename
        if not path.is_file():
            raise HTTPException(404, "file not found")
        try:
            content = path.read_text(encoding="utf-8")
        except Exception as exc:
            raise HTTPException(500, f"read error: {exc}")
        return PlainTextResponse(content)

    # ── HTTP API: stop the running pipeline ──────────────────────────────
    @app.post("/api/stop")
    async def api_stop():
        task = runtime.get("pipeline_task") if runtime else None
        if task is None or task.done():
            return JSONResponse({"ok": False, "reason": "no active pipeline"})
        task.cancel()
        if "stop_event" in runtime:
            runtime["stop_event"].set()
        await event_bus.put(
            {"type": "info", "agent": "system",
             "content": "Stop requested — pipeline cancellation in flight.",
             "ts": time.time()}
        )
        return JSONResponse({"ok": True})

    # ── HTTP API: continue an incomplete run ─────────────────────────────
    @app.post("/api/continue/{run_id}")
    async def api_continue(run_id: str):
        if not _RUN_ID_RE.match(run_id):
            raise HTTPException(400, "invalid run id")
        output_dir = OUTPUTS_DIR / run_id
        if not output_dir.is_dir():
            raise HTTPException(404, "run not found")
        start = (runtime or {}).get("start_run")
        if not callable(start):
            return JSONResponse({"ok": False, "reason": "runtime not ready"})
        # Cancel any in-flight pipeline.
        existing = (runtime or {}).get("pipeline_task")
        if existing and not existing.done():
            existing.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await existing
        await event_bus.put(
            {"type": "info", "agent": "system",
             "content": f"Continuing run {run_id} — completed agents will be skipped.",
             "ts": time.time()}
        )
        start(run_id=run_id, output_dir=output_dir, preload=True)
        return JSONResponse({"ok": True, "mode": "continue", "run_id": run_id})

    # ── HTTP API: restart a run from scratch ─────────────────────────────
    @app.post("/api/restart/{run_id}")
    async def api_restart(run_id: str):
        if not _RUN_ID_RE.match(run_id):
            raise HTTPException(400, "invalid run id")
        output_dir = OUTPUTS_DIR / run_id
        if not output_dir.is_dir():
            raise HTTPException(404, "run not found")
        start = (runtime or {}).get("start_run")
        if not callable(start):
            return JSONResponse({"ok": False, "reason": "runtime not ready"})
        existing = (runtime or {}).get("pipeline_task")
        if existing and not existing.done():
            existing.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await existing
        # Clear the existing Markdown so the pipeline starts fresh under
        # the same run id.
        removed = 0
        for p in output_dir.glob("*.md"):
            try:
                p.unlink()
                removed += 1
            except Exception:
                pass
        await event_bus.put(
            {"type": "info", "agent": "system",
             "content": f"Restarting run {run_id} — cleared {removed} previous file(s).",
             "ts": time.time()}
        )
        start(run_id=run_id, output_dir=output_dir, preload=False)
        return JSONResponse({"ok": True, "mode": "restart", "run_id": run_id})

    # ── HTTP API: launch a brand-new run ─────────────────────────────────
    @app.post("/api/new")
    async def api_new():
        start = (runtime or {}).get("start_run")
        if not callable(start):
            return JSONResponse({"ok": False, "reason": "runtime not ready"})
        existing = (runtime or {}).get("pipeline_task")
        if existing and not existing.done():
            existing.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await existing
        import datetime as _dt
        new_run_id = _dt.datetime.now().strftime("%Y-%m-%d_%H-%M")
        output_dir = OUTPUTS_DIR / new_run_id
        await event_bus.put(
            {"type": "info", "agent": "system",
             "content": f"Starting new run {new_run_id}.",
             "ts": time.time()}
        )
        start(run_id=new_run_id, output_dir=output_dir, preload=False)
        return JSONResponse({"ok": True, "mode": "new", "run_id": new_run_id})

    # ── WebSocket ────────────────────────────────────────────────────────
    @app.websocket("/ws")
    async def ws_endpoint(websocket: WebSocket):
        await websocket.accept()
        connected_clients.append(websocket)
        # Replay backlog of events for late-joining clients.
        async with history_lock:
            backlog = list(event_history)
        for ev in backlog:
            with suppress(Exception):
                await websocket.send_text(json.dumps(ev))
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        except Exception:
            pass
        finally:
            if websocket in connected_clients:
                connected_clients.remove(websocket)

    app.mount(
        "/static",
        StaticFiles(directory=str(DASHBOARD_DIR)),
        name="static",
    )

    async def broadcast_events():
        while True:
            ev = await event_bus.get()
            async with history_lock:
                event_history.append(ev)
                if len(event_history) > MAX_HISTORY:
                    del event_history[: len(event_history) - MAX_HISTORY]
            payload = json.dumps(ev)
            dead: list[WebSocket] = []
            for client in list(connected_clients):
                try:
                    await client.send_text(payload)
                except Exception:
                    dead.append(client)
            for d in dead:
                if d in connected_clients:
                    connected_clients.remove(d)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    server_cfg = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=int(config.get("dashboard_port", 7860)),
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(server_cfg)

    broadcaster = asyncio.create_task(broadcast_events())
    try:
        await server.serve()
    finally:
        broadcaster.cancel()
        with suppress(asyncio.CancelledError):
            await broadcaster
