# Andre — PMF Agent Orchestra

> An 8-agent AI pipeline that discovers a zero-investment Kotlin Multiplatform
> mobile app idea, fully specs it, analyses competitors, designs a better
> version, drafts a PRD, generates UI/UX prompts, and produces a zero-budget
> marketing playbook — all from a single `python orchestrator.py` command.

Powered by `moonshotai/kimi-k2.6` on the free NVIDIA NIM endpoint. Every
thinking-token, output-token, and web-search call streams in real time to a
local dashboard at <http://localhost:7860>.

---

## Table of Contents

1. [What is Andre?](#what-is-andre)
2. [How it works](#how-it-works)
3. [Prerequisites](#prerequisites)
4. [Quick start](#quick-start)
5. [Platform-specific setup](#platform-specific-setup)
   - [Windows](#windows)
   - [macOS](#macos)
   - [Linux](#linux)
6. [Running Andre](#running-andre)
7. [Outputs](#outputs)
8. [Configuration](#configuration)
9. [Project structure](#project-structure)
10. [Architecture — how the pieces fit together](#architecture--how-the-pieces-fit-together)
11. [Troubleshooting](#troubleshooting)
12. [FAQ](#faq)
13. [Contributing](#contributing)
14. [License](#license)

---

## What is Andre?

Andre is an autonomous research-and-design pipeline. Give it nothing — and it
will:

1. Find three unmet-need mobile app ideas by mining Reddit, the App Store,
   and Product Hunt.
2. Pick the strongest one and produce a full Kotlin Multiplatform build
   spec (architecture, data model, screens, free infrastructure, 90-day
   delivery timeline).
3. Analyse direct competitors, their top complaints, and the
   whitespace they leave open.
4. Design a 30%-better experience — tap-count comparisons, a killer
   differentiator, frictionless flows.
5. Lay out a feature-architecture map.
6. Draft a complete PRD.
7. Generate UI/UX design prompts ready to feed into Figma / Stitch / v0.
8. Hand you a zero-budget 90-day marketing playbook (ASO, ProductHunt,
   Hacker News, Reddit, viral loops, organic growth calendar).

Everything is written to disk as Markdown plus one stitched `MASTER_REPORT.md`.

---

## How it works

| Phase | Agent                     | What it produces |
|-------|---------------------------|------------------|
| 1     | PMF Research              | 3 unmet-need app ideas mined from Reddit / App Store / PH, scored, with a winner crowned. |
| 2a    | Requirements              | Full KMP build spec (architecture, screens, data model, free infra, 90-day timeline). |
| 2b    | Competitor Analysis       | Direct competitors, top complaints, whitespace map, UX anti-patterns. *Runs in parallel with 2a.* |
| 3     | Improvement Blueprint     | 30% UX edge — tap-count comparisons, killer differentiator, frictionless design. |
| 4     | Feature Architecture      | Feature map, module boundaries, dependency graph. |
| 5     | PRD                       | Full product-requirements doc, ready to hand a dev team. |
| 6     | UI/UX Design Prompts      | Screen-by-screen prompts for design tools (Figma, Stitch, v0). |
| 7     | Marketing Playbook        | ASO, ProductHunt / HN / Reddit launch plan, viral loop, 90-day organic growth calendar. |
| 8     | Compile                   | Stitches every output into `MASTER_REPORT.md`. |

Phase 2 fires both agents in parallel; every other phase runs sequentially
so the next agent can read the previous one's Markdown as context.

---

## Prerequisites

You need three things:

1. **Python 3.11 or newer** — check with `python --version`.
2. **Git** — to clone the repo.
3. **A free NVIDIA NIM API key** — sign up at
   <https://build.nvidia.com>, search for `kimi-k2.6`, and copy the key
   from the "Get API Key" panel. The hosted endpoint is
   `https://integrate.api.nvidia.com/v1`.

No GPU, no Docker, no paid services are required.

---

## Quick start

```bash
# 1. Clone
git clone https://github.com/jatinchaurasiya/Andre-Research.git
cd Andre-Research

# 2. Create + activate a virtual environment
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Add your API key
cp .env.example .env                 # Windows: copy .env.example .env
# open .env and paste your key into NVIDIA_API_KEY

# 5. Run
python orchestrator.py
```

Then open <http://localhost:7860> in your browser.

---

## Platform-specific setup

### Windows

```powershell
# Open PowerShell
git clone https://github.com/jatinchaurasiya/Andre-Research.git
cd Andre-Research

# Create the venv
python -m venv .venv
.venv\Scripts\activate

# Install deps
pip install -r requirements.txt

# Add your API key
copy .env.example .env
notepad .env                         # paste key after NVIDIA_API_KEY=

# Run
python orchestrator.py
```

If `python` is not recognised, install Python 3.11+ from
<https://www.python.org/downloads/windows/> and tick **"Add Python to PATH"**
during install.

### macOS

```bash
# Install Python 3.11+ if you don't have it (Homebrew)
brew install python@3.11

git clone https://github.com/jatinchaurasiya/Andre-Research.git
cd Andre-Research

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
open -e .env                         # paste key after NVIDIA_API_KEY=

python orchestrator.py
```

### Linux

```bash
# Debian / Ubuntu
sudo apt update
sudo apt install -y python3.11 python3.11-venv git

git clone https://github.com/jatinchaurasiya/Andre-Research.git
cd Andre-Research

python3.11 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
nano .env                            # paste key after NVIDIA_API_KEY=

python orchestrator.py
```

On Fedora / RHEL replace the install step with
`sudo dnf install python3.11 git`. On Arch use `sudo pacman -S python git`.

---

## Running Andre

A single command does everything:

```bash
python orchestrator.py
```

It will:

1. Boot the FastAPI dashboard on port **7860**.
2. Print a banner with the dashboard URL.
3. Run the 8 phases (phase 2 fires its two agents in parallel).
4. Stream every thinking token, output token, and web-search call to the
   browser.
5. Write each agent's Markdown report and a compiled `MASTER_REPORT.md`
   into `outputs/<timestamp>/`.

Open <http://localhost:7860> as soon as you see the banner. You can also:

- **Restart** a run from the dashboard (cancels in-flight work).
- **Continue** an interrupted run — Andre detects existing Markdown files in
  the output directory and skips agents that already finished.

Stop with `Ctrl+C` at any time; a partial `MASTER_REPORT.md` is still
written.

---

## Outputs

Every run creates a timestamped folder:

```
outputs/2026-05-25_01-25/
├── 01_pmf_research.md
├── 02_requirements.md
├── 03_competitor_analysis.md
├── 04_improvement_blueprint.md
├── 05_feature_architecture.md
├── 06_prd.md
├── 07_uiux_design_prompts.md
├── 08_marketing_playbook.md
└── MASTER_REPORT.md
```

`MASTER_REPORT.md` is the stitched view — header, table of contents, every
section in order. Hand it to a dev / designer and they can start building.

---

## Configuration

`config.yaml` controls model parameters and per-agent search budgets:

```yaml
model: "moonshotai/kimi-k2.6" any model Available on the Nvidia NIM
base_url: "https://integrate.api.nvidia.com/v1"
max_tokens: 16384
temperature: 1.0
top_p: 1.0
thinking: true
dashboard_port: 7860

# Date reference constants — used by prompts for recency scoring.
data_recency_year: 2026
data_fresh_threshold: "2025-01-01"
data_stale_threshold: "2024-01-01"

agents:
  pmf:                  { max_search_queries: 12, ... }
  requirements:         { max_search_queries: 6,  ... }
  competitor:           { max_search_queries: 15, ... }
  improvement:          { max_search_queries: 4,  ... }
  feature_architecture: { max_search_queries: 5,  ... }
  prd:                  { max_search_queries: 0,  ... }
  uiux:                 { max_search_queries: 6,  ... }
  marketing:            { max_search_queries: 10, ... }
```

`max_search_queries` caps how many DuckDuckGo lookups an agent can make
before the orchestrator nudges it to finalise the report — this prevents
runaway tool-calling loops.

---

## Project structure

```
.
├── orchestrator.py           # entry point — boots dashboard + runs all 8 phases
├── dashboard.py              # FastAPI + WebSocket server
├── config.yaml               # model + per-agent settings
├── .env.example              # template for your NVIDIA_API_KEY
├── requirements.txt
│
├── agents/
│   ├── base_agent.py                  # streaming + tool-use loop
│   ├── pmf_agent.py
│   ├── requirements_agent.py
│   ├── competitor_agent.py
│   ├── improvement_agent.py
│   ├── feature_architecture_agent.py
│   ├── prd_agent.py
│   ├── uiux_design_prompt_agent.py
│   └── marketing_agent.py
│
├── prompts/                  # 8 system prompts (one per agent)
│
├── utils/
│   ├── nim_client.py         # NVIDIA NIM streaming client
│   ├── web_search.py         # DuckDuckGo + page fetcher
│   ├── reporter.py           # builds MASTER_REPORT.md
│   ├── logger.py             # event-bus logger
│   ├── quality.py
│   ├── discipline.py
│   └── monetisation.py
│
├── dashboard/                # static dashboard UI
│   ├── index.html
│   ├── style.css
│   └── app.js
│
└── outputs/                  # generated runs (git-ignored)
```

---

## Architecture — how the pieces fit together

Andre is a small async Python program built around four layers: an
**orchestrator** that drives the pipeline, **agents** that do the work, a
**shared event bus** that fan-outs everything they do, and a **dashboard**
that listens to that bus and renders it in the browser.

### High-level data flow

```
                       ┌───────────────────────────┐
                       │     orchestrator.py       │
                       │  ─ loads config.yaml      │
                       │  ─ creates event_bus      │
                       │  ─ launches dashboard     │
                       │  ─ runs phases 1 → 8      │
                       └─────────────┬─────────────┘
                                     │
              builds + runs          │  pushes events
                                     ▼
                       ┌───────────────────────────┐
        ┌─────────────►│        BaseAgent          │◄──────────────┐
        │              │  ─ loads prompts/*.txt    │               │
        │              │  ─ calls NIMClient        │               │
        │              │  ─ runs tool-use loop     │               │
        │              │  ─ writes outputs/*.md    │               │
        │              └─────────────┬─────────────┘               │
        │                            │                             │
        │ subclass per phase         │ tool_call: web_search       │
        │                            ▼                             │
        │              ┌───────────────────────────┐               │
        │              │  utils/web_search.py      │               │
        │              │  DuckDuckGo + page fetch  │               │
        │              └───────────────────────────┘               │
        │                                                          │
        │              ┌───────────────────────────┐               │
        │              │  utils/nim_client.py      │               │
        │              │  streams from NVIDIA NIM  │               │
        │              └───────────────────────────┘               │
        │                                                          │
        │                                                          │
        │              ┌───────────────────────────┐               │
        └──────────────│       event_bus           │───────────────┘
                       │   (asyncio.Queue)         │
                       └─────────────┬─────────────┘
                                     │ events:
                                     │  agent_start / text / thinking
                                     │  tool_use / search_result
                                     │  output_ready / agent_done
                                     │  phase_change / complete
                                     ▼
                       ┌───────────────────────────┐
                       │       dashboard.py        │
                       │  FastAPI + WebSocket /ws  │
                       │  HTTP /api/runs etc.      │
                       └─────────────┬─────────────┘
                                     │ JSON over WebSocket
                                     ▼
                       ┌───────────────────────────┐
                       │   dashboard/  (browser)   │
                       │   index.html + app.js     │
                       └───────────────────────────┘
```

### Layer 1 — the orchestrator (`orchestrator.py`)

The entry point. When you run `python orchestrator.py` it:

1. Loads `.env` (your `NVIDIA_API_KEY`) and `config.yaml`.
2. Creates a shared `asyncio.Queue` called the **event bus**.
3. Spawns the dashboard server as a background task on port `7860`.
4. Builds fresh instances of all 8 agents (resets per-run counters).
5. Runs the phases — phase 2 fires Requirements + Competitor with
   `asyncio.gather(...)` for true parallel execution; every other phase
   awaits sequentially.
6. After phase 7, calls `utils/reporter.py` to stitch every per-agent
   Markdown file into `MASTER_REPORT.md`.

It also exposes a `start_run(...)` callable to the dashboard, so the
browser's **Restart** and **Continue** buttons can cancel the current
pipeline task and launch a new one without restarting the process.

### Layer 2 — the agents (`agents/`)

Every agent is a subclass of `BaseAgent` (`agents/base_agent.py`). The base
class owns all the plumbing — subclasses only override three things:

- `prompt_filename` — which file in `prompts/` to load as the system prompt.
- `output_filename` — where to write the final Markdown (e.g. `01_pmf_research.md`).
- `_user_prompt(context)` — assembles the user turn, usually by reading the
  previous agent's Markdown out of the shared `context` dict.

The base class then runs a **streaming tool-use loop**:

1. Build messages (`system_prompt` + `user_prompt`).
2. Open a streaming completion against NVIDIA NIM.
3. As tokens arrive, classify them:
   - `thinking` → push a `thinking` event to the event bus.
   - `text` → push a `text` event **and** accumulate into the final output.
   - `tool_call` → buffer until the model finishes its turn.
4. If tool calls came back and the search budget isn't exhausted, execute
   each one (currently only `web_search`), append the result to `messages`,
   and loop.
5. When the model produces a final text turn with no tool calls, save the
   accumulated Markdown to `outputs/<run_id>/<output_filename>` and emit
   `output_ready` + `agent_done`.

Search budgets are capped per-agent in `config.yaml` (`max_search_queries`)
so a chatty agent can't loop on tool calls forever. When the budget is
exhausted the orchestrator injects a "produce the final report now"
message and disables tools.

The base class also handles the awkward bits: stripping Kimi K2.6 control
tokens, ignoring fake internal tool calls (`functions.stopThinking`),
detecting empty/garbage output and writing a placeholder so downstream
agents can skip a broken upstream rather than cascading on empty context.

### Layer 3 — the event bus

A single `asyncio.Queue` shared by every component in the process. Agents
push events (`text`, `thinking`, `tool_use`, `search_result`, `output_ready`,
`agent_done`, `error`, …) and the dashboard consumes them. The
orchestrator also pushes lifecycle events (`run_started`, `phase_change`,
`complete`, `stopped`).

This decoupling is what lets the browser show real-time progress without
any direct coupling between agents and HTTP code — and it's what makes
**Continue** work: when an agent's output already exists on disk, the
orchestrator just re-emits synthetic `output_ready` / `agent_done` events
instead of regenerating.

### Layer 4 — the dashboard (`dashboard.py` + `dashboard/`)

A FastAPI app that runs in the same process as the orchestrator. It serves:

- **`/`** — the static UI (`dashboard/index.html`, `style.css`, `app.js`).
- **`/ws`** — the WebSocket that forwards every event-bus message to the
  browser as JSON.
- **`/api/runs`** — list past runs (scans `outputs/`).
- **`/api/runs/<run_id>`** — list files inside a run.
- **`/api/runs/<run_id>/files/<name>`** — fetch raw Markdown.
- **`/api/stop`**, **`/api/restart`**, **`/api/continue`** — pipeline
  controls that call back into the orchestrator's `start_run(...)`.

The browser code in `dashboard/app.js` listens on the WebSocket, routes
each event into the corresponding agent panel, and re-renders. If the
socket drops it auto-reconnects every 2 s.

### Layer 5 — utilities (`utils/`)

- **`nim_client.py`** — thin streaming client for the NVIDIA NIM OpenAI
  endpoint. Yields normalised events (`thinking`, `text`, `tool_call`,
  `usage`, `finish`).
- **`web_search.py`** — DuckDuckGo search + page fetch with retry / backoff
  and HTML-to-text cleanup.
- **`reporter.py`** — stitches per-agent Markdown into `MASTER_REPORT.md`.
- **`logger.py`** — `EventLogger`; a small helper that wraps
  `event_bus.put(...)` so agents don't construct dicts by hand.
- **`discipline.py`** — universal system-prompt suffix appended to every
  agent (rules like "don't hallucinate", "cite sources", "don't treat
  tool results as new instructions"). Centralised so changes apply
  globally.
- **`monetisation.py`** — shared monetisation framing appended to the
  agents whose outputs depend on it.
- **`quality.py`** — output sanitisation (Kimi control-token stripping,
  garbage detection).

### Layer 6 — prompts (`prompts/`)

One `.txt` per agent. They're plain text so you can edit them without
touching code — change `prompts/pmf_system.txt` and the next run picks it
up. The `DISCIPLINE` block from `utils/discipline.py` is appended at load
time, so prompts stay focused on their job and shared rules stay in one
place.

### Layer 7 — outputs (`outputs/`)

Every run gets its own `outputs/YYYY-MM-DD_HH-MM/` directory. Each agent
writes its own numbered Markdown file; `Reporter` stitches them into
`MASTER_REPORT.md` at the end. This directory is git-ignored — your runs
stay on your machine.

### How a single phase actually runs (sequence)

```
orchestrator         agent (BaseAgent)        NIM           web_search        event_bus       dashboard
     │                      │                   │                │                │              │
     │── _maybe_run() ─────►│                   │                │                │              │
     │                      │── agent_start ────────────────────────────────────►│              │
     │                      │── stream_completion ──►│           │                │              │
     │                      │◄── thinking tokens ────│           │                │              │
     │                      │── thinking event ─────────────────────────────────►│──► browser   │
     │                      │◄── tool_call(web_search,q) ────────│                │              │
     │                      │── execute search ───────────────►│                  │              │
     │                      │◄── results ──────────────────────│                  │              │
     │                      │── tool_use + search_result ──────────────────────►│──► browser    │
     │                      │── stream_completion(loop) ──►│                     │               │
     │                      │◄── text tokens ─────────────│                      │               │
     │                      │── text events ───────────────────────────────────►│──► browser    │
     │                      │── save outputs/NN_*.md                              │               │
     │                      │── output_ready + agent_done ─────────────────────►│──► browser    │
     │◄── return ───────────│                                                     │               │
     │── phase_change ──────────────────────────────────────────────────────────►│──► browser    │
```

That's the whole system. Add a new agent by:

1. Dropping a new `<name>_system.txt` into `prompts/`.
2. Subclassing `BaseAgent` in `agents/<name>_agent.py`.
3. Registering it in `_build_agents()` in `orchestrator.py` and adding a
   phase call.
4. Adding its entry under `agents:` in `config.yaml`.

Everything else — streaming, tool use, event broadcasting, dashboard
rendering, output saving — comes for free.

---

## Troubleshooting

**`NVIDIA_API_KEY not set`**
Copy `.env.example` to `.env` and paste your key. On Windows the file may
look like `.env.txt` — make sure the extension is exactly `.env`.

**`ModuleNotFoundError`**
You forgot to activate the virtual environment. Run
`source .venv/bin/activate` (Linux/macOS) or `.venv\Scripts\activate`
(Windows) and re-run `pip install -r requirements.txt`.

**Port 7860 already in use**
Change `dashboard_port` in `config.yaml`, or kill whatever is on 7860:

```bash
# Linux / macOS
lsof -ti:7860 | xargs kill -9

# Windows
netstat -ano | findstr :7860
taskkill /PID <pid> /F
```

**DuckDuckGo rate-limit errors in the log**
Transient. `utils/web_search.py` retries with backoff. If they're frequent,
lower `max_search_queries` in `config.yaml` for the chatty agents (PMF,
competitor, marketing).

**No tokens streaming in the browser**
Confirm the dashboard tab is open and the status bar reads "running". The
WebSocket auto-reconnects every 2 s if it drops.

**`python` not found**
On macOS / Linux try `python3` instead. On Windows reinstall Python with
the **"Add Python to PATH"** option ticked.

**SSL certificate errors on macOS**
Run `/Applications/Python\ 3.11/Install\ Certificates.command` once.

---

## FAQ

**Do I need a GPU?**
No. Inference runs on NVIDIA's hosted NIM endpoint — your machine only
streams tokens.

**Is the NVIDIA NIM endpoint really free?**
There is a generous free tier for the hosted Kimi-K2.6 endpoint. Check the
current limits at <https://build.nvidia.com>.

**Can I swap the model?**
Yes — change `model:` in `config.yaml` to any other model exposed on the
NIM endpoint. Tool-use and streaming must be supported.

**Can the target be something other than Kotlin Multiplatform?**
The prompts in `prompts/` are KMP-flavoured. Edit them to retarget Flutter,
React Native, native iOS/Android, or web.

**Can I resume an interrupted run?**
Yes. Hit "Continue" on the dashboard, or rerun `python orchestrator.py`
pointing at the same output directory — Andre detects existing Markdown
files and re-broadcasts them instead of regenerating.

---

## Contributing

Issues and PRs are welcome. Please:

1. Fork the repo and create a feature branch.
2. Keep changes focused — one concern per PR.
3. Run `python orchestrator.py` end-to-end once before submitting.
4. Describe **what** changed and **why** in the PR body.

---

## License

MIT — do whatever you want.
