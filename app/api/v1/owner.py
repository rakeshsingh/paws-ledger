"""Owner profile routes — view and update profile."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session
from typing import Optional
from uuid import UUID
from ...database import get_session
from ...models import User
from .common import serializer

router = APIRouter()


class AddressUpdate(BaseModel):
    address: str


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None


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
        "phone": user.phone or "",
        "address": user.address or "",
        "city": user.city or "",
        "country": user.country or "",
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


@router.put("/owner/profile")
async def update_owner_profile(
    payload: ProfileUpdate,
    request: Request,
    session: Session = Depends(get_session),
):
    user = _get_current_user(request, session)

    if payload.name is not None:
        user.name = payload.name
    if payload.email is not None:
        user.email = payload.email
    if payload.phone is not None:
        user.phone = payload.phone
    if payload.address is not None:
        user.address = payload.address
    if payload.city is not None:
        user.city = payload.city
    if payload.country is not None:
        user.country = payload.country

    session.add(user)
    session.commit()
    session.refresh(user)

    return {
        "id": str(user.id),
        "name": user.name,
        "email": user.email,
        "phone": user.phone or "",
        "address": user.address or "",
        "city": user.city or "",
        "country": user.country or "",
        "role": user.role,
        "pet_count": len(user.pets),
    }
