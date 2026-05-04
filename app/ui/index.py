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


def init_index_page():
    @ui.page('/')
    async def index_page():
        nav_header()

        # ── Hero Section ──
        with ui.element('section').classes('w-full py-16 md:py-24').style(
            'background: radial-gradient(circle at top right, rgba(255,218,210,0.5), transparent),'
            'radial-gradient(circle at bottom left, rgba(234,238,245,0.5), transparent);'
        ):
            with ui.row().classes('max-w-7xl mx-auto px-6 gap-12 items-center'):
                # Left column
                with ui.column().classes('flex-1 gap-8'):
                    # Badge
                    with ui.row().classes('items-center gap-2 px-3 py-1 rounded-full').style(
                        'background: rgba(193,82,55,0.1); border: 1px solid rgba(193,82,55,0.2);'
                    ):
                        ui.icon('verified_user').style('font-size: 16px; color: #c15237;')
                        ui.label('Every Pet Deserves a Home').style(
                            'font-size: 12px; font-weight: 600; color: #c15237;'
                        )

                    # Headline
                    ui.html(
                        '<h1 style="font-family: \'Plus Jakarta Sans\', sans-serif; font-size: clamp(2.5rem, 5vw, 4rem); '
                        'line-height: 1.15; font-weight: 700; color: #171c21;">'
                        'Found a pet? <span style="color: #a03a21;">Reconnect them.</span><br>'
                        'Love a pet? <span style="color: #7d5800;">Protect them.</span></h1>'
                    )

                    # Subtitle
                    ui.label(
                        'The universal microchip registry and recovery network. '
                        'We provide finders with the tools to scan and contact owners instantly, '
                        'and pet parents with the peace of mind they deserve.'
                    ).style('font-size: 18px; line-height: 1.6; color: #57423d; max-width: 32rem;')

                    # Search input
                    with ui.row().classes('w-full gap-2 items-center'):
                        chip_input = ui.input(
                            placeholder='Enter Microchip Number'
                        ).classes('flex-1').props('outlined rounded dense')
                        search_btn = ui.button('Search', on_click=lambda: do_lookup()).style(
                            'background-color: #7d5800; color: white; font-weight: 600;'
                        ).classes('px-6 py-2 rounded-lg')
                        ui.button(
                            'Protect',
                            on_click=lambda: ui.navigate.to(
                                '/register' if app.storage.user.get('email') else '/login'
                            ),
                        ).style(
                            'background-color: #a03a21; color: white; font-weight: 600;'
                        ).classes('px-6 py-2 rounded-lg')

                    # Search results area
                    results_card = ui.column().classes('w-full mt-4').style('display: none')
                    status_badge = ui.label('').classes('px-4 py-1 rounded-full text-xs font-bold uppercase mb-2 inline-block')
                    result_title = ui.label('').classes('text-2xl font-bold')
                    result_desc = ui.label('').style('color: #57423d; margin-bottom: 1rem;')
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
                                    status_badge.style('background-color: rgba(193,82,55,0.1); color: #a03a21;')
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

                                            async def nudge_owner(chip=pet.chip_id):
                                                import httpx
                                                async with httpx.AsyncClient(
                                                    base_url='http://localhost:8080'
                                                ) as http_client:
                                                    resp = await http_client.post(f'/api/v1/nudge/{chip}')
                                                    if resp.status_code == 200:
                                                        ui.notify('Nudge sent to owner!', type='positive')
                                                    else:
                                                        ui.notify('Failed to send nudge.', type='negative')

                                            ui.button(
                                                'Nudge Owner', icon='notifications',
                                                on_click=nudge_owner,
                                            ).classes('w-full mt-2').style(
                                                'background-color: #7d5800; color: white;'
                                            )
                                        else:
                                            ui.label(
                                                'This pet is registered on PawsLedger. '
                                                'Log in to view full details and contact the owner.'
                                            ).style('color: #57423d; font-size: 14px; margin-bottom: 0.75rem;')
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
                                        status_badge.style('background-color: #fff7ed; color: #9a3412;')
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
                                                        ui.label(label).style('font-weight: 600; color: #57423d;')
                                                        ui.label(str(value))

                                            ui.separator().classes('my-3')
                                            ui.label(
                                                'This pet is not yet on PawsLedger. '
                                                'Register it to create a secure digital identity.'
                                            ).style('font-size: 14px; font-style: italic; color: #57423d; margin-bottom: 1rem;')

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

                    # Social proof
                    with ui.row().classes('items-center gap-4 mt-4'):
                        with ui.row().classes('items-center').style('margin-right: -0.5rem;'):
                            for img_url in AVATAR_IMGS:
                                ui.image(img_url).classes('rounded-full').style(
                                    'width: 40px; height: 40px; object-fit: cover; '
                                    'border: 2px solid #f7f9ff; margin-right: -0.75rem;'
                                )
                        ui.label('Joined by 50,000+ responsible owners').style(
                            'font-weight: 600; color: #57423d; font-size: 14px;'
                        )

                # Right column — hero image
                with ui.column().classes('flex-1 items-center').style('min-width: 300px;'):
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
                                    'font-weight: 600; font-size: 14px; color: #171c21;'
                                )
                                ui.label('"Luna was found thanks to her chip."').style(
                                    'font-size: 12px; color: #57423d;'
                                )

        # # ── Dual Path Section ──
        # with ui.element('section').classes('w-full py-24').style('background-color: #f7f9ff;'):
        #     with ui.row().classes('max-w-7xl mx-auto px-6 gap-8'):
        #         # Finder path
        #         with ui.card().classes('flex-1 p-12 relative overflow-hidden').style(
        #             'border-radius: 2.5rem; background-color: #f5f5f4; border: 1px solid #e7e5e4;'
        #         ):
        #             with ui.column().classes('gap-6 relative z-10'):
        #                 with ui.element('span').classes(
        #                     'inline-block p-4 rounded-2xl shadow-sm'
        #                 ).style('background: white;'):
        #                     ui.icon('find_in_page').style('font-size: 32px; color: #7d5800;')
        #                 ui.label('I found a lost Pet').style(
        #                     "font-family: 'Plus Jakarta Sans'; font-size: 32px; font-weight: 600; color: #171c21;"
        #                 )
        #                 ui.label(
        #                     'Scan the microchip and search our global ledger to find contact details '
        #                     'for the owner. Your kindness is their miracle.'
        #                 ).style('color: #57423d; max-width: 24rem;')
        #                 ui.button(
        #                     'Start Recovery Process', icon='arrow_forward',
        #                     on_click=lambda: chip_input.run_method('focus'),
        #                 ).classes('px-8 py-4 rounded-xl font-semibold').style(
        #                     'background-color: #1c1917; color: white;'
        #                 )

        #         # Owner path
        #         with ui.card().classes('flex-1 p-12 relative overflow-hidden').style(
        #             'border-radius: 2.5rem; background: rgba(193,82,55,0.05); '
        #             'border: 1px solid rgba(193,82,55,0.1);'
        #         ):
        #             with ui.column().classes('gap-6 relative z-10'):
        #                 with ui.element('span').classes(
        #                     'inline-block p-4 rounded-2xl shadow-sm'
        #                 ).style('background: white;'):
        #                     ui.icon('shield_with_heart').style('font-size: 32px; color: #a03a21;')
        #                 ui.label('I am a Pet Owner').style(
        #                     "font-family: 'Plus Jakarta Sans'; font-size: 32px; font-weight: 600; color: #171c21;"
        #                 )
        #                 ui.label(
        #                     "Register your pet's chip and vital information. Keep your contact data "
        #                     "updated so you're always reachable in an emergency."
        #                 ).style('color: #57423d; max-width: 24rem;')
        #                 ui.button(
        #                     'Register My Pet Now', icon='add_circle',
        #                     on_click=lambda: ui.navigate.to('/login' if not app.storage.user.get('email') else '/register'),
        #                 ).classes('px-8 py-4 rounded-xl font-semibold').style(
        #                     'background-color: #a03a21; color: white;'
        #                 )



        # # ── How It Works Section ──
        # with ui.element('section').classes('w-full py-24').style('background-color: #f0f4fb;'):
        #     with ui.row().classes('max-w-7xl mx-auto px-6 gap-16 items-center'):
        #         # Image
        #         with ui.column().classes('flex-1'):
        #             ui.image(HOW_IT_WORKS_IMG).classes('w-full rounded-3xl shadow-xl').style(
        #                 'height: 500px; object-fit: cover; border: 1px solid white;'
        #             )

        #         # Steps
        #         with ui.column().classes('flex-1 gap-10'):
        #             ui.label('How It Works').style(
        #                 "font-family: 'Plus Jakarta Sans'; font-size: 32px; font-weight: 600; color: #171c21;"
        #             )
        #             ui.label(
        #                 'Three simple steps to bridge the gap between a lost pet and their home.'
        #             ).style('color: #57423d; margin-bottom: 1rem;')

        #             for num, title, desc in [
        #                 ('1', 'Scan & Locate',
        #                  'Any finder can take a lost pet to a vet or shelter to scan for a 15-digit microchip ID.'),
        #                 ('2', 'Search the Ledger',
        #                  "Enter the ID on PawsLedger to pull up the pet's profile and secure contact form."),
        #                 ('3', 'Initiate Reunion',
        #                  "We facilitate a safe, anonymous initial contact to coordinate the pet's safe return home."),
        #             ]:
        #                 with ui.row().classes('gap-6'):
        #                     with ui.element('div').classes(
        #                         'flex-shrink-0 flex items-center justify-center rounded-full font-bold shadow-sm'
        #                     ).style(
        #                         'width: 48px; height: 48px; background: white; color: #a03a21; '
        #                         'border: 1px solid #f5f5f4;'
        #                     ):
        #                         ui.label(num)
        #                     with ui.column().classes('gap-1'):
        #                         ui.label(title).style('font-weight: 600; color: #171c21;')
        #                         ui.label(desc).style('color: #57423d;')

        #             ui.button(
        #                 'Learn More About Microchips',
        #                 on_click=lambda: ui.navigate.to('/faq'),
        #             ).classes('px-8 py-4 rounded-xl font-semibold shadow-lg mt-4').style(
        #                 'background-color: #c15237; color: white;'
        #             )

        # ── Value Props Section ──
        with ui.element('section').classes('w-full py-24').style(
            'background: white; border-top: 1px solid #e7e5e4; border-bottom: 1px solid #e7e5e4;'
        ):
            with ui.column().classes('max-w-7xl mx-auto px-6 items-center'):
                ui.label('Why Trust PawsLedger?').style(
                    "font-family: 'Plus Jakarta Sans'; font-size: 32px; font-weight: 600; color: #171c21;"
                ).classes('mb-2')
                ui.label(
                    "Built on the principles of nurturing professionalism and absolute security for your pet's sensitive data."
                ).style('color: #57423d; margin-bottom: 3rem; text-align: center; max-width: 42rem;')

                with ui.row().classes('w-full gap-12 justify-center'):
                    for icon_name, color, title, desc in [
                        ('hub', '#a03a21', 'Global Connection',
                         'Our ledger connects with thousands of shelters and vet clinics worldwide for seamless identification.'),
                        ('encrypted', '#7d5800', 'Privacy First Security',
                         'Your personal data is encrypted and only shared with verified finders through our secure communication relay.'),
                        ('volunteer_activism', '#171c21', 'Peace of Mind',
                         'Real-time alerts and recovery assistance support you from the moment a pet is reported lost.'),
                    ]:
                        with ui.column().classes('flex-1 items-center text-center gap-4 px-6'):
                            with ui.element('div').classes(
                                'flex items-center justify-center rounded-2xl'
                            ).style(f'width: 64px; height: 64px; background: #eaeef5;'):
                                ui.icon(icon_name).style(f'font-size: 32px; color: {color};')
                            ui.label(title).style(
                                "font-family: 'Plus Jakarta Sans'; font-size: 24px; font-weight: 600; color: #171c21;"
                            )
                            ui.label(desc).style('color: #57423d;')
        # ── CTA Section ──
        # with ui.element('section').classes('w-full py-24 px-6'):
        #     with ui.element('div').classes(
        #         'max-w-7xl mx-auto rounded-3xl p-12 md:p-20 text-center relative overflow-hidden'
        #     ).style('background-color: #1c1917;'):
        #         with ui.column().classes('relative z-10 max-w-3xl mx-auto gap-8 items-center'):
        #             ui.label("Ready to secure your pet's future?").style(
        #                 "font-family: 'Plus Jakarta Sans'; font-size: 40px; font-weight: 700; "
        #                 "color: white; line-height: 1.2; letter-spacing: -0.02em;"
        #             )
        #             ui.label(
        #                 "Don't wait until it's too late. Registration takes less than 5 minutes and lasts a lifetime."
        #             ).style('font-size: 18px; color: #d6d3d1;')

        #             with ui.row().classes('gap-4 justify-center'):
        #                 ui.button(
        #                     'Register Your Pet Today',
        #                     on_click=lambda: ui.navigate.to('/login' if not app.storage.user.get('email') else '/register'),
        #                 ).classes('px-10 py-4 rounded-full font-semibold text-lg').style(
        #                     'background-color: #a03a21; color: white;'
        #                 )
        #                 ui.button(
        #                     'Contact Support',
        #                     on_click=lambda: ui.navigate.to('/contact'),
        #                 ).classes('px-10 py-4 rounded-full font-semibold text-lg').style(
        #                     'background: rgba(255,255,255,0.1); color: white; '
        #                     'border: 1px solid rgba(255,255,255,0.2);'
        #                 )

        nav_footer()
