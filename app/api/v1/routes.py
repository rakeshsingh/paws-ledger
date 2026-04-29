from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select
from typing import List
from ...database import get_session
from ...models import Pet, LedgerEvent, User
from ...services.integrations import AAHAClient, GoogleAuthService
from uuid import UUID

router = APIRouter(prefix="/api/v1")
aaha_client = AAHAClient()
google_auth = GoogleAuthService()

@router.get("/auth/login")
async def auth_login(request: Request):
    redirect_url = await google_auth.get_authorize_url(request)
    return RedirectResponse(url=redirect_url)

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
            
        return {
            "message": "Authentication successful",
            "user": {
                "id": str(user.id),
                "email": user.email,
                "name": user.name
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/lookup/{chip_id}")
async def lookup_pet(chip_id: str, session: Session = Depends(get_session)):
    # 1. Check local database
    statement = select(Pet).where(Pet.chip_id == chip_id)
    pet = session.exec(statement).first()
    
    if pet:
        return {
            "source": "local",
            "data": {
                "id": str(pet.id),
                "chip_id": pet.chip_id,
                "pet_species": pet.pet_species,
                "breed": pet.breed,
                "manufacturer": pet.manufacturer,
                "identity_status": pet.identity_status,
            },
            "message": "Pet found in PawsLedger registry."
        }
    
    # 2. If not found locally, trigger AAHA meta-search
    aaha_data = await aaha_client.lookup(chip_id)
    if aaha_data:
        return {
            "source": "aaha",
            "data": aaha_data,
            "message": "Pet found in Nationwide AAHA Network."
        }
        
    raise HTTPException(status_code=404, detail="Chip ID not found in any registry.")

@router.get("/qr/{tag_id}")
async def resolve_qr(tag_id: str, session: Session = Depends(get_session)):
    # In a real app, tag_id might be a separate ID or linked to chip_id
    # For now, we assume tag_id corresponds to the Pet.id (UUID) for simplicity
    try:
        pet_id = UUID(tag_id)
    except ValueError:
         raise HTTPException(status_code=400, detail="Invalid Tag ID format")
         
    pet = session.get(Pet, pet_id)
    if not pet:
        raise HTTPException(status_code=404, detail="Pet not found")
    
    # Log the scan event
    event = LedgerEvent(
        pet_id=pet.id,
        event_type="EMERGENCY_SCAN",
        description="Public QR tag scanned"
    )
    session.add(event)
    session.commit()
    
    return {
        "pet_species": pet.pet_species,
        "breed": pet.breed,
        "identity_status": pet.identity_status,
        "emergency_contact": "Contact info obfuscated (Mock)"
    }

@router.post("/ledger/transfer")
async def transfer_ownership(chip_id: str, new_owner_email: str, session: Session = Depends(get_session)):
    # Mock implementation of ownership transfer
    statement = select(Pet).where(Pet.chip_id == chip_id)
    pet = session.exec(statement).first()
    if not pet:
         raise HTTPException(status_code=404, detail="Pet not found")
    
    return {"message": f"Transfer of {chip_id} to {new_owner_email} initiated."}
