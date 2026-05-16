"""Secure Nudge routes — free tier one-way recovery messaging."""

import html
import os
import re
import secrets
from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlmodel import Session, select, func

from ...database import get_session
from ...models import Pet, NudgeSession, LedgerEvent, User, _utc_now
from .common import email_service, get_current_user, validate_chip_id

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

_HTML_TAG_RE = re.compile(r'<[^>]+>')


class NudgeRequest(BaseModel):
    message: str

    @field_validator('message')
    @classmethod
    def validate_message_length(cls, v):
        stripped = v.strip()
        if len(stripped) < 10:
            raise ValueError('Message must be at least 10 characters')
        if len(stripped) > 500:
            raise ValueError('Message must be at most 500 characters')
        return stripped


def _sanitize(text: str) -> str:
    """Strip HTML tags and escape special characters."""
    text = _HTML_TAG_RE.sub('', text)
    return html.escape(text)


def _purge_expired_nudges(session: Session):
    """Remove NudgeSession records older than 30 days."""
    cutoff = _utc_now() - timedelta(days=30)
    stale = session.exec(
        select(NudgeSession).where(NudgeSession.created_at < cutoff)
    ).all()
    for record in stale:
        session.delete(record)


@router.post("/nudge/{chip_id}")
@limiter.limit("10/hour")
async def send_nudge(chip_id: str, payload: NudgeRequest, request: Request, session: Session = Depends(get_session)):
    """Send a secure nudge to a pet owner. Requires authentication."""
    finder = get_current_user(request, session)
    chip_id = validate_chip_id(chip_id)

    pet = session.exec(select(Pet).where(Pet.chip_id == chip_id)).first()
    if not pet:
        raise HTTPException(status_code=404, detail="Pet not found")

    if not pet.owner_id:
        raise HTTPException(status_code=409, detail="This pet has no registered owner — nudge unavailable")

    if str(finder.id) == str(pet.owner_id):
        raise HTTPException(status_code=409, detail="You cannot nudge yourself")

    # Application-level rate limit: 3 nudges per finder per pet per 24h
    cutoff = _utc_now() - timedelta(hours=24)
    count = session.exec(
        select(func.count(NudgeSession.id)).where(
            NudgeSession.pet_id == pet.id,
            NudgeSession.finder_id == finder.id,
            NudgeSession.created_at >= cutoff,
        )
    ).one()
    if count >= 3:
        raise HTTPException(status_code=429, detail="Rate limit: maximum 3 nudges per pet per 24 hours")

    sanitized_message = _sanitize(payload.message)
    response_token = secrets.token_urlsafe(32)

    base_url = os.getenv('BASE_URL', 'https://www.pawsledger.com')
    dashboard_url = f"{base_url}/dashboard"

    pet_name = pet.name or pet.breed or "your pet"
    sent = await email_service.send_nudge_alert(
        pet.owner.email, pet_name, sanitized_message, dashboard_url
    )

    if not sent:
        raise HTTPException(status_code=502, detail="Unable to deliver notification. Please try again later.")

    nudge = NudgeSession(
        pet_id=pet.id,
        finder_id=finder.id,
        message=sanitized_message,
        response_token=response_token,
        expires_at=_utc_now() + timedelta(hours=48),
    )
    session.add(nudge)

    event = LedgerEvent(
        pet_id=pet.id,
        event_type="NUDGE_SENT",
        description="Secure nudge sent by a verified user",
    )
    session.add(event)

    _purge_expired_nudges(session)
    session.commit()

    return {"message": "Your nudge has been sent. The owner has been notified."}
