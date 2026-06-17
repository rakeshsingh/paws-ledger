import os
import httpx
from nicegui import ui, app
from starlette.requests import Request
from .header import nav_header
from .footer import nav_footer
from .common import try_restore_session


# All features with availability per tier (True = included, False = not, str = detail)
ALL_FEATURES = [
    ('Microchip + QR/NFC Tag Registration', True, True, True),
    ('Lost Pet (Microchip, QR Tag) Lookup', True, True, True),
    ('Finder Owner Communication', 'Email', 'Email/SMS/Secure Chat', 'Email/SMS/Secure Chat'),
    ('Verified Badge & Periodic Contact Reminders', False, True, True),
    ('Pet Care Instructions to Service Providers', False, True, True),
    ('Secure Ownership Transfer', False, True, 'Full Audit Trail'),
    ('Vaccination/Appointment Alerts', False, 'View Only', 'Email & SMS Delivery'),
    ('Document Upload', False, '1 per pet', 'Up to 100 per pet'),
    ('Vaccination Record Storage', False, 'Standard', 'Unlimited'),
    ('Service Provider Heartbeat (Sitter/Groomer check-ins)', False, False, 'Unlimited'),
    ('Tamper Proof Medical Documents', False, False, 'SHA-256 Signed'),
    ('Lost Pet Alert Broadcast', False, False, True),
    ('Emergency Vet Authorization Card', False, False, True),
]

# Pricing tier data
TIERS = [
    {
        'name': 'Free',
        'subtitle': 'Entry Level',
        'price': '$0',
        'period': '',
        'border_color': '#a8a29e',
        'badge': None,
        'col_index': 1,  # index into ALL_FEATURES tuples
        'button_text': 'Start Free',
        'button_style': 'background: #f0f4fb; color: #171c21; border: 1px solid #dec0b9;',
        'highlighted': False,
    },
    {
        'name': 'Verified',
        'subtitle': 'Official Protection',
        'price': '$1',
        'period': '/ month',
        'yearly_price': '$9.99',
        'border_color': '#7d5800',
        'badge': None,
        'col_index': 2,
        'button_text': 'Go Verified',
        'button_style': 'background: #a03a21; color: white;',
        'highlighted': True,
    },
    {
        'name': 'Guardian',
        'subtitle': 'Total Peace of Mind',
        'price': '$4.99',
        'period': '/ month',
        'yearly_price': '$49.99',
        'border_color': '#a03a21',
        'badge': 'Coming Soon',
        'col_index': 3,
        'button_text': 'Coming Soon',
        'button_style': 'background: #e7e5e4; color: #78716c; border: 1px solid #d6d3d1; cursor: not-allowed;',
        'highlighted': False,
        'disabled': True,
    },
]


