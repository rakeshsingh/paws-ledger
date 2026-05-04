from nicegui import ui
from sqlmodel import Session, select
from ..database import engine
from ..models import Pet, LedgerEvent
from .footer import nav_footer
from .common import email_service
import uuid


def init_qr_profile_page():
    @ui.page('/qr/{tag_id}')
    async def public_profile(tag_id: str):
        with Session(engine) as session:
            try:
                pet_uuid = uuid.UUID(tag_id)
            except ValueError:
                ui.label('Invalid QR Tag').classes('pl-page-title').style('color: var(--pl-primary)')
                return

            pet = session.exec(select(Pet).where(Pet.id == pet_uuid)).first()
            if not pet:
                ui.label('Invalid Tag').classes('pl-page-title').style('color: var(--pl-primary)')
                return

            # Log the scan
            event = LedgerEvent(pet_id=pet.id, event_type="EMERGENCY_SCAN", description="Public QR scan detected")
            session.add(event)
            session.commit()

            # Notify owner
            if pet.owner and pet.owner.email:
                await email_service.notify_owner_of_scan(pet.owner.email, pet.breed or "Pet")

            with ui.column().classes('w-full items-center p-8 min-h-screen').style('background: var(--pl-surface-warm)'):
                ui.icon('emergency', size='64px').style('color: var(--pl-primary)')
                ui.label('EMERGENCY PROFILE').classes('text-3xl font-black').style('color: var(--pl-primary)')

                with ui.card().classes('w-full max-w-md p-6 mt-6'):
                    ui.label(f'This {pet.pet_species} is registered with PawsLedger.').classes('text-center mb-4')
                    ui.label(f'Breed: {pet.breed}').classes('pl-section-title text-center')
                    ui.label(f'Chip ID: {pet.chip_id}').classes('pl-text-hint text-center mb-6')

                    if pet.vaccinations:
                        ui.separator().classes('my-4')
                        ui.label('Vaccination Records').classes('pl-label mb-2')
                        for v in pet.vaccinations:
                            with ui.row().classes('w-full justify-between items-center py-1'):
                                ui.label(v.vaccine_name).classes('font-medium')
                                ui.label(f'{v.date_given.date()}').classes('pl-text-xs')
                    else:
                        ui.separator().classes('my-4')
                        ui.label('No vaccination records on file').classes('pl-text-xs italic text-center mb-2')

                    async def contact_owner():
                        if pet.owner and pet.owner.email:
                            await email_service.send_email(
                                pet.owner.email,
                                f"URGENT: Someone found your pet ({pet.breed})",
                                f"Hello,\n\nSomeone scanned the QR tag of your pet {pet.breed} and is trying to contact you.\n\nPlease check your phone/dashboard."
                            )
                            ui.notify('Owner has been notified!', type='positive')
                        else:
                            ui.notify('Owner contact info not available.', type='negative')

                    ui.button('CONTACT OWNER', icon='email', on_click=contact_owner).classes(
                        'w-full py-4 text-xl mb-4'
                    ).style('background-color: #16a34a; color: white;')
                    ui.label(
                        'Owner PII is hidden for privacy. Clicking the button above sends an instant alert to the owner.'
                    ).classes('pl-text-xs text-center')

                ui.label('Information on this page is provided for emergency recovery only.').classes('pl-text-xs mt-8')
        nav_footer()
