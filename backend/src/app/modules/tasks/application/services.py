from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from app.modules.tasks.application.dtos import (
    CreateTaskCommand,
    ListTasksQuery,
    Page,
    UpdateTaskCommand,
)
from app.modules.tasks.domain.entities import Task
from app.modules.tasks.domain.errors import TaskNotFoundError
from app.modules.tasks.domain.ports import TaskRepository


def _utc_now() -> datetime:
    return datetime.now(UTC)


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

    async def get(self, *, owner_id: UUID, task_id: UUID) -> Task:
        task = await self.repo.get_by_id(task_id)
        if task is None or task.owner_id != owner_id:
            # Don't leak existence of other users' tasks within the tenant.
            raise TaskNotFoundError(f"Task {task_id} not found")
        return task

    async def list(self, *, owner_id: UUID, query: ListTasksQuery) -> Page:
        items, total = await self.repo.list_for_owner(
            owner_id=owner_id,
            status=query.status,
            limit=query.limit,
            offset=query.offset,
        )
        return Page(items=items, total=total, limit=query.limit, offset=query.offset)

    async def update(
        self, *, owner_id: UUID, task_id: UUID, command: UpdateTaskCommand
    ) -> Task:
        task = await self.get(owner_id=owner_id, task_id=task_id)
        task.update_details(
            title=command.title,
            description=command.description if command.description_set else None,  # type: ignore[arg-type]
            set_description=command.description_set,
            priority=command.priority,
            due_at=command.due_at,
            set_due_at=command.due_at_set,
            now=self.clock(),
        )
        await self.repo.update(task)
        return task

    async def start(self, *, owner_id: UUID, task_id: UUID) -> Task:
        task = await self.get(owner_id=owner_id, task_id=task_id)
        task.start(now=self.clock())
        await self.repo.update(task)
        return task

    async def complete(self, *, owner_id: UUID, task_id: UUID) -> Task:
        task = await self.get(owner_id=owner_id, task_id=task_id)
        task.complete(now=self.clock())
        await self.repo.update(task)
        return task

    async def cancel(self, *, owner_id: UUID, task_id: UUID) -> Task:
        task = await self.get(owner_id=owner_id, task_id=task_id)
        task.cancel(now=self.clock())
        await self.repo.update(task)
        return task

    async def delete(self, *, owner_id: UUID, task_id: UUID) -> None:
        # `get` enforces ownership; if it raises, we never reach `delete`.
        task = await self.get(owner_id=owner_id, task_id=task_id)
        await self.repo.delete(task.id)
