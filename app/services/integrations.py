import httpx
from typing import Optional, List, Dict

MANUFACTURER_MAP = {
    "900": "Shared/Unassigned",
    "985": "Datamars / HomeAgain",
    "981": "Datamars / PetLink",
    "977": "Trovan",
    "956": "AVID",
    "939": "Animal ID",
    "982": "Allflex",
}

def get_manufacturer_from_chip(chip_id: str) -> str:
    if not chip_id or len(chip_id) < 3:
        return "Unknown"
    prefix = chip_id[:3]
    return MANUFACTURER_MAP.get(prefix, f"Generic ({prefix})")

class DogAPIClient:
    BASE_URL = "https://api.thedogapi.com/v1"
    
    async def get_breeds(self) -> List[Dict]:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.BASE_URL}/breeds")
            if response.status_code == 200:
                return response.json()
            return []

    async def search_breed(self, name: str) -> List[Dict]:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.BASE_URL}/breeds/search?q={name}")
            if response.status_code == 200:
                return response.json()
            return []

class AAHAClient:
    """
    Mock client for the AAHA Universal Pet Microchip Lookup.
    In a production environment, this would use a web scraper or an official API.
    """
    async def lookup(self, chip_id: str) -> Optional[Dict]:
        # Simulate network latency
        import asyncio
        await asyncio.sleep(0.5)
        
        # Mock logic: if chip starts with 985, it's "found" in AAHA but not in our DB
        if chip_id.startswith("985"):
            return {
                "chip_id": chip_id,
                "found_in_aaha": True,
                "manufacturer": "HomeAgain (via AAHA Network)",
                "status": "Registered with HomeAgain",
                "last_seen": "2024-01-15",
                "message": "This chip is registered in the AAHA network but not yet claimed on PawsLedger."
            }
        return None
