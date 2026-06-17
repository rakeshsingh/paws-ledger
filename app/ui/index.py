from nicegui import ui, app
from sqlmodel import Session, select
from ..database import engine
from ..models import Pet
from .header import nav_header
from .footer import nav_footer

# Hero image URLs from the landing template
HERO_IMG = 'https://lh3.googleusercontent.com/aida-public/AB6AXuDOvgen58Uso2VUVVvFepK3xJ7zY0sAjCMDLZ3_gnMw9cVS9Ps1QXWxtOc1qyz_kE4_gVpcls0DrAOWN0Ly6c2PAHSN0UTMmn6TOKA74p7ANhFbJ-x0bMEZnqotilt3xWQRVg1-3uAO_fC4mjJhWJXSEN4hmhZ0vJU6yKg_cSAsjPxSv2IcfPBE2NB3f27YckVsQRUq44x-uXv6Yu4cHtahDqha_7J3-pgL6HFQXwtchhd-nKkIpFF-0fyU8ex_zKzbRmEalkpiCFQJ'
HOW_IT_WORKS_IMG = 'https://lh3.googleusercontent.com/aida-public/AB6AXuD7sRLjDUa5PYRXG_5lC5_DcSVugdSOEyKh6j_svphtfFScXP3IihV1iZfDyLHsIradsTlUSPWF9xhJYaQ2BJBhaKEMkK4T56nAih6tokt-91xelAg2AeTSJ9oEpeVag_aakhPKrDQ1Ux573URQeKYGVFaxA0PlWIabEKn0xsEIMSxvmiXpdRPCAlz1tVjgXmhjolQCwImyOmJHDI0bliEVAnYFB37GSw8Yfx8zKZHniPgFgs4vOAYfioxq521uU5EmNUKD0iY_brJV'
AVATAR_IMGS = [
    'https://lh3.googleusercontent.com/aida-public/AB6AXuDC_u-pLQN_9ELbNpRQc2wcKEpFxsSgBXSl1f5H2DekqHId9VWWxfwo2irG3Duz-x00Mf3xQa0okbayR1K8c3SMJ-2jmArBdJKzQKSBhQUeGqBWbXzmPJP3UWUvmePGD3RQyg9JhvvaEpbwoU1dMdsvCnzmn_XOSJns0FwXcJviaCQRrMZBxQzhBYZUf5JGdMCQWVzsG0s8OMs59NOXExLvthqFfqO9GYaEKv5CgEXJhLj840uUU_kXWXHIXZpOBNFPtn8fWeaP0KDq',
    'https://lh3.googleusercontent.com/aida-public/AB6AXuDnz47nE9O4bTIt-6TujxWMe9xipN_9YLnp-OGGXji5YZUjC9NgWM8b_UgN6Cde6vsAqBCtRnOap2KOnbUJP0PdAzsYIfnwrmQi7-XU37xSXgzGDA-D6AWs0BvuV2zQ_nWoTArEAujx2MqZD5HJ4vm7Q3pulZBQVHM7rKCaplUxlAG8oj-kRIVd9zZnnsJDOBjVDev7bnhUT7lZO8nSSJqoBnbVFhmfFhcIozt0yWCWrNwkdihTD_oNrC1cQh9yqaiIfUC6OC0tjvb3',
    'https://lh3.googleusercontent.com/aida-public/AB6AXuD45l7ug8S4bO--zSKW9GFzKnsZHeV0wiLk2Xds0q51lyCuHBe3NxImd5GsDTfgKBH6NN7P4vCuDsVhyY_4qn5pWRsgyxwnFvG3Dwdm9OsyL8dhqUDsJathvq-hRd7OPpD7yhj3mWkW2AzofjUR2Wof1fxujldmtVZV2jfssrummSVpX8hn0tfkoiU1JWg3EhPn3akPnNs3QaqC9nwwKFtKnZZ0lB9ALjk7BEHWZRPf4iRTZWHVqlv8iOjJ5efRMsFmgMJFt4M4UAkc',
]


