from nicegui import ui
from .header import nav_header
from .footer import nav_footer


def init_lost_page() -> None:
    @ui.page('/lost')
    async def lost_pets_page() -> None:
        nav_header()

        with ui.element('main').classes('w-full max-w-4xl mx-auto px-6 py-12'):
            # Page header
            with ui.column().classes('w-full items-center mb-10'):
                ui.label('Pet Recovery').style(
                    "font-family: 'Plus Jakarta Sans'; font-size: 40px; "
                    "font-weight: 700; line-height: 1.2; letter-spacing: -0.02em; "
                    "color: #171c21; text-align: center;"
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
                        'font-size: 48px; color: #9a3412;'
                    )
                    ui.label('Search the Global Ledger').style(
                        "font-family: 'Plus Jakarta Sans'; font-size: 24px; "
                        "font-weight: 600; color: #171c21;"
                    )
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

                        async def lookup():
                            if not chip_input.value:
                                ui.notify(
                                    'Please enter a Chip ID.', type='warning'
                                )
                                return
                            ui.navigate.to(f'/?chip={chip_input.value}')

                        ui.button(
                            'Search', icon='search', on_click=lookup,
                        ).style(
                            'background: #a03a21; color: white; font-weight: 600; '
                            'padding: 10px 24px; border-radius: 8px;'
                        ).props('no-caps')

            # Info cards
            with ui.row().classes('w-full gap-6 flex-wrap'):
                # Found a pet
                with ui.element('div').classes('flex-1 p-6 rounded-xl').style(
                    'background: white; box-shadow: 0 4px 12px rgba(0,0,0,0.05); '
                    'border-left: 4px solid #a03a21; min-width: 280px;'
                ):
                    with ui.row().classes('items-center gap-2 mb-4'):
                        ui.icon('pets').style('font-size: 24px; color: #a03a21;')
                        ui.label('Found a Pet?').style(
                            "font-family: 'Plus Jakarta Sans'; font-size: 20px; "
                            "font-weight: 600; color: #171c21;"
                        )
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
                        ui.icon('security').style('font-size: 24px; color: #7d5800;')
                        ui.label('Owner Privacy').style(
                            "font-family: 'Plus Jakarta Sans'; font-size: 20px; "
                            "font-weight: 600; color: #171c21;"
                        )
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

        nav_footer()
