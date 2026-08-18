from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task, TaskStatus


class TaskRepository:
    """Task persistence on an AsyncSession. The per-request session dependency
    owns the transaction (commit/rollback) — this only ever `flush()`es."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, task: Task) -> None:
        self._session.add(task)
        await self._session.flush()

    async def get_by_id(self, task_id: UUID) -> Task | None:
        return await self._session.get(Task, task_id)

    async def list_tasks(
        self,
        *,
        owner_id: UUID | None,
        status: TaskStatus | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Task], int]:
        # Tenant isolation is enforced by the per-request schema search_path, so
        # "all tasks" here means all tasks of the current organization. owner_id
        # narrows to one member's tasks (the "my tasks" view).
        base = select(Task)
        count_q = select(func.count()).select_from(Task)
        if owner_id is not None:
            base = base.where(Task.owner_id == owner_id)
            count_q = count_q.where(Task.owner_id == owner_id)
        if status is not None:
            base = base.where(Task.status == status.value)
            count_q = count_q.where(Task.status == status.value)

        rows = (
            await self._session.scalars(
                base.order_by(Task.created_at.desc()).limit(limit).offset(offset)
            )
        ).all()
        total = await self._session.scalar(count_q) or 0
        return list(rows), total

    async def update(self, task: Task) -> Task:
        # `task` was loaded via get_by_id in the same session (the service loads
        # before it mutates), so it is already tracked — flushing persists the
        # in-place changes. No re-fetch needed.
        await self._session.flush()
        return task

    async def delete(self, task_id: UUID) -> None:
        await self._session.execute(delete(Task).where(Task.id == task_id))
        await self._session.flush()
