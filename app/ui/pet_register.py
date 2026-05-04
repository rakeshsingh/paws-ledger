from nicegui import ui, app
from starlette.requests import Request
from sqlmodel import Session, select
from ..database import engine
from ..models import Pet, User
from ..services.integrations import get_manufacturer_from_chip
from .header import nav_header
from .footer import nav_footer
from .common import dog_client, try_restore_session
from datetime import datetime


def init_register_page():
    @ui.page('/register')
    async def register(request: Request):
        if not try_restore_session(request):
            ui.navigate.to('/login')
            return

        nav_header()
        with ui.column().classes('w-full items-center p-8'):
            ui.label('Register Your Pet').classes('pl-page-title mb-6')

            breeds = await dog_client.get_breeds()
            breed_options = {b['name']: b['name'] for b in breeds}

            with ui.card().classes('w-full max-w-lg p-6'):
                name = ui.input('Pet Name').classes('w-full mb-4')
                chip_id = ui.input('Chip ID (15 digits)').classes('w-full mb-4')
                species = ui.select(['DOG', 'CAT'], label='Species', value='DOG').classes('w-full mb-4')
                breed = ui.select(breed_options, label='Breed').props('use-input input-debounce="300"').classes('w-full mb-4')
                gender = ui.select(['Male', 'Female', 'Unknown'], label='Gender', value='Unknown').classes('w-full mb-4')
                dob = ui.input('Birth Date').classes('w-full mb-4').props('type=date')

                async def submit():
                    if not name.value:
                        ui.notify('Pet Name is required.', type='negative')
                        return
                    if not chip_id.value or len(chip_id.value) != 15 or not chip_id.value.isdigit():
                        ui.notify('Invalid Chip ID. Must be exactly 15 numeric digits.', type='negative')
                        return

                    manufacturer = get_manufacturer_from_chip(chip_id.value)

                    with Session(engine) as session:
                        user = session.exec(select(User).where(User.email == app.storage.user['email'])).first()
                        if not user:
                            return
                        if len(user.pets) >= 5:
                            ui.notify('Maximum of 5 pets reached per profile.', type='negative')
                            return
                        new_pet = Pet(
                            name=name.value,
                            chip_id=chip_id.value,
                            breed=breed.value,
                            pet_species=species.value,
                            gender=gender.value,
                            dob=datetime.fromisoformat(dob.value) if dob.value else None,
                            manufacturer=manufacturer,
                            identity_status="VERIFIED",
                            owner_id=user.id
                        )
                        session.add(new_pet)
                        session.commit()
                        ui.notify(f'Successfully registered {new_pet.breed}!', type='positive')
                        ui.navigate.to('/dashboard')

                ui.button('Create Identity', on_click=submit).classes('w-full mt-4 pl-btn-primary')
        nav_footer()
