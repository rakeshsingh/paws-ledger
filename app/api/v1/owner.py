"""Owner profile routes — view and update profile."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session
from uuid import UUID
from ...database import get_session
from ...models import User
from .common import serializer

router = APIRouter()


class AddressUpdate(BaseModel):
    address: str


def _get_current_user(request: Request, session: Session = Depends(get_session)) -> User:
    """Extract the authenticated user from the session cookie."""
    raw_cookie = request.cookies.get("paws_user_id")
    if not raw_cookie:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        user_id = serializer.loads(raw_cookie)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid session")

    user = session.get(User, UUID(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/owner/profile")
async def get_owner_profile(request: Request, session: Session = Depends(get_session)):
    user = _get_current_user(request, session)
    return {
        "id": str(user.id),
        "name": user.name,
        "email": user.email,
        "address": user.address or "",
        "role": user.role,
        "pet_count": len(user.pets),
    }


@router.put("/owner/profile/address")
async def update_owner_address(
    payload: AddressUpdate,
    request: Request,
    session: Session = Depends(get_session),
):
    user = _get_current_user(request, session)
    user.address = payload.address
    session.add(user)
    session.commit()
    session.refresh(user)
    return {
        "message": "Address updated successfully",
        "address": user.address,
    }
