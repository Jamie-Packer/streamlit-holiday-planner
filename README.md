# Holiday Planner

Streamlit app: describe an ideal holiday → get three matching destinations → dashboard with weather, venues, travel advice, and tabbed summaries.

## Where we are

**Phase 1 done** — DuckDB schema, `get_*` / `save_*` in `database.py`, stub `fetch_*` functions in `src/`, placeholder Streamlit shell, 100 destinations seeded in `planner.db`.

**Phase 2 now** — we're implementing the `fetch_*` helpers in parallel (`weather`, `scraper`, `wikivoyage`, `places`, `llm`), then wiring `get_or_fetch_*` in `database.py` to cache results (`fetch → save → get`). Phase 3 is the full UI and deploy.


## Local setup

From the repo root:

```powershell
conda create -n holiday-planner python=3.11 -y
conda activate holiday-planner
pip install -r requirements.txt
python src/database.py          # once — seeds planner.db if empty
streamlit run Home.py
```

API keys (Google Places, LLM) go in `.streamlit/secrets.toml` when we need them — see `.gitignore`. Not required for the placeholder app.

## Layout

```
Home.py / pages/     → UI (Phase 3)
src/database.py      → DuckDB cache
src/*.py             → fetch external data (no Streamlit, no DuckDB)
data/                → destinations.csv + planner.db
```
