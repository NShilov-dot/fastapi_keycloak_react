"""Service-level tests with an in-memory fake repository.

Verifies cross-cutting behaviours that the domain entity alone can't:
- ownership enforcement (other-owner reads return 404, not 403)
- partial update wiring (`*_set` flags from the request shape)
- transitions go through the repo
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.modules.tasks.application.dtos import (
    CreateTaskCommand,
    ListTasksQuery,
    UpdateTaskCommand,
)
from app.modules.tasks.application.services import TaskService
from app.modules.tasks.domain.entities import Task, TaskPriority, TaskStatus
from app.modules.tasks.domain.errors import TaskNotFoundError


class FakeRepo:
    def __init__(self) -> None:
        self._by_id: dict[UUID, Task] = {}

    async def add(self, task: Task) -> None:
        self._by_id[task.id] = task

    async def get_by_id(self, task_id: UUID) -> Task | None:
        return self._by_id.get(task_id)

    async def list_for_owner(
        self,
        *,
        owner_id: UUID,
        status: TaskStatus | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Task], int]:
        rows = [t for t in self._by_id.values() if t.owner_id == owner_id]
        if status is not None:
            rows = [t for t in rows if t.status == status]
        rows.sort(key=lambda t: t.created_at, reverse=True)
        return rows[offset : offset + limit], len(rows)

    async def update(self, task: Task) -> Task:
        self._by_id[task.id] = task
        return task

    async def delete(self, task_id: UUID) -> None:
        self._by_id.pop(task_id, None)


@pytest.fixture
def repo() -> FakeRepo:
    return FakeRepo()


@pytest.fixture
def service(repo: FakeRepo) -> TaskService:
    return TaskService(repo=repo, clock=lambda: datetime(2026, 6, 16, 12, 0, tzinfo=UTC))


@pytest.mark.asyncio
async def test_create_persists(service: TaskService, repo: FakeRepo) -> None:
    owner = uuid4()
    task = await service.create(
        owner_id=owner, command=CreateTaskCommand(title="ship")
    )
    assert await repo.get_by_id(task.id) is not None
    assert task.owner_id == owner


@pytest.mark.asyncio
async def test_other_owners_task_is_404_not_403(service: TaskService) -> None:
    alice, bob = uuid4(), uuid4()
    task = await service.create(owner_id=alice, command=CreateTaskCommand(title="x"))
    with pytest.raises(TaskNotFoundError):
        await service.get(owner_id=bob, task_id=task.id)


@pytest.mark.asyncio
async def test_list_filters_by_owner_and_status(service: TaskService) -> None:
    alice = uuid4()
    t1 = await service.create(owner_id=alice, command=CreateTaskCommand(title="a"))
    await service.create(owner_id=alice, command=CreateTaskCommand(title="b"))
    await service.complete(owner_id=alice, task_id=t1.id)

    page = await service.list(
        owner_id=alice, query=ListTasksQuery(status=TaskStatus.OPEN)
    )
    assert page.total == 1
    assert page.items[0].status is TaskStatus.OPEN


@pytest.mark.asyncio
async def test_update_clear_description(service: TaskService) -> None:
    alice = uuid4()
    task = await service.create(
        owner_id=alice,
        command=CreateTaskCommand(title="x", description="initial"),
    )
    updated = await service.update(
        owner_id=alice,
        task_id=task.id,
        command=UpdateTaskCommand(description=None, description_set=True),
    )
    assert updated.description is None


@pytest.mark.asyncio
async def test_update_preserves_description_when_not_set(service: TaskService) -> None:
    alice = uuid4()
    task = await service.create(
        owner_id=alice,
        command=CreateTaskCommand(title="x", description="keep"),
    )
    updated = await service.update(
        owner_id=alice,
        task_id=task.id,
        command=UpdateTaskCommand(priority=TaskPriority.HIGH),
    )
    assert updated.description == "keep"
    assert updated.priority is TaskPriority.HIGH


@pytest.mark.asyncio
async def test_delete_requires_ownership(service: TaskService, repo: FakeRepo) -> None:
    alice, bob = uuid4(), uuid4()
    task = await service.create(owner_id=alice, command=CreateTaskCommand(title="x"))
    with pytest.raises(TaskNotFoundError):
        await service.delete(owner_id=bob, task_id=task.id)
    assert await repo.get_by_id(task.id) is not None
