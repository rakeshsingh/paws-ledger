from nicegui import ui
from sqlmodel import Session, select
from ..database import engine
from ..models import Vaccination
from .header import nav_header
from .footer import nav_footer


def init_verify_page():
    @ui.page('/verify')
    async def verify_page():
        nav_header()
        with ui.column().classes('w-full items-center p-8 max-w-2xl mx-auto'):
            ui.label('Verify Vaccination Record').classes('pl-page-title mb-4')
            ui.label(
                'Enter the SHA-256 hash found at the bottom of a PawsLedger PDF export to verify its authenticity.'
            ).classes('pl-text-hint mb-8 text-center')

            hash_input = ui.input('Verification Hash').classes('w-full mb-4').props('outlined')

            results = ui.column().classes('w-full mt-4')

            async def verify():
                results.clear()
                if not hash_input.value:
                    return

                with Session(engine) as session:
                    vax = session.exec(select(Vaccination).where(Vaccination.record_hash == hash_input.value)).first()

                    if vax:
                        with results, ui.card().classes('w-full p-6').style('background: #f0fdf4; border-color: #bbf7d0;'):
                            with ui.row().classes('items-center gap-2 mb-2'):
                                ui.icon('verified').style('color: #16a34a')
                                ui.label('RECORD VERIFIED').classes('font-bold').style('color: #15803d')
                            ui.label(f"Vaccine: {vax.vaccine_name}")
                            ui.label(f"Pet ID: {vax.pet_id}")
                            ui.label(f"Date Given: {vax.date_given.date()}")
                            ui.label(f"Clinic: {vax.clinic_name}")
                    else:
                        with results, ui.card().classes('w-full p-6').style('background: #fef2f2; border-color: #fecaca;'):
                            with ui.row().classes('items-center gap-2 mb-2'):
                                ui.icon('error').style('color: #dc2626')
                                ui.label('VERIFICATION FAILED').classes('font-bold').style('color: #b91c1c')
                            ui.label('The provided hash does not match any records in our ledger.')

            ui.button('Verify Record', on_click=verify).classes('w-full pl-btn-primary')
        nav_footer()
