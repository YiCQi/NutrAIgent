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

## Importer status
- SR Legacy imported: 7793 foods, 89,435 nutrient values, 14,449 portions (12 core nutrients only). Spot check: raw whole egg 143 kcal, 12.56 g protein (matches USDA). Local DB `backend/data/nutraigent.db` (gitignored); run `python scripts/import_usda_sr_legacy.py --db <path>`. Default DB is `~/.nutraigent/nutraigent.db`, which is NOT yet populated.
- `state` derived from 'raw'/'cooked' words only (1386 raw, 1778 cooked, 4629 unknown). `edible_portion_pct` NULL for SR (not in CSV).
- Only 12 nutrients mapped; extend `NUTRIENT_MAP` + `CORE_NUTRIENTS` in `app/db.py` for more vitamins/minerals.

## Data downloaded (2026-11-16, in `backend/data/raw/`, gitignored)
- `cofid/CoFID_2021.xlsx` (GOV.UK, OGL v3.0, edition 19 Mar 2021). Sheets `1.2 Factors` (edible proportion), `1.3 Proximates`, `1.4 Inorganics`, `1.5 Vitamins`, ... Header rows: names, then nutrient tag (e.g. WATER), then name; data starts row 4. Column A = Food Code, B = Food Name, Group, etc. Blank/'N' cells need care: confirm CoFID missing-value conventions (e.g. 'N', 'Tr') in user guide before import.
- `usda_sr_legacy/` (FDC SR Legacy CSV, 2018-04, CC0): COMPLETE (food, food_nutrient, nutrient, food_portion, measure_unit...).
- `usda_foundation/` (FDC Foundation CSV 2026-10-29): INCOMPLETE, ignore (no food/food_nutrient tables; published archive is truncated).
- `usda_foundation_json/FoodData_Central_foundation_food_json_2026-10-29.json` (CC0, 9.3 MB): COMPLETE. Top key `FoundationFoods`, 424 foods; per food: `fdcId`, `description`, `foodNutrients`, `foodPortions`, `foodCategory`, `nutrientConversionFactors`. Use this for Foundation Foods. Open files with `encoding='utf-8'` (Windows default is gbk).
- Python: `openpyxl` installed in backend venv only (not yet in pyproject).

## Next steps
1. Importers: SR Legacy DONE (`backend/scripts/import_usda_sr_legacy.py`). TODO: CoFID, then Foundation Foods JSON. Reuse the nutrient-code mapping approach and zero-vs-missing rules (docstring in SR script).
2. Frontend: profile form, food search, intake logging, target trace display.
3. Micronutrient targets once reference standard chosen.
4. Roadmap phase 2: BYOK AI provider interface.

## Open questions
- Reference standard for micronutrient targets (UK DRVs vs others)?
- BMR equation (Mifflin-St Jeor vs Henry/Schofield)?
