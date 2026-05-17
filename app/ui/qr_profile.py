from nicegui import ui, app
from starlette.requests import Request
from sqlmodel import Session, select
from ..database import engine
from ..models import Pet, PetTag, LedgerEvent, _utc_now
from .header import nav_header
from .footer import nav_footer
from .common import email_service, try_restore_session
from .pet_profile import _render_nudge_form
import uuid


def init_qr_profile_page() -> None:
    @ui.page('/qr/{tag_id}')
    async def public_profile(request: Request, tag_id: str) -> None:
        try_restore_session(request)
        nav_header()

        with Session(engine) as session:
            pet = None

            tag = session.exec(
                select(PetTag).where(PetTag.tag_code == tag_id)
            ).first()
            if tag and tag.status == "ACTIVE":
                pet = tag.pet
            else:
                try:
                    pet_uuid = uuid.UUID(tag_id)
                    pet = session.exec(
                        select(Pet).where(Pet.id == pet_uuid)
                    ).first()
                except ValueError:
                    pass

            if not pet:
                with ui.element('main').classes('w-full max-w-4xl mx-auto px-6 py-12'):
                    with ui.column().classes('w-full items-center p-16'):
                        ui.icon('search_off').style(
                            'font-size: 64px; color: #a03a21; opacity: 0.5;'
                        )
                        ui.label('Tag Not Found').style(
                            "font-family: 'Plus Jakarta Sans'; font-size: 32px; "
                            "font-weight: 600; color: #171c21; margin-top: 1rem;"
                        )
                        ui.label(
                            'This tag is invalid, deactivated, or not linked to a pet.'
                        ).style('color: #57423d; margin-top: 0.5rem;')
                        ui.button(
                            'Search by Chip ID', icon='search',
                            on_click=lambda: ui.navigate.to('/'),
                        ).classes('mt-6').style(
                            'background: #a03a21; color: white; font-weight: 600; '
                            'padding: 10px 24px; border-radius: 8px;'
                        ).props('no-caps')
                nav_footer()
                return

            event = LedgerEvent(
                pet_id=pet.id, event_type="EMERGENCY_SCAN",
                description="Public QR/NFC scan detected",
            )
            session.add(event)
            session.commit()

            if pet.owner and pet.owner.email:
                await email_service.notify_owner_of_scan(
                    pet.owner.email, pet.breed or "Pet"
                )

            with ui.element('main').classes('w-full max-w-4xl mx-auto px-6 py-12'):
                # Emergency alert banner
                with ui.row().classes(
                    'w-full items-center gap-4 p-5 rounded-xl mb-8'
                ).style(
                    'background: #fff7ed; border: 1px solid rgba(251,191,36,0.2);'
                ):
                    ui.icon('notification_important').style(
                        'font-size: 32px; color: #9a3412;'
                    )
                    with ui.column().classes('gap-1'):
                        ui.label('This Pet is Registered on PawsLedger').style(
                            "font-family: 'Plus Jakarta Sans'; font-size: 20px; "
                            "font-weight: 600; color: #9a3412;"
                        )
                        ui.label(
                            'The owner has been notified of this scan. '
                            'Use the form below to send them a message.'
                        ).style('font-size: 14px; color: #57423d;')

                # Pet identification card
                with ui.element('div').classes('w-full p-8 rounded-xl mb-6').style(
                    'background: white; box-shadow: 0 4px 12px rgba(0,0,0,0.05); '
                    'border-left: 4px solid #a03a21;'
                ):
                    with ui.row().classes('gap-8 items-center'):
                        species = pet.pet_species or 'DOG'
                        icon_name = 'pets' if species == 'DOG' else 'emoji_nature'
                        bg = '#ffdad2' if species == 'DOG' else '#ffdea9'
                        fg = '#a03a21' if species == 'DOG' else '#7d5800'
                        with ui.element('div').classes(
                            'flex items-center justify-center rounded-full flex-shrink-0'
                        ).style(
                            f'width: 96px; height: 96px; background: {bg}; '
                            'border: 4px solid white; box-shadow: 0 4px 12px rgba(0,0,0,0.1);'
                        ):
                            ui.icon(icon_name).style(f'font-size: 48px; color: {fg};')

                        with ui.column().classes('gap-2'):
                            with ui.row().classes('items-center gap-3'):
                                ui.label(f'{pet.pet_species}').style(
                                    "font-family: 'Plus Jakarta Sans'; font-size: 28px; "
                                    "font-weight: 700; color: #171c21;"
                                )
                                ui.label('Registered').style(
                                    'padding: 4px 12px; background: #dcfce7; color: #166534; '
                                    'font-size: 12px; font-weight: 600; border-radius: 9999px;'
                                )
                            ui.label(
                                f'Breed: {pet.breed or "Unknown"}'
                            ).style('font-size: 16px; color: #57423d;')
                            ui.label(f'Chip ID: {pet.chip_id}').style(
                                'font-family: monospace; font-size: 14px; color: #8a716c;'
                            )
                            if pet.manufacturer:
                                ui.label(
                                    f'Manufacturer: {pet.manufacturer}'
                                ).style('font-size: 13px; color: #8a716c;')

                # Medical info
                if pet.vaccinations or pet.medical_conditions:
                    with ui.element('div').classes('w-full p-8 rounded-xl mb-6').style(
                        'background: white; box-shadow: 0 4px 12px rgba(0,0,0,0.05); '
                        'border-left: 4px solid #3b82f6;'
                    ):
                        ui.label('Medical Summary').style(
                            "font-family: 'Plus Jakarta Sans'; font-size: 20px; "
                            "font-weight: 600; color: #171c21; margin-bottom: 1rem;"
                        )

                        if pet.medical_conditions:
                            with ui.row().classes(
                                'w-full items-center gap-3 p-4 rounded-lg mb-4'
                            ).style('background: #fef2f2; border: 1px solid #fecaca;'):
                                ui.icon('priority_high').style(
                                    'font-size: 20px; color: #dc2626;'
                                )
                                ui.label(f'Medical Alert: {pet.medical_conditions}').style(
                                    'font-weight: 600; font-size: 14px; color: #b91c1c;'
                                )

                        if pet.vaccinations:
                            for v in pet.vaccinations:
                                is_current = v.expiration_date > _utc_now()
                                with ui.row().classes(
                                    'w-full items-center justify-between p-3 rounded-lg mb-2'
                                ).style('background: #f0f4fb;'):
                                    with ui.row().classes('items-center gap-3'):
                                        ui.icon('vaccines').style(
                                            'font-size: 18px; color: #3b82f6;'
                                        )
                                        ui.label(v.vaccine_name).style(
                                            'font-weight: 500; font-size: 14px;'
                                        )
                                    status_label = 'Current' if is_current else 'Expired'
                                    status_color = '#16a34a' if is_current else '#dc2626'
                                    ui.label(status_label).style(
                                        f'font-weight: 600; font-size: 13px; color: {status_color};'
                                    )

                # Nudge form
                with ui.element('div').classes('w-full p-8 rounded-xl').style(
                    'background: white; box-shadow: 0 4px 12px rgba(0,0,0,0.05); '
                    'border-left: 4px solid #7d5800;'
                ):
                    ui.label('Contact the Owner').style(
                        "font-family: 'Plus Jakarta Sans'; font-size: 20px; "
                        "font-weight: 600; color: #171c21; margin-bottom: 1rem;"
                    )
                    _render_nudge_form(pet)

                # Disclaimer
                with ui.row().classes(
                    'w-full items-center gap-2 mt-8 pt-6'
                ).style('border-top: 1px solid #e7e5e4;'):
                    ui.icon('info').style('font-size: 16px; color: #8a716c;')
                    ui.label(
                        'Information on this page is provided for emergency recovery only.'
                    ).style('font-size: 12px; color: #8a716c;')

        nav_footer()
