"""Tool-calling loop. The LLM parses language and explains; numbers come only from tools."""
import json

from . import tools
from .providers import Provider

MAX_STEPS = 6

SYSTEM = """You are NutrAIgent's nutrition assistant. Today is {today}.
Rules:
- NEVER state a nutrient amount, calorie figure or target unless it came from a tool result in this conversation. Do not estimate nutrition from memory.
- To log food: search_foods for each item, pick the best match (prefer raw/plain entries and the source the user names), get_food if you need portion gram weights, then call propose_log_entries IN THE SAME TURN as a short text stating your assumptions (that text is shown to the user; do not call anything after propose_log_entries). Search results already include household portions, so call get_food only if you need more detail. Issue all searches for a message in ONE turn (parallel tool calls). You cannot save entries; the user confirms in the UI. If a portion or food is genuinely unclear, asking the user a short clarifying question is fine (reply with text and no tool call). Otherwise use the database's household portion gram weights or a typical serving and state the assumption; the user can edit grams before confirming.
- Reply in the user's language. Food names in the database are English: translate the user's foods to English search terms (try simpler/alternative terms if a search returns nothing).
- To answer about intake or targets, call get_daily_intake / get_targets. Missing data (null) means unknown, not zero: say so.
- Explain nutrition concepts plainly and briefly. You are not a doctor; for medical conditions suggest consulting a professional.
- Defaults in targets are provisional; mention this if the user relies on them."""


def iter_chat(ctx: tools.Context, provider: Provider, history: list[dict]):
    """Generator of progress events; the last event has type 'done'.

    Events: {"type":"model","step":n} | {"type":"tool","tool":name,"input":{...}} |
            {"type":"tool_done","tool":name,"error":str|None} | {"type":"done","reply","proposals","trace"}
    Ends right after a fully valid propose_log_entries call (the assistant text sent with that call,
    or a fixed summary, is the reply) to save one slow model round trip.
    """
    messages = [{"role": m["role"], "content": m["content"]} for m in history]
    system = SYSTEM.format(today=ctx.today)
    trace = []
    for step in range(1, MAX_STEPS + 1):
        yield {"type": "model", "step": step}
        resp = provider.complete(system, messages, tools.TOOL_SPECS)
        content = resp["content"]
        messages.append({"role": "assistant", "content": content})
        text = "".join(b["text"] for b in content if b["type"] == "text").strip()
        if resp["stop"] != "tool_use":
            yield {"type": "done", "reply": text or "(no reply)", "proposals": ctx.proposals, "trace": trace}
            return
        results, finished = [], False
        for b in content:
            if b["type"] != "tool_use":
                continue
            yield {"type": "tool", "tool": b["name"], "input": b["input"]}
            out = tools.call(ctx, b["name"], b["input"])
            err = out.get("error") if isinstance(out, dict) else None
            trace.append({"tool": b["name"], "input": b["input"], "error": err})
            yield {"type": "tool_done", "tool": b["name"], "error": err}
            if b["name"] == "propose_log_entries" and out.get("proposed") and not out.get("errors"):
                finished = True
            results.append({"type": "tool_result", "tool_use_id": b["id"],
                            "content": json.dumps(out, default=str)})
        if finished:
            n = len(ctx.proposals)
            reply = text or f"Prepared {n} log entr{'y' if n == 1 else 'ies'}. Review the amounts and confirm."
            yield {"type": "done", "reply": reply, "proposals": ctx.proposals, "trace": trace}
            return
        messages.append({"role": "user", "content": results})
    yield {"type": "done", "reply": "Stopped: too many tool steps. Try a simpler request.",
           "proposals": ctx.proposals, "trace": trace}


def run_chat(ctx: tools.Context, provider: Provider, history: list[dict]) -> dict:
    last = None
    for ev in iter_chat(ctx, provider, history):
        last = ev
    return {k: last[k] for k in ("reply", "proposals", "trace")}
