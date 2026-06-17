"""Owner profile routes — view and update profile."""

import re
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlmodel import Session, select
from typing import Optional
from uuid import UUID
from ...database import get_session
from ...models import User, _utc_now
from .common import serializer, get_current_user, sanitize_text

_EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')

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

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        if v is not None and (len(v.strip()) == 0 or len(v) > 200):
            raise ValueError('Name must be 1-200 characters')
        return v.strip() if v else v

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if v is not None and not _EMAIL_RE.match(v):
            raise ValueError('Invalid email format')
        return v

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v):
        if v is not None and len(v) > 30:
            raise ValueError('Phone must be 30 characters or less')
        return v

    @field_validator('address', 'city', 'country')
    @classmethod
    def validate_length(cls, v):
        if v is not None and len(v) > 255:
            raise ValueError('Field must be 255 characters or less')
        return v


def _get_current_user(request: Request, session: Session = Depends(get_session)) -> User:
    """Delegate to shared auth dependency."""
    return get_current_user(request, session)


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

    if payload.email is not None and payload.email != user.email:
        existing = session.exec(
            select(User).where(User.email == payload.email)
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="Email already in use")

    if payload.name is not None:
        user.name = sanitize_text(payload.name)
    if payload.email is not None:
        user.email = payload.email
    if payload.phone is not None:
        user.phone = payload.phone
    if payload.address is not None:
        user.address = sanitize_text(payload.address)
    if payload.city is not None:
        user.city = sanitize_text(payload.city)
    if payload.country is not None:
        user.country = sanitize_text(payload.country)

    user.profile_updated_at = _utc_now()
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
