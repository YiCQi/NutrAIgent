"""Tool-calling loop. The LLM parses language and explains; numbers come only from tools."""
import json

from . import tools
from .providers import Provider

MAX_STEPS = 6

SYSTEM = """You are NutrAIgent's nutrition assistant. Today is {today}.
Rules:
- NEVER state a nutrient amount, calorie figure or target unless it came from a tool result in this conversation. Do not estimate nutrition from memory.
- To log food: search_foods for each item, pick the best match (prefer raw/plain entries and the source the user names), get_food if you need portion gram weights, then call propose_log_entries. You cannot save entries; the user confirms in the UI. If an amount or food is ambiguous, ask a short question instead of guessing.
- To answer about intake or targets, call get_daily_intake / get_targets. Missing data (null) means unknown, not zero: say so.
- Explain nutrition concepts plainly and briefly. You are not a doctor; for medical conditions suggest consulting a professional.
- Defaults in targets are provisional; mention this if the user relies on them."""


def run_chat(ctx: tools.Context, provider: Provider, history: list[dict]) -> dict:
    messages = [{"role": m["role"], "content": m["content"]} for m in history]
    system = SYSTEM.format(today=ctx.today)
    trace = []
    for _ in range(MAX_STEPS):
        resp = provider.complete(system, messages, tools.TOOL_SPECS)
        content = resp["content"]
        messages.append({"role": "assistant", "content": content})
        if resp["stop"] != "tool_use":
            text = "".join(b["text"] for b in content if b["type"] == "text").strip()
            return {"reply": text or "(no reply)", "proposals": ctx.proposals, "trace": trace}
        results = []
        for b in content:
            if b["type"] != "tool_use":
                continue
            out = tools.call(ctx, b["name"], b["input"])
            trace.append({"tool": b["name"], "input": b["input"],
                          "error": out.get("error") if isinstance(out, dict) else None})
            results.append({"type": "tool_result", "tool_use_id": b["id"],
                            "content": json.dumps(out, default=str)})
        messages.append({"role": "user", "content": results})
    return {"reply": "Stopped: too many tool steps. Try a simpler request.",
            "proposals": ctx.proposals, "trace": trace}
