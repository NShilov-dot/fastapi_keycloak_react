from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.deps import PrincipalDep, SessionDep
from app.core.security import AuthError, Principal
from app.modules.tasks.application.dtos import ListTasksQuery
from app.modules.tasks.application.services import TaskService
from app.modules.tasks.domain.entities import TaskStatus
from app.modules.tasks.infrastructure.repositories import SqlAlchemyTaskRepository
from app.modules.tasks.interface.schemas import (
    CreateTaskRequest,
    Envelope,
    PagedEnvelope,
    TaskResponse,
    UpdateTaskRequest,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _owner_id(principal: Principal) -> UUID:
    try:
        return UUID(principal.subject)
    except ValueError as exc:
        raise AuthError("Token 'sub' is not a UUID") from exc


async def _service(session: SessionDep) -> TaskService:
    return TaskService(repo=SqlAlchemyTaskRepository(session))


ServiceDep = Annotated[TaskService, Depends(_service)]


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=Envelope[TaskResponse],
    summary="Create a task",
)
async def create_task(
    body: CreateTaskRequest, principal: PrincipalDep, service: ServiceDep
) -> Envelope[TaskResponse]:
    task = await service.create(owner_id=_owner_id(principal), command=body.to_command())
    return Envelope(data=TaskResponse.from_entity(task))


@router.get(
    "",
    response_model=PagedEnvelope[TaskResponse],
    summary="List the caller's tasks",
)
async def list_tasks(
    principal: PrincipalDep,
    service: ServiceDep,
    status_: Annotated[TaskStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PagedEnvelope[TaskResponse]:
    page = await service.list(
        owner_id=_owner_id(principal),
        query=ListTasksQuery(status=status_, limit=limit, offset=offset),
    )
    return PagedEnvelope.from_page(page)


@router.get(
    "/{task_id}",
    response_model=Envelope[TaskResponse],
    summary="Get a task by id",
)
async def get_task(
    task_id: UUID, principal: PrincipalDep, service: ServiceDep
) -> Envelope[TaskResponse]:
    task = await service.get(owner_id=_owner_id(principal), task_id=task_id)
    return Envelope(data=TaskResponse.from_entity(task))


@router.patch(
    "/{task_id}",
    response_model=Envelope[TaskResponse],
    summary="Patch task details",
)
async def update_task(
    task_id: UUID,
    body: UpdateTaskRequest,
    principal: PrincipalDep,
    service: ServiceDep,
) -> Envelope[TaskResponse]:
    task = await service.update(
        owner_id=_owner_id(principal), task_id=task_id, command=body.to_command()
    )
    return Envelope(data=TaskResponse.from_entity(task))


@router.post(
    "/{task_id}/start",
    response_model=Envelope[TaskResponse],
    summary="Transition task to in_progress",
)
async def start_task(
    task_id: UUID, principal: PrincipalDep, service: ServiceDep
) -> Envelope[TaskResponse]:
    task = await service.start(owner_id=_owner_id(principal), task_id=task_id)
    return Envelope(data=TaskResponse.from_entity(task))


@router.post(
    "/{task_id}/complete",
    response_model=Envelope[TaskResponse],
    summary="Transition task to done",
)
async def complete_task(
    task_id: UUID, principal: PrincipalDep, service: ServiceDep
) -> Envelope[TaskResponse]:
    task = await service.complete(owner_id=_owner_id(principal), task_id=task_id)
    return Envelope(data=TaskResponse.from_entity(task))


@router.post(
    "/{task_id}/cancel",
    response_model=Envelope[TaskResponse],
    summary="Transition task to cancelled",
)
async def cancel_task(
    task_id: UUID, principal: PrincipalDep, service: ServiceDep
) -> Envelope[TaskResponse]:
    task = await service.cancel(owner_id=_owner_id(principal), task_id=task_id)
    return Envelope(data=TaskResponse.from_entity(task))


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a task",
)
async def delete_task(
    task_id: UUID, principal: PrincipalDep, service: ServiceDep
) -> Response:
    await service.delete(owner_id=_owner_id(principal), task_id=task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
