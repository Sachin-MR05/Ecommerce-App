from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Fixed vocabulary of WebSocket event names. The dashboard switches on
# these - keep in sync with monitoring-dashboard/src/api/types.ts.
EVENT_TRANSACTION_UPDATED = "transaction.updated"
EVENT_SERVICE_HEALTH_CHANGED = "service.health_changed"
EVENT_FAILURE_CREATED = "failure.created"
EVENT_ALERT_CREATED = "alert.created"
EVENT_ALERT_RESOLVED = "alert.resolved"
EVENT_AUDIT_EVENT = "audit.event"
EVENT_METRICS_UPDATED = "metrics.updated"


class MonitoringEventBus:
    """In-process pub-sub broadcasting monitoring events to every connected
    WebSocket client.

    This is intentionally the *only* thing that knows about WebSocket
    connections - MonitoringStore/HealthRegistry publish plain dicts here
    and never touch a WebSocket object directly, so they stay testable
    without a running server.

    Single-process only (matches every other in-memory store in this
    codebase, e.g. InMemoryAuditRepository) - a multi-instance deployment
    would back this with a shared pub-sub (Redis, etc.) behind the same
    publish()/subscribe() seam.
    """

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()
        self._lock = asyncio.Lock()

    async def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        async with self._lock:
            self._subscribers.add(queue)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue) -> None:
        async with self._lock:
            self._subscribers.discard(queue)

    async def publish(self, event: str, data: dict[str, Any]) -> None:
        message = {"event": event, "data": data}
        async with self._lock:
            subscribers = list(self._subscribers)
        for queue in subscribers:
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                logger.warning("Monitoring WS subscriber queue full; dropping event %s", event)

    def publish_threadsafe(self, loop: asyncio.AbstractEventLoop, event: str, data: dict[str, Any]) -> None:
        """Publish from a synchronous context (e.g. an AuditService
        listener, which is called from ordinary request-handling code, not
        a coroutine) by scheduling the coroutine onto the running loop."""
        asyncio.run_coroutine_threadsafe(self.publish(event, data), loop)