def init_index_page() -> None:
    @ui.page('/', title='PawsLedger — Universal Pet Microchip Registry & Recovery Network')
    async def index_page() -> None:
        ui.add_head_html(
            '<meta name="description" content="Register your pet\'s microchip for free. Store vaccination records, share care access with vets and sitters, and enable instant NFC/QR tag identification. If your pet is lost, anyone can reach you.">\n'
            '<link rel="canonical" href="https://www.pawsledger.com/">\n'
            '<meta property="og:title" content="PawsLedger — Universal Pet Microchip Registry & Recovery Network">\n'
            '<meta property="og:description" content="Register your pet\'s microchip for free. Store vaccination records, share care access, and enable instant NFC/QR tag identification.">\n'
            '<meta property="og:url" content="https://www.pawsledger.com/">\n'
            '<meta name="twitter:card" content="summary_large_image">\n'
            '<meta name="twitter:title" content="PawsLedger — Universal Pet Microchip Registry">\n'
            '<meta name="twitter:description" content="Register your pet\'s microchip. Enable instant identification with NFC/QR tags. Free forever.">\n'
        )
        nav_header()

        ui.add_css('''
.hero-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 3rem;
    align-items: center;
}
.how-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 3rem;
    align-items: center;
}
.owner-steps-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 2rem;
}
.diff-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1.5rem;
}
@media (max-width: 767px) {
    .hero-grid {
        grid-template-columns: 1fr;
    }
    .hero-grid .hero-image {
        max-height: 360px;
    }
    .how-grid {
        grid-template-columns: 1fr;
    }
    .owner-steps-grid {
        grid-template-columns: 1fr;
    }
    .diff-grid {
        grid-template-columns: 1fr 1fr;
    }
}
@media (max-width: 480px) {
    .diff-grid {
        grid-template-columns: 1fr;
    }
}
''')

        # ── Hero Section ── (Owner-first messaging)
        with ui.element('section').classes('w-full py-16 md:py-24').style(
            'background: radial-gradient(circle at top right, rgba(255,218,210,0.5), transparent),'
            'radial-gradient(circle at bottom left, rgba(234,238,245,0.5), transparent);'
        ):
            with ui.element('div').classes('hero-grid max-w-7xl mx-auto px-4 md:px-6'):
                # Left column
                with ui.column().classes('gap-8'):
                    # Badge
                    with ui.row().classes('items-center gap-2 px-3 py-1 rounded-full').style(
                        'background: rgba(160,58,33,0.1); border: 1px solid rgba(193,82,55,0.2);'
                    ):
                        ui.icon('verified_user').style('font-size: 16px; color: #c15237;')
                        ui.label('ISO 11784/11785 Compliant Registry').style(
                            'font-size: 12px; font-weight: 600; color: #c15237;'
                        )

                    # Headline — owner-first
                    ui.html(
                        '<h1 style="font-family: var(--pl-font); font-size: clamp(2.5rem, 5vw, 4rem); '
                        'line-height: 1.15; font-weight: 700; color: var(--pl-on-surface);">'
                        'Your pet\'s identity, medical records, and recovery — '
                        '<span style="color: var(--pl-primary);">in one secure ledger.</span></h1>'
                    )

                    # Subtitle
                    ui.label(
                        'Register your microchip. Store vaccination records. Share care access '
                        'with vets and sitters via time-limited links. If your pet is ever lost, '
                        'anyone who finds them can reach you instantly — no app download required.'
                    ).classes('pl-body-base').style('font-size: var(--pl-text-lg); max-width: 34rem;')

                    # Search input with real-time prefix identification
                    with ui.row().classes('w-full gap-2 items-center'):
                        chip_input = ui.input(
                            placeholder='Enter Microchip Number'
                        ).classes('flex-1').props('outlined rounded dense')
                        search_btn = ui.button(
                            'Search Registry', icon='search',
                            on_click=lambda: do_lookup(),
                        ).style(
                            'background-color: var(--pl-primary); color: white; font-weight: 600; '
                            'padding: 10px 28px;'
                        ).classes('rounded-lg').props('no-caps')

                    with ui.row().classes('items-center gap-1 mt-1'):
                        ui.label('Pet owner?').style(
                            'font-size: 13px; color: var(--pl-on-surface-variant);'
                        )
                        ui.link(
                            'Register & protect your pet — free →',
                            '/register' if app.storage.user.get('email') else '/login',
                        ).style(
                            'font-size: var(--pl-text-sm); font-weight: 600; color: var(--pl-primary); '
                            'text-decoration: none;'
                        )

                    # Prefix identification hint (shows manufacturer as user types)
                    prefix_hint = ui.label('').style(
                        'font-size: 13px; font-weight: 600; color: #7d5800; '
                        'padding: 4px 12px; border-radius: 6px; '
                        'background: rgba(125,88,0,0.08); display: none;'
                    )

                    def on_chip_input_change(e):
                        from ..services.integrations import get_chip_prefix_info
                        value = e.value.strip() if e.value else ''
                        if len(value) >= 3:
                            info = get_chip_prefix_info(value)
                            if info.get('identified') and info.get('manufacturer'):
                                hint_text = f'🔍 {info["manufacturer"]}'
                                if info.get('registry'):
                                    hint_text += f' • Registry: {info["registry"]}'
                                prefix_hint.text = hint_text
                                prefix_hint.style(
                                    'font-size: 13px; font-weight: 600; color: #7d5800; '
                                    'padding: 4px 12px; border-radius: 6px; '
                                    'background: rgba(125,88,0,0.08); display: inline-block;'
                                )
                            elif info.get('hint'):
                                prefix_hint.text = info['hint']
                                prefix_hint.style(
                                    'font-size: 13px; font-weight: 500; color: var(--pl-on-surface-variant); '
                                    'padding: 4px 12px; border-radius: 6px; '
                                    'background: rgba(0,0,0,0.03); display: inline-block;'
                                )
                            else:
                                prefix_hint.style('display: none;')
                        elif len(value) >= 1:
                            info = get_chip_prefix_info(value)
                            if info.get('hint'):
                                prefix_hint.text = info['hint']
                                prefix_hint.style(
                                    'font-size: 13px; font-weight: 500; color: #8a716c; '
                                    'padding: 4px 12px; border-radius: 6px; '
                                    'background: transparent; display: inline-block;'
                                )
                        else:
                            prefix_hint.style('display: none;')

                    chip_input.on('update:model-value', on_chip_input_change)

                    # Search results area
                    results_card = ui.column().classes('w-full mt-4').style('display: none')
                    status_badge = ui.label('').classes('px-4 py-1 rounded-full text-xs font-bold uppercase mb-2 inline-block')
                    result_title = ui.label('').classes('text-2xl font-bold')
                    result_desc = ui.label('').style('color: var(--pl-on-surface-variant); margin-bottom: 1rem;')
                    result_details = ui.column().classes('w-full pt-4').style('border-top: 1px solid #dec0b9;')

                    async def do_lookup():
                        chip_id = chip_input.value
                        if not chip_id:
                            ui.notify('Please enter a Chip ID', type='warning')
                            return

                        search_btn.disable()
                        search_btn.text = 'Searching...'

                        try:
                            is_logged_in = bool(app.storage.user.get('email'))

                            with Session(engine) as session:
                                pet = session.exec(
                                    select(Pet).where(Pet.chip_id == chip_id)
                                ).first()

                                results_card.style('display: block')

                                if pet:
                                    status_badge.text = 'Verified PawsLedger Record'
                                    status_badge.style('background-color: rgba(160,58,33,0.1); color: #a03a21;')
                                    result_title.text = f'{pet.name} • {pet.pet_species}'
                                    result_desc.text = f'Breed: {pet.breed} | Status: {pet.identity_status}'

                                    result_details.clear()
                                    with result_details:
                                        if is_logged_in:
                                            ui.button(
                                                'View Full Ledger',
                                                on_click=lambda pid=pet.id: ui.navigate.to(f'/pet/{pid}'),
                                            ).classes('w-full mt-2').style(
                                                'background-color: #a03a21; color: white;'
                                            )
                                        else:
                                            ui.label(
                                                'This pet is registered on PawsLedger. '
                                                'Log in to view full details and contact the owner.'
                                            ).style('color: var(--pl-on-surface-variant); font-size: 14px; margin-bottom: 0.75rem;')
                                            ui.button(
                                                'Login to View Details & Nudge Owner', icon='login',
                                                on_click=lambda: ui.navigate.to('/login'),
                                            ).classes('w-full').style(
                                                'background-color: #a03a21; color: white;'
                                            )
                                else:
                                    from ..api.v1.routes import aaha_client
                                    aaha_data = await aaha_client.lookup(chip_id)
                                    if aaha_data:
                                        status_badge.text = 'AAHA Nationwide Network'
                                        status_badge.style('background-color: #fff7ed; color: #83250e;')
                                        result_title.text = 'Identity Found Externally'
                                        result_desc.text = aaha_data.get('message', '')

                                        result_details.clear()
                                        with result_details:
                                            data = aaha_data.get('data', aaha_data)
                                            for label, value in [
                                                ('Manufacturer', data.get('manufacturer')),
                                                ('Status', data.get('status')),
                                                ('Last Seen', data.get('last_seen')),
                                            ]:
                                                if value:
                                                    with ui.row().classes('w-full justify-between py-1'):
                                                        ui.label(label).style('font-weight: 600; color: var(--pl-on-surface-variant);')
                                                        ui.label(str(value))

                                            ui.separator().classes('my-3')
                                            ui.label(
                                                'This pet is not yet on PawsLedger. '
                                                'Register it to create a secure digital identity.'
                                            ).style('font-size: 14px; font-style: italic; color: var(--pl-on-surface-variant); margin-bottom: 1rem;')

                                            if is_logged_in:
                                                ui.button(
                                                    'Register This Pet', icon='pets',
                                                    on_click=lambda: ui.navigate.to('/register'),
                                                ).classes('w-full').style('background-color: #a03a21; color: white;')
                                            else:
                                                ui.button(
                                                    'Login to Register This Pet', icon='login',
                                                    on_click=lambda: ui.navigate.to('/login'),
                                                ).classes('w-full').style('background-color: #a03a21; color: white;')
                                    else:
                                        ui.notify('No registration found for this ID.', type='negative')
                                        results_card.style('display: none')
                        finally:
                            search_btn.enable()
                            search_btn.text = 'Search'

                    # Social proof with metrics
                    with ui.row().classes('items-center gap-4 mt-4'):
                        with ui.row().classes('items-center').style('margin-right: -0.5rem;'):
                            for img_url in AVATAR_IMGS:
                                ui.image(img_url).classes('rounded-full').style(
                                    'width: 40px; height: 40px; object-fit: cover; '
                                    'border: 2px solid #f7f9ff; margin-right: -0.75rem;'
                                )
                        ui.label('3-registry cross-check • ISO 11784/11785 compliant').style(
                            'font-weight: 600; color: var(--pl-on-surface-variant); font-size: 13px;'
                        )

                # Right column — hero image
                with ui.column().classes('hero-image items-center'):
                    with ui.element('div').classes('relative w-full').style(
                        'aspect-ratio: 1; border-radius: 2rem; overflow: hidden; '
                        'box-shadow: 0 25px 50px -12px rgba(0,0,0,0.25); '
                        'border: 8px solid rgba(255,255,255,0.5);'
                    ):
                        ui.image(HERO_IMG).classes('w-full h-full object-cover')
                        # Glass overlay card
                        with ui.row().classes(
                            'absolute items-center gap-4 p-4 rounded-2xl'
                        ).style(
                            'bottom: 1.5rem; left: 1.5rem; right: 1.5rem; '
                            'background: rgba(255,255,255,0.7); backdrop-filter: blur(12px); '
                            'border: 1px solid rgba(255,255,255,0.3);'
                        ):
                            with ui.element('div').classes(
                                'flex items-center justify-center rounded-full p-3'
                            ).style('background-color: #c15237; color: white;'):
                                ui.icon('pets')
                            with ui.column().classes('gap-0'):
                                ui.label('Reunited in 15 mins').style(
                                    'font-weight: 600; font-size: 14px; color: var(--pl-on-surface);'
                                )
                                ui.label('"Luna was found thanks to her chip."').style(
                                    'font-size: 12px; color: var(--pl-on-surface-variant);'
                                )

        # ── Owner How It Works Section ──
        with ui.element('section').classes('w-full py-16 md:py-20').style(
            'background-color: #fafbfd;'
        ):
            with ui.column().classes('max-w-7xl mx-auto px-4 md:px-6 gap-10'):
                with ui.column().classes('items-center gap-2'):
                    ui.label('How It Works for Pet Owners').classes('pl-heading-2xl').style(
                        'text-align: center;'
                    )
                    ui.label(
                        'Three steps to give your pet a complete digital identity and safety net.'
                    ).classes('pl-body-base').style('text-align: center; max-width: 36rem;')

                with ui.element('div').classes('owner-steps-grid'):
                    for num, icon_name, title, desc in [
                        ('1', 'app_registration', 'Register',
                         'Add your microchip ID, pet details, and a photo. '
                         'We identify the chip manufacturer instantly from the ISO prefix.'),
                        ('2', 'share', 'Share',
                         'Generate time-limited care links for vets, sitters, or groomers. '
                         'They see vaccination records and care instructions — nothing else.'),
                        ('3', 'shield', 'Protect',
                         'If your pet is ever lost, anyone who scans their NFC tag or '
                         'looks up the chip can nudge you anonymously. No phone number exposed.'),
                    ]:
                        with ui.card().classes('p-8 text-center').style(
                            'border-radius: var(--pl-radius-xl); border: 1px solid #e7e5e4; '
                            'box-shadow: var(--pl-shadow-md);'
                        ):
                            with ui.column().classes('items-center gap-4'):
                                with ui.element('div').classes(
                                    'flex items-center justify-center rounded-full'
                                ).style(
                                    'width: 56px; height: 56px; '
                                    'background: rgba(160,58,33,0.08);'
                                ):
                                    ui.label(num).style(
                                        'font-size: 22px; font-weight: 800; color: var(--pl-primary);'
                                    )
                                ui.icon(icon_name).style(
                                    'font-size: 28px; color: var(--pl-primary);'
                                )
                                ui.label(title).style(
                                    'font-weight: 700; font-size: 18px; color: var(--pl-on-surface);'
                                )
                                ui.label(desc).style(
                                    'font-size: 14px; color: var(--pl-on-surface-variant); '
                                    'line-height: 1.6;'
                                )

        # ── Finder How It Works Section ──
        with ui.element('section').classes('w-full py-16 md:py-20').style(
            'background-color: white;'
        ):
            with ui.element('div').classes('how-grid max-w-7xl mx-auto px-4 md:px-6'):
                with ui.column().classes(''):
                    ui.image(HOW_IT_WORKS_IMG).classes('w-full').style(
                        'border-radius: 1.5rem; height: 420px; object-fit: cover; '
                        'box-shadow: 0 8px 24px rgba(0,0,0,0.08);'
                    )

                with ui.column().classes('gap-8'):
                    ui.label('Found a Lost Pet?').classes('pl-heading-2xl')
                    ui.label(
                        'No app download needed. Three steps to reconnect a pet with their owner.'
                    ).classes('pl-body-base')

                    for num, title, desc, icon_name in [
                        ('1', 'Scan the Chip', 'Take the pet to any vet or shelter to read the 15-digit microchip. Or scan the NFC/QR tag on their collar.', 'nfc'),
                        ('2', 'Search PawsLedger', "Enter the chip ID here or at /lookup. We'll identify the manufacturer and show you the pet's public profile.", 'search'),
                        ('3', 'Nudge the Owner', "Send an anonymous message through our system. The owner gets notified instantly — your contact details stay private too.", 'mail'),
                    ]:
                        with ui.row().classes('gap-4 items-start'):
                            with ui.element('div').classes(
                                'flex-shrink-0 flex items-center justify-center rounded-xl'
                            ).style(
                                'width: 44px; height: 44px; background: rgba(160,58,33,0.08); '
                                'color: var(--pl-primary);'
                            ):
                                ui.icon(icon_name).style('font-size: 22px;')
                            with ui.column().classes('gap-1'):
                                ui.label(title).style(
                                    'font-weight: 600; font-size: var(--pl-text-base); color: var(--pl-on-surface);'
                                )
                                ui.label(desc).classes('pl-body-sm').style('line-height: 1.5;')

                    ui.link(
                        'Go to Found a Pet page →', '/lost'
                    ).style(
                        'font-size: 14px; font-weight: 600; color: #a03a21; '
                        'text-decoration: none; margin-top: 4px;'
                    )

        # ── What Makes PawsLedger Different — concrete differentiators ──
        with ui.element('section').classes('w-full py-16').style('background: var(--pl-surface);'):
            with ui.column().classes('max-w-7xl mx-auto px-6 gap-10'):
                with ui.column().classes('items-center gap-2'):
                    ui.label('What Makes PawsLedger Different').classes('pl-heading-xl').style(
                        'text-align: center;'
                    )
                    ui.label(
                        'Not just another microchip registry. A complete digital identity for your pet.'
                    ).classes('pl-body-base').style('text-align: center; max-width: 32rem;')

                with ui.element('div').classes('diff-grid'):
                    for icon_name, color, title, desc in [
                        ('nfc', 'var(--pl-primary)', 'NFC/QR Tags',
                         'Instant identification without a vet scanner. '
                         'Anyone with a phone can scan the tag and reach you.'),
                        ('timer', 'var(--pl-secondary)', 'Time-Limited Care Links',
                         'Share vaccination records and care instructions with vets or sitters. '
                         'Access auto-expires — no permanent data exposure.'),
                        ('enhanced_encryption', '#3b82f6', 'Tamper-Proof Records',
                         'Exported vaccination PDFs are SHA-256 signed. '
                         'Anyone can verify authenticity at /verify — no forgery possible.'),
                        ('cell_tower', '#7c3aed', 'Real-Time Chip ID',
                         'As you type, we identify the chip manufacturer from the ISO prefix. '
                         'Supports all major registries: HomeAgain, PetLink, AKC, 24PetWatch.'),
                    ]:
                        with ui.card().classes('p-6').style(
                            'border-radius: var(--pl-radius-xl); '
                            'border: 1px solid #e7e5e4; box-shadow: var(--pl-shadow-md);'
                        ):
                            with ui.column().classes('gap-3'):
                                with ui.element('div').classes(
                                    'flex items-center justify-center rounded-xl'
                                ).style(
                                    f'width: 44px; height: 44px; '
                                    f'background: color-mix(in srgb, {color} 10%, transparent); color: {color};'
                                ):
                                    ui.icon(icon_name).style('font-size: 22px;')
                                ui.label(title).style(
                                    'font-weight: 600; font-size: var(--pl-text-base); color: var(--pl-on-surface);'
                                )
                                ui.label(desc).classes('pl-body-sm').style('line-height: 1.5;')

        # ── Bottom CTA Section ──
        with ui.element('section').classes('w-full py-24 px-6'):
            with ui.element('div').classes(
                'max-w-7xl mx-auto rounded-3xl p-12 md:p-20 text-center relative overflow-hidden'
            ).style('background-color: #1c1917;'):
                with ui.column().classes('relative z-10 max-w-3xl mx-auto gap-8 items-center'):
                    ui.label("Your pet's safety shouldn't depend on luck.").style(
                        "font-family: 'Plus Jakarta Sans'; font-size: clamp(28px, 4vw, 40px); font-weight: 700; "
                        "color: white; line-height: 1.2; letter-spacing: -0.02em;"
                    )
                    ui.label(
                        "Registration is free. Microchip + QR/NFC tags + vaccination records + "
                        "finder communication — all at no cost. Upgrade only if you want verified status, "
                        "care sharing, and document storage."
                    ).style('font-size: 18px; color: #d6d3d1; max-width: 36rem; line-height: 1.6;')

                    with ui.row().classes('gap-4 justify-center flex-wrap'):
                        ui.button(
                            'Register Your Pet — Free',
                            on_click=lambda: ui.navigate.to('/login' if not app.storage.user.get('email') else '/register'),
                        ).classes('px-10 py-4 rounded-full font-semibold text-lg').style(
                            'background-color: var(--pl-primary); color: white;'
                        ).props('no-caps')
                        ui.button(
                            'View Pricing',
                            on_click=lambda: ui.navigate.to('/pricing'),
                        ).classes('px-10 py-4 rounded-full font-semibold text-lg').style(
                            'background: rgba(255,255,255,0.1); color: white; '
                            'border: 1px solid rgba(255,255,255,0.2);'
                        ).props('no-caps')

        nav_footer()
