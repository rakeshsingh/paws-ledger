from nicegui import ui
from .header import nav_header
from .footer import nav_footer


def init_about_page() -> None:
    @ui.page('/about')
    async def about_page() -> None:
        nav_header()

        with ui.element('main').classes('w-full max-w-4xl mx-auto px-6 py-12'):
            # Hero section
            with ui.column().classes('w-full items-center mb-12'):
                ui.label('About PawsLedger').style(
                    "font-family: 'Plus Jakarta Sans'; font-size: 40px; "
                    "font-weight: 700; line-height: 1.2; letter-spacing: -0.02em; "
                    "color: #171c21; text-align: center;"
                )
                ui.label(
                    'A universal microchip registry and recovery platform — '
                    'the single source of truth for pet identification.'
                ).style(
                    'font-size: 18px; line-height: 1.6; color: #57423d; '
                    'text-align: center; margin-top: 0.5rem; max-width: 640px;'
                )

            # Mission cards
            with ui.row().classes('w-full gap-6 mb-12 flex-wrap'):
                for icon_name, title, description in [
                    (
                        'hub',
                        'Decoupled Identity',
                        'Pet records separated from proprietary manufacturer databases. '
                        'Your data belongs to you, not a chip vendor.',
                    ),
                    (
                        'swap_horiz',
                        'Trusted Transfer',
                        'Secure ownership changes with full audit trail. '
                        'Every handoff is cryptographically recorded.',
                    ),
                    (
                        'share',
                        'Seamless Access',
                        'Time-bound access for vets, sitters, and caregivers. '
                        'Share records without sharing your identity.',
                    ),
                ]:
                    with ui.element('div').classes(
                        'flex-1 p-6 rounded-xl'
                    ).style(
                        'background: #f0f4fb; border: 1px solid rgba(222,192,185,0.3); '
                        'min-width: 200px;'
                    ):
                        with ui.element('div').classes(
                            'flex items-center justify-center rounded-full mb-4'
                        ).style(
                            'width: 48px; height: 48px; background: #ffdad2;'
                        ):
                            ui.icon(icon_name).style(
                                'font-size: 24px; color: #a03a21;'
                            )
                        ui.label(title).style(
                            "font-family: 'Plus Jakarta Sans'; font-size: 18px; "
                            "font-weight: 600; color: #171c21; margin-bottom: 0.5rem;"
                        )
                        ui.label(description).style(
                            'font-size: 14px; line-height: 1.6; color: #57423d;'
                        )

            # How it works
            with ui.element('div').classes('w-full p-10 rounded-xl mb-10').style(
                'background: white; box-shadow: 0 4px 12px rgba(0,0,0,0.05); '
                'border-left: 4px solid #7d5800;'
            ):
                ui.label('How It Works').style(
                    "font-family: 'Plus Jakarta Sans'; font-size: 24px; "
                    "font-weight: 600; color: #171c21; margin-bottom: 1.5rem;"
                )

                for num, title, desc in [
                    (
                        '1',
                        'Register Your Pet',
                        'Add your pet with their 15-digit microchip number, breed, '
                        'and care details. Link physical NFC or QR tags for instant access.',
                    ),
                    (
                        '2',
                        'Build the Ledger',
                        'Upload vaccination records, set medical alerts, and generate '
                        'SHA-256 sealed PDF exports for official use.',
                    ),
                    (
                        '3',
                        'Stay Connected',
                        'If your pet is found, finders search the chip or scan the tag. '
                        'We facilitate safe, anonymous contact through our secure relay.',
                    ),
                ]:
                    with ui.row().classes('gap-5 mb-6 items-start'):
                        with ui.element('div').classes(
                            'flex items-center justify-center rounded-full flex-shrink-0'
                        ).style(
                            'width: 40px; height: 40px; background: #fff7ed; '
                            'border: 2px solid #7d5800; color: #7d5800; '
                            'font-weight: 700; font-size: 16px;'
                        ):
                            ui.label(num)
                        with ui.column().classes('gap-1'):
                            ui.label(title).style(
                                'font-weight: 600; font-size: 16px; color: #171c21;'
                            )
                            ui.label(desc).style(
                                'font-size: 14px; line-height: 1.6; color: #57423d;'
                            )

            # Standards section
            with ui.element('div').classes('w-full p-8 rounded-xl').style(
                'background: #fff7ed; border: 1px solid rgba(251,191,36,0.2);'
            ):
                with ui.row().classes('items-center gap-2 mb-4'):
                    ui.icon('verified_user').style('font-size: 24px; color: #9a3412;')
                    ui.label('Industry Standards').style(
                        "font-family: 'Plus Jakarta Sans'; font-size: 20px; "
                        "font-weight: 600; color: #9a3412;"
                    )
                ui.label(
                    'PawsLedger integrates with the AAHA Universal Pet Microchip '
                    'Lookup network and supports ISO 11784/11785 standards for '
                    '134.2 kHz FDX-B transponders. All vaccination exports follow '
                    'NASPHV Form 51 requirements.'
                ).style('font-size: 14px; line-height: 1.6; color: #57423d;')

        nav_footer()
