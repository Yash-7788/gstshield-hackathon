"""One bounded local channel loop; no automatic resend of an ambiguous transmission."""

import logging
import threading

from app.errors import StorageError
from app.services.whatsapp_commands import WhatsAppCommands

logger = logging.getLogger("gstshield")


class WhatsAppWorker:
    def __init__(self, channel):
        self.channel = channel
        self.commands = WhatsAppCommands(channel)
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.run, name="gstshield-whatsapp", daemon=True)
        self.ticks = 0

    def start(self):
        with self.channel.store.transaction() as connection:
            self.channel.recover(connection)
        self.thread.start()

    def tick(self):
        # Only this loop processes channel effects. A preceding failed tick is no longer in flight.
        with self.channel.store.transaction() as connection:
            self.channel.recover(connection)
        self.commands.process_one()
        self.ticks += 1
        if self.ticks % 10 == 0:
            self.commands.watches()
            self.commands.alerts()
        if not self.stop_event.is_set():
            self.channel.send_one()

    def run(self):
        while not self.stop_event.wait(0.5):
            try:
                self.tick()
            except Exception as exc:
                logger.error("Channel worker failure exception_type=%s", type(exc).__name__)

    def close(self):
        self.stop_event.set()
        if self.thread.is_alive():
            self.thread.join(
                timeout=float(
                    self.channel.settings.http_connect_timeout_seconds
                    + self.channel.settings.http_read_timeout_seconds
                    + self.channel.settings.http_write_timeout_seconds
                )
                + 5
            )
        if self.thread.is_alive():
            raise StorageError("Channel worker did not stop; preserve storage.")
