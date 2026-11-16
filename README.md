# NutrAIgent

Local-first, AI-powered personal nutrition management. Evidence-based targets, transparent calculations, adaptive meal planning. Health data stays on your machine.

## Run
Double-click `start.bat` (or `.\start.ps1`): serves the app at http://127.0.0.1:8000. `.\start.ps1 -Dev` for hot-reload development.

## Modules
- **A. Nutrition profile**: age, sex, height, weight, activity, goals (muscle gain / fat loss / maintenance) -> energy and nutrient targets.
- **B. Food database**: SQLite food-nutrient tables from UK CoFID and USDA FoodData Central. Units, serving sizes, edible portions, raw/cooked state, sources. Zero vs missing distinguished.
- **C. Analysis engine**: daily intake vs targets; deficiencies, excesses, imbalances; transparent math.
- **D. AI assistant**: BYOK, provider-independent. Natural-language logging and Q&A. LLM parses and explains; it never invents nutrient values.
- **E. Meal planning**: daily/weekly plans, substitutions, leftovers, adaptation to actual intake.

## Architecture
- Backend: Python + FastAPI, SQLite, deterministic nutrition engine.
- Frontend: React (Vite), served locally. Desktop wrapper optional later.
- AI: provider-agnostic interface, user-supplied API keys stored locally.
- Deterministic calculation is strictly separated from AI reasoning.

## Roadmap
1. MVP: profile, food DB, targets, daily intake tracking.
2. AI: BYOK, NL food logging, Q&A.
3. Meal planning: weekly plans, optimisation, substitutions.
4. Advanced: trends, adaptive recommendations.

## Principles
Scientific accuracy over AI assumptions. Traceable data sources. Local-first privacy. Modular design.
