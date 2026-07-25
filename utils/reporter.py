"""Compiles per-agent Markdown outputs into a single MASTER_REPORT.md."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path


class Reporter:
    """Reads the 8 per-agent Markdown files and stitches them together."""

    FILE_MAP = [
        ("01_pmf_research.md",          "PMF Research"),
        ("02_requirements.md",          "Build Requirements"),
        ("03_competitor_analysis.md",   "Competitor Analysis"),
        ("04_improvement_blueprint.md", "Improvement Blueprint"),
        ("05_feature_architecture.md",  "Feature Architecture"),
        ("06_PRD.md",                   "Product Requirements Document"),
        ("07_UI_UX_DESIGN_PROMPT.md",   "UI/UX Design Prompt"),
        ("08_marketing_playbook.md",    "Marketing Playbook"),
    ]

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)

    def compile(self, context: dict) -> Path:
        run_id = context.get("run_id", "unknown")
        pmf = context.get("pmf", {}) or {}
        winner = pmf.get("winner_name") or "(unknown)"
        persona = pmf.get("persona") or "(unknown)"
        problem = pmf.get("problem") or "(unknown)"
        killer = pmf.get("killer_insight") or "(unknown)"

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines: list[str] = []
        lines.append(f"# Andre Master Report — {winner}")
        lines.append("")
        lines.append(f"- **Run ID:** {run_id}")
        lines.append(f"- **Generated:** {ts}")
        lines.append(f"- **Winning App:** {winner}")
        lines.append(f"- **Core Persona:** {persona}")
        lines.append(f"- **Problem Solved:** {problem}")
        lines.append(f"- **Killer Insight:** {killer}")
        lines.append("")
        lines.append("## Table of Contents")
        for fname, title in self.FILE_MAP:
            anchor = title.lower().replace(" ", "-")
            lines.append(f"- [{title}](#{anchor})")
        lines.append("")
        lines.append("---")
        lines.append("")

        for fname, title in self.FILE_MAP:
            fpath = self.output_dir / fname
            lines.append(f"## {title}")
            lines.append("")
            if fpath.exists():
                try:
                    content = fpath.read_text(encoding="utf-8").strip()
                except Exception as exc:
                    content = f"_Could not read {fname}: {exc}_"
                # Demote any top-level H1 inside the agent file so the master
                # report's H2 structure stays intact.
                content = self._demote_headings(content)
                lines.append(content)
            else:
                lines.append(f"_File missing: {fname}_")
            lines.append("")
            lines.append("---")
            lines.append("")

        master_path = self.output_dir / "MASTER_REPORT.md"
        master_path.write_text("\n".join(lines), encoding="utf-8")
        return master_path

    @staticmethod
    def _demote_headings(md: str) -> str:
        out: list[str] = []
        for line in md.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("#"):
                # Count leading hashes
                hashes = 0
                for ch in stripped:
                    if ch == "#":
                        hashes += 1
                    else:
                        break
                if hashes <= 5:
                    rest = stripped[hashes:]
                    out.append("#" * (hashes + 1) + rest)
                    continue
            out.append(line)
        return "\n".join(out)
