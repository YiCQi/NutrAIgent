"""Tool-calling loop for questions about intake, targets and nutrition. Numbers come only from tools."""
import json

from . import tools
from .providers import Provider

MAX_STEPS = 6

SYSTEM = """You are NutrAIgent's nutrition assistant. Today is {today}.
Rules:
- NEVER state a nutrient amount, calorie figure or target unless it came from a tool result in this conversation. Do not estimate nutrition from memory.
- Use search_foods / get_food for food facts (database names are English; translate the user's foods), get_daily_intake / get_targets for the user's day and goals. Missing data (null) means unknown, not zero: say so.
- "What should I eat / what am I missing today" requests: call get_nutrient_gaps first. Then search_foods for suitable foods and propose 2-3 concrete options (a title and foods with grams). Call evaluate_meal for EACH option before presenting it, and present only options that cover a short nutrient. Prioritise nutrients marked repeated (short yesterday too). Never add foods that are rich in an over_limit nutrient. Say which nutrients have missing data (unknown) instead of guessing.
- Editing an estimate: if the user corrects an amount (e.g. "only 5 g soy sauce"), re-run evaluate_meal with the new grams instead of recalculating by hand.
- You cannot log food here. If the user wants to log food, tell them to describe what they ate in one message (e.g. "I had two eggs and rice for lunch") and the app will prepare entries to confirm.
- Reply in the user's language. Explain nutrition concepts plainly and briefly. You are not a doctor; for medical conditions suggest consulting a professional.
- Defaults in targets are provisional; mention this if the user relies on them. Asking a short clarifying question is fine."""


def iter_chat(ctx: tools.Context, provider: Provider, history: list[dict], lang: str = "en"):
    """Generator of progress events; the last event has type 'done'.

    Events: {"type":"model","step":n} | {"type":"tool","tool","input"} |
            {"type":"tool_done","tool","error"} | {"type":"done","reply","trace"}
    """
    messages = [{"role": m["role"], "content": m["content"]} for m in history]
    system = SYSTEM.format(today=ctx.today) + ("\nAlways reply in Simplified Chinese." if lang == "zh" else "")
    trace = []
    for step in range(1, MAX_STEPS + 1):
        yield {"type": "model", "step": step}
        resp = provider.complete(system, messages, tools.TOOL_SPECS)
        content = resp["content"]
        messages.append({"role": "assistant", "content": content})
        if resp["stop"] != "tool_use":
            text = "".join(b["text"] for b in content if b["type"] == "text").strip()
            yield {"type": "done", "reply": text or "(no reply)", "trace": trace}
            return
        results = []
        for b in content:
            if b["type"] != "tool_use":
                continue
            yield {"type": "tool", "tool": b["name"], "input": b["input"]}
            out = tools.call(ctx, b["name"], b["input"])
            err = out.get("error") if isinstance(out, dict) else None
            trace.append({"tool": b["name"], "input": b["input"], "error": err})
            yield {"type": "tool_done", "tool": b["name"], "error": err}
            results.append({"type": "tool_result", "tool_use_id": b["id"],
                            "content": json.dumps(out, default=str)})
        messages.append({"role": "user", "content": results})
    yield {"type": "done", "reply": "Stopped: too many tool steps. Try a simpler request.", "trace": trace}
