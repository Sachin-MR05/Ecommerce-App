from __future__ import annotations

import json
import threading
from abc import ABC, abstractmethod
from pathlib import Path

from audit.audit_event import AuditEvent


class AuditRepository(ABC):
    """Append-only persistence for AuditEvents.

    This Python service (merchant-agent-core) has no database of its own
    today - all commerce/persistence state lives behind the Java Tool
    Layer (see README.md: "it never touches ... a database"). This
    abstraction lets the Audit Service be wired against whatever storage
    is appropriate for a given deployment (in-memory for tests, a JSONL
    file for a single-process dev/staging run, or - if/when this service
    gains its own database, or an `audit` tool is exposed on the Java Tool
    Layer - a real repository implementation) without any caller-facing
    change. Implementations must never overwrite or mutate a previously
    appended event.
    """

    @abstractmethod
    def append(self, event: AuditEvent) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_by_transaction(self, transaction_id: str) -> list[AuditEvent]:
        raise NotImplementedError

    @abstractmethod
    def get_by_request(self, request_id: str) -> list[AuditEvent]:
        raise NotImplementedError


class InMemoryAuditRepository(AuditRepository):
    """Process-local, append-only audit store. Default for tests and for
    development when no durable audit trail is required."""

    def __init__(self):
        self._events: list[AuditEvent] = []
        self._lock = threading.Lock()

    def append(self, event: AuditEvent) -> None:
        with self._lock:
            self._events.append(event)

    def get_by_transaction(self, transaction_id: str) -> list[AuditEvent]:
        with self._lock:
            return [e for e in self._events if e.transaction_id == transaction_id]

    def get_by_request(self, request_id: str) -> list[AuditEvent]:
        with self._lock:
            return [e for e in self._events if e.request_id == request_id]


class JsonlAuditRepository(AuditRepository):
    """Append-only audit store backed by a JSON-lines file - one JSON
    object per line, never rewritten in place. Suitable for a single
    instance of this service; a multi-instance deployment should back
    this interface with a shared database instead (swap the
    implementation, not the AuditService/AuditRepository contract)."""

    def __init__(self, path: str | Path):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def append(self, event: AuditEvent) -> None:
        line = event.model_dump_json()
        with self._lock:
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")

    def get_by_transaction(self, transaction_id: str) -> list[AuditEvent]:
        return [e for e in self._read_all() if e.transaction_id == transaction_id]

    def get_by_request(self, request_id: str) -> list[AuditEvent]:
        return [e for e in self._read_all() if e.request_id == request_id]

    def _read_all(self) -> list[AuditEvent]:
        if not self._path.exists():
            return []
        events: list[AuditEvent] = []
        with self._lock:
            with self._path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    events.append(AuditEvent.model_validate(json.loads(line)))
        return events