def init_pricing_page() -> None:
    @ui.page('/pricing')
    async def pricing_page(request: Request) -> None:
        nav_header()

        # Detect current user tier if logged in
        user_tier = 'free'
        try_restore_session(request)
        if app.storage.user.get('email'):
            base_url = os.getenv('BASE_URL', 'http://localhost:8080')
            cookies = {'paws_user_id': request.cookies.get('paws_user_id', '')}
            async with httpx.AsyncClient(base_url=base_url) as client:
                resp = await client.get('/api/v1/subscription/status', cookies=cookies)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get('status') == 'active':
                        user_tier = data.get('tier', 'free')

        with ui.element('main').classes('w-full max-w-7xl mx-auto px-6 py-16'):
            # ── Hero section ──
            with ui.column().classes('w-full items-center mb-16'):
                ui.label('Choose the Right Protection for Your Pet').classes(
                    'pl-heading-3xl'
                ).style('text-align: center;')
                ui.label(
                    'Secure medical records, emergency alerts, and verified ownership. '
                    'Professional-grade ledger management for every pet owner.'
                ).classes('pl-body-base').style(
                    'font-size: var(--pl-text-lg); text-align: center; max-width: 640px; margin-top: 1rem;'
                )

                # Billing period toggle
                billing_period = {'value': 'monthly'}

                with ui.row().classes('items-center gap-3 mt-6 px-4 py-2 rounded-full').style(
                    'background: #f5f5f4; border: 1px solid #e7e5e4;'
                ):
                    monthly_btn = ui.button('Monthly').props('no-caps flat').style(
                        'background: white; color: var(--pl-on-surface); font-weight: 600; '
                        'border-radius: 99px; padding: 6px 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);'
                    )
                    yearly_btn = ui.button('Yearly (Save 2 months)').props('no-caps flat').style(
                        'background: transparent; color: var(--pl-on-surface-variant); font-weight: 500; '
                        'border-radius: 99px; padding: 6px 20px;'
                    )

                cards_container = ui.row().classes(
                    'w-full gap-8 justify-center items-stretch'
                ).style('flex-wrap: wrap;')

            def render_cards():
                cards_container.clear()
                with cards_container:
                    for tier in TIERS:
                        _render_pricing_card(tier, user_tier, billing_period['value'])

            def select_monthly():
                billing_period['value'] = 'monthly'
                monthly_btn.style(
                    'background: white; color: var(--pl-on-surface); font-weight: 600; '
                    'border-radius: 99px; padding: 6px 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);'
                )
                yearly_btn.style(
                    'background: transparent; color: var(--pl-on-surface-variant); font-weight: 500; '
                    'border-radius: 99px; padding: 6px 20px;'
                )
                render_cards()

            def select_yearly():
                billing_period['value'] = 'yearly'
                yearly_btn.style(
                    'background: white; color: var(--pl-on-surface); font-weight: 600; '
                    'border-radius: 99px; padding: 6px 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);'
                )
                monthly_btn.style(
                    'background: transparent; color: var(--pl-on-surface-variant); font-weight: 500; '
                    'border-radius: 99px; padding: 6px 20px;'
                )
                render_cards()

            monthly_btn.on_click(select_monthly)
            yearly_btn.on_click(select_yearly)

            # Initial render
            render_cards()

        nav_footer()


