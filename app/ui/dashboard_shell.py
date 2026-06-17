"""Authenticated dashboard shell — sidebar + content layout for all logged-in pages."""

from contextlib import contextmanager
from nicegui import ui, app
from sqlmodel import Session, select
from uuid import UUID

from ..database import engine
from ..models import Pet, User, Subscription
from .common import (
    try_restore_session,
    SPECIES_ICONS, SPECIES_ICON_DEFAULT, SPECIES_BG, SPECIES_BG_DEFAULT,
    SPECIES_FG, SPECIES_FG_DEFAULT,
)


def _logout():
    """Clear session storage and redirect to server-side logout to delete HttpOnly cookie."""
    app.storage.user.clear()
    ui.navigate.to('/api/v1/auth/logout')

# Species emoji for sidebar pet avatars
_SPECIES_EMOJI = {'DOG': '\U0001F415', 'CAT': '\U0001F408'}

_SHELL_CSS = '''
/* ── Dashboard Shell ── */
/* Override NiceGUI default content constraint for dashboard layout */
.nicegui-content:has(.ds-container) {
    max-width: 100% !important;
    padding: 0 !important;
}

.ds-container {
    display: flex;
    min-height: 100vh;
    width: 100%;
}

/* Sidebar */
.ds-sidebar {
    width: 260px;
    min-width: 260px;
    background: #ffffff;
    border-right: 1px solid #e7e5e4;
    display: flex;
    flex-direction: column;
    position: fixed;
    top: 0;
    left: 0;
    bottom: 0;
    z-index: 100;
    overflow-y: auto;
}

/* Main content */
.ds-main {
    flex: 1;
    margin-left: 260px;
    display: flex;
    flex-direction: column;
    min-height: 100vh;
    background: var(--pl-bg);
}

/* Topbar */
.ds-topbar {
    background: #ffffff;
    border-bottom: 1px solid #e7e5e4;
    padding: 16px 32px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 8px;
    position: sticky;
    top: 0;
    z-index: 50;
}

.ds-topbar-breadcrumb {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    color: var(--pl-text-hint);
    min-width: 0;
    flex-shrink: 1;
}

.ds-topbar-breadcrumb .ds-bc-current {
    font-weight: 700;
    color: var(--pl-on-surface);
}

.ds-topbar-breadcrumb a {
    color: var(--pl-text-hint);
    text-decoration: none;
}

.ds-topbar-breadcrumb a:hover {
    color: var(--pl-primary);
}

.ds-topbar-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
}

.ds-action-btn {
    padding: 8px 16px;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    border: none;
    display: inline-flex !important;
    align-items: center;
    gap: 6px;
    transition: all 0.15s ease;
    white-space: nowrap;
}

.ds-action-btn-primary {
    background: #a03a21 !important;
    color: #ffffff !important;
}

.ds-action-btn-primary .q-icon,
.ds-action-btn-primary .q-label,
.ds-action-btn-primary label {
    color: #ffffff !important;
}

.ds-action-btn-primary:hover {
    background: #83250e !important;
}

.ds-action-btn-ghost {
    background: transparent;
    color: var(--pl-on-surface-variant);
    border: 1px solid #e7e5e4;
}

.ds-action-btn-ghost:hover {
    background: var(--pl-surface-container);
}

/* Content area */
.ds-content {
    flex: 1;
    padding: 32px;
}

/* Brand section */
.ds-brand {
    padding: 20px 16px 16px;
    display: flex;
    align-items: center;
    cursor: pointer;
}

.ds-brand img {
    height: 36px;
    width: auto;
}

/* Navigation section */
.ds-nav-section {
    padding: 0 12px;
    margin-bottom: 8px;
}

.ds-section-label {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: var(--pl-text-hint);
    padding: 12px 12px 6px 12px;
    font-weight: 600;
}

.ds-nav-item {
    padding: 10px 12px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    gap: 10px;
    cursor: pointer;
    transition: background 0.15s ease;
    text-decoration: none;
    color: var(--pl-on-surface-variant);
    font-size: 14px;
    font-weight: 500;
}

.ds-nav-item:hover {
    background: var(--pl-surface-container);
}

.ds-nav-item-active {
    background: var(--pl-primary-light) !important;
    color: var(--pl-primary) !important;
    font-weight: 600 !important;
}

.ds-nav-item-active .ds-nav-icon {
    color: var(--pl-primary) !important;
}

.ds-nav-icon {
    font-size: 20px;
    color: var(--pl-text-hint);
}

/* Pet list items */
.ds-pet-item {
    padding: 8px 12px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    gap: 10px;
    cursor: pointer;
    transition: background 0.15s ease;
    text-decoration: none;
}

.ds-pet-item:hover {
    background: var(--pl-surface-container);
}

.ds-pet-item-active {
    background: var(--pl-primary-light) !important;
}

.ds-pet-avatar {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
    flex-shrink: 0;
}

.ds-pet-info {
    display: flex;
    flex-direction: column;
    min-width: 0;
}

.ds-pet-name {
    font-size: 13px;
    font-weight: 600;
    color: var(--pl-on-surface);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.ds-pet-breed {
    font-size: 11px;
    color: var(--pl-text-hint);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

/* Register link */
.ds-register-link {
    padding: 10px 12px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    color: var(--pl-primary);
    font-size: 13px;
    font-weight: 600;
    transition: background 0.15s ease;
}

.ds-register-link:hover {
    background: var(--pl-primary-light);
}

/* Bottom section */
.ds-sidebar-bottom {
    margin-top: auto;
    padding: 12px;
    border-top: 1px solid #e7e5e4;
}

.ds-user-footer {
    padding: 12px;
    display: flex;
    align-items: center;
    gap: 10px;
    border-top: 1px solid #e7e5e4;
}

.ds-user-avatar {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: var(--pl-primary-light);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    font-weight: 700;
    color: var(--pl-primary);
    flex-shrink: 0;
}

.ds-user-info {
    display: flex;
    flex-direction: column;
    min-width: 0;
}

.ds-user-name {
    font-size: 13px;
    font-weight: 600;
    color: var(--pl-on-surface);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.ds-tier-badge {
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding: 2px 8px;
    border-radius: 9999px;
}

.ds-tier-free {
    background: var(--pl-surface-container);
    color: var(--pl-text-hint);
}

.ds-tier-verified {
    background: #dcfce7;
    color: #166534;
}

.ds-tier-guardian {
    background: #fef3c7;
    color: #92400e;
}

/* Spacer */
.ds-spacer {
    flex: 1;
}

/* ── Quasar Theme Overrides for Dashboard ── */
/* Tabs: use terracotta instead of Quasar default blue */
.ds-main .q-tab--active {
    color: var(--pl-primary) !important;
}
.ds-main .q-tab__indicator {
    background: var(--pl-primary) !important;
}
.ds-main .q-tab:hover {
    color: var(--pl-primary) !important;
}

/* Cards within dashboard: clean borders matching mockup */
.ds-content .q-card {
    border: 1px solid #e7e5e4 !important;
    border-radius: 12px !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06) !important;
}

/* Buttons in topbar actions: override Quasar ripple color */
.ds-main .q-btn--standard.bg-primary,
.ds-main .q-btn.bg-primary {
    background-color: var(--pl-primary) !important;
}

/* Mobile hamburger button — hidden on desktop */
.ds-mobile-menu-btn {
    display: none !important;
}

/* Responsive: hide sidebar on mobile, show hamburger */
@media (max-width: 767px) {
    .ds-sidebar {
        display: none;
    }
    .ds-main {
        margin-left: 0;
    }
    .ds-topbar {
        padding: 12px 16px;
    }
    .ds-content {
        padding: 16px;
    }
    .ds-mobile-menu-btn {
        display: inline-flex !important;
    }
    .ds-topbar-actions {
        flex-wrap: wrap;
    }
    .ds-action-btn {
        padding: 6px 12px;
        font-size: 12px;
    }
}
'''


