from nicegui import ui
from .header import nav_header
from .footer import nav_footer


# All features with availability per tier (True = included, False = not, str = detail)
ALL_FEATURES = [
    ('Microchip + QR/NFC Tag Registration', True, True, True),
    ('Lost Pet (Microchip, QR Tag) Lookup', True, True, True),
    ('Finder Owner Communication', 'Email', 'Email/SMS/Secure Chat', 'Email/SMS/Secure Chat'),
    ('Verified Badge & Periodic Alerts to maintain updated contact', False, True, True),
    ('Pet Care Instructions to Service providers', False, True, True),
    ('Secure Ownership Transfer', False, True, 'Full Audit Trail'),
    ('Appointment/Vaccination Alerts', False, True, True),
    ('Vaccination Storage', False, 'Standard', 'Unlimited'),
    ('Service Provider Heartbeat (Sitter/Groomer check-ins)', False, False, 'Unlimited'),
    ('Tamper Proof Medical Documents', False, False, 'SHA-256 Signed'),
    ('Lost Pet Alert Broadcast', False, False, True),
    ('Emergency Vet Authorization Card', False, False, True),

]

# Pricing tier data
TIERS = [
    {
        'name': 'Forever Free',
        'subtitle': 'Entry Level',
        'price': '$0',
        'period': 'forever',
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
        'price': '$2',
        'period': '/ year',
        'border_color': '#7d5800',
        'badge': 'Upcoming',
        'beta_offer': 'Beta offer: $1/year forever (until end of 2026)',
        'col_index': 2,
        'button_text': 'Go Verified',
        'button_style': 'background: #a03a21; color: white;',
        'highlighted': True,
    },
    {
        'name': 'Guardian',
        'subtitle': 'Total Peace of Mind',
        'price': '$2',
        'period': '/ month',
        'border_color': '#a03a21',
        'badge': 'Upcoming',
        'col_index': 3,
        'button_text': 'Become a Guardian',
        'button_style': 'background: white; color: #a03a21; border: 1px solid rgba(160,58,33,0.2);',
        'highlighted': False,
    },
]


def init_pricing_page() -> None:
    @ui.page('/pricing')
    async def pricing_page() -> None:
        nav_header()

        with ui.element('main').classes('w-full max-w-7xl mx-auto px-6 py-16'):
            # ── Hero section ──
            with ui.column().classes('w-full items-center mb-16'):
                ui.label('Choose the Right Protection for Your Pet').style(
                    "font-family: 'Plus Jakarta Sans'; font-size: 40px; "
                    "font-weight: 700; line-height: 1.2; letter-spacing: -0.02em; "
                    "color: #171c21; text-align: center;"
                )
                ui.label(
                    'Secure medical records, emergency alerts, and verified ownership. '
                    'Professional-grade ledger management for every pet owner.'
                ).style(
                    'font-size: 18px; line-height: 1.6; color: #57423d; '
                    'text-align: center; max-width: 640px; margin-top: 1rem;'
                )

            # ── Pricing cards with full feature comparison ──
            with ui.row().classes('w-full gap-8 justify-center items-stretch').style('flex-wrap: wrap;'):
                for tier in TIERS:
                    _render_pricing_card(tier)

        nav_footer()


def _render_pricing_card(tier):
    """Render a pricing card showing only included features."""
    col_idx = tier['col_index']
    highlighted = tier['highlighted']

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

        # Header
        with ui.column().classes('gap-2 mb-6'):
            with ui.row().classes('items-center gap-2'):
                ui.label(tier['name']).style(
                    "font-family: 'Plus Jakarta Sans'; font-size: 24px; "
                    "font-weight: 600; color: #171c21;"
                )
                if tier['badge']:
                    ui.label(tier['badge']).style(
                        'padding: 2px 8px; border-radius: 4px; '
                        'font-size: 10px; font-weight: 700; text-transform: uppercase; '
                        'letter-spacing: -0.02em; '
                        'background: rgba(160,58,33,0.1); color: #a03a21; '
                        'border: 1px solid rgba(160,58,33,0.2);'
                    )
            ui.label(tier['subtitle']).style(
                'font-size: 12px; font-weight: 500; color: #57423d; '
                'text-transform: uppercase; letter-spacing: 0.1em;'
            )
            with ui.row().classes('items-center gap-2 mt-2 flex-wrap'):
                ui.label(tier['price']).style(
                    'font-size: 36px; font-weight: 700; color: #171c21;'
                )
                ui.label(tier['period']).style(
                    'font-size: 12px; color: #57423d; margin-right: 4px;'
                )
                if tier.get('beta_offer'):
                    ui.label(tier['beta_offer']).style(
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
                        'font-size: 18px; color: #a03a21;'
                    )
                    ui.label(feature_name).style(
                        'font-size: 14px; color: #171c21;'
                    )
                    if isinstance(value, str):
                        ui.label(f'({value})').style(
                            'font-size: 11px; color: #7d5800; font-weight: 600;'
                        )

        # CTA button
        ui.button(
            tier['button_text'],
            on_click=lambda: ui.navigate.to('/login'),
        ).classes('w-full py-3 rounded-lg font-semibold').style(
            tier['button_style']
        ).props('no-caps')
