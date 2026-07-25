"""Phase 3 — 30%+ Improvement Blueprint agent."""
from __future__ import annotations

import re
from typing import Any

from agents.base_agent import BaseAgent


class ImprovementAgent(BaseAgent):
    prompt_filename = "improvement_system.txt"
    output_filename = "04_improvement_blueprint.md"
    use_tools = True

    def _user_prompt(self, context: dict) -> str:
        pmf = context.get("pmf", {}) or {}
        reqs = context.get("requirements", {}) or {}
        comp = context.get("competitor", {}) or {}
        return (
            "Design a measurably better version of the winning app — at "
            "least 30% better than the strongest competitor on UX dimensions.\n\n"
            f"### App\n{pmf.get('winner_name') or '(unknown)'}\n\n"
            f"### Killer insight\n{pmf.get('killer_insight') or '(unknown)'}\n\n"
            "### Requirements spec (excerpt)\n"
            f"{(reqs.get('raw_md') or '')[:5000]}\n\n"
            "### Competitor analysis (excerpt)\n"
            f"{(comp.get('raw_md') or '')[:5000]}\n\n"
            "Now produce the full 30% Improvement Blueprint in the exact "
            "Markdown structure from your system prompt. Be ruthlessly "
            "specific about UI/UX wins, tap-count comparisons, and the one "
            "killer differentiator."
        )

    async def run(self, context: dict) -> dict:
        await self.execute(context)
        return context

    def _parse_output(self, md: str, context: dict) -> dict[str, Any]:
        return {"differentiator": _extract_section_text(md, "Killer Differentiator")}


def _extract_section_text(md: str, heading: str) -> str:
    pattern = rf"^##\s*{re.escape(heading)}.*?$(.*?)(?=^##\s|\Z)"
    m = re.search(pattern, md, re.MULTILINE | re.DOTALL)
    if not m:
        return ""
    block = m.group(1).strip()
    # Take the first non-empty paragraph
    paragraphs = [p.strip() for p in block.split("\n\n") if p.strip()]
    return paragraphs[0] if paragraphs else block
