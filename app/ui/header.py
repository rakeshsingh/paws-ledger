from nicegui import ui, app


def nav_header():
    with ui.header().classes(
        'bg-stone-50/80 backdrop-blur-md border-b border-stone-200 shadow-sm px-6 md:px-12 py-4'
    ).style("font-family: 'Plus Jakarta Sans', sans-serif;"):
        with ui.row().classes('w-full max-w-7xl mx-auto justify-between items-center'):
            # Brand
            ui.link('PawsLedger', '/').classes(
                'text-2xl font-bold tracking-tight no-underline'
            ).style('color: #c24112;')

            # Nav links
            with ui.row().classes('gap-8 items-center'):
                link_classes = 'text-stone-600 font-medium no-underline'

                ui.link('Home', '/').classes(link_classes)
                ui.link('Dashboard', '/dashboard').classes(link_classes)

                # About dropdown with submenu
                with ui.button('About', icon='arrow_drop_down').props(
                    'flat no-caps'
                ).classes('text-stone-600 font-medium'):
                    with ui.menu():
                        ui.menu_item('About', on_click=lambda: ui.navigate.to('/about'))
                        ui.menu_item('Contact', on_click=lambda: ui.navigate.to('/contact'))
                        ui.menu_item('FAQ', on_click=lambda: ui.navigate.to('/faq'))

            # Right actions
            with ui.row().classes('gap-4 items-center'):
                if app.storage.user.get('email'):
                    ui.button('Logout', on_click=lambda: (
                        app.storage.user.clear(), ui.navigate.to('/')
                    )).props('flat no-caps').classes('text-stone-600 font-medium')
                else:
                    ui.button('Register Pet', on_click=lambda: ui.navigate.to('/login')).classes(
                        'text-white px-6 py-2 rounded-full font-semibold shadow-md'
                    ).style('background-color: #a03a21;')
