"""Deterministic audit event recording."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from project_recovery_council.contracts import AuditEvent, EvidenceReference


class DeterministicClock:
    """Injectable clock that advances by a fixed step on each read."""

    def __init__(
        self,
        start_at: datetime | None = None,
        step: timedelta = timedelta(seconds=1),
    ) -> None:
        base = start_at or datetime(2026, 6, 29, 16, 0, 0, tzinfo=UTC)
        if base.tzinfo is None:
            base = base.replace(tzinfo=UTC)
        self._current = base
        self._step = step

    def now(self) -> datetime:
        current = self._current
        self._current = self._current + self._step
        return current


class AuditRecorder:
    """Append-only ordered audit event builder."""

    def __init__(
        self,
        case_id: str,
        clock: DeterministicClock | None = None,
        existing_events: list[AuditEvent] | None = None,
    ) -> None:
        self.case_id = case_id
        self.clock = clock or DeterministicClock()
        self._events: list[AuditEvent] = list(existing_events or [])

    @property
    def events(self) -> list[AuditEvent]:
        return list(self._events)

    def record(
        self,
        event_type: str,
        actor: str,
        summary: str,
        *,
        evidence: list[EvidenceReference] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        sequence = len(self._events) + 1
        event = AuditEvent(
            event_id=f"AUDIT-{sequence:04d}",
            sequence=sequence,
            case_id=self.case_id,
            occurred_at=self.clock.now(),
            event_type=event_type,
            actor=actor,
            action=event_type,
            summary=summary,
            evidence=evidence or [],
            metadata=metadata or {},
        )
        self._events.append(event)
        return event

    def model_timestamp(self) -> datetime:
        """Return a deterministic timestamp for non-audit model fields."""

        return self.clock.now()
