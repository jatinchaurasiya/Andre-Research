"""Phase 2a — Build Requirements agent (runs in parallel with competitor)."""
from __future__ import annotations

import re
from typing import Any

from agents.base_agent import BaseAgent


class RequirementsAgent(BaseAgent):
    prompt_filename = "requirements_system.txt"
    output_filename = "02_requirements.md"
    use_tools = True

    def _user_prompt(self, context: dict) -> str:
        pmf = context.get("pmf", {}) or {}
        return (
            "Produce the complete Build Requirements Spec for the winning app.\n\n"
            f"### App\n{pmf.get('winner_name') or '(unknown)'}\n\n"
            f"### Persona\n{pmf.get('persona') or '(unknown)'}\n\n"
            f"### Core problem\n{pmf.get('problem') or '(unknown)'}\n\n"
            f"### Killer insight\n{pmf.get('killer_insight') or '(unknown)'}\n\n"
            "### Full PMF report (for reference)\n"
            f"{(pmf.get('raw_md') or '')[:6000]}\n\n"
            "Now produce the full Markdown spec — architecture, features, "
            "screen map, user flows, tech stack (every dep on a free tier), "
            "data model, free infrastructure plan, distribution plan (iOS + "
            "Android both $0), monetisation path, and a 90-day build timeline. "
            "Be specific; no placeholders."
        )

    async def run(self, context: dict) -> dict:
        await self.execute(context)
        return context

    def _parse_output(self, md: str, context: dict) -> dict[str, Any]:
        return {"tech_stack": _extract_section_list(md, "Tech Stack")}


def _extract_section_list(md: str, heading: str) -> list[str]:
    pattern = rf"^##\s*{re.escape(heading)}.*?$(.*?)(?=^##\s|\Z)"
    m = re.search(pattern, md, re.MULTILINE | re.DOTALL)
    if not m:
        return []
    block = m.group(1)
    items: list[str] = []
    for line in block.splitlines():
        line = line.strip()
        if line.startswith(("- ", "* ")):
            items.append(line[2:].strip())
    return items
