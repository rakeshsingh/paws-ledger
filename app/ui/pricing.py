from nicegui import ui
from .header import nav_header
from .footer import nav_footer


# All features with availability per tier (True = included, False = not, str = detail)
ALL_FEATURES = [
    ('Public Identity Lookup', True, True, True),
    ('Emergency Medical Alerts', True, True, True),
    ('Ownership Handshake', 'Receive Only', 'Full Access', 'Audit Trail'),
    ('Verified Identity Badge', False, True, True),
    ('Vaccination Storage', False, True, True),
    ('SHA-256 Sealed PDFs', False, 'Standard', 'Signed'),
    ('AI Photo-Match (Vision)', False, False, True),
    ('Sitter Heartbeat', False, False, 'Unlimited'),
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
        'price': '$1',
        'period': '/ year',
        'border_color': '#7d5800',
        'badge': 'Upcoming',
        'col_index': 2,
        'button_text': 'Go Verified',
        'button_style': 'background: #a03a21; color: white;',
        'highlighted': True,
    },
    {
        'name': 'Guardian',
        'subtitle': 'Total Peace of Mind',
        'price': '$1',
        'period': '/ month',
        'border_color': '#a03a21',
        'badge': 'Upcoming',
        'col_index': 3,
        'button_text': 'Become a Guardian',
        'button_style': 'background: white; color: #a03a21; border: 1px solid rgba(160,58,33,0.2);',
        'highlighted': False,
    },
]


def init_pricing_page():
    @ui.page('/pricing')
    async def pricing_page():
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
            with ui.row().classes('w-full gap-8 justify-center items-stretch'):
                for tier in TIERS:
                    _render_pricing_card(tier)

        nav_footer()


def _render_pricing_card(tier):
    """Render a pricing card with full feature comparison built in."""
    scale = 'transform: scale(1.05); z-index: 10;' if tier['highlighted'] else ''
    shadow = (
        'box-shadow: 0 12px 24px rgba(0,0,0,0.1);'
        if tier['highlighted']
        else 'box-shadow: 0 4px 4px rgba(0,0,0,0.05);'
    )
    col_idx = tier['col_index']

    with ui.element('div').classes(
        'flex flex-col rounded-xl p-10 relative overflow-hidden'
    ).style(
        f'background: white; border-left: 4px solid {tier["border_color"]}; '
        f'{shadow} {scale} flex: 1; min-width: 280px; max-width: 380px;'
    ):
        # Header
        with ui.column().classes('gap-2 mb-6'):
            ui.label(tier['name']).style(
                "font-family: 'Plus Jakarta Sans'; font-size: 24px; "
                "font-weight: 600; color: #171c21;"
            )
            if tier['badge']:
                ui.label(tier['badge']).style(
                    'display: inline-block; padding: 2px 8px; border-radius: 4px; '
                    'font-size: 10px; font-weight: 700; text-transform: uppercase; '
                    'letter-spacing: -0.02em; '
                    'background: rgba(160,58,33,0.1); color: #a03a21; '
                    'border: 1px solid rgba(160,58,33,0.2);'
                )
            ui.label(tier['subtitle']).style(
                'font-size: 12px; font-weight: 500; color: #57423d; '
                'text-transform: uppercase; letter-spacing: 0.1em;'
            )
            with ui.row().classes('items-baseline gap-1 mt-2'):
                ui.label(tier['price']).style(
                    'font-size: 36px; font-weight: 700; color: #171c21;'
                )
                ui.label(tier['period']).style(
                    'font-size: 12px; color: #57423d;'
                )

        # Features with check/dash/detail
        with ui.column().classes('gap-3 flex-grow mb-8'):
            for feature_row in ALL_FEATURES:
                feature_name = feature_row[0]
                value = feature_row[col_idx]

                with ui.row().classes('items-center gap-2'):
                    if value is True:
                        ui.icon('check_circle').style(
                            'font-size: 18px; color: #a03a21;'
                        )
                        ui.label(feature_name).style(
                            'font-size: 14px; color: #171c21;'
                        )
                    elif value is False:
                        ui.icon('remove_circle_outline').style(
                            'font-size: 18px; color: #d4d4d8;'
                        )
                        ui.label(feature_name).style(
                            'font-size: 14px; color: #a8a29e; '
                            'text-decoration: line-through;'
                        )
                    else:
                        # String value — included with detail
                        ui.icon('check_circle').style(
                            'font-size: 18px; color: #a03a21;'
                        )
                        ui.label(feature_name).style(
                            'font-size: 14px; color: #171c21;'
                        )
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