@contextmanager
def dashboard_shell(title='Dashboard', breadcrumbs=None, actions=None, active_pet_id=None):
    """Reusable authenticated dashboard layout with sidebar and content pane.

    Args:
        title: page title shown as the final breadcrumb item.
        breadcrumbs: list of (label, url) tuples for the breadcrumb trail.
            If None, defaults to [('Dashboard', '/dashboard')].
        actions: list of dicts with keys: label, icon, on_click, style ('primary' or 'ghost').
        active_pet_id: UUID string of the currently viewed pet (for sidebar highlight).
    """
    ui.add_css(_SHELL_CSS)
    # Ensure nicegui-content is full-width for sidebar layout
    ui.run_javascript('''
        document.querySelectorAll('.nicegui-content').forEach(el => {
            el.style.maxWidth = '100%';
            el.style.padding = '0';
        });
    ''')

    # Fetch user data for sidebar
    user_email = app.storage.user.get('email', '')
    user_name = app.storage.user.get('name', '')
    user_id = app.storage.user.get('id', '')

    pets = []
    user_tier = 'free'
    if user_id:
        with Session(engine) as session:
            pets = session.exec(
                select(Pet).where(Pet.owner_id == UUID(user_id))
            ).all()
            sub = session.exec(
                select(Subscription).where(Subscription.user_id == UUID(user_id))
            ).first()
            if sub and sub.status == 'active':
                user_tier = sub.tier

    # Build breadcrumb data
    if breadcrumbs is None:
        breadcrumbs = [('Dashboard', '/dashboard')]

    # ── Outer container ──
    with ui.element('div').classes('ds-container'):

        # ── Sidebar ──
        with ui.element('nav').classes('ds-sidebar'):

            # Brand — logo SVG linking to home
            with ui.element('div').classes('ds-brand').on(
                'click', lambda: ui.navigate.to('/')
            ):
                ui.html('<img src="/assets/logo.svg" style="height: 36px; width: auto;">')

            # Primary navigation
            with ui.element('div').classes('ds-nav-section'):
                _nav_item('Home', 'home', '/', active=False)
                _nav_item('Dashboard', 'dashboard', '/dashboard',
                          active=(title == 'Dashboard' and active_pet_id is None))
                _nav_item('Chip Lookup', 'search', '/lookup',
                          active=(title == 'Chip Lookup'))

            # My Pets section
            with ui.element('div').classes('ds-nav-section'):
                with ui.element('div').classes('ds-section-label'):
                    ui.label('MY PETS')

                for pet in pets:
                    is_active = (active_pet_id is not None and str(pet.id) == str(active_pet_id))
                    _pet_item(pet, is_active)

                # Register new pet link
                with ui.element('div').classes('ds-register-link').on(
                    'click', lambda: ui.navigate.to('/register')
                ):
                    ui.icon('add_circle_outline').style('font-size: 18px;')
                    ui.label('Register New Pet')

            # Quick Actions section
            with ui.element('div').classes('ds-nav-section'):
                with ui.element('div').classes('ds-section-label'):
                    ui.label('QUICK ACTIONS')
                _nav_item('Share Access', 'share', '/shared-access',
                          active=(title == 'Share Access'))
                _nav_item('Manage Tags', 'qr_code_2', '/tags',
                          active=(title == 'Manage Tags'))

            # Spacer
            ui.element('div').classes('ds-spacer')

            # Bottom navigation
            with ui.element('div').classes('ds-sidebar-bottom'):
                _nav_item('Profile', 'person', '/owner/profile',
                          active=(title == 'Profile'))
                _nav_item(
                    'Verified Plan' if user_tier != 'free' else 'Upgrade Plan',
                    'verified',
                    '/subscription/manage' if user_tier != 'free' else '/pricing',
                    active=False,
                )
                _nav_item('Help & FAQ', 'help_outline', '/faq',
                          active=(title == 'Help & FAQ'))

            # User footer
            with ui.element('div').classes('ds-user-footer'):
                initials = ''.join(
                    part[0].upper() for part in user_name.split()[:2]
                ) if user_name else '?'
                with ui.element('div').classes('ds-user-avatar'):
                    ui.label(initials)
                with ui.element('div').classes('ds-user-info'):
                    ui.label(user_name or 'User').classes('ds-user-name')
                    tier_class = f'ds-tier-{user_tier}'
                    ui.label(user_tier.capitalize()).classes(f'ds-tier-badge {tier_class}')

        # ── Main area ──
        with ui.element('div').classes('ds-main'):

            # Topbar
            with ui.element('div').classes('ds-topbar'):
                # Mobile hamburger menu
                with ui.button(icon='menu').props('flat dense').classes(
                    'ds-mobile-menu-btn'
                ).style('color: var(--pl-on-surface);'):
                    with ui.menu().classes('min-w-[240px]'):
                        ui.menu_item(
                            'Home',
                            on_click=lambda: ui.navigate.to('/'),
                        )
                        ui.menu_item(
                            'Dashboard',
                            on_click=lambda: ui.navigate.to('/dashboard'),
                        )
                        ui.menu_item(
                            'Chip Lookup',
                            on_click=lambda: ui.navigate.to('/lookup'),
                        )
                        ui.separator()
                        if pets:
                            ui.label('MY PETS').style(
                                'font-size: 10px; font-weight: 600; letter-spacing: 0.8px; '
                                'color: var(--pl-text-hint); padding: 8px 16px 4px;'
                            )
                            for pet in pets:
                                _emoji = _SPECIES_EMOJI.get(pet.pet_species or 'DOG', '\U0001F43E')
                                ui.menu_item(
                                    f'{_emoji}  {pet.name or "Unnamed"}',
                                    on_click=lambda p=pet: ui.navigate.to(f'/pet/{p.id}'),
                                )
                            ui.separator()
                        ui.menu_item(
                            'Register New Pet',
                            on_click=lambda: ui.navigate.to('/register'),
                        )
                        ui.menu_item(
                            'Share Access',
                            on_click=lambda: ui.navigate.to('/shared-access'),
                        )
                        ui.menu_item(
                            'Manage Tags',
                            on_click=lambda: ui.navigate.to('/tags'),
                        )
                        ui.separator()
                        ui.menu_item(
                            'Profile',
                            on_click=lambda: ui.navigate.to('/owner/profile'),
                        )
                        ui.menu_item(
                            'Pricing',
                            on_click=lambda: ui.navigate.to('/pricing'),
                        )
                        ui.menu_item(
                            'Help & FAQ',
                            on_click=lambda: ui.navigate.to('/faq'),
                        )
                        ui.separator()
                        ui.menu_item(
                            'Logout',
                            on_click=lambda: _logout(),
                        )

                # Breadcrumb
                with ui.element('div').classes('ds-topbar-breadcrumb'):
                    for i, (bc_label, bc_url) in enumerate(breadcrumbs):
                        if i > 0:
                            ui.label('/').style('margin: 0 2px; color: var(--pl-text-hint);')
                        ui.link(bc_label, bc_url).style(
                            'color: var(--pl-text-hint); text-decoration: none; font-size: 13px;'
                        )
                    # Current page title as last item
                    if breadcrumbs:
                        ui.label('/').style('margin: 0 2px; color: var(--pl-text-hint);')
                    ui.label(title).classes('ds-bc-current')

                # Action buttons
                if actions:
                    with ui.element('div').classes('ds-topbar-actions'):
                        for action in actions:
                            style = action.get('style', 'primary')
                            btn_class = f'ds-action-btn ds-action-btn-{style}'
                            icon_color = '#ffffff' if style == 'primary' else 'var(--pl-on-surface-variant)'
                            label_color = '#ffffff' if style == 'primary' else 'var(--pl-on-surface-variant)'
                            with ui.element('button').classes(btn_class).on(
                                'click', action.get('on_click', lambda: None)
                            ):
                                if action.get('icon'):
                                    ui.icon(action['icon']).style(
                                        f'font-size: 16px; color: {icon_color};'
                                    )
                                ui.label(action.get('label', '')).style(
                                    f'color: {label_color};'
                                )

            # Content area — this is where the page renders its content
            with ui.element('div').classes('ds-content'):
                yield


