from fastapi import APIRouter, Depends

from app.config import get_settings
from app.schemas.auth import AuthStatusResponse
from app.security import get_optional_principal


router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=AuthStatusResponse)
def get_auth_status(principal=Depends(get_optional_principal)) -> AuthStatusResponse:
    settings = get_settings()
    if principal is None:
        return AuthStatusResponse(
            auth_enabled=settings.auth_enabled,
            authenticated=False,
            principal_name=None,
            scopes=[] if settings.auth_enabled else ["read", "write", "import", "admin"],
            tenant_ids=None,
            tenant_restricted=False,
        )

    return AuthStatusResponse(
        auth_enabled=settings.auth_enabled,
        authenticated=True,
        principal_name=principal.name,
        scopes=sorted(principal.scopes),
        tenant_ids=sorted(principal.tenant_ids) if principal.tenant_ids is not None else None,
        tenant_restricted=principal.is_tenant_restricted,
    )
