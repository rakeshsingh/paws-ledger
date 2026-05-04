from nicegui import ui
from sqlmodel import Session, select
from ..database import engine
from ..models import LedgerEvent, SharedAccess
from .header import nav_header
from .footer import nav_footer
from .common import email_service
from datetime import datetime


def init_shared_access_page():
    @ui.page('/shared/{token}')
    async def shared_profile(token: str):
        nav_header()
        with Session(engine) as session:
            statement = select(SharedAccess).where(SharedAccess.token == token)
            shared_access = session.exec(statement).first()

            if not shared_access or shared_access.expires_at < datetime.utcnow():
                with ui.column().classes('w-full items-center p-8'):
                    ui.label('Access Expired or Invalid').classes('pl-page-title').style('color: var(--pl-primary)')
                    ui.label('This shared link is no longer active.').classes('pl-text-hint')
                return

            pet = shared_access.pet

            # Log Heartbeat Audit
            event = LedgerEvent(
                pet_id=pet.id,
                event_type="HEARTBEAT_ACCESS",
                description="Shared records accessed via time-bound link"
            )
            session.add(event)
            session.commit()

            # Notify owner
            if pet.owner and pet.owner.email:
                await email_service.notify_owner_of_access(pet.owner.email, pet.breed or "Pet", "Service Provider (Shared Link)")

            with ui.column().classes('w-full items-center p-8 max-w-4xl mx-auto'):
                ui.label(f'Care Guide & Records: {pet.breed}').classes('pl-page-title mb-6')

                with ui.row().classes('w-full gap-4'):
                    with ui.card().classes('flex-1 p-6'):
                        ui.label('Vaccination History').classes('pl-section-title pl-border-section')
                        if not pet.vaccinations:
                            ui.label('No vaccination records found.').classes('pl-text-hint italic')
                        else:
                            for v in pet.vaccinations:
                                with ui.row().classes('justify-between w-full mb-2'):
                                    with ui.column():
                                        ui.label(v.vaccine_name).classes('font-bold')
                                        ui.label(f"Given: {v.date_given.date()}").classes('pl-text-xs')
                                    ui.label(f"Expires: {v.expiration_date.date()}").classes('pl-text-xs font-bold').style('color: var(--pl-primary)')

                    with ui.card().classes('w-64 p-6'):
                        ui.label('Quick Info').classes('font-bold pl-border-section')
                        ui.label(f'Species: {pet.pet_species}')
                        ui.label(f'Breed: {pet.breed}')
                        ui.label(f'DOB: {pet.dob.date() if pet.dob else "Unknown"}')
                        ui.separator().classes('my-2')
                        ui.label('Access Status').classes('pl-text-xs')
                        ui.label('Active').classes('pl-status-active')
                        ui.label(f"Expires: {shared_access.expires_at.strftime('%Y-%m-%d %H:%M')}").classes('pl-text-xs')
        nav_footer()
