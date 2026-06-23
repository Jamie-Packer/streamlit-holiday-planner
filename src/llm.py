"""LLM routing and tab summary generation."""

from __future__ import annotations


def route_destinations(prompt: str, destinations: list[dict], api_key: str) -> list[int]:
    """Return exactly 3 destination IDs matching the user prompt.

    Args:
        prompt: User's open-ended holiday description.
        destinations: Rows with id, name, country, region, tags only.
        api_key: LLM provider API key (passed in from UI layer).

    Returns:
        List of exactly 3 destination IDs with geographic diversity.
    """
    raise NotImplementedError


def summarise_tab(raw_text: str, tab_type: str, api_key: str) -> str:
    """Generate a concise summary for a dashboard tab.

    Args:
        raw_text: Source text from Wikivoyage or FCDO scrape.
        tab_type: One of see, do, drink, or safety.
        api_key: LLM provider API key (passed in from UI layer).

    Returns:
        Concise summary string for display in the tab panel.
    """
    raise NotImplementedError
