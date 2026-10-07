"""Bounded local business scans. No provider requests, sends or statutory scheduler."""

import logging
import threading

logger = logging.getLogger("gstshield")


class ActionMonitor:
    def __init__(self, actions, passports=None):
        self.actions = actions
        self.passports = passports
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.run, name="gstshield-actions", daemon=True)
        self.cursor = ""

    def tick(self):
        with self.actions.store.transaction(write=False) as connection:
            row = connection.execute(
                "SELECT id FROM workspaces WHERE id>? ORDER BY id LIMIT 1", (self.cursor,)
            ).fetchone()
            if row is None:
                row = connection.execute("SELECT id FROM workspaces ORDER BY id LIMIT 1").fetchone()
        if row is not None:
            self.cursor = row["id"]
            self.actions.refresh(row["id"])
            if self.passports is not None:
                self.passports.scan(row["id"])

    def start(self):
        # Synchronous bounded catch-up before readiness; the thread rotates other workspaces.
        self.tick()
        self.thread.start()

    def run(self):
        while not self.stop_event.wait(self.actions.settings.automation_interval_seconds):
            try:
                self.tick()
            except Exception as exc:
                logger.error("Action monitor failure exception_type=%s", type(exc).__name__)

    def close(self):
        self.stop_event.set()
        if self.thread.is_alive():
            self.thread.join(timeout=10)
        if self.thread.is_alive():
            from app.errors import StorageError

            raise StorageError("Local action monitor did not stop; preserve storage.")
