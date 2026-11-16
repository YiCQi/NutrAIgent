# HANDOFF

## Status (2026-11-16)
- MVP scaffold done and pushed. Backend: 4 pytest tests pass. Frontend: `npm run build` OK. Frontend not run against live backend yet.
- Remote: https://github.com/YiCQi/NutrAIgent. Policy: always commit and push after each task.
- Commit identity (repo-local): YiCQi + GitHub noreply email.

## Phase 2 (AI, BYOK) - built 2026-11-16, NOT yet tested against a real provider
- `backend/app/ai/`: `providers.py` (provider-independent `Provider.complete()`; adapters `anthropic` and `openai_compatible` [OpenAI/OpenRouter/Ollama/LM Studio/etc., base_url configurable]; add new vendors via `REGISTRY`), `tools.py` (deterministic tools: search_foods, get_food, get_targets, get_daily_intake, propose_log_entries), `agent.py` (tool loop, max 6 steps, system prompt forbids stating numbers not from tools).
- NL logging: LLM searches DB and calls `propose_log_entries`; nothing is saved until the user clicks Confirm in the UI (Assistant tab -> POST /api/intake per entry).
- Endpoints: `GET/PUT /api/ai/settings` (key never returned; `api_key` null=keep, ""=clear), `POST /api/ai/chat` (502 with clear message on provider/config errors).
- Settings + API key stored in table `settings` (schema v3) in the local SQLite file, PLAINTEXT. Consider OS keyring later.
- Privacy: chat text and tool results (foods, daily intake/targets) are sent to the configured provider; UI says so.
- 18 tests pass using scripted fake provider + httpx MockTransport. Real-API behaviour (tool-call formats, model names) unverified: needs the user's key. UI Assistant tab renders and settings API verified live; full chat flow not run.
- Live test (2026-11-16, user's KCL OpenAI-compatible endpoint, model `arc:apex`): tool calling works. Chinese meal message -> 6 proposed entries, but took ~45-103 s (6-12 model round trips, ~8 s each). Fixed: empty `tools` array omitted (server 400), prompt now assumes portions instead of asking, replies in user's language, UI shows elapsed timer and editable grams. TODO: stream progress (SSE) or cut steps; faster model.
- Streaming (2026-11-16): `POST /api/ai/chat/stream` (NDJSON events model/tool/tool_done/done/error); `agent.iter_chat` generator; Assistant tab shows progress bar, elapsed seconds and a live step list. Agent ends immediately after a valid `propose_log_entries` (saves a round trip). Search results include 3 portions each, limit 5. User decision: assistant asking clarifying questions is fine (prompt allows it).
- Latency finding: with the user's KCL endpoint (`arc:apex`) the model itself is the bottleneck: single rounds took 8-80 s, full Chinese-meal run 45-190 s, varying run to run. Not fixable in code; use a faster/non-reasoning model if available. Possible: add optional reasoning-effort setting.
- `foods.py` holds shared search/detail logic. `httpx` and `openpyxl` now in pyproject deps.

## Layout
- `backend/` FastAPI. `app/schema.sql` (schema v1), `app/db.py`, `app/engine/targets.py`, `app/engine/analysis.py`, `app/main.py` (routes under `/api`), `tests/`.
- `frontend/` Vite + React; proxies `/api` to 127.0.0.1:8000. Tabs: Log (daily entries + intake vs targets + all totals, remove entry), Foods (word-start token search, food detail with per-100g/for-N-g nutrients, portions picker, log with meal/date), Profile (form, targets, calc trace, provisional warning). Missing data shown as "no data"/"present, amount unknown (N)"; 'trace' labelled. Verified end to end in browser (profile save -> search -> log -> comparison).
- DB path: `~/.nutraigent/nutraigent.db` (override `NUTRAIGENT_DB`).
- Dev servers also in `.claude/launch.json` (backend :8000, frontend :5173). Search: every token must start a word in the food name (`GET /api/foods?q=`). Food detail now returns `portions` and nutrient `qualifier`.
- Run: `cd backend && .venv/Scripts/python -m uvicorn app.main:app --reload`; `cd frontend && npm run dev`.

## PROVISIONAL defaults (unconfirmed, flagged in API trace `provisional: true`)
- BMR Mifflin-St Jeor; PAL 1.2-1.9; goal energy -20% / 0 / +10%; protein 1.8 g/kg (fat loss, muscle gain) or 1.0 (maintenance); fat 30% energy; sat fat max 10%; fibre 30 g; sodium max 2400 mg.
- Only core nutrients seeded (energy, macros, fibre, sugars, sat fat, sodium, Ca, Fe, vit C, B12). Micronutrient targets not implemented.

## Decisions
- Stack: Python + FastAPI backend, React (Vite) frontend, SQLite. (User chose 2026-11-16.)
- Vision/modules/roadmap: see README.md.

## Importer status
- SR Legacy imported: 7793 foods, 89,435 nutrient values, 14,449 portions (12 core nutrients only). Spot check: raw whole egg 143 kcal, 12.56 g protein (matches USDA). Local DB `backend/data/nutraigent.db` (gitignored); run `python scripts/import_usda_sr_legacy.py --db <path>`. Default DB `~/.nutraigent/nutraigent.db` IS populated (all 3 sources, 11,104 foods; test profile/log entries removed).
- `state` derived from 'raw'/'cooked' words only (1386 raw, 1778 cooked, 4629 unknown). `edible_portion_pct` NULL for SR (not in CSV).
- Only 12 nutrients mapped; extend `NUTRIENT_MAP` + `CORE_NUTRIENTS` in `app/db.py` for more vitamins/minerals.

- CoFID imported: 2887 foods, 33,754 value rows (1,927 'Tr', 1,246 'N'). Rules: 'Tr' -> value 0.0 + `qualifier='trace'`; 'N' -> NULL + `qualifier='N'` (counts as missing); blank -> no row. Schema bumped to v2 (`food_nutrients.qualifier`, auto-migrated in `init_db`). Analysis engine does not yet surface `trace` qualifier (trace counts as 0).
- CoFID choices: fibre = AOAC fibre; sat fat = per 100 g food; `food_group` = CoFID group code (e.g. DR, DG; names not in workbook, see user guide PDF); `edible_portion_pct` = Edible proportion x100 ('N' -> NULL; 2853/2887 set); sheets joined on (code, name) because code 13-669 is duplicated in source (2nd stored `13-669#2`). Alcoholic drinks are per 100 ml, not converted (unit caveat).
- Local DB `backend/data/nutraigent.db` now holds SR Legacy + CoFID. 6 tests pass.

- Foundation imported: 424 foods, 3,498 values, 394 portions. Energy = 1008 > 2048 (Atwater specific) > 2047 (general) since Foundation rarely reports 1008. Fibre 1079 > 2033; sugars 1063 > 2000; carbs 1005 > 1050. 10 foods had slightly negative 'carbohydrate by difference' in source (min -0.705 g); clamped to 0.0 (stat `clamped_negative`); any other negative aborts. Foundation has duplicate-name foods (e.g. two 'Hummus, commercial' samples) distinguished by fdcId.
- Local DB `backend/data/nutraigent.db` now holds SR Legacy + CoFID + Foundation (11,104 foods). 7 tests pass.
- Cross-source duplicates (same food in CoFID/SR/Foundation) are NOT merged; food search will show all.

## Data downloaded (2026-11-16, in `backend/data/raw/`, gitignored)
- `cofid/CoFID_2021.xlsx` (GOV.UK, OGL v3.0, edition 19 Mar 2021). Sheets `1.2 Factors` (edible proportion), `1.3 Proximates`, `1.4 Inorganics`, `1.5 Vitamins`, ... Header rows: names, then nutrient tag (e.g. WATER), then name; data starts row 4. Column A = Food Code, B = Food Name, Group, etc. Blank/'N' cells need care: confirm CoFID missing-value conventions (e.g. 'N', 'Tr') in user guide before import.
- `usda_sr_legacy/` (FDC SR Legacy CSV, 2018-04, CC0): COMPLETE (food, food_nutrient, nutrient, food_portion, measure_unit...).
- `usda_foundation/` (FDC Foundation CSV 2026-10-29): INCOMPLETE, ignore (no food/food_nutrient tables; published archive is truncated).
- `usda_foundation_json/FoodData_Central_foundation_food_json_2026-10-29.json` (CC0, 9.3 MB): COMPLETE. Top key `FoundationFoods`, 424 foods; per food: `fdcId`, `description`, `foodNutrients`, `foodPortions`, `foodCategory`, `nutrientConversionFactors`. Use this for Foundation Foods. Open files with `encoding='utf-8'` (Windows default is gbk).
- Python: `openpyxl` installed in backend venv only (not yet in pyproject).

## Next steps
1. Importers: SR Legacy DONE (`backend/scripts/import_usda_sr_legacy.py`). CoFID DONE (`backend/scripts/import_cofid.py`). Foundation DONE (`backend/scripts/import_usda_foundation.py`). All 3 importers done. Also TODO: populate default DB, add `openpyxl` to pyproject, merge/dedupe same food across sources (none yet).
2. Frontend polish: edit logged grams, multi-day view, surface 'trace' flag in analysis, unit caveat for CoFID per-100ml drinks, merge/dedupe foods across sources.
3. Micronutrient targets once reference standard chosen.
4. Test Phase 2 with a real key (Anthropic and an OpenAI-compatible endpoint); tune system prompt; add Gemini adapter if wanted; streaming responses; keyring for key storage; persist chat history (optional).
5. Phase 3: meal planning.

## Open questions
- Reference standard for micronutrient targets (UK DRVs vs others)?
- BMR equation (Mifflin-St Jeor vs Henry/Schofield)?
