from nicegui import ui, app
from starlette.requests import Request
from sqlmodel import Session, select, col
from datetime import timedelta

from ..database import engine
from ..models import (
    Pet, User, LedgerEvent, NudgeSession, Subscription,
    VaccinationAlert, TagScan, _utc_now,
)
from .dashboard_shell import dashboard_shell
from .common import (
    try_restore_session,
    SPECIES_ICONS, SPECIES_ICON_DEFAULT, SPECIES_BG, SPECIES_BG_DEFAULT,
    SPECIES_FG, SPECIES_FG_DEFAULT,
)

# Species emoji for pet card avatars
_SPECIES_EMOJI = {'DOG': '\U0001F415', 'CAT': '\U0001F408'}
_SPECIES_EMOJI_DEFAULT = '\U0001F43E'


def _relative_time(dt) -> str:
    """Return a human-friendly relative time string."""
    now = _utc_now()
    diff = now - dt
    seconds = int(diff.total_seconds())
    if seconds < 60:
        return 'Just now'
    minutes = seconds // 60
    if minutes < 60:
        return f'{minutes}m ago'
    hours = minutes // 60
    if hours < 24:
        return f'{hours}h ago'
    days = hours // 24
    if days < 7:
        return f'{days}d ago'
    if days < 30:
        weeks = days // 7
        return f'{weeks}w ago'
    return dt.strftime('%b %d, %Y')


_DASHBOARD_CSS = '''
/* Quick stat cards */
.qs-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
}
.qs-card {
    background: #ffffff;
    border: 1px solid #e7e5e4;
    border-radius: 10px;
    padding: 16px 20px;
    display: flex;
    align-items: center;
    gap: 14px;
}
.qs-icon-box {
    width: 40px;
    height: 40px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}
.qs-info {
    display: flex;
    flex-direction: column;
    gap: 2px;
}
.qs-value {
    font-size: 20px;
    font-weight: 700;
    color: var(--pl-on-surface);
    line-height: 1.2;
}
.qs-label {
    font-size: 12px;
    color: var(--pl-text-hint);
    font-weight: 500;
}

/* Pet cards grid */
.pet-cards-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 16px;
}
.pet-card {
    background: #ffffff;
    border: 1px solid #e7e5e4;
    border-radius: 12px;
    padding: 20px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
    cursor: pointer;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
.pet-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 16px rgba(0,0,0,0.1);
}
.pet-card-register {
    background: transparent;
    border: 2px dashed #d6d3d1;
    border-radius: 12px;
    padding: 20px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
    cursor: pointer;
    transition: border-color 0.15s ease, background 0.15s ease;
    min-height: 180px;
}
.pet-card-register:hover {
    border-color: var(--pl-primary);
    background: rgba(160,58,33,0.03);
}
.pet-avatar {
    width: 64px;
    height: 64px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 32px;
    flex-shrink: 0;
}
.pet-card-name {
    font-size: 16px;
    font-weight: 700;
    color: var(--pl-on-surface);
    text-align: center;
}
.pet-card-breed {
    font-size: 12px;
    color: var(--pl-text-hint);
    text-align: center;
}
.pet-card-stats {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-top: 4px;
}
.pet-card-stat {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 11px;
    color: var(--pl-text-hint);
}

/* Bottom 2-col grid */
.bottom-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
}
.bottom-card {
    background: #ffffff;
    border: 1px solid #e7e5e4;
    border-radius: 12px;
    padding: 24px;
}
.bottom-card-title {
    font-size: 16px;
    font-weight: 700;
    color: var(--pl-on-surface);
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 8px;
}
.activity-item {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 8px 0;
}
.activity-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
    margin-top: 6px;
}
.activity-text {
    font-size: 13px;
    color: var(--pl-on-surface);
    font-weight: 500;
}
.activity-time {
    font-size: 11px;
    color: var(--pl-text-hint);
    margin-top: 2px;
}

/* Responsive */
@media (max-width: 1023px) {
    .qs-grid {
        grid-template-columns: repeat(2, 1fr);
    }
    .bottom-grid {
        grid-template-columns: 1fr;
    }
}
@media (max-width: 767px) {
    .qs-grid {
        grid-template-columns: 1fr;
    }
    .pet-cards-grid {
        grid-template-columns: 1fr;
    }
}
'''

