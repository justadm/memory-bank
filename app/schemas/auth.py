from pydantic import BaseModel


class AuthStatusResponse(BaseModel):
    auth_enabled: bool
    authenticated: bool
    principal_name: str | None
    scopes: list[str]
    tenant_ids: list[str] | None = None
    tenant_restricted: bool = False
