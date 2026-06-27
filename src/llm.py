"""LLM routing and tab summary generation."""

from __future__ import annotations

import csv
import io
import logging

from google import genai
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_MODEL = "gemini-3.1-flash-lite"

# London, Paris, Rome — used only if the Gemini call fails entirely or the
# model returns too few valid IDs to fill three slots.
_FALLBACK_IDS = [1, 2, 3]


class _DestinationChoice(BaseModel):
    """Structured output schema for the routing LLM call."""

    destination_ids: list[int] = Field(
        description="Exactly 3 distinct destination IDs drawn from the catalogue."
    )


_SYSTEM_PROMPT = """\
You are a holiday destination router for the Holiday Planner app.

You will be given:
1. A user's open-ended description of their ideal holiday.
2. A catalogue of candidate destinations in CSV form, with columns:
   id,name,country,region,tags
   The `tags` field is semicolon-delimited (e.g. culture;history;food).

Your task:
- Choose exactly 3 destinations from the catalogue that best match the user's
  description.
- Return only the integer `id` values from the catalogue.

Selection rules:
- If the user names a specific region, country, or theme (e.g. "skiing in the
  Alps", "temples in Japan"), respect that constraint and stay within it. Do
  NOT inject geographic diversity that contradicts the request.
- Only when the user's request is broad or vague (e.g. "take me somewhere
  warm") should you prefer a geographically diverse spread (different regions
  or continents).
- The 3 chosen IDs must be distinct.
- Only use IDs that appear in the catalogue. Never invent destinations.
"""


def _build_catalogue_csv(destinations: list[dict]) -> str:
    """Serialise destination rows to a compact CSV string for the prompt."""
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=["id", "name", "country", "region", "tags"],
        quoting=csv.QUOTE_MINIMAL,
    )
    writer.writeheader()
    for row in destinations:
        writer.writerow({
            "id": row.get("id"),
            "name": row.get("name", ""),
            "country": row.get("country", ""),
            "region": row.get("region", ""),
            "tags": row.get("tags", ""),
        })
    return buf.getvalue()


def route_destinations(prompt: str, destinations: list[dict], api_key: str) -> list[int]:
    """Return exactly 3 destination IDs matching the user prompt.

    Args:
        prompt: User's open-ended holiday description.
        destinations: Rows with id, name, country, region, tags only.
        api_key: Google Gemini API key (passed in from UI layer).

    Returns:
        List of exactly 3 distinct destination IDs drawn from `destinations`.
        Falls back to a fixed list ([1, 2, 3]) if the Gemini call fails
        entirely (network/auth errors) or if the model returns too few valid
        IDs to fill three slots.
    """
    valid_ids = {int(r["id"]) for r in destinations if "id" in r}
    if not valid_ids:
        return []

    catalogue = _build_catalogue_csv(destinations)
    user_content = (
        f"User request:\n{prompt}\n\n"
        f"Destination catalogue (CSV):\n{catalogue}"
    )

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=_MODEL,
            contents=user_content,
            config={
                "system_instruction": _SYSTEM_PROMPT,
                "response_mime_type": "application/json",
                "response_json_schema": _DestinationChoice.model_json_schema(),
                "temperature": 0.2,
            },
        )
        choice = _DestinationChoice.model_validate_json(response.text)
        ids = choice.destination_ids
    except Exception as exc:
        logger.warning(
            "Gemini routing failed; using fallback IDs %s: %s", _FALLBACK_IDS, exc
        )
        return [i for i in _FALLBACK_IDS if i in valid_ids][:3] or list(valid_ids)[:3]

    # Keep only valid, distinct IDs, preserving model order.
    seen: set[int] = set()
    cleaned: list[int] = []
    for i in ids:
        if i in valid_ids and i not in seen:
            seen.add(i)
            cleaned.append(i)
        if len(cleaned) == 3:
            break

    # Pad from fallback if the model returned too few valid IDs.
    for fb in _FALLBACK_IDS:
        if len(cleaned) == 3:
            break
        if fb in valid_ids and fb not in seen:
            seen.add(fb)
            cleaned.append(fb)

    # Final guard: fall back to any valid ID if the fixed list doesn't cover it.
    if len(cleaned) < 3:
        for vid in valid_ids:
            if vid not in seen:
                seen.add(vid)
                cleaned.append(vid)
            if len(cleaned) == 3:
                break

    return cleaned[:3]


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