# Dot colors by event type
_EVENT_DOT_COLORS = {
    'VACCINATION': '#16a34a',
    'EMERGENCY_SCAN': '#dc2626',
    'HEARTBEAT_ACCESS': '#2563eb',
    'OWNERSHIP_CHANGE': '#7c3aed',
    'WEIGHT_CHECK': '#ca8a04',
}


def init_dashboard_page() -> None:
    @ui.page('/dashboard')
    async def dashboard(request: Request) -> None:
        if not try_restore_session(request):
            ui.navigate.to('/login')
            return

        if app.storage.user.get('greet_user'):
            ui.notify(f"Welcome back, {app.storage.user['name']}!", type='positive')
            app.storage.user['greet_user'] = False

        # ── Data fetching ──
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
            pet_ids = [p.id for p in pets]

            # Recent ledger events
            recent_events = []
            if pet_ids:
                recent_events = session.exec(
                    select(LedgerEvent)
                    .where(col(LedgerEvent.pet_id).in_(pet_ids))
                    .order_by(LedgerEvent.timestamp.desc())
                    .limit(5)
                ).all()

            # Total vaccinations
            total_vax = 0
            for pet in pets:
                total_vax += len(pet.vaccinations)

            # Pending alerts count
            pending_alerts_count = 0
            user_sub = session.exec(
                select(Subscription).where(Subscription.user_id == user.id)
            ).first()
            user_tier = user_sub.tier if user_sub and user_sub.status == "active" else "free"
            is_verified = user_tier in ("verified", "guardian")

            if is_verified and pet_ids:
                pending_alerts_count = len(session.exec(
                    select(VaccinationAlert)
                    .where(
                        col(VaccinationAlert.pet_id).in_(pet_ids),
                        VaccinationAlert.is_sent == False,
                        VaccinationAlert.alert_date <= _utc_now() + timedelta(days=30),
                    )
                ).all())

            # Nudge sessions (recovery alerts)
            recent_nudges = []
            if pet_ids:
                for pid in pet_ids:
                    nudge = session.exec(
                        select(NudgeSession)
                        .where(NudgeSession.pet_id == pid)
                        .order_by(NudgeSession.created_at.desc())
                        .limit(1)
                    ).first()
                    if nudge:
                        pet_for_nudge = next((p for p in pets if p.id == pid), None)
                        recent_nudges.append((nudge, pet_for_nudge))

            # Tag + scan counts per pet
            pet_stats = {}
            for pet in pets:
                tag_count = len(pet.tags)
                scan_count = len(session.exec(
                    select(TagScan).where(TagScan.pet_id == pet.id)
                ).all())
                vax_count = len(pet.vaccinations)
                pet_stats[pet.id] = {
                    'tags': tag_count,
                    'scans': scan_count,
                    'vaccinations': vax_count,
                }

        # ── Render ──
        first_name = (app.storage.user.get('name') or 'there').split()[0]

        with dashboard_shell(title='Dashboard'):
            ui.add_css(_DASHBOARD_CSS)

            # ── Subscription status warnings ──
            if user_sub and user_sub.status == "past_due":
                with ui.element('div').classes('w-full p-4 mb-4 rounded-lg').style(
                    'background: #fef2f2; border: 1px solid #fecaca; border-radius: 10px;'
                ):
                    with ui.row().classes('items-center gap-3'):
                        ui.icon('warning').style('font-size: 24px; color: #dc2626;')
                        with ui.column().classes('gap-1 flex-1'):
                            ui.label('Payment Failed').style(
                                'font-size: 14px; font-weight: 700; color: #991b1b;'
                            )
                            ui.label(
                                'Your last payment failed. Please update your billing information '
                                'to keep your Verified features active.'
                            ).style('font-size: 13px; color: #7f1d1d;')
                        ui.button(
                            'Update Billing', icon='credit_card',
                            on_click=lambda: ui.navigate.to('/subscription/manage'),
                        ).props('no-caps dense').style(
                            'background: #dc2626; color: white; border-radius: 6px; font-size: 12px;'
                        )

            elif user_sub and user_sub.cancel_at_period_end and user_sub.status == "active":
                end_date = user_sub.current_period_end
                end_str = end_date.strftime('%B %d, %Y') if end_date else 'end of period'
                with ui.element('div').classes('w-full p-4 mb-4 rounded-lg').style(
                    'background: #fffbeb; border: 1px solid #fde68a; border-radius: 10px;'
                ):
                    with ui.row().classes('items-center gap-3'):
                        ui.icon('info').style('font-size: 24px; color: #d97706;')
                        with ui.column().classes('gap-1 flex-1'):
                            ui.label('Subscription Canceling').style(
                                'font-size: 14px; font-weight: 700; color: #92400e;'
                            )
                            ui.label(
                                f'Your Verified subscription will end on {end_str}. '
                                'You can reactivate anytime before then.'
                            ).style('font-size: 13px; color: #78350f;')
                        ui.button(
                            'Reactivate', icon='autorenew',
                            on_click=lambda: ui.navigate.to('/subscription/manage'),
                        ).props('no-caps dense').style(
                            'background: #d97706; color: white; border-radius: 6px; font-size: 12px;'
                        )

            # Welcome header
            with ui.column().classes('gap-1 mb-6'):
                ui.label(f'Welcome back, {first_name}').style(
                    'font-size: 24px; font-weight: 800; color: var(--pl-on-surface); '
                    'letter-spacing: -0.02em;'
                )
                ui.label("Manage your pets' medical records and recovery tools.").style(
                    'font-size: 14px; color: var(--pl-text-hint);'
                )

            # ── Quick stats row ──
            with ui.element('div').classes('qs-grid mb-8'):
                # Registered Pets
                _quick_stat(
                    value=str(len(pets)),
                    label='Registered Pets',
                    icon='pets',
                    bg='#dcfce7',
                    fg='#166534',
                )
                # Total Vaccinations
                _quick_stat(
                    value=str(total_vax),
                    label='Total Vaccinations',
                    icon='vaccines',
                    bg='#dbeafe',
                    fg='#1e40af',
                )
                # Pending Alerts
                _quick_stat(
                    value=str(pending_alerts_count),
                    label='Pending Alerts',
                    icon='notifications',
                    bg='#fef9c3',
                    fg='#854d0e',
                )
                # Plan Status
                _quick_stat(
                    value=user_tier.capitalize(),
                    label='Plan Status',
                    icon='verified',
                    bg='#f3e8ff',
                    fg='#6b21a8',
                )

            # ── My Pets heading + grid ──
            ui.label('My Pets').style(
                'font-size: 18px; font-weight: 700; color: var(--pl-on-surface); margin-bottom: 12px;'
            )

            with ui.element('div').classes('pet-cards-grid mb-8'):
                for pet in pets:
                    species = pet.pet_species or 'DOG'
                    _AVATAR_BG = {'DOG': '#fef3c7', 'CAT': '#e0e7ff'}
                    bg = _AVATAR_BG.get(species, '#f5f5f4')
                    emoji = _SPECIES_EMOJI.get(species, _SPECIES_EMOJI_DEFAULT)
                    stats = pet_stats.get(pet.id, {'vaccinations': 0, 'tags': 0, 'scans': 0})

                    with ui.element('div').classes('pet-card').on(
                        'click', lambda p=pet: ui.navigate.to(f'/pet/{p.id}')
                    ):
                        # Avatar — photo if available, emoji fallback
                        if pet.photo_url:
                            ui.image(
                                f'/api/v1/pets/{pet.id}/photo'
                            ).classes('pet-avatar').style(
                                'object-fit: cover; border: 2px solid #e7e5e4;'
                            )
                        else:
                            with ui.element('div').classes('pet-avatar').style(f'background: {bg};'):
                                ui.label(emoji).style('font-size: 32px; line-height: 1;')

                        # Name
                        ui.label(pet.name or 'Unnamed').classes('pet-card-name')

                        # Breed
                        ui.label(pet.breed or species.capitalize()).classes('pet-card-breed')

                        # Verified badge
                        if is_verified:
                            with ui.element('div').style(
                                'display: inline-flex; align-items: center; gap: 4px; '
                                'padding: 2px 8px; background: #dcfce7; border-radius: 9999px;'
                            ):
                                ui.icon('verified').style('font-size: 12px; color: #166534;')
                                ui.label('Verified').style(
                                    'font-size: 10px; font-weight: 600; color: #166534;'
                                )

                        # Stat row
                        with ui.element('div').classes('pet-card-stats'):
                            with ui.element('div').classes('pet-card-stat'):
                                ui.icon('vaccines').style('font-size: 14px;')
                                ui.label(str(stats['vaccinations']))
                            with ui.element('div').classes('pet-card-stat'):
                                ui.icon('qr_code_2').style('font-size: 14px;')
                                ui.label(str(stats['tags']))
                            with ui.element('div').classes('pet-card-stat'):
                                ui.icon('radar').style('font-size: 14px;')
                                ui.label(str(stats['scans']))

                # Register New Pet card
                with ui.element('div').classes('pet-card-register').on(
                    'click', lambda: ui.navigate.to('/register')
                ):
                    ui.icon('add_circle_outline').style(
                        'font-size: 32px; color: var(--pl-text-hint);'
                    )
                    ui.label('Register New Pet').style(
                        'font-size: 14px; font-weight: 600; color: var(--pl-on-surface);'
                    )

            # ── Bottom 2-column grid: Recent Activity + Recovery Alerts ──
            with ui.element('div').classes('bottom-grid'):

                # Recent Activity
                with ui.element('div').classes('bottom-card'):
                    with ui.element('div').classes('bottom-card-title'):
                        ui.icon('history').style('font-size: 20px; color: var(--pl-primary);')
                        ui.label('Recent Activity')

                    if recent_events:
                        for event in recent_events:
                            dot_color = _EVENT_DOT_COLORS.get(event.event_type, '#a8a29e')
                            with ui.element('div').classes('activity-item'):
                                ui.element('div').classes('activity-dot').style(
                                    f'background: {dot_color};'
                                )
                                with ui.column().classes('gap-0'):
                                    ui.label(event.description).classes('activity-text')
                                    ui.label(_relative_time(event.timestamp)).classes('activity-time')
                    else:
                        ui.label('No recent activity yet.').style(
                            'font-size: 13px; color: var(--pl-text-hint); font-style: italic;'
                        )

                # Recovery Alerts
                with ui.element('div').classes('bottom-card'):
                    with ui.element('div').classes('bottom-card-title'):
                        ui.icon('notifications_active').style(
                            'font-size: 20px; color: var(--pl-primary);'
                        )
                        ui.label('Recovery Alerts')

                    if recent_nudges:
                        for nudge, nudge_pet in recent_nudges:
                            dot_color = '#dc2626'
                            with ui.element('div').classes('activity-item'):
                                ui.element('div').classes('activity-dot').style(
                                    f'background: {dot_color};'
                                )
                                with ui.column().classes('gap-0'):
                                    pet_name = nudge_pet.name if nudge_pet else 'Unknown'
                                    preview = nudge.message[:80] + ('...' if len(nudge.message) > 80 else '')
                                    ui.label(f'{pet_name}: "{preview}"').classes('activity-text')
                                    ui.label(_relative_time(nudge.created_at)).classes('activity-time')
                    else:
                        with ui.column().classes('items-center justify-center gap-2').style(
                            'padding: 24px 0;'
                        ):
                            ui.icon('shield').style(
                                'font-size: 32px; color: #16a34a; opacity: 0.7;'
                            )
                            ui.label('All pets are protected').style(
                                'font-size: 13px; color: var(--pl-text-hint); font-weight: 500;'
                            )
                            ui.label('No recovery alerts at this time.').style(
                                'font-size: 12px; color: var(--pl-text-hint);'
                            )


def _quick_stat(value: str, label: str, icon: str, bg: str, fg: str) -> None:
    """Render a quick-stat card."""
    with ui.element('div').classes('qs-card'):
        with ui.element('div').classes('qs-icon-box').style(f'background: {bg};'):
            ui.icon(icon).style(f'font-size: 20px; color: {fg};')
        with ui.element('div').classes('qs-info'):
            ui.label(value).classes('qs-value')
            ui.label(label).classes('qs-label')
