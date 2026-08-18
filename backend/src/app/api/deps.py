"""Composition root: FastAPI providers that wire services to their repositories.

The cross-cutting security/session/rate-limit dependencies live in
`app.core.deps`; this module only assembles the per-request service objects.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.core.db import get_sessionmaker
from app.core.deps import KeycloakAdminDep, SessionDep, SettingsDep
from app.repositories.task import TaskRepository
from app.services.task import TaskService
from app.services.tenant import TenantProvisioningService, run_tenant_migrations


async def task_service(session: SessionDep) -> TaskService:
    return TaskService(repo=TaskRepository(session))


TaskServiceDep = Annotated[TaskService, Depends(task_service)]


def provisioning_service(
    kc: KeycloakAdminDep, settings: SettingsDep
) -> TenantProvisioningService:
    return TenantProvisioningService(
        sessionmaker=get_sessionmaker(),
        kc=kc,
        migrate_schema=run_tenant_migrations,
        invite_client_id=settings.oidc_client_id,
    )


ProvisioningDep = Annotated[TenantProvisioningService, Depends(provisioning_service)]
