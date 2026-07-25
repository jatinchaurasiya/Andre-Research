"""Phase 4 — Feature Architecture agent.

Receives PMF + Requirements + Competitor + Improvement context. Produces
a fully-specified feature document (every feature with acceptance
criteria, UI states, business logic, and monetisation integration).
"""
from __future__ import annotations

import re
from typing import Any

from agents.base_agent import BaseAgent
from utils.monetisation import MONETISATION_MODEL


class FeatureArchitectureAgent(BaseAgent):
    prompt_filename = "feature_architecture_system.txt"
    output_filename = "05_feature_architecture.md"
    use_tools = True

    async def _load_system_prompt(self) -> str:
        # Append the shared monetisation model so this agent reasons from
        # the same business model as every other agent.
        base = await super()._load_system_prompt()
        return base + "\n\n" + MONETISATION_MODEL

    def _user_prompt(self, context: dict) -> str:
        pmf = context.get("pmf", {}) or {}
        req = context.get("requirements", {}) or {}
        comp = context.get("competitor", {}) or {}
        impr = context.get("improvement", {}) or {}
        return (
            "Produce the complete Feature Architecture Document for the "
            "winning app.\n\n"
            f"### App\n{pmf.get('winner_name') or '(unknown)'}\n"
            f"### Core problem\n{pmf.get('problem') or '(unknown)'}\n"
            f"### Persona\n{pmf.get('persona') or '(unknown)'}\n"
            f"### Killer insight\n{pmf.get('killer_insight') or '(unknown)'}\n\n"
            "### Requirements Spec (excerpt)\n"
            f"{(req.get('raw_md') or '')[:4000]}\n\n"
            "### Competitor weaknesses + monetisation landscape (excerpt)\n"
            f"{(comp.get('raw_md') or '')[:3000]}\n\n"
            "### Improvement Blueprint (excerpt)\n"
            f"{(impr.get('raw_md') or '')[:3000]}\n\n"
            "Now produce the full document in the exact Markdown structure "
            "from your system prompt. Every feature spec'd; every feature "
            "classified FREE / PAID / FREE_WITH_REWARDED_AD; every ad "
            "placement justified; RevenueCat entitlement map and AdMob ad "
            "unit map populated."
        )

    async def run(self, context: dict) -> dict:
        await self.execute(context)
        return context

    def _parse_output(self, md: str, context: dict) -> dict[str, Any]:
        features = [
            m.group(1).strip()
            for m in re.finditer(r"^###\s*Feature\s*:\s*(.+?)\s*$", md, re.MULTILINE)
        ]
        return {
            "feature_list": features,
            "monetisation_map": _extract_section_text(md, "Monetisation Architecture Summary"),
            "revenuecat_entitlements": _extract_section_text(md, "RevenueCat Entitlement Map"),
            "admob_units": _extract_section_text(md, "AdMob Ad Unit Map"),
        }


def _extract_section_text(md: str, heading: str) -> str:
    pattern = rf"^##\s*{re.escape(heading)}.*?$(.*?)(?=^##\s|\Z)"
    m = re.search(pattern, md, re.MULTILINE | re.DOTALL)
    return m.group(1).strip() if m else ""
