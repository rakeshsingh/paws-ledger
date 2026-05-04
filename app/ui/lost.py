from nicegui import ui
from .header import nav_header
from .footer import nav_footer


def init_lost_page():
    @ui.page('/lost')
    async def lost_pets_page():
        nav_header()
        with ui.column().classes('w-full items-center p-8 max-w-4xl mx-auto'):
            ui.label('Public Safety & Recovery').classes('pl-page-title mb-4')
            ui.label(
                'If you have found a pet, use our global lookup or scan their QR tag to notify the owner.'
            ).classes('pl-text-hint mb-8 text-center')

            with ui.card().classes('w-full p-8 items-center').style('background: var(--pl-surface-variant); border: none;'):
                ui.icon('search', size='48px').style('color: var(--pl-primary)')
                ui.label('Search the Global Ledger').classes('pl-section-title mt-4')
                chip_input = ui.input('Enter 15-digit Microchip ID').classes('w-64 mt-2')

                async def lookup():
                    if not chip_input.value:
                        return
                    ui.navigate.to(f'/?chip={chip_input.value}')

                ui.button('Search Nationwide Network', on_click=lookup).classes('mt-4 pl-btn-primary')

            with ui.row().classes('w-full gap-6 mt-8'):
                with ui.card().classes('flex-1 p-6'):
                    ui.label('Found a Pet?').classes('pl-section-title mb-2')
                    ui.label('1. Check for a PawsLedger QR tag.').classes('pl-text-hint')
                    ui.label('2. Scan with your phone camera.').classes('pl-text-hint')
                    ui.label('3. Tap "Contact Owner" to send an alert.').classes('pl-text-hint')

                with ui.card().classes('flex-1 p-6'):
                    ui.label('Owner Privacy').classes('pl-section-title mb-2')
                    ui.label(
                        'We never show owner phone numbers or addresses publicly. '
                        'Alerts are sent via our secure bridge.'
                    ).classes('pl-text-hint')

        nav_footer()
