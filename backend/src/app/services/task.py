from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import NamedTuple
from uuid import UUID

from app.core.errors import TaskAccessDeniedError, TaskNotFoundError
from app.models.task import Task, TaskPriority, TaskStatus
from app.repositories.task import TaskRepository


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True, kw_only=True)
class CreateTaskCommand:
    title: str
    description: str | None = None
    priority: TaskPriority = TaskPriority.MEDIUM
    due_at: datetime | None = None

@dataclass(slots=True, kw_only=True)
class UpdateTaskCommand:
    title: str | None = None
    description: str | None = None
    description_set: bool = False
    priority: TaskPriority | None = None
    due_at: datetime | None = None
    due_at_set: bool = False


@dataclass(slots=True, kw_only=True)
class ListTasksQuery:
    status: TaskStatus | None = None
    limit: int = 20
    offset: int = 0


class Page(NamedTuple):
    items: list[Task]
    total: int
    limit: int
    offset: int


# --- Service ----------------------------------------------------------------


@dataclass(slots=True)
class TaskService:
    repo: TaskRepository
    clock: Callable[[], datetime] = field(default=_utc_now)

    async def create(self, *, owner_id: UUID, command: CreateTaskCommand) -> Task:
        task = Task.create(
            owner_id=owner_id,
            title=command.title,
            description=command.description,
            priority=command.priority,
            due_at=command.due_at,
            now=self.clock(),
        )
        await self.repo.add(task)
        return task

    async def get(self, *, task_id: UUID) -> Task:
        """Org-wide read: any member of the organization may view any task."""
        task = await self.repo.get_by_id(task_id)
        if task is None:
            raise TaskNotFoundError(f"Task {task_id} not found")
        return task

    async def list(self, *, query: ListTasksQuery, owner_id: UUID | None = None) -> Page:
        """List org tasks. owner_id=None → all org tasks; set it for "my tasks"."""
        items, total = await self.repo.list_tasks(
            owner_id=owner_id,
            status=query.status,
            limit=query.limit,
            offset=query.offset,
        )
        return Page(items=items, total=total, limit=query.limit, offset=query.offset)

    async def update(
        self, *, task_id: UUID, actor_id: UUID, can_manage_any: bool, command: UpdateTaskCommand
    ) -> Task:
        task = await self._load_for_write(task_id, actor_id, can_manage_any)
        task.update_details(
            title=command.title,
            description=command.description if command.description_set else None,
            set_description=command.description_set,
            priority=command.priority,
            due_at=command.due_at,
            set_due_at=command.due_at_set,
            now=self.clock(),
        )
        await self.repo.update(task)
        return task

    async def start(self, *, task_id: UUID, actor_id: UUID, can_manage_any: bool) -> Task:
        task = await self._load_for_write(task_id, actor_id, can_manage_any)
        task.start(now=self.clock())
        await self.repo.update(task)
        return task

    async def complete(self, *, task_id: UUID, actor_id: UUID, can_manage_any: bool) -> Task:
        task = await self._load_for_write(task_id, actor_id, can_manage_any)
        task.complete(now=self.clock())
        await self.repo.update(task)
        return task

    async def cancel(self, *, task_id: UUID, actor_id: UUID, can_manage_any: bool) -> Task:
        task = await self._load_for_write(task_id, actor_id, can_manage_any)
        task.cancel(now=self.clock())
        await self.repo.update(task)
        return task

    async def delete(self, *, task_id: UUID, actor_id: UUID, can_manage_any: bool) -> None:
        task = await self._load_for_write(task_id, actor_id, can_manage_any)
        await self.repo.delete(task.id)

    async def _load_for_write(
        self, task_id: UUID, actor_id: UUID, can_manage_any: bool
    ) -> Task:
        """Load a task and enforce write access: owner, or an org/platform admin."""
        task = await self.repo.get_by_id(task_id)
        if task is None:
            raise TaskNotFoundError(f"Task {task_id} not found")
        if task.owner_id != actor_id and not can_manage_any:
            raise TaskAccessDeniedError("Only the task owner or a tenant admin can modify it")
        return task
