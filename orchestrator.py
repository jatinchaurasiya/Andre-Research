#!/usr/bin/env python3
"""Andre — PMF Agent Orchestra.

Single entry point. Boots the dashboard, then runs 8 specialised agents in
phases (1 → 2a‖2b → 3 → 4 → 5 → 6 → 7) and compiles a master report.

The pipeline is implemented as a relaunchable task — the dashboard can call
``runtime["start_run"]`` (via ``/api/restart`` or ``/api/continue``) to
abort the current run and launch a new one (fresh or resumed).

Usage:
    python orchestrator.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from contextlib import suppress
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel


load_dotenv()


def _fatal(msg: str) -> "NoReturn":  # type: ignore[name-defined]
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def _load_config() -> dict:
    cfg_path = Path(__file__).parent / "config.yaml"
    if not cfg_path.exists():
        _fatal("config.yaml not found next to orchestrator.py")
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _build_agents(config: dict, event_bus: asyncio.Queue) -> dict:
    """Construct fresh agent instances. Called once per pipeline launch so
    per-run counters (tokens, searches, pages, errors) reset."""
    from agents.pmf_agent import PMFAgent
    from agents.requirements_agent import RequirementsAgent
    from agents.competitor_agent import CompetitorAgent
    from agents.improvement_agent import ImprovementAgent
    from agents.feature_architecture_agent import FeatureArchitectureAgent
    from agents.prd_agent import PRDAgent
    from agents.uiux_design_prompt_agent import UIUXDesignPromptAgent
    from agents.marketing_agent import MarketingAgent
    return {
        "pmf":                  PMFAgent("pmf", config, event_bus),
        "requirements":         RequirementsAgent("requirements", config, event_bus),
        "competitor":           CompetitorAgent("competitor", config, event_bus),
        "improvement":          ImprovementAgent("improvement", config, event_bus),
        "feature_architecture": FeatureArchitectureAgent("feature_architecture", config, event_bus),
        "prd":                  PRDAgent("prd", config, event_bus),
        "uiux":                 UIUXDesignPromptAgent("uiux", config, event_bus),
        "marketing":            MarketingAgent("marketing", config, event_bus),
    }


def _preload_context(output_dir: Path, agents: dict, run_id: str) -> dict:
    """Build a context dict populated with whatever Markdown outputs already
    exist in ``output_dir``. Used for /api/continue."""
    context: dict = {"run_id": run_id, "output_dir": str(output_dir)}
    for agent_id, agent in agents.items():
        f = output_dir / agent.output_filename
        if not f.exists():
            continue
        try:
            md = f.read_text(encoding="utf-8")
        except Exception:
            continue
        slot = {"raw_md": md}
        try:
            slot.update(agent._parse_output(md, context))
        except Exception:
            pass
        context[agent_id] = slot
    return context


async def _maybe_run(agent, context: dict, event_bus: asyncio.Queue) -> None:
    """Run an agent — but if its output is already in context (because we're
    continuing a previous run), emit synthetic events so the dashboard sees
    the agent as completed without redoing the work."""
    aid = agent.id
    existing = context.get(aid)
    if existing and existing.get("raw_md"):
        md = existing["raw_md"]
        await event_bus.put({"type": "agent_start", "agent": aid, "ts": time.time()})
        await event_bus.put(
            {"type": "info", "agent": aid,
             "content": "Loaded from previous run — skipping re-generation.",
             "ts": time.time()}
        )
        await event_bus.put(
            {"type": "output_ready", "agent": aid, "markdown": md, "ts": time.time()}
        )
        await event_bus.put(
            {"type": "agent_done", "agent": aid,
             "tokens_in": 0, "tokens_out": 0, "reasoning_tokens": 0,
             "searches": 0, "pages": 0, "errors": 0,
             "ts": time.time()}
        )
        return
    await agent.run(context)


async def _run_pipeline(
    config: dict,
    event_bus: asyncio.Queue,
    console: Console,
    run_id: str,
    output_dir: Path,
    preload: bool,
) -> Path | None:
    """One full execution of the 7-phase Andre pipeline.

    If ``preload`` is true, agents whose Markdown file already exists in
    ``output_dir`` are skipped (their output is re-broadcast to the
    dashboard but no NIM calls are made).
    """
    from utils.reporter import Reporter

    output_dir.mkdir(parents=True, exist_ok=True)
    agents = _build_agents(config, event_bus)

    if preload:
        context = _preload_context(output_dir, agents, run_id)
    else:
        context = {"run_id": run_id, "output_dir": str(output_dir)}

    await event_bus.put({"type": "run_started", "run_id": run_id, "ts": time.time()})

    async def _emit_phase(n: int, label: str) -> None:
        await event_bus.put(
            {"type": "phase_change", "phase": n, "label": label, "ts": time.time()}
        )

    started = time.time()
    try:
        await _emit_phase(1, "PMF Research")
        console.print(f"[bold]Phase 1[/bold] — PMF Research Agent  (run {run_id})")
        await _maybe_run(agents["pmf"], context, event_bus)

        await _emit_phase(2, "Requirements + Competitor")
        console.print("[bold]Phase 2[/bold] — Requirements + Competitor (parallel)")
        await asyncio.gather(
            _maybe_run(agents["requirements"], context, event_bus),
            _maybe_run(agents["competitor"], context, event_bus),
        )

        await _emit_phase(3, "Improvement")
        console.print("[bold]Phase 3[/bold] — Improvement Agent")
        await _maybe_run(agents["improvement"], context, event_bus)

        await _emit_phase(4, "Feature Architecture")
        console.print("[bold]Phase 4[/bold] — Feature Architecture Agent")
        await _maybe_run(agents["feature_architecture"], context, event_bus)

        await _emit_phase(5, "PRD")
        console.print("[bold]Phase 5[/bold] — PRD Agent")
        await _maybe_run(agents["prd"], context, event_bus)

        await _emit_phase(6, "UI/UX")
        console.print("[bold]Phase 6[/bold] — UI/UX Design Prompt Agent")
        await _maybe_run(agents["uiux"], context, event_bus)

        await _emit_phase(7, "Marketing")
        console.print("[bold]Phase 7[/bold] — Marketing Agent")
        await _maybe_run(agents["marketing"], context, event_bus)

        await _emit_phase(8, "Compile")
        master_path = Reporter(output_dir).compile(context)
        master_md = master_path.read_text(encoding="utf-8")
        elapsed = int(time.time() - started)
        console.print(
            f"[bold green]✓ Complete[/bold green] in {elapsed}s — "
            f"reports in [cyan]{output_dir}[/cyan]"
        )
        await event_bus.put(
            {"type": "complete", "run_id": run_id,
             "output_dir": str(output_dir), "master_markdown": master_md,
             "ts": time.time()}
        )
        return master_path

    except asyncio.CancelledError:
        # Compile whatever finished into a partial master report.
        try:
            partial = Reporter(output_dir).compile(context)
            md = partial.read_text(encoding="utf-8")
            await event_bus.put(
                {"type": "stopped", "run_id": run_id,
                 "output_dir": str(output_dir), "master_markdown": md,
                 "ts": time.time()}
            )
            console.print(
                f"[yellow]Pipeline cancelled.[/yellow] Partial report: [cyan]{partial}[/cyan]"
            )
        except Exception as exc:
            console.print(f"[dim]Could not compile partial report: {exc}[/dim]")
        raise

    except Exception as exc:
        await event_bus.put(
            {"type": "error", "agent": "system",
             "content": f"Pipeline failed: {exc}", "ts": time.time()}
        )
        console.print(f"[red]Pipeline failed:[/red] {exc}")
        raise


async def main_async() -> None:
    if not os.getenv("NVIDIA_API_KEY"):
        _fatal(
            "NVIDIA_API_KEY not set. Copy .env.example to .env and add your key."
        )

    console = Console()
    console.print(
        Panel.fit(
            "[bold cyan]ANDRE[/bold cyan] — PMF Agent Orchestra\n"
            "[dim]moonshotai/kimi-k2.6 @ NVIDIA NIM[/dim]\n"
            "[dim]8 Agents · DuckDuckGo Search · Kotlin Multiplatform target[/dim]",
            border_style="cyan",
        )
    )

    config = _load_config()
    initial_run_id = datetime.now().strftime("%Y-%m-%d_%H-%M")
    initial_output_dir = Path("outputs") / initial_run_id
    config["output_dir"] = str(initial_output_dir)
    config["run_id"] = initial_run_id

    event_bus: asyncio.Queue = asyncio.Queue()
    runtime: dict = {
        "stop_event":    asyncio.Event(),
        "pipeline_task": None,
        "start_run":     None,   # set below
        "current_run_id":  initial_run_id,
        "current_output_dir": initial_output_dir,
    }
    config["_runtime"] = runtime

    from dashboard import start_dashboard

    dashboard_task = asyncio.create_task(start_dashboard(event_bus, config))
    port = config.get("dashboard_port", 7860)
    console.print(
        f"\n[green]Dashboard:[/green] [cyan]http://localhost:{port}[/cyan]"
    )
    console.print(
        "[dim]Open it in your browser — every token streams in real time.[/dim]\n"
    )

    # Give uvicorn a moment to start listening.
    await asyncio.sleep(2.0)

    def start_run(run_id: str, output_dir: Path, preload: bool = False):
        """Launch (or relaunch) a pipeline. Cancels any running pipeline
        first. Returns the new task. Called by the orchestrator itself for
        the initial run, and by the dashboard for restart/continue."""
        existing = runtime.get("pipeline_task")
        if existing and not existing.done():
            existing.cancel()
            # NOTE: we don't await the cancellation here because we're
            # called from a sync function; the new task will be created
            # while the old one tears itself down on the next loop tick.
        config["run_id"] = run_id
        config["output_dir"] = str(output_dir)
        runtime["current_run_id"] = run_id
        runtime["current_output_dir"] = output_dir
        task = asyncio.create_task(
            _run_pipeline(config, event_bus, console, run_id, output_dir, preload)
        )
        runtime["pipeline_task"] = task
        return task

    runtime["start_run"] = start_run

    # Kick off the initial run.
    start_run(initial_run_id, initial_output_dir, preload=False)

    try:
        # Stay alive until the dashboard server exits (Ctrl+C). Pipelines
        # may come and go via start_run; they're tracked independently.
        await dashboard_task
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")
    except Exception as exc:
        console.print(f"\n[red]Dashboard crashed:[/red] {exc}")
    finally:
        # Cancel any in-flight pipeline so we exit cleanly.
        existing = runtime.get("pipeline_task")
        if existing and not existing.done():
            existing.cancel()
            with suppress(Exception):
                await existing
        if not dashboard_task.done():
            dashboard_task.cancel()
            with suppress(Exception):
                await dashboard_task


def main() -> None:
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\nAndre stopped.")


if __name__ == "__main__":
    main()
