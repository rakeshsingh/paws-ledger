"""Authentication routes — login, callback, /me."""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlmodel import Session, select
from ...database import get_session
from ...models import User
from .common import google_auth, serializer
from uuid import UUID
import httpx
import os

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


@router.get("/auth/login")
@limiter.limit("5/minute")
async def auth_login(request: Request):
    """Redirect to Google OAuth. Uses Authlib to build the authorization URL."""
    return await google_auth.authorize_redirect(request)


@router.get("/auth/callback")
@limiter.limit("10/minute")
async def auth_callback(request: Request, session: Session = Depends(get_session)):
    """Handle Google OAuth callback.
    
    Uses a direct token exchange approach that doesn't depend on session
    state verification, which can fail behind reverse proxies (Cloudflare
    Tunnel + Nginx) where session cookies may not survive the redirect.
    """
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    try:
        # Try Authlib's standard flow first (works when session cookie is preserved)
        token = await google_auth.authorize_access_token(request)
        user_info = await google_auth.get_user_info(token)
    except Exception:
        # Fallback: Direct token exchange without session state verification
        # This handles the case where the session cookie is lost during redirect
        client_id = os.getenv("GOOGLE_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        redirect_uri = os.getenv("GOOGLE_CALLBACK_URL")

        if not all([client_id, client_secret, redirect_uri]):
            raise HTTPException(status_code=500, detail="OAuth not configured")

        # Exchange code for tokens directly
        async with httpx.AsyncClient() as http_client:
            token_resp = await http_client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            if token_resp.status_code != 200:
                raise HTTPException(
                    status_code=400,
                    detail="Authentication failed. Please try signing in again.",
                )
            token_data = token_resp.json()

            # Get user info from Google
            userinfo_resp = await http_client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {token_data['access_token']}"},
            )
            if userinfo_resp.status_code != 200:
                raise HTTPException(
                    status_code=400,
                    detail="Failed to fetch user info from Google",
                )
            user_info = userinfo_resp.json()

    sub = user_info.get("sub")
    email = user_info.get("email")
    name = user_info.get("name", email)

    if not sub or not email:
        raise HTTPException(status_code=400, detail="Invalid user info from Google")

    # Check if user exists by sub, then email
    statement = select(User).where(User.sub == sub)
    user = session.exec(statement).first()
    if not user:
        statement = select(User).where(User.email == email)
        user = session.exec(statement).first()
        if user:
            user.sub = sub
        else:
            user = User(sub=sub, email=email, name=name)
            session.add(user)
        session.commit()
        session.refresh(user)

    # Set cookie for session restoration on NiceGUI pages
    response = RedirectResponse(url="/dashboard")
    is_prod = os.getenv("APP_ENV") == "prod"
    response.set_cookie(
        "paws_user_id",
        serializer.dumps(str(user.id)),
        httponly=True,
        samesite="lax",
        secure=is_prod,
        max_age=7 * 24 * 3600,  # 7 days
    )
    return response


@router.get("/me")
async def get_me(request: Request, session: Session = Depends(get_session)):
    raw_cookie = request.cookies.get("paws_user_id")
    if not raw_cookie:
        return {"authenticated": False}

    try:
        user_id = serializer.loads(raw_cookie)
    except Exception:
        return {"authenticated": False}

    user = session.get(User, UUID(user_id))
    if not user:
        return {"authenticated": False}

    return {
        "authenticated": True,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "name": user.name
        }
    }
