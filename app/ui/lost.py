from nicegui import ui, app
from sqlmodel import Session, select
from ..database import engine
from ..models import Pet
from .layout import page_shell


def init_lost_page() -> None:
    @ui.page('/lost')
    async def lost_pets_page() -> None:
        with page_shell():
            # Page header
            with ui.column().classes('w-full items-center mb-10'):
                ui.label('Pet Recovery').classes('pl-heading-3xl').style(
                    'text-align: center;'
                )
                ui.label(
                    'Found a pet? Use our global lookup or scan their QR/NFC tag '
                    'to notify the owner instantly.'
                ).style(
                    'font-size: 18px; line-height: 1.6; color: #57423d; '
                    'text-align: center; margin-top: 4px; max-width: 600px;'
                )

            # Search section
            with ui.element('div').classes(
                'w-full p-10 rounded-xl items-center mb-8'
            ).style(
                'background: #fff7ed; border: 1px solid rgba(251,191,36,0.2);'
            ):
                with ui.column().classes('w-full items-center gap-4'):
                    ui.icon('search').style(
                        'font-size: 48px; color: #83250e;'
                    )
                    ui.label('Search the Global Ledger').classes('pl-heading-xl')
                    ui.label(
                        'Enter the 15-digit microchip ID to search across '
                        'PawsLedger and the AAHA Universal Network.'
                    ).style(
                        'font-size: 14px; color: #57423d; text-align: center;'
                    )

                    with ui.row().classes('items-center gap-3 mt-4').style(
                        'width: 100%; max-width: 480px;'
                    ):
                        chip_input = ui.input(
                            placeholder='Enter Microchip ID'
                        ).classes('flex-1').props('outlined dense')

                        search_btn = ui.button(
                            'Search', icon='search',
                            on_click=lambda: lookup(),
                        ).style(
                            'background: #a03a21; color: white; font-weight: 600; '
                            'padding: 10px 24px; border-radius: 8px;'
                        ).props('no-caps')

                    # Results area
                    results_card = ui.column().classes('w-full mt-6').style(
                        'display: none; max-width: 480px;'
                    )

                    async def lookup():
                        chip_id = chip_input.value.strip() if chip_input.value else ''
                        if not chip_id:
                            ui.notify('Please enter a Chip ID.', type='warning')
                            return

                        search_btn.disable()
                        search_btn.text = 'Searching...'

                        try:
                            with Session(engine) as session:
                                pet = session.exec(
                                    select(Pet).where(Pet.chip_id == chip_id)
                                ).first()

                                results_card.clear()
                                results_card.style('display: block')

                                with results_card:
                                    if pet:
                                        with ui.element('div').classes('p-5 rounded-xl').style(
                                            'background: white; border: 1px solid #dec0b9;'
                                        ):
                                            ui.label('Verified PawsLedger Record').style(
                                                'font-size: 12px; font-weight: 700; text-transform: uppercase; '
                                                'color: #a03a21; background: rgba(160,58,33,0.1); '
                                                'padding: 4px 10px; border-radius: 99px; display: inline-block; margin-bottom: 8px;'
                                            )
                                            ui.label(f'{pet.name} • {pet.pet_species}').style(
                                                'font-size: 20px; font-weight: 700; color: #171c21;'
                                            )
                                            ui.label(f'Breed: {pet.breed} | Status: {pet.identity_status}').style(
                                                'font-size: 14px; color: #57423d; margin-top: 4px;'
                                            )

                                            is_logged_in = bool(app.storage.user.get('email'))
                                            if is_logged_in:
                                                ui.button(
                                                    'View Full Ledger',
                                                    on_click=lambda pid=pet.id: ui.navigate.to(f'/pet/{pid}'),
                                                ).classes('w-full mt-4').style(
                                                    'background: #a03a21; color: white;'
                                                ).props('no-caps')
                                            else:
                                                ui.label(
                                                    'Log in to view full details and contact the owner.'
                                                ).style('font-size: 13px; color: #57423d; margin-top: 8px;')
                                                ui.button(
                                                    'Login to View Details & Nudge Owner', icon='login',
                                                    on_click=lambda: ui.navigate.to('/login'),
                                                ).classes('w-full mt-3').style(
                                                    'background: #a03a21; color: white;'
                                                ).props('no-caps')
                                    else:
                                        from ..api.v1.routes import aaha_client
                                        aaha_data = await aaha_client.lookup(chip_id)
                                        if aaha_data:
                                            with ui.element('div').classes('p-5 rounded-xl').style(
                                                'background: white; border: 1px solid #dec0b9;'
                                            ):
                                                ui.label('AAHA Nationwide Network').style(
                                                    'font-size: 12px; font-weight: 700; text-transform: uppercase; '
                                                    'color: #83250e; background: #fff7ed; '
                                                    'padding: 4px 10px; border-radius: 99px; display: inline-block; margin-bottom: 8px;'
                                                )
                                                ui.label('Identity Found Externally').style(
                                                    'font-size: 20px; font-weight: 700; color: #171c21;'
                                                )
                                                data = aaha_data.get('data', aaha_data)
                                                for label, value in [
                                                    ('Manufacturer', data.get('manufacturer')),
                                                    ('Status', data.get('status')),
                                                    ('Last Seen', data.get('last_seen')),
                                                ]:
                                                    if value:
                                                        with ui.row().classes('w-full justify-between py-1'):
                                                            ui.label(label).style('font-weight: 600; color: #57423d;')
                                                            ui.label(str(value)).style('color: #171c21;')

                                                ui.separator().classes('my-3')
                                                ui.label(
                                                    'This pet is not yet on PawsLedger. '
                                                    'Register it to create a secure digital identity.'
                                                ).style('font-size: 13px; font-style: italic; color: #57423d;')
                                        else:
                                            with ui.element('div').classes('p-5 rounded-xl').style(
                                                'background: white; border: 1px solid #e7e5e4;'
                                            ):
                                                ui.icon('search_off').style('font-size: 32px; color: #8a716c;')
                                                ui.label('No registration found').style(
                                                    'font-size: 16px; font-weight: 600; color: #171c21; margin-top: 8px;'
                                                )
                                                ui.label(
                                                    f'Chip ID "{chip_id}" was not found in PawsLedger or the AAHA network. '
                                                    'Double-check the number and try again.'
                                                ).style('font-size: 14px; color: #57423d; margin-top: 4px;')
                        finally:
                            search_btn.enable()
                            search_btn.text = 'Search'


            # Info cards
            with ui.row().classes('w-full gap-6 flex-wrap'):
                # Found a pet
                with ui.element('div').classes('flex-1 p-6 rounded-xl').style(
                    'background: white; box-shadow: 0 4px 12px rgba(0,0,0,0.05); '
                    'border-left: 4px solid #a03a21; min-width: 280px;'
                ):
                    with ui.row().classes('items-center gap-2 mb-4'):
                        ui.icon('pets').style('font-size: 24px; color: var(--pl-primary);')
                        ui.label('Found a Pet?').classes('pl-heading-lg')
                    for step in [
                        'Check for a PawsLedger QR or NFC tag on the collar.',
                        'Scan with your phone camera or tap with NFC.',
                        'Use the secure nudge form to alert the owner.',
                        'Take the pet to any vet to scan the microchip.',
                    ]:
                        with ui.row().classes('items-start gap-3 mb-3'):
                            ui.icon('check_circle').style(
                                'font-size: 16px; color: #16a34a; margin-top: 2px;'
                            )
                            ui.label(step).style(
                                'font-size: 14px; color: #57423d; line-height: 1.5;'
                            )

                # Owner privacy
                with ui.element('div').classes('flex-1 p-6 rounded-xl').style(
                    'background: white; box-shadow: 0 4px 12px rgba(0,0,0,0.05); '
                    'border-left: 4px solid #7d5800; min-width: 280px;'
                ):
                    with ui.row().classes('items-center gap-2 mb-4'):
                        ui.icon('security').style('font-size: 24px; color: var(--pl-secondary);')
                        ui.label('Owner Privacy').classes('pl-heading-lg')
                    ui.label(
                        'We never expose owner names, phone numbers, or addresses '
                        'to finders. All communication goes through our secure '
                        'relay system. The owner receives an email notification '
                        'with your message and can choose how to respond.'
                    ).style(
                        'font-size: 14px; line-height: 1.6; color: #57423d;'
                    )
                    with ui.row().classes('items-center gap-2 mt-4 pt-3').style(
                        'border-top: 1px solid #e7e5e4;'
                    ):
                        ui.icon('verified_user').style(
                            'font-size: 16px; color: #7d5800;'
                        )
                        ui.label(
                            'Identity-verified nudges only — no anonymous spam.'
                        ).style(
                            'font-size: 12px; font-weight: 600; color: #7d5800;'
                        )

