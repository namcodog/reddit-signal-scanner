#!/usr/bin/env python3
"""
Generate a simple coverage summary from coverage.xml.
Outputs markdown to stdout and writes reports/coverage_summary.md.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path


def main() -> int:
    cov_xml = Path("coverage.xml")
    if not cov_xml.exists():
        print("⚠️ coverage.xml not found; run tests with coverage first")
        return 0

    tree = ET.parse(str(cov_xml))
    root = tree.getroot()

    # Cobertura schema: root has attributes line-rate, branch-rate
    line_rate = root.get("line-rate")
    branch_rate = root.get("branch-rate")
    line_pct = round(float(line_rate) * 100, 2) if line_rate else None
    branch_pct = round(float(branch_rate) * 100, 2) if branch_rate else None

    # Collect per-package lowest coverage modules (optional best-effort)
    lows: list[tuple[str, float]] = []
    for pkg in root.findall("packages/package"):
        for cls in pkg.findall("classes/class"):
            name = cls.get("filename") or cls.get("name") or "unknown"
            lr = cls.get("line-rate")
            if lr is None:
                continue
            lows.append((name, float(lr) * 100.0))

    lows.sort(key=lambda x: x[1])
    top5 = lows[:5]

    md_lines: list[str] = []
    md_lines.append("## Coverage Summary\n")
    if line_pct is not None:
        md_lines.append(f"- Line Coverage: {line_pct}%\n")
    if branch_pct is not None:
        md_lines.append(f"- Branch Coverage: {branch_pct}%\n")
    if top5:
        md_lines.append("- Lowest 5 files:\n")
        for name, pct in top5:
            md_lines.append(f"  - {name}: {round(pct, 2)}%\n")

    out_dir = Path("reports")
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / "coverage_summary.md"
    out_file.write_text("".join(md_lines), encoding="utf-8")
    print("".join(md_lines), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

