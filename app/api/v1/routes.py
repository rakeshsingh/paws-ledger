from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List
from ...database import get_session
from ...models import Pet, LedgerEvent, User
from ...services.integrations import AAHAClient
from uuid import UUID

router = APIRouter(prefix="/api/v1")
aaha_client = AAHAClient()

@router.get("/lookup/{chip_id}")
async def lookup_pet(chip_id: str, session: Session = Depends(get_session)):
    # 1. Check local database
    statement = select(Pet).where(Pet.chip_id == chip_id)
    pet = session.exec(statement).first()
    
    if pet:
        return {
            "source": "local",
            "data": pet,
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
