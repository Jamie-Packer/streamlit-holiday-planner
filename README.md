# Holiday Planner

Describe your ideal trip in plain language and get three curated destination recommendations, each with live weather, nearby venues on a map, and AI summaries of what to see, do, drink, and how to stay safe.

View the live deployment here!

✨[https://super-epic-holiday-inspo-app.streamlit.app/](https://super-epic-holiday-inspo-app.streamlit.app/)✨

> Note: The map feature will likely stop working when the google API key is disabled some day.

## Features

- **Natural-language search**: Google Gemini reads your prompt and picks three matching destinations from a curated catalogue of 300 cities worldwide.
- **Destination dashboard**: hero imagery, quick switcher between your three suggestions, and deep links via `?dest=<id>` for sharing.
- **Weather**: monthly climate chart, seven-day forecast, and today's conditions via Open-Meteo (no API key required).
- **Venue map**: Google Places nearby search for cafes, bars, attractions, and nightclubs, rendered on an interactive Folium map.
- **Tabbed guides**: Wikivoyage content and GOV.UK FCDO travel advice, condensed into readable summaries by Gemini:
  - **See**: sights and landmarks
  - **Do**: activities and experiences
  - **Drink**: bars, cafés, and nightlife
  - **Safety**: official foreign travel advice
- **Smart caching**: DuckDB stores fetched data so repeat visits are fast and API usage stays low.

## How it works

1. **Search**: enter a prompt (e.g. *"warm beach city with great food and nightlife"*). Gemini returns three geographically diverse matches.
2. **Choose**: click a destination card to open its dashboard.
3. **Explore**: browse weather, venues, and summary tabs. Switch between your three suggestions from the top bar, or share a link with `?dest=<id>`.

Recommendations come only from `data/destinations.csv`; the LLM filters and ranks within that list and never invents destinations outside it.

## Data sources

| Source | Used for |
|--------|----------|
| Google Gemini | Search routing + tab summaries |
| Google Places API (New) | Dashboard venue map |
| Open-Meteo | Weather and climate |
| Wikivoyage (MediaWiki API) | See / Do / Drink raw content |
| GOV.UK FCDO | Safety tab (web scrape) |
| DuckDB | Local cache (`data/planner.db`) |

## Run locally

```powershell
conda create -n holiday-planner python=3.11 -y
conda activate holiday-planner
pip install -r requirements.txt
streamlit run Home.py
```

`Home.py` initialises the database on startup. The repo ships with a pre-seeded `data/planner.db`. To rebuild from scratch:

```powershell
python src/database.py
```

### API keys

Create `.streamlit/secrets.toml` (gitignored):

```toml
GEMINI_API_KEY = "your-key"
GOOGLE_PLACES_API_KEY = "your-key"
```

| Key | Used for |
|-----|----------|
| `GEMINI_API_KEY` | Search routing + tab summaries |
| `GOOGLE_PLACES_API_KEY` | Dashboard venue map |

Weather, Wikivoyage, and FCDO travel advice need no keys.

## Deploy

The app is designed for [Streamlit Community Cloud](https://streamlit.io/cloud). Connect your GitHub repo, set the same secrets in the Cloud dashboard, and point the entry file to `Home.py`. The committed `data/planner.db` gives the deployed app a warm cache from the first request.

## Project layout

```
Home.py              → single-page router (search ↔ dashboard)
views/               → search_view.py, dashboard_view.py
theme.py             → global CSS and image helpers
src/database.py      → DuckDB cache + get_or_fetch orchestrators
src/*.py             → fetch external data (no Streamlit imports)
data/                → destinations.csv + planner.db
tests/               → local smoke tests
pages/3_Dev_Tools.py → cache inspect stub (optional)
```

## Development

Opt-in smoke tests exercise individual fetchers and LLM calls locally (not run on deploy):

```powershell
python tests/run_smoke_tests.py --weather --wikivoyage --scraper   # no keys
python tests/run_smoke_tests.py --llm --summarise                  # GEMINI_API_KEY
python tests/run_smoke_tests.py --all                              # full suite (needs keys)
```

Reports are written to `tests/reports/smoke_report.txt`. See `tests/run_smoke_tests.py --help` for all flags.
