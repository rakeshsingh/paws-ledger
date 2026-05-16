"""Shared service instances and utilities used across API route modules."""

import os
import sys
from uuid import UUID
from fastapi import Depends, HTTPException, Request
from itsdangerous import URLSafeSerializer
from sqlmodel import Session
from ...database import get_session
from ...models import User
from ...services.integrations import AAHAClient, GoogleAuthService, EmailService, HashService, PDFService

aaha_client = AAHAClient()
google_auth = GoogleAuthService()
email_service = EmailService()
hash_service = HashService()
pdf_service = PDFService()

# Enforce strong secret key in production
_storage_secret = os.getenv("STORAGE_SECRET")
if not _storage_secret and os.getenv("APP_ENV") == "prod":
    print("FATAL: STORAGE_SECRET environment variable is required in production.", file=sys.stderr)
    sys.exit(1)
_storage_secret = _storage_secret or "paws_dev_secret_not_for_production"

serializer = URLSafeSerializer(_storage_secret)

IS_PRODUCTION = os.getenv("APP_ENV") == "prod"


def get_current_user(request: Request, session: Session = Depends(get_session)) -> User:
    """Extract authenticated user from cookie. Raises 401 if not authenticated."""
    raw_cookie = request.cookies.get("paws_user_id")
    if not raw_cookie:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        user_id = serializer.loads(raw_cookie)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid session")
    user = session.get(User, UUID(user_id))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user
