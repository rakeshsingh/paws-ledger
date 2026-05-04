from nicegui import ui, app
from starlette.requests import Request
from sqlmodel import Session, select
from ..database import engine
from ..models import Pet, User, LedgerEvent
from .header import nav_header
from .footer import nav_footer
from .common import try_restore_session

# Species icon mapping for placeholder avatars
SPECIES_ICONS = {
    'DOG': 'pets',       # paw icon — dogs
    'CAT': 'emoji_nature',  # nature icon — cats
}
SPECIES_ICON_DEFAULT = 'pets'

# Background tints per species for the icon placeholder
SPECIES_BG = {
    'DOG': '#ffdad2',
    'CAT': '#ffdea9',
}
SPECIES_BG_DEFAULT = '#eaeef5'

# Icon foreground color per species
SPECIES_FG = {
    'DOG': '#a03a21',
    'CAT': '#7d5800',
}
SPECIES_FG_DEFAULT = '#57423d'

BORDER_COLORS = ['#a03a21', '#7d5800', '#5d5c58', '#a03a21', '#7d5800']


def init_dashboard_page():
    @ui.page('/dashboard')
    async def dashboard(request: Request):
        if not try_restore_session(request):
            ui.navigate.to('/login')
            return

        if app.storage.user.get('greet_user'):
            ui.notify(f"Welcome back, {app.storage.user['name']}!", type='positive')
            app.storage.user['greet_user'] = False

        nav_header()

        with Session(engine) as session:
            user = session.exec(
                select(User).where(User.email == app.storage.user['email'])
            ).first()
            if not user:
                user = User(
                    sub=f"manual|{app.storage.user['email']}",
                    email=app.storage.user['email'],
                    name=app.storage.user['name'],
                )
                session.add(user)
                session.commit()
                session.refresh(user)

            pets = session.exec(select(Pet).where(Pet.owner_id == user.id)).all()

            # Gather recent ledger events across all pets
            pet_ids = [p.id for p in pets]
            recent_events = []
            if pet_ids:
                from sqlmodel import col
                recent_events = session.exec(
                    select(LedgerEvent)
                    .where(col(LedgerEvent.pet_id).in_(pet_ids))
                    .order_by(LedgerEvent.timestamp.desc())
                    .limit(5)
                ).all()

            # Calculate vaccination health score
            total_vax = 0
            current_vax = 0
            from datetime import datetime
            for pet in pets:
                for v in pet.vaccinations:
                    total_vax += 1
                    if v.expiration_date > datetime.utcnow():
                        current_vax += 1
            health_pct = round((current_vax / total_vax) * 100) if total_vax > 0 else 0
            health_label = 'Optimal Health' if health_pct >= 80 else ('Needs Attention' if health_pct >= 50 else 'Action Required')
            health_sub = 'All shots current' if health_pct >= 80 else f'{current_vax}/{total_vax} vaccinations current'

        # ── Main content ──
        with ui.element('main').classes('w-full max-w-7xl mx-auto px-6 py-10'):
            with ui.row().classes('w-full gap-10 items-start'):

                # ── Left: Pet Cards (8/12) ──
                with ui.column().classes('flex-1 gap-6').style('min-width: 0;'):
                    # Header row
                    with ui.row().classes('w-full justify-between items-center'):
                        with ui.column().classes('gap-1'):
                            ui.label('My Pets').style(
                                "font-family: 'Plus Jakarta Sans'; font-size: 40px; "
                                "font-weight: 700; line-height: 1.2; letter-spacing: -0.02em; color: #171c21;"
                            )
                            ui.label("Manage and view your pets' medical records.").style(
                                'color: #57423d; font-size: 16px;'
                            )

                    # Pet cards grid
                    with ui.row().classes('w-full gap-6 flex-wrap'):
                        for idx, pet in enumerate(pets):
                            border_color = BORDER_COLORS[idx % len(BORDER_COLORS)]
                            badge_text = 'Verified Identity' if pet.identity_status == 'VERIFIED' else 'Unverified'
                            has_photo = bool(pet.photo_url)

                            with ui.card().classes(
                                'overflow-hidden flex flex-col cursor-pointer'
                            ).style(
                                f'border-left: 4px solid {border_color}; border-radius: 0.75rem; '
                                'box-shadow: 0 4px 12px rgba(0,0,0,0.05); width: calc(50% - 0.75rem); '
                                'min-width: 260px; transition: box-shadow 0.3s;'
                            ).on('click', lambda p=pet: ui.navigate.to(f'/pet/{p.id}')):
                                # Pet photo or species icon placeholder
                                with ui.element('div').style(
                                    'height: 192px; overflow: hidden; position: relative;'
                                ):
                                    if has_photo:
                                        ui.image(pet.photo_url).style(
                                            'width: 100%; height: 100%; object-fit: cover;'
                                        )
                                    else:
                                        # Icon-based placeholder
                                        species = pet.pet_species or 'DOG'
                                        bg = SPECIES_BG.get(species, SPECIES_BG_DEFAULT)
                                        fg = SPECIES_FG.get(species, SPECIES_FG_DEFAULT)
                                        icon_name = SPECIES_ICONS.get(species, SPECIES_ICON_DEFAULT)
                                        with ui.element('div').classes(
                                            'flex items-center justify-center w-full h-full'
                                        ).style(f'background: {bg};'):
                                            ui.icon(icon_name).style(
                                                f'font-size: 72px; color: {fg}; opacity: 0.7;'
                                            )
                                    # Badge
                                    ui.label(badge_text).style(
                                        'position: absolute; top: 1rem; right: 1rem; '
                                        'background: #ffc65d; color: #755100; font-size: 10px; '
                                        'text-transform: uppercase; letter-spacing: 0.1em; '
                                        'font-weight: 700; padding: 4px 12px; border-radius: 9999px;'
                                    )

                                # Info
                                with ui.column().classes('p-6 gap-1'):
                                    ui.label(pet.name or 'Unnamed').style(
                                        "font-family: 'Plus Jakarta Sans'; font-size: 24px; "
                                        "font-weight: 600; color: #171c21;"
                                    )
                                    ui.label(
                                        f'{pet.pet_species}, {pet.breed or "Unknown"}'
                                    ).style('color: #57423d; font-size: 16px;')

                                    with ui.row().classes('items-center gap-2 pt-4'):
                                        ui.label('View Records').style(
                                            'color: #a03a21; font-weight: 600; font-size: 14px;'
                                        )
                                        ui.icon('arrow_forward').style(
                                            'font-size: 14px; color: #a03a21;'
                                        )

                        # Add New Pet placeholder
                        with ui.card().classes(
                            'flex flex-col items-center justify-center cursor-pointer'
                        ).style(
                            'border: 2px dashed #dec0b9; border-radius: 0.75rem; '
                            'width: calc(50% - 0.75rem); min-width: 260px; min-height: 300px; '
                            'background: transparent; box-shadow: none;'
                        ).on('click', lambda: ui.navigate.to('/register')):
                            with ui.element('div').classes(
                                'flex items-center justify-center rounded-full'
                            ).style(
                                'width: 64px; height: 64px; background: #eaeef5;'
                            ):
                                ui.icon('add').style('font-size: 36px; color: #57423d;')
                            ui.label('Add New Pet').style(
                                'font-weight: 600; color: #171c21; margin-top: 1rem;'
                            )
                            ui.label('Register a new companion').style(
                                'font-size: 12px; color: #57423d;'
                            )

                # ── Right: Sidebar Widgets (4/12) ──
                with ui.column().classes('gap-6').style('width: 340px; flex-shrink: 0;'):

                    # Recent Activity Widget
                    with ui.card().classes('w-full p-6').style(
                        'border-radius: 0.75rem; background: #f0f4fb; '
                        'border: 1px solid rgba(222,192,185,0.3);'
                    ):
                        with ui.row().classes('items-center gap-2 mb-4'):
                            ui.icon('history').style('color: #a03a21;')
                            ui.label('Recent Activity').style(
                                "font-family: 'Plus Jakarta Sans'; font-size: 24px; "
                                "font-weight: 600; color: #171c21;"
                            )

                        if recent_events:
                            with ui.column().classes('gap-4'):
                                event_icons = {
                                    'VACCINATION': ('vaccines', '#c15237', '#fffbff'),
                                    'EMERGENCY_SCAN': ('qr_code_scanner', '#7d5800', '#ffffff'),
                                    'HEARTBEAT_ACCESS': ('medical_services', '#ffc65d', '#755100'),
                                    'OWNERSHIP_CHANGE': ('swap_horiz', '#767470', '#fcffe0'),
                                    'WEIGHT_CHECK': ('monitor_weight', '#ffc65d', '#755100'),
                                }
                                for event in recent_events:
                                    icon_name, bg_color, fg_color = event_icons.get(
                                        event.event_type, ('description', '#767470', '#fcffe0')
                                    )
                                    with ui.row().classes('gap-4'):
                                        with ui.element('div').classes(
                                            'flex items-center justify-center rounded-full flex-shrink-0'
                                        ).style(
                                            f'width: 32px; height: 32px; background: {bg_color}; color: {fg_color};'
                                        ):
                                            ui.icon(icon_name).style('font-size: 16px;')
                                        with ui.column().classes('gap-0'):
                                            ui.label(event.description).style(
                                                'font-weight: 600; font-size: 14px; color: #171c21;'
                                            )
                                            ui.label(
                                                event.timestamp.strftime('%b %d, %Y • %H:%M')
                                            ).style('font-size: 12px; color: #57423d;')
                        else:
                            ui.label('No recent activity.').style(
                                'color: #57423d; font-style: italic; font-size: 14px;'
                            )

                    # Medical Status Widget
                    with ui.card().classes('w-full p-6 relative overflow-hidden').style(
                        'border-radius: 0.75rem; background: #dee3e9; '
                        'border: 1px solid rgba(222,192,185,0.3);'
                    ):
                        with ui.column().classes('relative z-10 gap-1'):
                            ui.label('Medical Status').style(
                                "font-family: 'Plus Jakarta Sans'; font-size: 24px; "
                                "font-weight: 600; color: #171c21;"
                            )
                            ui.label('Your overall pet health status').style(
                                'font-size: 12px; color: #57423d; margin-bottom: 1rem;'
                            )

                            with ui.row().classes('items-center gap-4 p-4 rounded-lg').style(
                                'background: rgba(255,255,255,0.4); backdrop-filter: blur(4px);'
                            ):
                                # Health ring
                                ring_color = '#16a34a' if health_pct >= 80 else ('#ca8a04' if health_pct >= 50 else '#dc2626')
                                with ui.element('div').classes(
                                    'flex items-center justify-center rounded-full'
                                ).style(
                                    f'width: 48px; height: 48px; '
                                    f'border: 4px solid {ring_color}; border-top-color: transparent;'
                                ):
                                    ui.label(f'{health_pct}%').style(
                                        'font-weight: 700; font-size: 14px; color: #171c21;'
                                    )
                                with ui.column().classes('gap-0'):
                                    ui.label(health_label).style(
                                        'font-weight: 600; font-size: 14px; color: #171c21;'
                                    )
                                    ui.label(health_sub).style(
                                        'font-size: 12px; color: #57423d;'
                                    )

                        # Decorative background icon
                        ui.icon('pets').style(
                            'position: absolute; right: -10px; bottom: -10px; '
                            'font-size: 160px; opacity: 0.1; color: #171c21;'
                        )

              

        nav_footer()
