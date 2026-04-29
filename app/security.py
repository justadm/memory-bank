from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.config import get_settings


@dataclass
class AuthPrincipal:
    name: str
    scopes: set[str]
    api_key: str
    tenant_ids: set[str] | None = None

    @property
    def is_tenant_restricted(self) -> bool:
        return self.tenant_ids is not None


def get_current_principal(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> AuthPrincipal:
    settings = get_settings()
    if not settings.auth_enabled:
        return AuthPrincipal(name="anonymous", scopes={"read", "write", "import", "admin"}, api_key="")

    registry = _parse_auth_registry(settings.auth_api_keys)
    if not registry:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Auth is enabled but no valid API keys are configured",
        )

    api_key = _extract_api_key(authorization, x_api_key)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    principal = registry.get(api_key)
    if not principal:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return principal


def require_write_access(
    principal: Annotated[AuthPrincipal, Depends(get_current_principal)],
) -> AuthPrincipal:
    return _require_scopes({"write"}, principal)


def require_read_access(
    principal: Annotated[AuthPrincipal, Depends(get_current_principal)],
) -> AuthPrincipal:
    return _require_scopes({"read", "write", "import", "admin"}, principal)


def require_import_access(
    principal: Annotated[AuthPrincipal, Depends(get_current_principal)],
) -> AuthPrincipal:
    return _require_scopes({"import", "admin"}, principal)


def require_admin_access(
    principal: Annotated[AuthPrincipal, Depends(get_current_principal)],
) -> AuthPrincipal:
    return _require_scopes({"admin"}, principal)


def _require_scopes(required: set[str], principal: AuthPrincipal | None = None) -> AuthPrincipal:
    if principal is None or not isinstance(principal, AuthPrincipal):
        principal = get_current_principal()
    if required.intersection(principal.scopes):
        return principal
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Missing required scope: {'/'.join(sorted(required))}",
    )


def _extract_api_key(authorization: str | None, x_api_key: str | None) -> str | None:
    if x_api_key and x_api_key.strip():
        return x_api_key.strip()
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        return token or None
    return None


def _parse_auth_registry(raw: str) -> dict[str, AuthPrincipal]:
    registry: dict[str, AuthPrincipal] = {}
    for index, chunk in enumerate(raw.split(","), start=1):
        item = chunk.strip()
        if not item:
            continue
        parts = item.split(":")
        tenant_ids: set[str] | None = None
        if len(parts) == 2:
            key, scopes_raw = parts
            name = f"key-{index}"
        elif len(parts) == 3:
            name, key, scopes_raw = parts[0], parts[1], ":".join(parts[2:])
        elif len(parts) >= 4:
            name, key, scopes_raw, tenants_raw = parts[0], parts[1], parts[2], ":".join(parts[3:])
            tenant_values = {tenant.strip() for tenant in tenants_raw.split("|") if tenant.strip()}
            tenant_ids = None if not tenant_values or "*" in tenant_values else tenant_values
        else:
            continue
        scopes = {scope.strip() for scope in scopes_raw.split("|") if scope.strip()}
        if not key.strip() or not scopes:
            continue
        registry[key.strip()] = AuthPrincipal(
            name=name.strip() or f"key-{index}",
            scopes=scopes,
            api_key=key.strip(),
            tenant_ids=tenant_ids,
        )
    return registry


def ensure_tenant_access(principal: AuthPrincipal, tenant_id: str | None) -> None:
    if principal.tenant_ids is None:
        return
    if not tenant_id or tenant_id not in principal.tenant_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant access denied")


def resolve_tenant_for_create(principal: AuthPrincipal, requested_tenant_id: str | None) -> str | None:
    if principal.tenant_ids is None:
        return requested_tenant_id
    if requested_tenant_id:
        ensure_tenant_access(principal, requested_tenant_id)
        return requested_tenant_id
    if len(principal.tenant_ids) == 1:
        return next(iter(principal.tenant_ids))
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="tenant_id is required for this principal")
