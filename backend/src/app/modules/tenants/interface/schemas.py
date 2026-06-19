from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

# A tenant_admin may only grant tenant-scoped roles — never platform_admin.
MemberRole = Literal["tenant_user", "tenant_admin"]


class CreateTenantRequest(BaseModel):
    slug: str = Field(
        pattern=r"^[a-z][a-z0-9_]{1,40}$",
        description="Lowercase identifier, becomes the Postgres schema tenant_<slug>.",
        examples=["acme"],
    )
    name: str = Field(min_length=1, max_length=200, examples=["ACME Corp"])
    admin_email: EmailStr = Field(description="Email of the organization's first admin user.")


class TenantCreatedResponse(BaseModel):
    tenant_id: UUID
    slug: str
    keycloak_group_id: str
    admin_user_id: str


class InviteMemberRequest(BaseModel):
    email: EmailStr
    roles: list[MemberRole] = Field(default_factory=lambda: ["tenant_user"])


class MemberInvitedResponse(BaseModel):
    user_id: str
    tenant_id: UUID
    email: EmailStr
