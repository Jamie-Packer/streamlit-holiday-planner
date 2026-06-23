"""Wikivoyage MediaWiki API client for See / Do / Drink sections."""

from __future__ import annotations


def fetch_section(page_title: str, section: str) -> str:
    """Fetch plain text for a Wikivoyage article section.

    Args:
        page_title: Wikivoyage article title (same as destinations.name).
        section: One of "See", "Do", or "Drink".

    Returns:
        Plain text content for the requested section.
    """
    raise NotImplementedError
