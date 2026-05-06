from nicegui import ui, app


def nav_header():
    with ui.header().classes(
        'bg-stone-50/80 backdrop-blur-md border-b border-stone-200 shadow-sm px-6 md:px-12 py-4'
    ).style("font-family: 'Plus Jakarta Sans', sans-serif;"):
        with ui.row().classes('w-full max-w-7xl mx-auto justify-between items-center'):
            # Brand (left)
            ui.link('PawsLedger', '/').classes(
                'text-2xl font-bold tracking-tight no-underline'
            ).style('color: #c24112;')

            # Nav links + auth (right-aligned together)
            with ui.row().classes('gap-8 items-center'):
                link_classes = 'text-stone-600 font-medium no-underline'

                ui.link('Home', '/').classes(link_classes)
                ui.link('Dashboard', '/dashboard').classes(link_classes)

                if app.storage.user.get('email'):
                    full_name = app.storage.user.get('name', '')
                    first_name = full_name.split()[0] if full_name else 'User'

                    # User avatar + name button with dropdown
                    with ui.button(on_click=lambda: None).props(
                        'flat no-caps no-wrap'
                    ).classes('text-stone-600 font-medium'):
                        with ui.row().classes('items-center gap-2'):
                            with ui.element('div').classes(
                                'flex items-center justify-center rounded-full'
                            ).style(
                                'width: 32px; height: 32px; background: #ffdad2;'
                            ):
                                ui.icon('person').style(
                                    'font-size: 18px; color: #a03a21;'
                                )
                            ui.label(first_name).style(
                                'font-weight: 600; font-size: 14px; color: #171c21;'
                            )

                        with ui.menu():
                            ui.menu_item(
                                'My Profile',
                                on_click=lambda: ui.navigate.to('/owner/profile'),
                            )
                            ui.menu_item(
                                'Dashboard',
                                on_click=lambda: ui.navigate.to('/dashboard'),
                            )
                            ui.separator()
                            ui.menu_item(
                                'Logout',
                                on_click=lambda: (
                                    app.storage.user.clear(), ui.navigate.to('/')
                                ),
                            )
                else:
                    ui.link('Login', '/login').classes(link_classes)
