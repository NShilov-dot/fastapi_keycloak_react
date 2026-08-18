from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import TaskServiceDep
from app.core.deps import PrincipalDep, check_csrf, check_rate_limit
from app.core.security import AuthError, Principal
from app.models.task import TaskStatus
from app.schemas.task import (
    CreateTaskRequest,
    Envelope,
    PagedEnvelope,
    TaskResponse,
    UpdateTaskRequest,
)
from app.services.task import ListTasksQuery

router = APIRouter(
    prefix="/tasks",
    tags=["tasks"],
    # check_csrf is a no-op for safe methods (GET) and enforces an Origin/Referer
    # allowlist on writes as defense-in-depth beyond SameSite=Lax.
    dependencies=[Depends(check_rate_limit), Depends(check_csrf)],
)


# Roles allowed to modify ANY task in the org (not just their own).
_MANAGE_ANY_ROLES = frozenset({"tenant_admin", "platform_admin"})


def _owner_id(principal: Principal) -> UUID:
    try:
        return UUID(principal.subject)
    except ValueError as exc:
        raise AuthError("Token 'sub' is not a UUID") from exc


def _can_manage_any(principal: Principal) -> bool:
    return bool(principal.roles & _MANAGE_ANY_ROLES)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=Envelope[TaskResponse],
    summary="Create a task",
)
async def create_task(
    body: CreateTaskRequest, principal: PrincipalDep, service: TaskServiceDep
) -> Envelope[TaskResponse]:
    task = await service.create(owner_id=_owner_id(principal), command=body.to_command())
    return Envelope(data=TaskResponse.from_model(task))


@router.get(
    "",
    response_model=PagedEnvelope[TaskResponse],
    summary="List the organization's tasks (all members' tasks)",
)
async def list_tasks(
    principal: PrincipalDep,
    service: TaskServiceDep,
    status_: Annotated[TaskStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    mine: Annotated[bool, Query(description="Only my own tasks")] = False,
) -> PagedEnvelope[TaskResponse]:
    page = await service.list(
        query=ListTasksQuery(status=status_, limit=limit, offset=offset),
        owner_id=_owner_id(principal) if mine else None,
    )
    return PagedEnvelope.from_page(page)


@router.get(
    "/{task_id}",
    response_model=Envelope[TaskResponse],
    summary="Get a task by id",
)
async def get_task(
    task_id: UUID, principal: PrincipalDep, service: TaskServiceDep
) -> Envelope[TaskResponse]:
    # Org-wide read: any member may view any task in their organization.
    task = await service.get(task_id=task_id)
    return Envelope(data=TaskResponse.from_model(task))


@router.patch(
    "/{task_id}",
    response_model=Envelope[TaskResponse],
    summary="Patch task details (owner or tenant admin)",
)
async def update_task(
    task_id: UUID,
    body: UpdateTaskRequest,
    principal: PrincipalDep,
    service: TaskServiceDep,
) -> Envelope[TaskResponse]:
    task = await service.update(
        task_id=task_id,
        actor_id=_owner_id(principal),
        can_manage_any=_can_manage_any(principal),
        command=body.to_command(),
    )
    return Envelope(data=TaskResponse.from_model(task))


@router.post(
    "/{task_id}/start",
    response_model=Envelope[TaskResponse],
    summary="Transition task to in_progress (owner or tenant admin)",
)
async def start_task(
    task_id: UUID, principal: PrincipalDep, service: TaskServiceDep
) -> Envelope[TaskResponse]:
    task = await service.start(
        task_id=task_id, actor_id=_owner_id(principal), can_manage_any=_can_manage_any(principal)
    )
    return Envelope(data=TaskResponse.from_model(task))


@router.post(
    "/{task_id}/complete",
    response_model=Envelope[TaskResponse],
    summary="Transition task to done (owner or tenant admin)",
)
async def complete_task(
    task_id: UUID, principal: PrincipalDep, service: TaskServiceDep
) -> Envelope[TaskResponse]:
    task = await service.complete(
        task_id=task_id, actor_id=_owner_id(principal), can_manage_any=_can_manage_any(principal)
    )
    return Envelope(data=TaskResponse.from_model(task))


@router.post(
    "/{task_id}/cancel",
    response_model=Envelope[TaskResponse],
    summary="Transition task to cancelled (owner or tenant admin)",
)
async def cancel_task(
    task_id: UUID, principal: PrincipalDep, service: TaskServiceDep
) -> Envelope[TaskResponse]:
    task = await service.cancel(
        task_id=task_id, actor_id=_owner_id(principal), can_manage_any=_can_manage_any(principal)
    )
    return Envelope(data=TaskResponse.from_model(task))


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a task (owner or tenant admin)",
)
async def delete_task(
    task_id: UUID, principal: PrincipalDep, service: TaskServiceDep
) -> Response:
    await service.delete(
        task_id=task_id, actor_id=_owner_id(principal), can_manage_any=_can_manage_any(principal)
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
