# HANDOFF

## Status (2026-11-16)
- MVP scaffold done and pushed. Backend: 4 pytest tests pass. Frontend: `npm run build` OK. Frontend not run against live backend yet.
- Remote: https://github.com/YiCQi/NutrAIgent. Policy: always commit and push after each task.
- Commit identity (repo-local): YiCQi + GitHub noreply email.

## Layout
- `backend/` FastAPI. `app/schema.sql` (schema v1), `app/db.py`, `app/engine/targets.py`, `app/engine/analysis.py`, `app/main.py` (routes under `/api`), `tests/`.
- `frontend/` Vite + React; proxies `/api` to 127.0.0.1:8000. Only a status page + daily comparison table. No profile form, no food search/log UI.
- DB path: `~/.nutraigent/nutraigent.db` (override `NUTRAIGENT_DB`).
- Run: `cd backend && .venv/Scripts/python -m uvicorn app.main:app --reload`; `cd frontend && npm run dev`.

## PROVISIONAL defaults (unconfirmed, flagged in API trace `provisional: true`)
- BMR Mifflin-St Jeor; PAL 1.2-1.9; goal energy -20% / 0 / +10%; protein 1.8 g/kg (fat loss, muscle gain) or 1.0 (maintenance); fat 30% energy; sat fat max 10%; fibre 30 g; sodium max 2400 mg.
- Only core nutrients seeded (energy, macros, fibre, sugars, sat fat, sodium, Ca, Fe, vit C, B12). Micronutrient targets not implemented.

## Decisions
- Stack: Python + FastAPI backend, React (Vite) frontend, SQLite. (User chose 2026-11-16.)
- Vision/modules/roadmap: see README.md.

## Next steps
1. Ingest CoFID and USDA FDC (confirm versions/licences first); importer scripts in `backend/scripts/`.
2. Frontend: profile form, food search, intake logging, target trace display.
3. Micronutrient targets once reference standard chosen.
4. Roadmap phase 2: BYOK AI provider interface.

## Open questions
- Reference standard for micronutrient targets (UK DRVs vs others)?
- BMR equation (Mifflin-St Jeor vs Henry/Schofield)?
