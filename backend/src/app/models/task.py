"""Task: the single representation of a task — SQLAlchemy row + behaviour.

Tenant-scoped: lives in `tenant_<slug>` via the current search_path, so there is
deliberately no `schema=` override. Factory / transition methods enforce the
business invariants (state machine, field validation) directly on the row.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.errors import TaskTransitionError, TaskValidationError


class TaskStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"


class TaskPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


TITLE_MAX = 200
DESCRIPTION_MAX = 4_000


def _now() -> datetime:
    return datetime.now(UTC)


def _validate_title(title: str) -> str:
    title = title.strip()
    if not title:
        raise TaskValidationError("Task title cannot be empty")
    if len(title) > TITLE_MAX:
        raise TaskValidationError(f"Task title exceeds {TITLE_MAX} characters")
    return title


def _validate_description(description: str | None) -> str | None:
    if description is None:
        return None
    if len(description) > DESCRIPTION_MAX:
        raise TaskValidationError(f"Task description exceeds {DESCRIPTION_MAX} characters")
    return description


def _validate_due_at(due_at: datetime | None) -> datetime | None:
    if due_at is None:
        return None
    if due_at.tzinfo is None:
        raise TaskValidationError("due_at must be timezone-aware")
    return due_at


class Task(Base):
    """Tenant-scoped row. Lives in `tenant_<slug>` via current search_path —
    no `schema=` override here on purpose."""

    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'in_progress', 'done', 'cancelled')",
            name="tasks_status_chk",
        ),
        CheckConstraint(
            "priority IN ('low', 'medium', 'high')", name="tasks_priority_chk"
        ),
        CheckConstraint(
            "char_length(title) BETWEEN 1 AND 200", name="tasks_title_len_chk"
        ),
        Index("ix_tasks_owner_status", "owner_id", "status"),
        Index("ix_tasks_owner_created_at", "owner_id", "created_at"),
        Index("ix_tasks_due_at", "due_at"),
        {"info": {"tenant_scope": "tenant"}},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # status / priority are stored as plain strings (matches the CHECK constraints and
    # existing schema). TaskStatus / TaskPriority are StrEnum, so assigning an enum
    # persists its value and `row.status == TaskStatus.DONE` / set-membership both work.
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="open")
    priority: Mapped[str] = mapped_column(String(20), nullable=False, server_default="medium")
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    @classmethod
    def create(
        cls,
        *,
        owner_id: uuid.UUID,
        title: str,
        description: str | None = None,
        priority: TaskPriority = TaskPriority.MEDIUM,
        due_at: datetime | None = None,
        now: datetime | None = None,
    ) -> Task:
        ts = now or _now()
        # id / timestamps are set app-side (not left to the server defaults) so a
        # freshly created, not-yet-flushed instance is fully readable — the repo just
        # persists it as-is.
        return cls(
            id=uuid.uuid4(),
            owner_id=owner_id,
            title=_validate_title(title),
            description=_validate_description(description),
            status=TaskStatus.OPEN,
            priority=priority,
            due_at=_validate_due_at(due_at),
            created_at=ts,
            updated_at=ts,
            completed_at=None,
        )

    def update_details(
        self,
        *,
        title: str | None = None,
        description: str | None = None,
        set_description: bool = False,
        priority: TaskPriority | None = None,
        due_at: datetime | None = None,
        set_due_at: bool = False,
        now: datetime | None = None,
    ) -> None:
        """Partial update.

        `title` / `priority` are touched only when not None. For nullable fields
        (`description`, `due_at`), the caller MUST set the matching `set_*` flag
        to apply the value — that distinguishes "leave alone" from "set to null".
        """
        if self.status in {TaskStatus.DONE, TaskStatus.CANCELLED}:
            raise TaskTransitionError(
                f"Cannot edit a task in status {self.status!s}",
            )
        if title is not None:
            self.title = _validate_title(title)
        if set_description:
            self.description = _validate_description(description)
        if priority is not None:
            self.priority = priority
        if set_due_at:
            self.due_at = _validate_due_at(due_at)
        self.updated_at = now or _now()

    def start(self, *, now: datetime | None = None) -> None:
        if self.status != TaskStatus.OPEN:
            raise TaskTransitionError(
                f"Only OPEN tasks can be started (was {self.status!s})",
            )
        self.status = TaskStatus.IN_PROGRESS
        self.updated_at = now or _now()

    def complete(self, *, now: datetime | None = None) -> None:
        if self.status in {TaskStatus.DONE, TaskStatus.CANCELLED}:
            raise TaskTransitionError(
                f"Cannot complete a task in status {self.status!s}",
            )
        ts = now or _now()
        self.status = TaskStatus.DONE
        self.completed_at = ts
        self.updated_at = ts

    def cancel(self, *, now: datetime | None = None) -> None:
        if self.status in {TaskStatus.DONE, TaskStatus.CANCELLED}:
            raise TaskTransitionError(
                f"Cannot cancel a task in status {self.status!s}",
            )
        self.status = TaskStatus.CANCELLED
        self.updated_at = now or _now()
