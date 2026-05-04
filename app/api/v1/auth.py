"""Authentication routes — login, callback, /me."""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select
from ...database import get_session
from ...models import User
from .common import google_auth, serializer
from uuid import UUID

router = APIRouter()


@router.get("/auth/login")
async def auth_login(request: Request):
    return await google_auth.authorize_redirect(request)


@router.get("/auth/callback")
async def auth_callback(request: Request, session: Session = Depends(get_session)):
    try:
        token = await google_auth.authorize_access_token(request)
        user_info = await google_auth.get_user_info(token)

        sub = user_info["sub"]
        email = user_info["email"]
        name = user_info.get("name", email)

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
        response.set_cookie("paws_user_id", serializer.dumps(str(user.id)), httponly=True, samesite="lax")
        return response
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


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
