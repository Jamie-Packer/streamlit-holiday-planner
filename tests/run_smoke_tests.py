"""Run local smoke tests for implemented fetch modules.

Usage (from any directory):
    python tests/run_smoke_tests.py --wikivoyage
    python tests/run_smoke_tests.py --weather --places
    python tests/run_smoke_tests.py --all
    python -m tests.run_smoke_tests --all --no-keys

Pass at least one test flag (or --all). Nothing runs by default.

Flags:
    --all       Run weather, places, llm, summarise, wikivoyage (not flights)
    --no-keys   With --all, skip places (Geoapify needs GEOAPIFY_API_KEY)
    --weather   Open-Meteo forecast + climate (no key)
    --places    Geoapify nearby venues (uses GEOAPIFY_API_KEY)
    --flights   Selenium Momondo scrape (slow, needs Chrome) — never included in --all
    --llm       Gemini destination routing (uses GEMINI_API_KEY)
    --summarise Gemini tab summarisation (uses GEMINI_API_KEY)
    --wikivoyage Wikivoyage MediaWiki fetcher (live, no key)
    --wikivoyage-summary Wikivoyage fetch → Gemini see-tab summary (GEMINI_API_KEY)
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
    "summarise": "tests.smoke_summarise",
    "wikivoyage": "tests.smoke_wikivoyage",
    "wikivoyage_summary": "tests.smoke_wikivoyage_summary",
}

# --all runs these; flights is always opt-in separately (Selenium, slow, needs Chrome).
_ALL_TESTS = ("weather", "places", "llm", "summarise", "wikivoyage")


def _load_module(name: str):
    import importlib

    return importlib.import_module(_SMOKE_MODULES[name])


def _run_module(name: str, mod) -> tuple[str, str | None]:
    try:
        mod.run()
        return name, None
    except Exception as exc:
        return name, str(exc)


def _resolve_tests(args: argparse.Namespace) -> list[str]:
    """Build ordered, de-duplicated list of tests to run from CLI flags."""
    selected: set[str] = set()
    if args.all:
        selected.update(_ALL_TESTS)
    if args.weather:
        selected.add("weather")
    if args.places:
        selected.add("places")
    if args.flights:
        selected.add("flights")
    if args.llm:
        selected.add("llm")
    if args.summarise:
        selected.add("summarise")
    if args.wikivoyage:
        selected.add("wikivoyage")
    if args.wikivoyage_summary:
        selected.add("wikivoyage_summary")

    if not selected:
        return []

    if args.no_keys:
        selected.discard("places")

    # Preserve stable run order regardless of flag order on the CLI.
    return [name for name in _SMOKE_MODULES if name in selected]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run fetcher smoke tests locally (opt-in — pass at least one flag).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run weather, places, llm, summarise, wikivoyage (not flights)",
    )
    parser.add_argument(
        "--no-keys",
        action="store_true",
        help="With --all, skip places (Geoapify)",
    )
    parser.add_argument("--weather", action="store_true", help="Open-Meteo weather fetchers")
    parser.add_argument("--places", action="store_true", help="Geoapify nearby venues")
    parser.add_argument(
        "--flights",
        action="store_true",
        help="Selenium Momondo scrape (slow, needs Chrome; not part of --all)",
    )
    parser.add_argument("--llm", action="store_true", help="Gemini destination routing")
    parser.add_argument("--summarise", action="store_true", help="Gemini tab summarisation")
    parser.add_argument("--wikivoyage", action="store_true", help="Wikivoyage MediaWiki fetcher")
    parser.add_argument(
        "--wikivoyage-summary",
        action="store_true",
        help="Wikivoyage fetch → Gemini see-tab summary pipeline",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT, help="Report output path")
    args = parser.parse_args()

    to_run = _resolve_tests(args)
    if not to_run:
        parser.error(
            "pass at least one test flag "
            "(--weather, --places, --llm, --summarise, --wikivoyage, "
            "--wikivoyage-summary, --flights) or --all"
        )

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        f"Smoke tests — {timestamp}",
        "========================================",
    ]
    if args.all and args.no_keys:
        lines.append("Note: places skipped (--no-keys)")

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

    lines.append("========================================")
    lines.append(f"{passed} passed, {failed} failed, {len(to_run)} run")

    report = "\n".join(lines)
    print(report)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report + "\n", encoding="utf-8")
    print(f"\nReport written to {args.output}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
