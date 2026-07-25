"""Phase 5 — Product Requirements Document agent.

Synthesises every prior agent output into a single, complete, sourced
PRD. No new web searches — relies entirely on prior research.
"""
from __future__ import annotations

import re
from typing import Any

from agents.base_agent import BaseAgent
from utils.monetisation import MONETISATION_MODEL


class PRDAgent(BaseAgent):
    prompt_filename = "prd_system.txt"
    output_filename = "06_PRD.md"
    use_tools = False  # synthesise from context, no new searches

    async def _load_system_prompt(self) -> str:
        base = await super()._load_system_prompt()
        return base + "\n\n" + MONETISATION_MODEL

    def _user_prompt(self, context: dict) -> str:
        sections: list[str] = []
        for key, label in [
            ("pmf",                  "PMF RESEARCH REPORT"),
            ("requirements",         "BUILD REQUIREMENTS"),
            ("competitor",           "COMPETITOR ANALYSIS"),
            ("improvement",          "IMPROVEMENT BLUEPRINT"),
            ("feature_architecture", "FEATURE ARCHITECTURE"),
        ]:
            ctx = context.get(key) or {}
            raw = (ctx.get("raw_md") or "")[:4500]
            if raw:
                sections.append(f"=== {label} ===\n{raw}")

        pmf = context.get("pmf", {}) or {}
        header = (
            "Synthesise the following research into a complete, "
            "professional PRD for the winning app.\n\n"
            "Do NOT invent requirements — every section must trace back to "
            "the research below.\n"
            f"Effective date: 2026.\n"
            f"App: {pmf.get('winner_name') or '(unknown)'}.\n\n"
        )
        return header + "\n\n".join(sections)

    async def run(self, context: dict) -> dict:
        await self.execute(context)
        return context

    def _parse_output(self, md: str, context: dict) -> dict[str, Any]:
        pmf = context.get("pmf", {}) or {}
        return {
            "app_name": pmf.get("winner_name") or "",
            "executive_summary": _extract_section_text(md, "1.1 Product Vision"),
            "anti_goals": _extract_section_text(md, "2.3 Anti-Goals (Explicit Out-of-Scope)"),
        }


def _extract_section_text(md: str, heading: str) -> str:
    pattern = rf"^#{{1,4}}\s*{re.escape(heading)}.*?$(.*?)(?=^#{{1,4}}\s|\Z)"
    m = re.search(pattern, md, re.MULTILINE | re.DOTALL)
    return m.group(1).strip() if m else ""
