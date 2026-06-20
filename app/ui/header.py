from nicegui import ui, app


def _logout():
    """Clear session storage and redirect to server-side logout to delete HttpOnly cookie."""
    app.storage.user.clear()
    ui.navigate.to('/api/v1/auth/logout')


def nav_header():
    ui.add_css('''
    .desktop-nav { display: flex !important; }
    .mobile-menu { display: none !important; }
    @media (max-width: 767px) {
        .desktop-nav { display: none !important; }
        .mobile-menu { display: inline-flex !important; }
    }
    ''')

    with ui.header().classes(
        'bg-stone-50/80 backdrop-blur-md border-b border-stone-200 shadow-sm px-6 md:px-12 py-4'
    ).style("font-family: var(--pl-font);"):
        with ui.row().classes('w-full max-w-7xl mx-auto justify-between items-center flex-nowrap'):
            # Brand (left)
            with ui.link('', '/').classes('no-underline shrink-0'):
                ui.html('<img src="/assets/logo.svg" style="height: 40px; width: auto;">')

            # Desktop nav links + auth (hidden on mobile)
            with ui.row().classes('desktop-nav gap-4 md:gap-8 items-center flex-nowrap'):
                link_classes = 'text-stone-600 font-medium no-underline'

                ui.link('Home', '/').classes(link_classes)
                ui.link('Found a Pet?', '/lost').classes(link_classes)
                ui.link('Pet Parents', '/dashboard').classes(link_classes)
                ui.link('Support', '/faq').classes(link_classes)

                if app.storage.user.get('email'):
                    full_name = app.storage.user.get('name', '')
                    first_name = full_name.split()[0] if full_name else 'User'

                    with ui.button(on_click=lambda: None).props(
                        'flat no-caps no-wrap'
                    ).classes('text-stone-600 font-medium shrink-0'):
                        with ui.row().classes('items-center gap-2'):
                            with ui.element('div').classes(
                                'flex items-center justify-center rounded-full'
                            ).style(
                                'width: 32px; height: 32px; background: var(--pl-primary-light);'
                            ):
                                ui.icon('person').style(
                                    'font-size: 18px; color: var(--pl-primary);'
                                )
                            ui.label(first_name).style(
                                'font-weight: 600; font-size: 14px; color: var(--pl-on-surface);'
                            )

                        with ui.menu():
                            ui.menu_item(
                                'My Profile',
                                on_click=lambda: ui.navigate.to('/owner/profile'),
                            )
                            ui.menu_item(
                                'Pet Parents',
                                on_click=lambda: ui.navigate.to('/dashboard'),
                            )
                            ui.separator()
                            ui.menu_item(
                                'Logout',
                                on_click=_logout,
                            )
                else:
                    ui.button(
                        'Login', on_click=lambda: ui.navigate.to('/login'),
                    ).style(
                        'background: var(--pl-primary); color: white; font-weight: 600; '
                        'padding: 8px 24px; border-radius: 8px;'
                    ).props('no-caps')

            # Mobile hamburger menu (visible only on small screens)
            with ui.button(icon='menu').props('flat dense').classes(
                'mobile-menu text-stone-700'
            ):
                with ui.menu().classes('min-w-[200px]'):
                    ui.menu_item(
                        'Home',
                        on_click=lambda: ui.navigate.to('/'),
                    )
                    ui.menu_item(
                        'Found a Pet?',
                        on_click=lambda: ui.navigate.to('/lost'),
                    )
                    ui.menu_item(
                        'Pet Parents',
                        on_click=lambda: ui.navigate.to('/dashboard'),
                    )
                    ui.menu_item(
                        'Support',
                        on_click=lambda: ui.navigate.to('/faq'),
                    )
                    ui.separator()
                    if app.storage.user.get('email'):
                        full_name = app.storage.user.get('name', '')
                        first_name = full_name.split()[0] if full_name else 'User'
                        ui.menu_item(
                            f'Hi, {first_name}',
                        ).props('disable')
                        ui.menu_item(
                            'My Profile',
                            on_click=lambda: ui.navigate.to('/owner/profile'),
                        )
                        ui.menu_item(
                            'Logout',
                            on_click=_logout,
                        )
                    else:
                        ui.menu_item(
                            'Login',
                            on_click=lambda: ui.navigate.to('/login'),
                        )