def _render_pricing_card(tier, user_tier='free', billing_period='monthly'):
    """Render a pricing card showing only included features."""
    col_idx = tier['col_index']
    highlighted = tier['highlighted']

    # Map tier names to tier keys for comparison
    tier_key_map = {'Free': 'free', 'Verified': 'verified', 'Guardian': 'guardian'}
    this_tier_key = tier_key_map.get(tier['name'], 'free')
    is_current_plan = (user_tier == this_tier_key)

    if highlighted:
        bg = 'background: linear-gradient(135deg, #fffbf7 0%, #fff0eb 100%);'
        shadow = 'box-shadow: 0 16px 40px rgba(160,58,33,0.15);'
        border = f'border: 2px solid {tier["border_color"]};'
    else:
        bg = 'background: white;'
        shadow = 'box-shadow: 0 4px 12px rgba(0,0,0,0.05);'
        border = f'border: 1px solid #e7e5e4; border-left: 4px solid {tier["border_color"]};'

    with ui.element('div').classes(
        'flex flex-col rounded-xl p-10 relative overflow-hidden'
    ).style(
        f'{bg} {border} {shadow} flex: 1 1 280px; min-width: 280px; max-width: 380px; align-self: stretch;'
    ):

        # Determine displayed price based on billing period
        if billing_period == 'yearly' and tier.get('yearly_price'):
            display_price = tier['yearly_price']
            display_period = '/ year'
        else:
            display_price = tier['price']
            display_period = tier['period']

        # Header
        with ui.column().classes('gap-2 mb-6'):
            with ui.row().classes('items-center gap-2'):
                ui.label(tier['name']).classes('pl-heading-xl')
                if is_current_plan:
                    ui.label('Current Plan').style(
                        'padding: 2px 8px; border-radius: 4px; '
                        'font-size: 10px; font-weight: 700; text-transform: uppercase; '
                        'letter-spacing: -0.02em; '
                        'background: #dcfce7; color: #166534; '
                        'border: 1px solid #bbf7d0;'
                    )
                elif tier['badge']:
                    ui.label(tier['badge']).style(
                        'padding: 2px 8px; border-radius: 4px; '
                        'font-size: 10px; font-weight: 700; text-transform: uppercase; '
                        'letter-spacing: -0.02em; '
                        'background: rgba(160,58,33,0.1); color: #a03a21; '
                        'border: 1px solid rgba(160,58,33,0.2);'
                    )
            ui.label(tier['subtitle']).classes('pl-label-upper')
            with ui.row().classes('items-center gap-2 mt-2 flex-wrap'):
                ui.label(display_price).style(
                    'font-size: 36px; font-weight: 700; color: var(--pl-on-surface);'
                )
                ui.label(display_period).classes('pl-body-xs').style(
                    'margin-right: 4px;'
                )
                if tier.get('beta_offer'):
                    ui.label(tier['beta_offer']).style(
                        'font-size: 11px; font-weight: 600; color: #166534; '
                        'background: #dcfce7; padding: 3px 8px; border-radius: 4px; '
                        'border: 1px solid #bbf7d0;'
                    )
                if billing_period == 'yearly' and tier.get('yearly_price'):
                    ui.label('Save 2 months').style(
                        'font-size: 11px; font-weight: 600; color: #166534; '
                        'background: #dcfce7; padding: 3px 8px; border-radius: 4px; '
                        'border: 1px solid #bbf7d0;'
                    )

        # Only show included features
        with ui.column().classes('gap-3 flex-grow mb-8'):
            for feature_row in ALL_FEATURES:
                feature_name = feature_row[0]
                value = feature_row[col_idx]

                if value is False:
                    continue

                with ui.row().classes('items-center gap-2'):
                    ui.icon('check_circle').style(
                        'font-size: 18px; color: var(--pl-primary);'
                    )
                    ui.label(feature_name).style(
                        'font-size: var(--pl-text-sm); color: var(--pl-on-surface);'
                    )
                    if isinstance(value, str):
                        ui.label(f'({value})').style(
                            'font-size: var(--pl-text-xs); color: var(--pl-secondary); font-weight: 600;'
                        )

        # CTA button
        if is_current_plan:
            ui.button(
                'Current Plan', icon='check_circle',
                on_click=lambda: ui.navigate.to('/subscription/manage'),
            ).classes('w-full py-3 rounded-lg font-semibold').style(
                'background: #dcfce7; color: #166534; border: 1px solid #bbf7d0;'
            ).props('no-caps')
        elif tier.get('disabled'):
            ui.button(
                tier['button_text'],
            ).classes('w-full py-3 rounded-lg font-semibold').style(
                tier['button_style']
            ).props('no-caps disable')
        else:
            async def handle_cta(t=tier, bp=billing_period):
                from nicegui import app as nicegui_app
                is_logged_in = bool(nicegui_app.storage.user.get('email'))
                if not is_logged_in:
                    ui.navigate.to('/login')
                    return
                if t['name'] == 'Free':
                    ui.navigate.to('/register')
                    return
                from nicegui import context
                tier_key = 'verified' if t['name'] == 'Verified' else 'guardian'
                base_url = os.getenv('BASE_URL', 'http://localhost:8080')
                cookies = context.client.request.cookies
                async with httpx.AsyncClient(base_url=base_url) as client:
                    resp = await client.post(
                        '/api/v1/subscription/checkout',
                        json={'tier': tier_key, 'billing_period': bp},
                        cookies={'paws_user_id': cookies.get('paws_user_id', '')},
                    )
                    if resp.status_code == 200:
                        checkout_url = resp.json().get('checkout_url')
                        if checkout_url:
                            ui.navigate.to(checkout_url)
                    elif resp.status_code == 409:
                        ui.notify('You already have an active subscription.', type='info')
                        ui.navigate.to('/subscription/manage')
                    else:
                        ui.notify('Failed to start checkout. Please try again.', type='negative')

            ui.button(
                tier['button_text'],
                on_click=handle_cta,
            ).classes('w-full py-3 rounded-lg font-semibold').style(
                tier['button_style']
            ).props('no-caps')