def _nav_item(label: str, icon: str, url: str, active: bool = False):
    """Render a sidebar navigation item."""
    classes = 'ds-nav-item'
    if active:
        classes += ' ds-nav-item-active'

    with ui.element('div').classes(classes).on('click', lambda: ui.navigate.to(url)):
        ui.icon(icon).classes('ds-nav-icon')
        ui.label(label)


def _pet_item(pet: Pet, active: bool = False):
    """Render a sidebar pet list item with avatar."""
    classes = 'ds-pet-item'
    if active:
        classes += ' ds-pet-item-active'

    _AVATAR_BG = {'DOG': '#fef3c7', 'CAT': '#e0e7ff'}
    species = pet.pet_species or 'DOG'
    bg = _AVATAR_BG.get(species, '#f5f5f4')
    emoji = _SPECIES_EMOJI.get(species, '\U0001F43E')

    with ui.element('div').classes(classes).on(
        'click', lambda p=pet: ui.navigate.to(f'/pet/{p.id}')
    ):
        with ui.element('div').classes('ds-pet-avatar').style(f'background: {bg};'):
            ui.label(emoji).style('line-height: 1;')
        with ui.element('div').classes('ds-pet-info'):
            ui.label(pet.name or 'Unnamed').classes('ds-pet-name')
            ui.label(pet.breed or species.capitalize()).classes('ds-pet-breed')
