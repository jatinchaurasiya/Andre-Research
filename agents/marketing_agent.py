"""Phase 4 — Zero-Budget Marketing Playbook agent."""
from __future__ import annotations

import re
from typing import Any

from agents.base_agent import BaseAgent


class MarketingAgent(BaseAgent):
    prompt_filename = "marketing_system.txt"
    output_filename = "08_marketing_playbook.md"
    use_tools = True

    def _user_prompt(self, context: dict) -> str:
        pmf = context.get("pmf", {}) or {}
        reqs = context.get("requirements", {}) or {}
        comp = context.get("competitor", {}) or {}
        imp = context.get("improvement", {}) or {}
        return (
            "Produce the full Zero-Budget Marketing Playbook for getting the "
            "first 10,000 downloads at $0 spend.\n\n"
            f"### App\n{pmf.get('winner_name') or '(unknown)'}\n"
            f"### Persona\n{pmf.get('persona') or '(unknown)'}\n"
            f"### Killer differentiator\n{imp.get('differentiator') or '(unknown)'}\n\n"
            "### Requirements (excerpt)\n"
            f"{(reqs.get('raw_md') or '')[:2500]}\n\n"
            "### Competitor analysis (excerpt)\n"
            f"{(comp.get('raw_md') or '')[:2500]}\n\n"
            "### Improvement blueprint (excerpt)\n"
            f"{(imp.get('raw_md') or '')[:3000]}\n\n"
            "Use web_search to find the exact subreddits, ASO keywords, "
            "ProductHunt patterns, and micro-influencers relevant to this "
            "persona. Then produce the full Markdown playbook following the "
            "exact structure in your system prompt."
        )

    async def run(self, context: dict) -> dict:
        await self.execute(context)
        return context

    def _parse_output(self, md: str, context: dict) -> dict[str, Any]:
        return {
            "aso_keywords": _extract_section_lines(md, "Keyword Research"),
            "launch_plan": _extract_section_text(md, "Day 1 (Launch Day)"),
        }


def _extract_section_text(md: str, heading: str) -> str:
    # Header may be H3 (### …) inside Launch Week Plan
    pattern = rf"^#{{2,4}}\s*{re.escape(heading)}.*?$(.*?)(?=^#{{2,4}}\s|\Z)"
    m = re.search(pattern, md, re.MULTILINE | re.DOTALL)
    if not m:
        return ""
    return m.group(1).strip()


def _extract_section_lines(md: str, heading: str) -> list[str]:
    text = _extract_section_text(md, heading)
    out: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(("- ", "* ")):
            out.append(line[2:].strip())
        elif re.match(r"^\d+\.\s+", line):
            out.append(re.sub(r"^\d+\.\s+", "", line).strip())
    return out
