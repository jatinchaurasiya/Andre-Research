"""Phase 6 — UI/UX Design Prompt agent.

Produces a complete design brief that can be pasted into Claude to
generate production-ready UI designs / component code / Figma specs.
"""
from __future__ import annotations

from typing import Any

from agents.base_agent import BaseAgent
from utils.monetisation import MONETISATION_MODEL


class UIUXDesignPromptAgent(BaseAgent):
    prompt_filename = "uiux_design_prompt_system.txt"
    output_filename = "07_UI_UX_DESIGN_PROMPT.md"
    use_tools = True  # researches 2025–2026 design trends

    async def _load_system_prompt(self) -> str:
        base = await super()._load_system_prompt()
        return base + "\n\n" + MONETISATION_MODEL

    def _user_prompt(self, context: dict) -> str:
        pmf = context.get("pmf", {}) or {}
        prd = context.get("prd", {}) or {}
        feat = context.get("feature_architecture", {}) or {}
        impr = context.get("improvement", {}) or {}
        app_name = pmf.get("winner_name") or "the app"

        return (
            f"App name: {app_name}\n"
            f"Problem solved: {pmf.get('problem') or '(unknown)'}\n"
            f"Target persona: {pmf.get('persona') or '(unknown)'}\n"
            f"Killer differentiator: {pmf.get('killer_insight') or '(unknown)'}\n\n"
            "--- PRD (excerpt, for goals + screen list) ---\n"
            f"{(prd.get('raw_md') or '')[:3500]}\n\n"
            "--- FEATURE ARCHITECTURE (excerpt, for screen-by-screen prompts) ---\n"
            f"{(feat.get('raw_md') or '')[:3500]}\n\n"
            "--- IMPROVEMENT BLUEPRINT (excerpt, for UX principles) ---\n"
            f"{(impr.get('raw_md') or '')[:2500]}\n\n"
            "Search for current 2025–2026 design trends in this app's "
            "category. Search for what the top competitor apps look like "
            "visually. Then produce the complete UI_UX_DESIGN_PROMPT.md.\n\n"
            "The output will be pasted directly into Claude to generate "
            "designs. Every section must be precise enough to generate "
            "without guessing — design system, component specs, screen "
            "prompts, ad styling, paywall."
        )

    async def run(self, context: dict) -> dict:
        await self.execute(context)
        return context

    def _parse_output(self, md: str, context: dict) -> dict[str, Any]:
        return {}
