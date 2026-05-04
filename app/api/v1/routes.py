"""
API v1 route aggregator.

Combines entity-specific routers into a single prefixed router and
re-exports shared objects so existing imports continue to work:
    from app.api.v1.routes import router, serializer, aaha_client, ...
"""

from fastapi import APIRouter
from .auth import router as auth_router
from .pets import router as pets_router
from .owner import router as owner_router

# Re-export shared instances for backward compatibility
from .common import aaha_client, google_auth, email_service, hash_service, pdf_service, serializer  # noqa: F401

router = APIRouter(prefix="/api/v1")
router.include_router(auth_router)
router.include_router(pets_router)
router.include_router(owner_router)
