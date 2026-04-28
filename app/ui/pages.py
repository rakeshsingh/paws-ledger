from nicegui import ui, app
from sqlmodel import Session, select
from ..database import engine
from ..models import Pet, User, LedgerEvent
from ..services.integrations import get_manufacturer_from_chip, DogAPIClient
import uuid

dog_client = DogAPIClient()

def init_pages():
    @ui.page('/dashboard')
    async def dashboard():
        with ui.column().classes('w-full items-center p-8'):
            ui.label('PawsLedger Dashboard').classes('text-4xl font-bold text-primary')
            ui.label('The Single Source of Truth for Pet Identity').classes('text-lg text-gray-500 mb-8')

            with ui.card().classes('w-full max-w-md p-6'):
                ui.label('Lookup Pet by Chip ID').classes('text-xl mb-4')
                chip_input = ui.input('Enter 15-digit Chip ID').classes('w-full mb-4')
                
                async def do_lookup():
                    chip_id = chip_input.value
                    if not chip_id:
                        ui.notify('Please enter a chip ID', type='warning')
                        return
                    
                    with Session(engine) as session:
                        pet = session.exec(select(Pet).where(Pet.chip_id == chip_id)).first()
                        if pet:
                            ui.notify(f'Pet found: {pet.breed}', type='positive')
                            ui.open(f'/pet/{pet.id}')
                        else:
                            ui.notify('Pet not found in registry', type='negative')
                
                ui.button('Search Registry', on_click=do_lookup).classes('w-full')

            ui.button('Register New Pet', on_click=lambda: ui.open('/register')).classes('mt-8').props('outline')

    @ui.page('/register')
    async def register():
        with ui.column().classes('w-full items-center p-8'):
            ui.label('Register Your Pet').classes('text-3xl font-bold mb-6')
            
            breeds = await dog_client.get_breeds()
            breed_options = {b['name']: b['name'] for b in breeds}

            with ui.card().classes('w-full max-w-lg p-6'):
                chip_id = ui.input('Chip ID (15 digits)').classes('w-full mb-4')
                breed = ui.select(breed_options, label='Breed', with_filter=True).classes('w-full mb-4')
                species = ui.select(['DOG', 'CAT'], label='Species', value='DOG').classes('w-full mb-4')
                
                async def submit():
                    if not chip_id.value or len(chip_id.value) != 15:
                        ui.notify('Invalid Chip ID. Must be 15 digits.', type='negative')
                        return
                    
                    manufacturer = get_manufacturer_from_chip(chip_id.value)
                    
                    with Session(engine) as session:
                        new_pet = Pet(
                            chip_id=chip_id.value,
                            breed=breed.value,
                            pet_species=species.value,
                            manufacturer=manufacturer,
                            identity_status="VERIFIED"
                        )
                        session.add(new_pet)
                        session.commit()
                        ui.notify(f'Successfully registered {new_pet.breed}!', type='positive')
                        ui.open('/')

                ui.button('Create Identity', on_click=submit).classes('w-full mt-4')

    @ui.page('/pet/{pet_id}')
    async def pet_profile(pet_id: str):
        with Session(engine) as session:
            pet = session.get(Pet, uuid.UUID(pet_id))
            if not pet:
                ui.label('Pet Not Found').classes('text-2xl text-red-500')
                return

            with ui.column().classes('w-full items-center p-8'):
                ui.label(f'Identity Ledger: {pet.chip_id}').classes('text-3xl font-bold')
                
                with ui.row().classes('gap-4 mt-6'):
                    with ui.card().classes('p-4 w-64'):
                        ui.label('General Info').classes('font-bold border-b mb-2')
                        ui.label(f'Species: {pet.pet_species}')
                        ui.label(f'Breed: {pet.breed}')
                        ui.label(f'Manufacturer: {pet.manufacturer}')
                        ui.label(f'Status: {pet.identity_status}').classes('text-green-600' if pet.identity_status == 'VERIFIED' else 'text-yellow-600')

                    with ui.card().classes('p-4 w-80'):
                        ui.label('Ledger Events').classes('font-bold border-b mb-2')
                        for event in pet.ledger_events:
                            with ui.row().classes('justify-between w-full'):
                                ui.label(event.event_type).classes('text-xs font-mono')
                                ui.label(event.timestamp.strftime('%Y-%m-%d')).classes('text-xs text-gray-400')
                            ui.label(event.description).classes('text-sm mb-2')
                        
                        if not pet.ledger_events:
                            ui.label('No events recorded.').classes('text-sm italic')

                ui.button('Back to Home', on_click=lambda: ui.open('/')).classes('mt-8').props('flat')

    @ui.page('/qr/{tag_id}')
    async def public_profile(tag_id: str):
        with Session(engine) as session:
            pet = session.get(Pet, uuid.UUID(tag_id))
            if not pet:
                 ui.label('Invalid Tag').classes('text-2xl text-red-500')
                 return
            
            # Log the scan
            event = LedgerEvent(pet_id=pet.id, event_type="EMERGENCY_SCAN", description="Public QR scan detected")
            session.add(event)
            session.commit()

            with ui.column().classes('w-full items-center p-8 bg-red-50 min-h-screen'):
                ui.icon('emergency', size='64px', color='red')
                ui.label('EMERGENCY PROFILE').classes('text-3xl font-black text-red-700')
                
                with ui.card().classes('w-full max-w-md p-6 mt-6 shadow-xl'):
                    ui.label(f'This {pet.pet_species} is registered with PawsLedger.').classes('text-center mb-4')
                    ui.label(f'Breed: {pet.breed}').classes('text-xl font-bold text-center')
                    ui.label(f'Chip ID: {pet.chip_id}').classes('text-sm text-gray-500 text-center mb-6')
                    
                    ui.button('CALL OWNER', icon='phone').classes('w-full bg-green-600 text-white py-4 text-xl mb-4')
                    ui.button('NOTIFY VET', icon='local_hospital', color='secondary').classes('w-full')
                
                ui.label('Information on this page is provided for emergency recovery only.').classes('text-xs text-gray-400 mt-8')
