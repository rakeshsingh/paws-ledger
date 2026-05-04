from nicegui import ui
from sqlmodel import Session, select
from ..database import engine
from ..models import Pet, LedgerEvent, Vaccination, SharedAccess
from .header import nav_header
from .footer import nav_footer
from .common import hash_service, pdf_service
from datetime import datetime, timedelta
import uuid


def init_pet_profile_page():
    @ui.page('/pet/{pet_id}')
    async def pet_profile(pet_id: str):
        nav_header()
        with Session(engine) as session:
            pet = session.exec(select(Pet).where(Pet.id == uuid.UUID(pet_id))).first()
            if not pet:
                ui.label('Pet Not Found').classes('pl-page-title').style('color: var(--pl-primary)')
                return

            with ui.column().classes('w-full items-center p-8 max-w-6xl mx-auto'):
                ui.label(f'Identity Ledger: {pet.chip_id}').classes('pl-page-title mb-8')

                with ui.row().classes('w-full gap-6 items-start'):
                    # Left Column: General Info & Shared Access
                    with ui.column().classes('w-1/3 gap-6'):
                        with ui.card().classes('w-full p-6'):
                            ui.label('General Info').classes('pl-section-title pl-border-section')
                            ui.label(f'Species: {pet.pet_species}')
                            ui.label(f'Breed: {pet.breed}')
                            ui.label(f'Manufacturer: {pet.manufacturer}')
                            status_cls = 'pl-status-verified' if pet.identity_status == 'VERIFIED' else 'pl-status-unverified'
                            ui.label(f'Status: {pet.identity_status}').classes(status_cls)
                            if pet.owner:
                                ui.label(f'Owner: {pet.owner.name}').classes('pl-text-hint mt-2')

                        with ui.card().classes('w-full p-6'):
                            ui.label('Managed Access').classes('pl-section-title pl-border-section')
                            ui.label('Generate a time-bound care link for sitters/vets.').classes('pl-text-xs mb-4')

                            async def create_link():
                                access = SharedAccess(pet_id=pet.id, expires_at=datetime.utcnow() + timedelta(hours=24))
                                session.add(access)
                                session.commit()
                                url = f"/shared/{access.token}"
                                with ui.dialog() as dialog, ui.card():
                                    ui.label('Shared Access Link Created').classes('font-bold')
                                    ui.label('Valid for 24 hours.').classes('pl-text-xs')
                                    ui.input(value=url).classes('w-full mt-2').props('readonly outline')
                                    ui.button('Close', on_click=dialog.close).classes('mt-4')
                                dialog.open()

                            ui.button('Create 24h Link', icon='share', on_click=create_link).classes('w-full').props('outline')

                    # Middle Column: Vaccination Ledger
                    with ui.column().classes('flex-1 gap-6'):
                        with ui.card().classes('w-full p-6'):
                            with ui.row().classes('justify-between items-center w-full mb-4 pl-border-section'):
                                ui.label('Vaccination Ledger').classes('pl-section-title')

                                async def export_pdf():
                                    if not pet.vaccinations:
                                        ui.notify('No vaccinations to export.', type='warning')
                                        return
                                    aggregate_data = [v.dict(exclude={"id", "pet_id", "record_hash", "pet"}) for v in pet.vaccinations]
                                    export_hash = hash_service.hash_record({"pet_id": str(pet.id), "vaccinations": aggregate_data})
                                    path = pdf_service.generate_vaccination_report(pet.breed or "Pet", pet.vaccinations, export_hash)
                                    ui.download(path, f"{pet.breed}_vaccinations.pdf")

                                ui.button('Export Verified PDF', icon='download', on_click=export_pdf).props('flat small')

                            if not pet.vaccinations:
                                ui.label('No vaccinations recorded.').classes('pl-text-hint italic')
                            else:
                                for v in pet.vaccinations:
                                    with ui.card().classes('w-full mb-2 p-3').style('background: var(--pl-surface-variant); border: none; box-shadow: none;'):
                                        with ui.row().classes('justify-between w-full'):
                                            with ui.column():
                                                ui.label(v.vaccine_name).classes('font-bold')
                                                ui.label(f"By {v.administering_vet} @ {v.clinic_name}").classes('pl-text-xs')
                                            with ui.column().classes('items-end'):
                                                ui.label(f"Expires: {v.expiration_date.date()}").classes('pl-text-xs font-bold').style('color: var(--pl-primary)')
                                                ui.label(f"Hash: {v.record_hash[:8]}...").classes('pl-mono')

                            with ui.expansion('Add Vaccination Record', icon='add').classes('w-full mt-4'):
                                v_name = ui.input('Vaccine Name (e.g. Rabies 3yr)').classes('w-full')
                                v_man = ui.input('Manufacturer').classes('w-full')
                                v_serial = ui.input('Serial #').classes('w-full')
                                v_lot = ui.input('Lot #').classes('w-full')
                                v_date = ui.input('Date Given (YYYY-MM-DD)').classes('w-full')
                                v_exp = ui.input('Expiration Date (YYYY-MM-DD)').classes('w-full')
                                v_vet = ui.input('Administering Vet').classes('w-full')
                                v_license = ui.input('Vet License #').classes('w-full')
                                v_clinic = ui.input('Clinic Name').classes('w-full')
                                v_phone = ui.input('Clinic Phone').classes('w-full')

                                async def save_vaccination():
                                    try:
                                        new_v = Vaccination(
                                            pet_id=pet.id,
                                            vaccine_name=v_name.value,
                                            manufacturer=v_man.value,
                                            serial_number=v_serial.value,
                                            lot_number=v_lot.value,
                                            date_given=datetime.strptime(v_date.value, '%Y-%m-%d'),
                                            expiration_date=datetime.strptime(v_exp.value, '%Y-%m-%d'),
                                            administering_vet=v_vet.value,
                                            vet_license=v_license.value,
                                            clinic_name=v_clinic.value,
                                            clinic_phone=v_phone.value
                                        )
                                        record_data = new_v.dict(exclude={"id", "pet_id", "record_hash", "pet"})
                                        new_v.record_hash = hash_service.hash_record(record_data)

                                        session.add(new_v)
                                        session.add(LedgerEvent(pet_id=pet.id, event_type="VACCINATION", description=f"Vaccination added: {v_name.value}"))
                                        session.commit()
                                        ui.notify('Vaccination record added to ledger!', type='positive')
                                        ui.navigate.to(f'/pet/{pet.id}')
                                    except Exception as e:
                                        ui.notify(f'Error: {str(e)}', type='negative')

                                ui.button('Commit to Ledger', on_click=save_vaccination).classes('w-full mt-2 pl-btn-primary')

                    # Right Column: Audit Trail
                    with ui.column().classes('w-64 gap-6'):
                        with ui.card().classes('w-full p-6'):
                            ui.label('Audit Trail').classes('pl-section-title pl-border-section')
                            for event in sorted(pet.ledger_events, key=lambda x: x.timestamp, reverse=True):
                                with ui.column().classes('mb-3'):
                                    with ui.row().classes('justify-between w-full'):
                                        ui.label(event.event_type).classes('pl-mono font-bold')
                                        ui.label(event.timestamp.strftime('%H:%M')).classes('pl-mono')
                                    ui.label(event.description).classes('pl-text-xs')

                            if not pet.ledger_events:
                                ui.label('No events recorded.').classes('pl-text-hint italic')

                ui.button('Back to Dashboard', on_click=lambda: ui.navigate.to('/dashboard')).classes('mt-8').props('flat')
        nav_footer()
