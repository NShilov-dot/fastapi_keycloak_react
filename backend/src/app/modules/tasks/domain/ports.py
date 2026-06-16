from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.modules.tasks.domain.entities import Task, TaskStatus


class TaskRepository(Protocol):
    """Port for task persistence. Implemented in infrastructure layer."""

    async def add(self, task: Task) -> None: ...

    async def get_by_id(self, task_id: UUID) -> Task | None: ...

    async def list_for_owner(
        self,
        *,
        owner_id: UUID,
        status: TaskStatus | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Task], int]: ...

    async def update(self, task: Task) -> None: ...

    async def delete(self, task_id: UUID) -> None: ...
