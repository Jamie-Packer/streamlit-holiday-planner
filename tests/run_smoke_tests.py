"""Run local smoke tests for implemented fetch modules.

Usage (from any directory):
    python tests/run_smoke_tests.py
    python -m tests.run_smoke_tests

Flags:
    --no-keys   Weather only (skip Geoapify)
    --flights   Also run Selenium Momondo scrape (slow, needs Chrome)
    --llm       Also run Gemini destination routing (uses GEMINI_API_KEY)
    --output    Report file path (default: tests/reports/smoke_report.txt)

Not intended for Streamlit Cloud — avoids burning API credits on deploy.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

DEFAULT_REPORT = ROOT / "tests" / "reports" / "smoke_report.txt"

_SMOKE_MODULES = {
    "weather": "tests.smoke_weather",
    "places": "tests.smoke_places",
    "flights": "tests.smoke_flights",
    "llm": "tests.smoke_llm",
}


def _load_module(name: str):
    import importlib

    return importlib.import_module(_SMOKE_MODULES[name])


def _run_module(name: str, mod) -> tuple[str, str | None]:
    try:
        mod.run()
        return name, None
    except Exception as exc:
        return name, str(exc)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run fetcher smoke tests locally.")
    parser.add_argument("--no-keys", action="store_true", help="Skip Geoapify (weather only)")
    parser.add_argument("--flights", action="store_true", help="Include Selenium flight scrape")
    parser.add_argument("--llm", action="store_true", help="Include Gemini destination routing")
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT, help="Report output path")
    args = parser.parse_args()

    to_run: list[str] = ["weather"]
    skipped: list[str] = []

    if args.no_keys:
        skipped.append("places")
    else:
        to_run.append("places")

    if args.flights:
        to_run.append("flights")
    else:
        skipped.append("flights")

    if args.llm:
        to_run.append("llm")
    else:
        skipped.append("llm")

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        f"Smoke tests — {timestamp}",
        "========================================",
    ]

    passed = 0
    failed = 0
    for name in to_run:
        try:
            mod = _load_module(name)
        except Exception as exc:
            lines.append(f"{name:<10} FAIL — {exc}")
            failed += 1
            continue
        _, err = _run_module(name, mod)
        if err is None:
            lines.append(f"{name:<10} PASS")
            passed += 1
        else:
            lines.append(f"{name:<10} FAIL — {err}")
            failed += 1

    for name in skipped:
        lines.append(f"{name:<10} SKIPPED")

    lines.append("========================================")
    lines.append(f"{passed} passed, {failed} failed, {len(skipped)} skipped")

    report = "\n".join(lines)
    print(report)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report + "\n", encoding="utf-8")
    print(f"\nReport written to {args.output}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
