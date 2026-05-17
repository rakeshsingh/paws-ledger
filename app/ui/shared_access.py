from nicegui import ui
from sqlmodel import Session, select
from ..database import engine
from ..models import LedgerEvent, SharedAccess, _utc_now
from .header import nav_header
from .footer import nav_footer
from .common import email_service


def init_shared_access_page() -> None:
    @ui.page('/shared/{token}')
    async def shared_profile(token: str) -> None:
        nav_header()

        with Session(engine) as session:
            statement = select(SharedAccess).where(SharedAccess.token == token)
            shared_access = session.exec(statement).first()

            if not shared_access or shared_access.expires_at < _utc_now():
                with ui.element('main').classes('w-full max-w-4xl mx-auto px-6 py-12'):
                    with ui.column().classes('w-full items-center p-16'):
                        ui.icon('link_off').style(
                            'font-size: 64px; color: #a03a21; opacity: 0.5;'
                        )
                        ui.label('Access Expired or Invalid').style(
                            "font-family: 'Plus Jakarta Sans'; font-size: 32px; "
                            "font-weight: 600; color: #171c21; margin-top: 1rem;"
                        )
                        ui.label(
                            'This shared care link is no longer active. '
                            'Please request a new link from the pet owner.'
                        ).style('color: #57423d; margin-top: 0.5rem; text-align: center;')
                nav_footer()
                return

            pet = shared_access.pet

            event = LedgerEvent(
                pet_id=pet.id,
                event_type="HEARTBEAT_ACCESS",
                description="Shared records accessed via time-bound link",
            )
            session.add(event)
            session.commit()

            if pet.owner and pet.owner.email:
                await email_service.notify_owner_of_access(
                    pet.owner.email, pet.breed or "Pet",
                    "Service Provider (Shared Link)",
                )

            with ui.element('main').classes('w-full max-w-4xl mx-auto px-6 py-12'):
                # Page header
                with ui.column().classes('w-full items-center mb-8'):
                    ui.label('Shared Care Access').style(
                        "font-family: 'Plus Jakarta Sans'; font-size: 40px; "
                        "font-weight: 700; line-height: 1.2; letter-spacing: -0.02em; "
                        "color: #171c21;"
                    )
                    ui.label(
                        f'Temporary care records for {pet.name or pet.breed or "Pet"}'
                    ).style(
                        'font-size: 18px; line-height: 1.6; color: #57423d; margin-top: 4px;'
                    )

                # Access status banner
                with ui.row().classes(
                    'w-full items-center gap-4 p-5 rounded-xl mb-8'
                ).style(
                    'background: #fff7ed; border: 1px solid rgba(251,191,36,0.2);'
                ):
                    ui.icon('schedule').style('font-size: 28px; color: #9a3412;')
                    with ui.column().classes('gap-1 flex-1'):
                        ui.label('Time-Limited Access').style(
                            'font-weight: 600; font-size: 16px; color: #9a3412;'
                        )
                        ui.label(
                            f'Expires: {shared_access.expires_at.strftime("%b %d, %Y at %H:%M UTC")}'
                        ).style('font-size: 13px; color: #57423d;')
                    ui.label('Active').style(
                        'padding: 4px 12px; background: #dcfce7; color: #166534; '
                        'font-size: 12px; font-weight: 600; border-radius: 9999px;'
                    )

                # Main content row
                with ui.row().classes('w-full gap-6 flex-wrap items-start'):
                    # Left: Pet info + vaccinations
                    with ui.column().classes('flex-1 gap-6').style('min-width: 360px;'):
                        # Pet identification
                        with ui.element('div').classes('w-full p-8 rounded-xl').style(
                            'background: white; box-shadow: 0 4px 12px rgba(0,0,0,0.05); '
                            'border-left: 4px solid #a03a21;'
                        ):
                            ui.label('Pet Information').style(
                                "font-family: 'Plus Jakarta Sans'; font-size: 20px; "
                                "font-weight: 600; color: #171c21; margin-bottom: 1rem;"
                            )
                            info_items = [
                                ('pets', 'Name', pet.name or 'Unknown'),
                                ('category', 'Species', pet.pet_species or 'Unknown'),
                                ('genetics', 'Breed', pet.breed or 'Unknown'),
                                ('cake', 'Date of Birth',
                                 pet.dob.strftime('%b %d, %Y') if pet.dob else 'Unknown'),
                                ('fingerprint', 'Chip ID', pet.chip_id),
                            ]
                            for icon_name, label, value in info_items:
                                with ui.row().classes(
                                    'w-full items-center justify-between py-3'
                                ).style('border-bottom: 1px solid #f0f4fb;'):
                                    with ui.row().classes('items-center gap-3'):
                                        ui.icon(icon_name).style(
                                            'font-size: 18px; color: #a03a21;'
                                        )
                                        ui.label(label).style(
                                            'font-size: 14px; color: #57423d;'
                                        )
                                    ui.label(value).style(
                                        'font-size: 14px; font-weight: 600; color: #171c21;'
                                    )

                        # Vaccination records
                        with ui.element('div').classes('w-full p-8 rounded-xl').style(
                            'background: white; box-shadow: 0 4px 12px rgba(0,0,0,0.05); '
                            'border-left: 4px solid #3b82f6;'
                        ):
                            ui.label('Vaccination Records').style(
                                "font-family: 'Plus Jakarta Sans'; font-size: 20px; "
                                "font-weight: 600; color: #171c21; margin-bottom: 1rem;"
                            )
                            if pet.vaccinations:
                                for v in pet.vaccinations:
                                    is_current = v.expiration_date > _utc_now()
                                    row_bg = '#f7f9ff' if is_current else '#fef2f2'
                                    exp_color = '#16a34a' if is_current else '#dc2626'
                                    with ui.row().classes(
                                        'w-full items-center justify-between p-4 rounded-lg mb-3'
                                    ).style(f'background: {row_bg};'):
                                        with ui.column().classes('gap-1'):
                                            ui.label(v.vaccine_name).style(
                                                'font-weight: 600; font-size: 14px; color: #171c21;'
                                            )
                                            ui.label(
                                                f'Given: {v.date_given.strftime("%Y-%m-%d")}'
                                            ).style('font-size: 12px; color: #57423d;')
                                        with ui.column().classes('items-end gap-1'):
                                            status = 'Current' if is_current else 'Expired'
                                            ui.label(status).style(
                                                f'font-weight: 600; font-size: 12px; color: {exp_color};'
                                            )
                                            ui.label(
                                                f'Exp: {v.expiration_date.strftime("%Y-%m-%d")}'
                                            ).style(f'font-size: 12px; color: {exp_color};')
                            else:
                                ui.label('No vaccination records available.').style(
                                    'color: #57423d; font-style: italic; font-size: 14px;'
                                )

                    # Right sidebar: Care info + medical alerts
                    with ui.column().classes('gap-6').style(
                        'width: 300px; flex-shrink: 0;'
                    ):
                        # Care info
                        with ui.element('div').classes('w-full p-6 rounded-xl').style(
                            'background: #f0f4fb; border: 1px solid rgba(222,192,185,0.3);'
                        ):
                            with ui.row().classes('items-center gap-2 mb-4'):
                                ui.icon('favorite').style(
                                    'font-size: 20px; color: #a03a21;'
                                )
                                ui.label('Care Guide').style(
                                    "font-family: 'Plus Jakarta Sans'; font-size: 18px; "
                                    "font-weight: 600; color: #171c21;"
                                )

                            care_items = [
                                ('bolt', 'Energy Level', pet.energy_level),
                                ('schedule', 'Max Alone Hours',
                                 f'{pet.max_alone_hours}h' if pet.max_alone_hours else None),
                                ('restaurant', 'Feeds Per Day',
                                 str(pet.feeds_per_day) if pet.feeds_per_day else None),
                                ('directions_run', 'Exercise', pet.exercise_needs),
                                ('mood', 'Temperament', pet.temperament),
                            ]
                            visible_care = [(i, l, v) for i, l, v in care_items if v]

                            if visible_care:
                                for icon_name, label, value in visible_care:
                                    with ui.row().classes(
                                        'items-center justify-between py-2'
                                    ).style('border-bottom: 1px solid rgba(222,192,185,0.2);'):
                                        with ui.row().classes('items-center gap-2'):
                                            ui.icon(icon_name).style(
                                                'font-size: 16px; color: #57423d;'
                                            )
                                            ui.label(label).style(
                                                'font-size: 13px; color: #57423d;'
                                            )
                                        ui.label(value).style(
                                            'font-size: 13px; font-weight: 600; color: #171c21;'
                                        )
                            else:
                                ui.label('No care info recorded.').style(
                                    'color: #57423d; font-style: italic; font-size: 13px;'
                                )

                            if pet.dietary_notes:
                                with ui.column().classes('mt-4 pt-3').style(
                                    'border-top: 1px solid rgba(222,192,185,0.2);'
                                ):
                                    ui.label('Dietary Notes').style(
                                        'font-size: 12px; font-weight: 600; color: #57423d;'
                                    )
                                    ui.label(pet.dietary_notes).style(
                                        'font-size: 13px; color: #171c21; margin-top: 4px;'
                                    )

                        # Medical alert
                        if pet.medical_conditions:
                            with ui.element('div').classes('w-full p-6 rounded-xl').style(
                                'background: #fef2f2; border: 1px solid #fecaca;'
                            ):
                                with ui.row().classes('items-center gap-2 mb-2'):
                                    ui.icon('warning').style(
                                        'font-size: 20px; color: #dc2626;'
                                    )
                                    ui.label('Medical Alert').style(
                                        'font-weight: 700; font-size: 16px; color: #b91c1c;'
                                    )
                                ui.label(pet.medical_conditions).style(
                                    'font-size: 14px; color: #b91c1c;'
                                )

                # Footer disclaimer
                with ui.row().classes(
                    'w-full items-center gap-2 mt-8 pt-6'
                ).style('border-top: 1px solid #e7e5e4;'):
                    ui.icon('info').style('font-size: 16px; color: #8a716c;')
                    ui.label(
                        'This is a time-limited care access link. '
                        'The pet owner has been notified of this access.'
                    ).style('font-size: 12px; color: #8a716c;')

        nav_footer()
