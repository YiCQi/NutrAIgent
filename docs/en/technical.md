# Technical notes

For developers and anyone who wants to know how NutrAIgent works. For usage, see the [README](../../README.md).

## Architecture

- **Backend:** Python 3.11+, FastAPI, SQLite (one local file). Code in `backend/app/`.
- **Frontend:** React + Vite. Built into `frontend/dist/` and served by the backend, so the app runs on one port.
- **Nutrition engine:** deterministic Python (`backend/app/engine/`). Targets and totals are calculated in code, never by the AI.
- **AI assistant:** `backend/app/ai/`. Provider adapters, food parsing (`nllog.py`), food matching (`aliases.py`, `matching.py`), tool-based agent for questions (`agent.py`).
- **Meal planner:** `backend/app/planner.py`. The AI proposes foods and grams; the backend looks up nutrients and scales the day to the energy target.
- **Background jobs:** `backend/app/jobs.py`. Chat replies and meal-plan generation keep running if the browser tab is closed.

## Food data

| Source | Version | Foods | Licence |
|---|---|---|---|
| UK CoFID (McCance and Widdowson) | 2021 | 2,887 | Open Government Licence v3.0 |
| USDA FoodData Central, SR Legacy | 2018-04 | 7,793 | CC0 |
| USDA FoodData Central, Foundation Foods | 2026-10-29 (JSON) | 424 | CC0 |

- Foods from different sources are not merged. The same food can appear more than once in search.
- Stored nutrients: energy, protein, carbohydrate, fat, fibre, sugars, saturated fat, sodium, calcium, iron, vitamin C, vitamin B12. Other nutrients are not yet tracked.
- Values are per 100 g (alcoholic drinks in the CoFID data are per 100 ml and are not converted).

### Missing data is never zero

| Source value | Stored as |
|---|---|
| Blank or no row | Missing (shown as "no data") |
| CoFID `N` (present, no reliable amount) | Missing |
| CoFID `Tr` (trace) | 0, flagged as trace |
| Measured `0` | 0 |

Totals never count a missing value as zero.

### Importing the data

The database starts empty. The importers read raw files you download yourself (they are not in the repository, see the [README](../../README.md#step-4-load-food-data-once)).

```
backend/scripts/import_cofid.py            [--xlsx FILE] [--db PATH]
backend/scripts/import_usda_sr_legacy.py   [--raw DIR]   [--db PATH]
backend/scripts/import_usda_foundation.py  [--json FILE] [--db PATH]
```

- Each importer replaces only its own source, so re-running is safe.
- Default database: `~/.nutraigent/nutraigent.db` (Windows: `C:\Users\<name>\.nutraigent\nutraigent.db`). Override with the `NUTRAIGENT_DB` environment variable or `--db`.

## Calculation (provisional)

These are the defaults used for targets. They are **not yet checked against an official reference standard**, and the app marks them as provisional.

- **BMR:** Mifflin-St Jeor.
- **Activity factor:** 1.2 to 1.9 by activity level.
- **Energy:** fat loss -20 %, maintenance 0 %, muscle gain +10 % of TDEE.
- **Protein:** 1.8 g/kg (fat loss, muscle gain); 1.0 g/kg (maintenance).
- **Fat:** 30 % of energy.
- **Saturated fat:** at most 10 % of energy.
- **Fibre:** 30 g.
- **Sodium:** at most 2,400 mg.

Micronutrient targets are not implemented yet. The profile page shows the calculation steps.

## AI assistant

### Setup

Bring your own key (BYOK). Supported provider types:

- **Anthropic** (Claude models).
- **OpenAI-compatible** endpoints: OpenAI, OpenRouter, Ollama, LM Studio and similar. Set the base URL and model name.

New providers can be added in `backend/app/ai/providers.py` (`REGISTRY`).

### What is sent, and where it is stored

- Your chat text and the food search results or daily intake needed for the reply are sent to the provider you chose.
- The API key and provider settings are stored **in plain text** in the local SQLite database. The key is never returned to the browser. Do not use this on a shared computer.
- Nothing is logged until you click **Confirm** on a proposal.

### Logging flow

1. The model extracts items from your text (food name, amount, meal, date) in one call.
2. The backend matches each item to the database and looks up the portion size. The model does not supply nutrient values.
3. The app shows a proposal card. You can change the food, grams or meal, or untick items.
4. **Confirm** saves the entries. Composite dishes can be saved as recipes with their ingredients.

## Developer commands

```
.\start.ps1               build the frontend if needed and run the app on port 8000
.\start.ps1 -Dev          backend (8000) and Vite dev server with hot reload (5173)
.\start.ps1 -Port 9000 -NoBrowser
```

Tests:

```
cd backend
.venv\Scripts\python -m pytest
```

Frontend build:

```
cd frontend
npm run build
```

Environment variables:

- `NUTRAIGENT_DB`: path to the SQLite database.
- `NUTRAIGENT_API`: backend URL used by the Vite dev proxy.

Only `start.bat` and `start.ps1` are tested on Windows. macOS and Linux users can run the backend with `uvicorn app.main:app` from `backend/` and build the frontend with `npm run build`; this path is not tested.

## Roadmap

1. ~~MVP: profile, food database, targets, daily tracking.~~ Done.
2. ~~AI assistant: bring-your-own key, natural-language logging, Q&A.~~ Done.
3. ~~Meal planning.~~ Basic version done. Still open: adapting plans to actual intake, shopping lists, weekly summaries.
4. Advanced: trends, adaptive recommendations, more nutrients.

## Principles

Scientific accuracy over AI assumptions. Traceable data sources. Local-first privacy. Modular design.
