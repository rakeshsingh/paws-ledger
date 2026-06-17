from nicegui import ui
from sqlmodel import Session, select
from ..database import engine
from ..models import Vaccination
from .layout import page_shell


def init_verify_page() -> None:
    @ui.page('/verify')
    async def verify_page() -> None:
        with page_shell():
            # Page header
            with ui.column().classes('w-full items-center mb-10'):
                ui.label('Verify Vaccination Record').classes('pl-heading-3xl').style(
                    'text-align: center;'
                )
                ui.label(
                    'Enter the SHA-256 hash found at the bottom of a '
                    'PawsLedger PDF export to verify its authenticity.'
                ).classes('pl-body-base').style(
                    'font-size: var(--pl-text-lg); text-align: center; margin-top: 4px; max-width: 600px;'
                )

            # Verification form
            with ui.element('div').classes('w-full max-w-2xl mx-auto p-8 rounded-xl').style(
                'background: white; box-shadow: 0 4px 12px rgba(0,0,0,0.05); '
                'border-left: 4px solid #7d5800;'
            ):
                with ui.column().classes('w-full gap-1 mb-6'):
                    ui.label('Verification Hash').style(
                        'font-weight: 600; font-size: 14px; color: #171c21;'
                    )
                    hash_input = ui.input(
                        placeholder='e.g. a3f2b8c91d4e5f6...'
                    ).classes('w-full').props('outlined dense')
                    ui.label(
                        'Paste the full SHA-256 hash string from the PDF footer.'
                    ).style('font-size: 12px; color: #8a716c; margin-top: 4px;')

                results = ui.column().classes('w-full')

                async def verify():
                    results.clear()
                    if not hash_input.value or not hash_input.value.strip():
                        ui.notify('Please enter a hash value.', type='warning')
                        return

                    with Session(engine) as session:
                        vax = session.exec(
                            select(Vaccination).where(
                                Vaccination.record_hash == hash_input.value.strip()
                            )
                        ).first()

                        if vax:
                            with results:
                                with ui.element('div').classes(
                                    'w-full p-6 rounded-xl mt-4'
                                ).style(
                                    'background: white; border-left: 4px solid #16a34a; '
                                    'box-shadow: 0 4px 12px rgba(0,0,0,0.05);'
                                ):
                                    with ui.row().classes('items-center gap-3 mb-4'):
                                        ui.icon('verified').style(
                                            'font-size: 28px; color: #16a34a;'
                                        )
                                        ui.label('Record Verified').style(
                                            "font-family: var(--pl-font); "
                                            "font-size: var(--pl-text-lg); font-weight: 600; "
                                            "color: #166534;"
                                        )
                                    for label, value in [
                                        ('Vaccine', vax.vaccine_name),
                                        ('Date Given', str(vax.date_given.date())),
                                        ('Clinic', vax.clinic_name or 'Not specified'),
                                        ('Manufacturer', vax.manufacturer or 'Not specified'),
                                    ]:
                                        with ui.row().classes(
                                            'w-full items-center justify-between py-2'
                                        ).style('border-bottom: 1px solid #f0fdf4;'):
                                            ui.label(label).style(
                                                'font-size: 14px; color: #57423d;'
                                            )
                                            ui.label(value).style(
                                                'font-size: 14px; font-weight: 600; '
                                                'color: #171c21;'
                                            )
                        else:
                            with results:
                                with ui.element('div').classes(
                                    'w-full p-6 rounded-xl mt-4'
                                ).style(
                                    'background: white; border-left: 4px solid #dc2626; '
                                    'box-shadow: 0 4px 12px rgba(0,0,0,0.05);'
                                ):
                                    with ui.row().classes('items-center gap-3 mb-2'):
                                        ui.icon('error').style(
                                            'font-size: 28px; color: #dc2626;'
                                        )
                                        ui.label('Verification Failed').style(
                                            "font-family: var(--pl-font); "
                                            "font-size: var(--pl-text-lg); font-weight: 600; "
                                            "color: #b91c1c;"
                                        )
                                    ui.label(
                                        'The provided hash does not match any records '
                                        'in our ledger. The document may have been '
                                        'tampered with or the hash was entered incorrectly.'
                                    ).style(
                                        'font-size: 14px; color: #57423d; '
                                        'line-height: 1.5;'
                                    )

                ui.button(
                    'Verify Record', icon='fingerprint', on_click=verify,
                ).classes('w-full mt-4').style(
                    'background: #7d5800; color: white; font-weight: 600; '
                    'padding: 12px 24px; border-radius: 8px;'
                ).props('no-caps')

            # Info banner
            with ui.row().classes(
                'w-full max-w-2xl mx-auto items-start gap-3 mt-6 p-4 rounded-xl'
            ).style(
                'background: #fff7ed; border: 1px solid rgba(251,191,36,0.2);'
            ):
                ui.icon('info').style(
                    'font-size: 20px; color: #83250e; margin-top: 2px;'
                )
                ui.label(
                    'Each PawsLedger vaccination PDF contains a unique SHA-256 hash '
                    'computed from the record data. This ensures tamper-evident, '
                    'cryptographically verifiable medical documentation.'
                ).style('font-size: 12px; color: #57423d; line-height: 1.5;')

