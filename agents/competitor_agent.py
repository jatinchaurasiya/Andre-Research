"""Phase 2b — Competitor Analysis agent (runs in parallel with requirements)."""
from __future__ import annotations

import re
from typing import Any

from agents.base_agent import BaseAgent


class CompetitorAgent(BaseAgent):
    prompt_filename = "competitor_system.txt"
    output_filename = "03_competitor_analysis.md"
    use_tools = True

    def _user_prompt(self, context: dict) -> str:
        pmf = context.get("pmf", {}) or {}
        return (
            "Produce the full Competitor Analysis Report for the winning app.\n\n"
            f"### App\n{pmf.get('winner_name') or '(unknown)'}\n\n"
            f"### Core problem solved\n{pmf.get('problem') or '(unknown)'}\n\n"
            f"### Persona\n{pmf.get('persona') or '(unknown)'}\n\n"
            "### PMF report (for reference)\n"
            f"{(pmf.get('raw_md') or '')[:4000]}\n\n"
            "Use the web_search tool heavily — issue at least 10 distinct, "
            "well-scoped queries to find direct competitors, scrape negative "
            "reviews, and uncover Reddit discussions before drafting. Then "
            "produce the final Markdown report following the exact structure "
            "in your system prompt."
        )

    async def run(self, context: dict) -> dict:
        await self.execute(context)
        return context

    def _parse_output(self, md: str, context: dict) -> dict[str, Any]:
        return {
            "top_complaints": _extract_numbered_list(md, "Top 10 User Complaints"),
            "whitespace_opportunities": _extract_numbered_list(md, "Whitespace Map"),
        }


def _extract_numbered_list(md: str, heading: str) -> list[str]:
    pattern = rf"^##\s*{re.escape(heading)}.*?$(.*?)(?=^##\s|\Z)"
    m = re.search(pattern, md, re.MULTILINE | re.DOTALL)
    if not m:
        return []
    block = m.group(1)
    items: list[str] = []
    for line in block.splitlines():
        line = line.strip()
        if re.match(r"^\d+\.\s+", line):
            items.append(re.sub(r"^\d+\.\s+", "", line).strip())
        elif line.startswith(("- ", "* ")):
            items.append(line[2:].strip())
    return items
