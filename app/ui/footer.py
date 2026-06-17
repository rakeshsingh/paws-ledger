from nicegui import ui


def nav_footer():
    with ui.footer().classes('w-full py-4 px-6 md:px-12').style(
        "background-color: var(--pl-surface); border-top: 1px solid var(--pl-outline-variant); "
        "font-family: var(--pl-font); font-size: var(--pl-text-xs);"
    ):
        with ui.row().classes('pl-footer-inner max-w-7xl mx-auto w-full justify-between items-center'):
            # Left — brand + copyright
            with ui.row().classes('items-center gap-3'):
                ui.label('PawsLedger').style(
                    'font-weight: 700; font-size: 14px; color: var(--pl-primary);'
                )
                ui.label('© 2026 PawsLedger. Nurturing Professionalism in Pet Care.').style(
                    'color: var(--pl-text-hint);'
                )

            # Right — inline links
            with ui.row().classes('pl-footer-links items-center gap-6'):
                ui.link('About', '/about').style('color: var(--pl-text-hint); text-decoration: none;')
                ui.link('Pricing', '/pricing').style('color: var(--pl-text-hint); text-decoration: none;')
                ui.link('Verify', '/verify').style('color: var(--pl-text-hint); text-decoration: none;')
                ui.link('Privacy', '/privacy').style('color: var(--pl-text-hint); text-decoration: none;')
                ui.link('Terms', '/terms').style('color: var(--pl-text-hint); text-decoration: none;')
                ui.link('Contact', '/contact').style('color: var(--pl-text-hint); text-decoration: none;')
                ui.link('FAQ', '/faq').style('color: var(--pl-text-hint); text-decoration: none;')
