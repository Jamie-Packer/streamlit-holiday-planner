# Holiday Planner

Streamlit app: describe an ideal holiday → get three matching destinations → dashboard with weather, venues, travel advice, and tabbed summaries.

## Where we are

**MVP complete.** The full user flow works locally: Gemini routes prompts to three destinations from the walled-garden CSV, the user picks one, and the dashboard loads weather, a Google Places venue map, and lazy-loaded See / Do / Drink / Safety summaries — all cached in DuckDB.

Next steps are refinements (UI polish, deploy, error states) rather than core functionality.

## Local setup

From the repo root:

```powershell
conda create -n holiday-planner python=3.11 -y
conda activate holiday-planner
pip install -r requirements.txt
streamlit run Home.py
```

`Home.py` calls `init_db()` on startup. The repo includes a pre-seeded `data/planner.db`; run `python src/database.py` only if you need to rebuild the database from `destinations.csv`.

### API keys

Create `.streamlit/secrets.toml` (gitignored) for live features:

```toml
GEMINI_API_KEY = "your-key"
GOOGLE_PLACES_API_KEY = "your-key"
```

| Key | Used for |
|-----|----------|
| `GEMINI_API_KEY` | Search routing + tab summaries |
| `GOOGLE_PLACES_API_KEY` | Dashboard venue map |

Weather, Wikivoyage, and FCDO travel advice need no keys.

## Smoke tests

Local opt-in checks for `src/` fetchers — not run on deploy. Pass at least one flag (nothing runs by default):

```powershell
python tests/run_smoke_tests.py --weather --wikivoyage --scraper   # no keys
python tests/run_smoke_tests.py --llm --summarise                  # GEMINI_API_KEY
python tests/run_smoke_tests.py --all --no-keys                    # skip Geoapify
python tests/run_smoke_tests.py --all                              # full suite (needs keys)
```

Reports are written to `tests/reports/smoke_report.txt`. See `tests/run_smoke_tests.py --help` for individual flags (`--orchestrators`, `--fcdo-summary`, `--flights`, etc.).

## Layout

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
