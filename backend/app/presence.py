"""Stop the local server after the last browser tab closes.

Only active when NUTRAIGENT_AUTOSTOP=1 (start.ps1 sets it; -KeepRunning turns it off). Each open page pings
/api/presence/ping every PING_EVERY seconds with a random client id and sends /api/presence/bye on pagehide.
The server exits when no page has pinged within TIMEOUT seconds, or when every page said bye and none came
back within GRACE seconds (a reload sends bye and then pings again). It never exits while a background job runs.
"""
import os
import threading
import time
from collections.abc import Callable

TIMEOUT = 150.0  # background tabs are throttled to about one timer call per minute
GRACE = 5.0      # reload = bye, then a new ping within this window


class Presence:
    def __init__(self, timeout: float = TIMEOUT, grace: float = GRACE):
        self.timeout = timeout
        self.grace = grace
        self.seen: dict[str, float] = {}  # client id -> last ping time
        self.armed = False  # becomes True on the first ping, so starting the server alone never stops it
        self.empty_since: float | None = None
        self.lock = threading.Lock()

    def ping(self, client: str, now: float) -> None:
        with self.lock:
            self.armed = True
            self.seen[client] = now

    def bye(self, client: str) -> None:
        with self.lock:
            self.seen.pop(client, None)

    def should_stop(self, now: float, busy: bool) -> bool:
        with self.lock:
            if not self.armed or busy:
                self.empty_since = None
                return False
            for c in [c for c, t in self.seen.items() if now - t > self.timeout]:
                del self.seen[c]
            if self.seen:
                self.empty_since = None
                return False
            if self.empty_since is None:
                self.empty_since = now
            return now - self.empty_since >= self.grace


def start_watchdog(presence: Presence, busy: Callable[[], bool],
                   clock: Callable[[], float] = time.time, exit_fn: Callable[[int], None] = os._exit) -> None:
    def loop():
        while True:
            time.sleep(1)
            if presence.should_stop(clock(), busy()):
                print("NutrAIgent: no browser page open, stopping server.", flush=True)
                exit_fn(0)

    threading.Thread(target=loop, daemon=True).start()
