"""Phase 1 — Product-Market Fit research agent."""
from __future__ import annotations

import re
from typing import Any

from agents.base_agent import BaseAgent


class PMFAgent(BaseAgent):
    prompt_filename = "pmf_system.txt"
    output_filename = "01_pmf_research.md"
    use_tools = True

    def _user_prompt(self, context: dict) -> str:
        return (
            "Run the full PMF Research Process now.\n\n"
            "Goal: identify the single best zero-investment mobile app idea, "
            "targeting Kotlin Multiplatform (iOS + Android), founded on real "
            "user complaints sourced from Reddit, App Store / Play Store "
            "reviews, Product Hunt, X/Twitter, and HN.\n\n"
            "Constraints:\n"
            "- Must be buildable solo in 90 days for $0.\n"
            "- Must serve a real, documented persona — quote them.\n"
            "- Avoid saturated commodity categories.\n\n"
            "Use the web_search tool aggressively to gather evidence before "
            "drafting. Score 3 candidate ideas, then crown the winner. "
            "Output the final report in the exact Markdown structure described "
            "in your system prompt."
        )

    async def run(self, context: dict) -> dict:
        await self.execute(context)
        return context

    def _parse_output(self, md: str, context: dict) -> dict[str, Any]:
        winner_name = _extract_winner_name(md)
        persona = _extract_field(md, "Core user persona")
        problem = _extract_field(md, "The single core problem this solves")
        killer = _extract_field(md, "Killer insight")
        return {
            "winner_name": winner_name,
            "persona": persona,
            "problem": problem,
            "killer_insight": killer,
        }


def _extract_winner_name(md: str) -> str:
    # Match: ## Winner: <Name>
    m = re.search(r"^##\s*Winner\s*:\s*(.+?)\s*$", md, re.MULTILINE)
    if m:
        return m.group(1).strip().strip("[]")
    return ""


def _extract_field(md: str, label: str) -> str:
    # Match: **Label:** value (single line)
    pattern = rf"\*\*{re.escape(label)}\s*:\*\*\s*(.+?)\s*(?:\n|$)"
    m = re.search(pattern, md)
    if m:
        return m.group(1).strip().strip("[]")
    return ""
