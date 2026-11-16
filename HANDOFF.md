# HANDOFF

## Status (2026-11-16)
- Repo bootstrapped. README and HANDOFF only. No code yet.
- Remote: https://github.com/YiCQi/NutrAIgent (was empty). Policy: always commit and push after each task.
- Commit identity (repo-local): YiCQi + GitHub noreply email.

## Decisions
- Stack: Python + FastAPI backend, React (Vite) frontend, SQLite. (User chose 2026-11-16.)
- Vision/modules/roadmap: see README.md.

## Next steps
1. Scaffold `backend/` (FastAPI, SQLite, pytest) and `frontend/` (Vite React).
2. Design DB schema: foods, nutrients, food_nutrients (value NULL = missing, 0 = true zero), sources, portions, users, intake_log.
3. Ingest CoFID and USDA FDC (confirm dataset versions/licences first).
4. Targets engine (BMR/TDEE, macro and micronutrient targets; confirm reference standard, e.g. UK SACN/DRV vs EFSA/NASEM).
5. Daily intake tracking + analysis.

## Open questions
- Reference standard for micronutrient targets (UK DRVs vs others)?
- BMR equation (Mifflin-St Jeor vs Henry/Schofield)?
