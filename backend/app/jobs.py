"""Run a generator of events in a background thread and stream them as NDJSON.

If the HTTP client disconnects (page switch, reload) the worker keeps running to completion,
so results (chat replies, plans) are still saved. Events after the disconnect are dropped.
"""
import json
import queue
import threading
from collections.abc import Callable, Iterator

from .ai.providers import ProviderError

NL = chr(10)


def stream_in_background(make_events: Callable[[], Iterator[dict]], on_finish: Callable[[], None] | None = None):
    q: queue.Queue = queue.Queue()

    def worker():
        try:
            for ev in make_events():
                q.put(ev)
        except Exception as e:  # keep the stream well-formed for the UI
            msg = str(e) if isinstance(e, ProviderError) else f"internal error: {type(e).__name__}"
            q.put({"type": "error", "message": msg})
        finally:
            if on_finish:
                on_finish()
            q.put(None)

    threading.Thread(target=worker, daemon=True).start()

    def reader():
        while True:
            ev = q.get()
            if ev is None:
                return
            yield json.dumps(ev, default=str) + NL

    return reader()
