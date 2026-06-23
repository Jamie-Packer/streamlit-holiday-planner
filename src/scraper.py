"""FCDO travel advice HTML scraping."""

from __future__ import annotations


def fetch_fcdo_advice(country: str) -> dict:
    """Scrape FCDO travel advice for a country.

    Args:
        country: Human-readable country name from destinations.country
            (e.g. "United Kingdom"). Slug resolution is handled inside
            this module in Phase 2.

    Returns:
        {"safety_text": str, "entry_text": str}
    """
    raise NotImplementedError
